# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube video downloader with Jellyfin media server integration. Single Flask app (`app.py`) with two functional areas:

- **Manual download** (`/`): Submit a YouTube URL, yt-dlp runs in a background thread, progress is streamed to the browser via SSE (`/progress/<job_id>/stream`).
- **Watches** (`/watches`): CRUD UI for scheduled channel monitors. A background scheduler thread checks every 5 minutes and runs yt-dlp for any enabled watch whose `interval_hours` cooldown has elapsed.

## Commands

```bash
# Run locally
uv pip install -r requirements.txt
uv run app.py

# Run tests
pytest tests/ -v

# Run a single test class
pytest tests/test_app.py::TestWatchesRoutes -v

# Docker (production)
docker compose build
docker compose up -d
```

## Architecture

All logic lives in `app.py` (single-file Flask app). Key globals:

- `_jobs` / `_jobs_lock` — in-memory dict of active/completed download jobs (keyed by UUID), each with `status` (`running`/`done`/`error`), `progress` (0-100), `log` (deque, maxlen 50), and `title`. Populated by both manual downloads and watch runs triggered from the UI.
- `_watch_jobs` / `_watch_jobs_lock` — maps `watch_id -> job_id` for currently-running watch jobs, so the Watches UI can show live progress and disable the "Run now" button. Entry is removed in the `finally` block of `_run_watch` when the job ends.
- `WATCHES_LOCK` — guards all reads/writes of `WATCHES_FILE`; always go through `load_watches()`/`save_watches()`, never touch the file directly.
- `WATCHES_FILE` — `/app/data/watches.json` persists the list of Watch configs.
- `ARCHIVES_DIR` — `/app/archives/`, one `<watch_id>.txt` per watch for yt-dlp's `--download-archive`.

Any code that mutates `_jobs` or `_watch_jobs` from a new thread must acquire the corresponding lock first (see `watches_run`); the SSE stream readers only read, so they don't lock.

Progress reporting is shared between manual downloads and UI-triggered watch runs: both spawn yt-dlp via `subprocess.Popen(..., "--newline", ...)`, parse `[download] NN.N%` lines with `_PROGRESS_RE`/`_parse_progress`, and stream job state to the browser over SSE (`/progress/<job_id>/stream`). The scheduler path (`_run_watch` called with no `job_id`) instead runs yt-dlp synchronously via `run_ytdlp()` with no progress tracking.

The scheduler (`_scheduler_loop`) runs as a daemon thread started at app launch. It does not use cron; it polls every 5 minutes and runs any enabled, in-date-window watch whose `interval_hours` cooldown has elapsed.

Watch fields: `id`, `name`, `channel_url`, `title_filter`, `title_exclude`, `start_date`, `end_date`, `interval_hours`, `enabled`, `last_run`.

`load_watches()` auto-migrates legacy `playlist_url` → `channel_url` on read.

For `@channel` URLs (no trailing path), `_run_watch` appends `/videos` to avoid downloading Shorts from the channel home tab.

Frontend: `templates/` holds one Jinja template per view (`base.html` layout, `download.html`/`progress.html`/`result.html` for manual downloads, `watches.html`/`watch_form.html` for watch CRUD). `static/watches.js` polls/streams job progress for the Watches list (mobile card layout + per-watch progress bars); `static/style.css` and `static/watches.css` are split by area.

## Configuration

- `.env` — Must contain `JELLYFIN_TOKEN`
- Hardcoded in `app.py`: `JELLYFIN_URL`, `YOUTUBE_PATH` (`/mnt/ceph-videos/YouTube/`)
- `yt-dlp.conf` (repo root) — used by manual downloads via `--config-locations /app/yt-dlp.conf`
- Watch-triggered downloads pass yt-dlp flags directly in `_run_watch()`, not via the config file

## Testing notes

- `tests/conftest.py`'s `client` fixture monkeypatches `WATCHES_FILE`/`ARCHIVES_DIR` to a `tmp_path` so tests never touch real watch data; use it (or the standalone `tmp_watches_file` fixture) instead of hitting the real `WATCHES_FILE` path.
- CI (`.github/workflows/test.yml`) runs `pytest tests/ -v` on Python 3.13 for every push/PR to `main`.
