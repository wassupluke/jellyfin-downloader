# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube video downloader with Jellyfin media server integration. Two modes:
- **Web UI** (`app.py`): Flask app on port 5000 for manual URL downloads. Uses yt-dlp with config from `app/yt-dlp.conf`. After download, triggers a Jellyfin library scan via API.
- **Auto downloader** (`autodownloader.sh`): Cron-scheduled bash script that monitors a YouTube playlist, downloads new matching videos (by title regex + date filter), and tracks already-downloaded videos in `download-archive.txt`.

## Commands

```bash
# Run locally
pip install -r requirements.txt
python app.py

# Docker (production)
docker compose build
docker compose up -d
```

No test suite or linter is configured.

## Architecture

- `app.py` — Single-route Flask app (GET shows form, POST downloads URL via `os.system` → yt-dlp, then POSTs to Jellyfin API)
- `autodownloader.sh` — Standalone script with its own yt-dlp options (separate from `app/yt-dlp.conf`)
- `templates/` — Jinja2 templates: `download.html` (form), `result.html` (status)
- `app/yt-dlp.conf` — yt-dlp config for the web UI downloads only

## Configuration

- `.env` — Must contain `JELLYFIN_TOKEN` (Jellyfin API key)
- Hardcoded values in `app.py`: Jellyfin URL (`http://192.168.5.39:8096`), output path (`/mnt/ceph-videos/YouTube/`)
- `autodownloader.sh` has its own hardcoded playlist URL, title match regex, and output directory
