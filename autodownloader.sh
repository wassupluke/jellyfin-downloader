#!/bin/bash

# Exit on error
set -e

# Defaults
DAYS="1"
MATCH_TITLE=".*EXTENDED HIGHLIGHTS.*" # regex
OUTPUT_DIR="/home/wassu/my-ceph-nas/Videos/jellyfin-videos/YouTube"
PLAYLIST_URL="https://www.youtube.com/watch?v=DYDtrq5ykHg&list=PLXEMPXZ3PY1iF-PYG6aslYgw_ainwQDhN"

echo "[INFO] Starting download for playlist: $PLAYLIST_URL"
echo "[INFO] Downloading videos from the last $DAYS day(s)..."

# Run yt-dlp
/usr/local/bin/yt-dlp \
  --dateafter "now-${DAYS}days" \
  --match-title "${MATCH_TITLE}" \
  --write-thumbnail \
  --output "${OUTPUT_DIR}/%(uploader)s/%(playlist_title)s/%(title)s.%(ext)s" \
  "$PLAYLIST_URL"

echo "[INFO] Download complete"
