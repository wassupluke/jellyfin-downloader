# Luke's Media Downloader

YouTube video downloader with Jellyfin media server integration. Runs a web UI on port 5000 with two features:

- **Manual Download** — paste a YouTube URL to download it immediately
- **Playlist Watches** — configure playlists to be monitored automatically on a schedule, with title filtering and date windows

After each download, a Jellyfin library scan is triggered automatically.

## Setup

1. Create a `.env` file with your Jellyfin API key:
   ```
   JELLYFIN_TOKEN=<your_api_token_here>
   ```
   Optionally secure it with `chmod 0600 .env`

2. Build and run:
   ```bash
   docker compose build && docker compose up -d
   ```

3. Navigate to `http://<ip>:5000`

## Playlist Watches

Go to the **Playlist Watches** tab in the web UI to add monitored playlists. Each watch has:

- **Playlist URL** — the YouTube playlist to monitor
- **Title must contain** — only download videos whose title contains this text (leave blank for all)
- **Start / End Date** — active date window for monitoring
- **Check interval** — how often to check for new videos (1h–12h)

The built-in scheduler checks every 5 minutes and runs any watches that are due. Each watch maintains its own download archive to avoid re-downloading videos.

Watch data is stored in `watches.json` and download archives in `archives/`, both volume-mounted for persistence across container rebuilds.

## Configuration

- `yt-dlp.conf` — yt-dlp options for manual downloads (format, metadata, subtitles, etc.)
- Jellyfin URL and output path are configured in `app.py`
- Playlist watches use their own yt-dlp flags (configured in code, matching the manual download options)
