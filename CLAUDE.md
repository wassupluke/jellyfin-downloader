# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube video downloader with Jellyfin media server integration. Single Flask app (`app.py`) with two functional areas:

- **Manual download** (`/`): Submit a YouTube URL, yt-dlp runs in a background thread, progress is streamed to the browser via SSE (`/progress/<job_id>/stream`).
- **Watches** (`/watches`): CRUD UI for scheduled channel monitors. A background scheduler thread checks every 5 minutes and runs yt-dlp for any enabled watch whose `interval_hours` cooldown has elapsed.

## Commands

```bash
# Run locally
pip install -r requirements.txt
python app.py

# Run tests
pytest tests/ -v

# Run a single test class
pytest tests/test_app.py::TestWatchesRoutes -v

# Docker (production)
docker compose build
docker compose up -d
```

## Architecture

All logic lives in `app.py`. Key globals:

- `_jobs` — in-memory dict of active/completed download jobs (keyed by UUID), each with `status`, `progress`, `log` (deque), and `title`.
- `WATCHES_FILE` — `/app/data/watches.json` persists the list of Watch configs.
- `ARCHIVES_DIR` — `/app/archives/`, one `<watch_id>.txt` per watch for yt-dlp's `--download-archive`.

The scheduler (`_scheduler_loop`) runs as a daemon thread started at app launch. It does not use cron.

Watch fields: `id`, `name`, `channel_url`, `title_filter`, `title_exclude`, `start_date`, `end_date`, `interval_hours`, `enabled`, `last_run`.

`load_watches()` auto-migrates legacy `playlist_url` → `channel_url` on read.

For `@channel` URLs (no trailing path), `_run_watch` appends `/videos` to avoid downloading Shorts from the channel home tab.

## Configuration

- `.env` — Must contain `JELLYFIN_TOKEN`
- Hardcoded in `app.py`: `JELLYFIN_URL` (`http://192.168.5.39:8096`), `YOUTUBE_PATH` (`/mnt/ceph-videos/YouTube/`)
- `yt-dlp.conf` (repo root) — used by manual downloads via `--config-locations /app/yt-dlp.conf`
- Watch-triggered downloads pass yt-dlp flags directly in `_run_watch()`, not via the config file
