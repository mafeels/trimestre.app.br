import os
import re
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse

app = FastAPI(title="trimestre.app.br", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = BASE_DIR / "media" / "recordings"
LEGACY_MEDIA_DIR = BASE_DIR / "media" / "audios"
LOGOS_DIR = BASE_DIR / "media" / "logos"
TEMPLATES_DIR = BASE_DIR / "templates"

RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
LOGOS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Company Metadata Dictionary
COMPANY_INFO = {
    # NASDAQ
    "NVDA": {"name": "NVIDIA", "exchange": "NASDAQ"},
    "AMD": {"name": "AMD", "exchange": "NASDAQ"},
    "META": {"name": "Meta", "exchange": "NASDAQ"},
    "GOOGL": {"name": "Alphabet (Google)", "exchange": "NASDAQ"},
    # B3
    "WEGE3": {"name": "WEG", "exchange": "B3"},
    "UGPA3": {"name": "Ultrapar", "exchange": "B3"},
    "PETR4": {"name": "Petrobras", "exchange": "B3"},
    "VALE3": {"name": "Vale", "exchange": "B3"},
}

SUPPORTED_EXTENSIONS = {".mp3", ".m4a"}


def get_catalog():
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    items = []

    # Scan both media/recordings/{ticker}/ and legacy media/audios/
    scan_paths = []

    # 1. New structure: media/recordings/<TICKER>/<file>
    for entry in os.scandir(RECORDINGS_DIR):
        if entry.is_dir() and not entry.name.startswith("."):
            for sub_entry in os.scandir(entry.path):
                if sub_entry.is_file() and not sub_entry.name.startswith("."):
                    scan_paths.append((sub_entry, f"{entry.name}/{sub_entry.name}"))
        elif entry.is_file() and not entry.name.startswith("."):
            scan_paths.append((entry, entry.name))

    # 2. Legacy structure: media/audios/<file>
    for entry in os.scandir(LEGACY_MEDIA_DIR):
        if entry.is_file() and not entry.name.startswith("."):
            scan_paths.append((entry, entry.name))

    seen_rel_urls = set()

    for file_entry, rel_path in scan_paths:
        ext = Path(file_entry.name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        stem = Path(file_entry.name).stem
        parts = stem.split("_")
        if len(parts) < 2:
            continue

        ticker = parts[0].strip().upper()
        quarter = parts[1].strip().upper()

        if not ticker or not quarter:
            continue

        date_str = ""
        if len(parts) >= 3:
            raw_date = parts[2].strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
                date_str = raw_date

        if not date_str:
            try:
                mtime = file_entry.stat().st_mtime
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")

        company_meta = COMPANY_INFO.get(
            ticker,
            {"name": ticker, "exchange": "OUTROS"},
        )

        stream_url = f"/stream/{rel_path}"
        if stream_url in seen_rel_urls:
            continue
        seen_rel_urls.add(stream_url)

        items.append({
            "filename": file_entry.name,
            "ticker": ticker,
            "company": company_meta["name"],
            "exchange": company_meta["exchange"],
            "quarter": quarter,
            "date": date_str,
            "url": stream_url,
        })

    items.sort(key=lambda x: (x["date"], x["ticker"]), reverse=True)
    return items


@app.get("/api/audios")
def list_audios():
    return get_catalog()


@app.get("/stream/{filepath:path}")
@app.get("/media/audios/{filepath:path}")
def stream_audio(filepath: str, request: Request):
    # Resolve against RECORDINGS_DIR or LEGACY_MEDIA_DIR safely
    safe_rel = Path(filepath)
    # Check recordings dir first
    target_path = (RECORDINGS_DIR / safe_rel).resolve()
    if not (str(target_path).startswith(str(RECORDINGS_DIR.resolve())) and target_path.is_file()):
        # Try legacy audios dir
        target_path = (LEGACY_MEDIA_DIR / safe_rel).resolve()
        if not (str(target_path).startswith(str(LEGACY_MEDIA_DIR.resolve())) and target_path.is_file()):
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    file_size = target_path.stat().st_size
    range_header = request.headers.get("range")

    content_type = "audio/mpeg" if target_path.suffix.lower() == ".mp3" else "audio/mp4"

    if not range_header:
        def file_iterator():
            with open(target_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk

        return StreamingResponse(
            file_iterator(),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": f'inline; filename="{target_path.name}"',
            },
        )

    # Parse range header e.g. "bytes=0-1024" or "bytes=1024-"
    range_match = re.match(r"^bytes=(\d+)-(\d*)$", range_header.strip())
    if not range_match:
        return Response(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    start_str, end_str = range_match.groups()
    start = int(start_str)
    end = int(end_str) if end_str else file_size - 1

    if start >= file_size or end >= file_size or start > end:
        return Response(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = (end - start) + 1

    def ranged_file_iterator(offset: int, length: int):
        with open(target_path, "rb") as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                read_amount = min(64 * 1024, remaining)
                chunk = f.read(read_amount)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        ranged_file_iterator(start, chunk_size),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=content_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Disposition": f'inline; filename="{target_path.name}"',
        },
    )


@app.get("/media/logos/{filename}")
def get_logo(filename: str):
    safe_name = Path(filename).name
    file_path = (LOGOS_DIR / safe_name).resolve()
    if not str(file_path).startswith(str(LOGOS_DIR.resolve())) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Logo não encontrado.")
    return FileResponse(file_path)


@app.get("/", response_class=HTMLResponse)
def index():
    html_file = TEMPLATES_DIR / "index.html"
    if not html_file.is_file():
        return HTMLResponse("<h1>index.html not found</h1>", status_code=500)
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)

