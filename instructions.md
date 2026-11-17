# Prompt: Build Ultra-Lean MVP — trimestre.app.br

Build the simplest, lightest, and fastest possible MVP for the **trimestre.app.br** web application—an audio streaming catalog and player for Investor Relations (IR) events (quarterly earnings calls), designed to run locally on my **Ubuntu (WSL2)** environment and ready for quick deployment to AWS.

The application must operate almost like a static site, **with no user authentication and no admin panel (`/admin`)**, and **zero manual JSON/database editing**. Whenever I drop a properly named audio file into `./media/audios/`, the app must automatically detect it and display it in the catalog ready to play.

## 1. Mandatory Tech Stack
- **Backend:** Python 3 + FastAPI + Uvicorn (solely to serve the HTML page, scan the audio folder, return the catalog JSON, and stream audio files with Range Requests support).
- **Database / Storage:** **Zero database needed** (no PostgreSQL, no SQLite, no manual JSON). The `./media/audios/` folder itself is the single source of truth via a standardized filename convention.
- **Frontend:** HTML5 + Tailwind CSS (via CDN) + Vanilla JavaScript in a single `index.html` file.
- **Audio Storage:** Local folder `./media/audios/` where I manually drop `.mp3` or `.m4a` files. The server must serve this folder with native **HTTP Range Requests** support (essential so users can scrub/seek forward and backward on the audio timeline smoothly).

## 2. Automatic Folder Scanner & Filename Convention (CRITICAL)
Implement an automatic directory scanner function in Python (`sync_audios()` / `get_catalog()`) using only standard libraries (`os` / `pathlib` / `datetime`)—no heavy watchers like `watchdog` required:
- **Trigger:** The backend must automatically scan `./media/audios/` on server startup AND every time the frontend fetches `GET /api/audios` (or reloads the page), so dropping a file into the folder immediately makes it available on the site without restarting the server.
- **Filename Convention:** Parse metadata directly from filenames formatted as:
  `{TICKER}_{QUARTER}_{YYYY-MM-DD}.{ext}`
  - Example 1: `WEGE3_3T26_2026-10-28.mp3` → Ticker: `WEGE3`, Company: `WEG`, Exchange: `B3`, Quarter: `3T26`, Date: `2026-10-28`
  - Example 2: `NVDA_3Q26_2026-11-19.m4a` → Ticker: `NVDA`, Company: `NVIDIA`, Exchange: `NASDAQ`, Quarter: `3Q26`, Date: `2026-11-19`
- **Fallback Parsing:** If I drop a file with a simpler name like `PETR4_3T26.mp3` (without the date), parse the Ticker and Quarter gracefully and use the file's filesystem modification date (`st_mtime`) as the fallback date. Ignore any unrecognized files or hidden files (like `.gitkeep`).

## 3. Company Metadata Dictionary (Hardcoded in Backend)
Map tickers automatically to their full company name and exchange using a clean Python dictionary:

**NASDAQ:**
- `NVDA`: NVIDIA
- `AMD`: AMD
- `META`: Meta
- `GOOGL`: Alphabet (Google)

**B3:**
- `WEGE3`: WEG
- `UGPA3`: Ultrapar
- `PETR4`: Petrobras
- `VALE3`: Vale

*(If an audio file is dropped with a new ticker not in this dictionary, still display it using the ticker itself as the company name and `"OUTROS"` / `"OTHER"` as the exchange).*

## 4. Language & Localization (IMPORTANT)
- **Default Language:** The entire website interface must be in **Portuguese (PT-BR) by default**.
- **Language Switcher:** Include a clean flag toggle button in the top header (e.g., 🇧🇷 / 🇺🇸) allowing the user to switch the UI between **Portuguese** and **English** instantly on the client side (via Vanilla JS dictionary/translations) without reloading the page or interrupting the audio player.

## 5. Interface & Core Features (Lean Spotify-Style UX)
- **Single-Page Interface (`index.html`):**
  - Clean header featuring the **trimestre.app.br** brand, search bar (filter by ticker or company name), a subtle "Atualizar / Refresh" button (which re-queries `/api/audios` without stopping playback), and the PT/EN flag switcher.
  - Quick filter buttons: `Todas` / `All`, `B3`, `NASDAQ`, plus a dynamic quarter filter populated from the detected files.
  - Clean list/cards displaying detected calls (Ticker, Company Name, Exchange, Quarter, Date, and Play button).
  - If `./media/audios/` has no audio files yet, display a clean empty-state message explaining the filename format (`TICKER_TRIMESTRE_AAAA-MM-DD.mp3`).
- **Persistent Global Footer Player:**
  - Fixed bar at the bottom of the screen (custom HTML5 `<audio>` player).
  - Must continue playing uninterrupted while the user searches, filters, refreshes the list, or toggles the site language.
  - Required controls: Play/Pause, clickable progress bar, current/total time, `-15s` and `+15s` skip buttons, and playback speed selector (`1.0x`, `1.25x`, `1.5x`, `2.0x`).
- **Legal Disclaimer:** Subtle footer notice (translated according to the active language):
  - *PT:* "Ferramenta estritamente informativa de organização de eventos públicos de Relações com Investidores. Não constitui recomendação de investimento."
  - *EN:* "Strictly informational tool for organizing public Investor Relations events. Does not constitute investment advice."

## 6. Expected Deliverables
1. Minimal project file structure (`main.py`, `templates/index.html`, empty `media/audios/.gitkeep`, `requirements.txt`).
2. Only `fastapi` and `uvicorn` in `requirements.txt` (zero external dependencies beyond those two).
3. Exact terminal commands to create the `venv`, install dependencies, and start the local server on WSL (`uvicorn main:app --reload`).