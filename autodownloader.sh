#!/bin/bash

# Exit on error
set -e

# SET PLAYLIST URL
PLAYLIST_URL="https://www.youtube.com/watch?v=DYDtrq5ykHg&list=PLXEMPXZ3PY1iF-PYG6aslYgw_ainwQDhN"

# Defaults
DAYS="1"
MATCH_TITLE=".*Vuelta a España 2025.*EXTENDED HIGHLIGHTS.*" # regex
OUTPUT_DIR="/mnt/ceph-videos/YouTube"

echo "[INFO] Starting download for playlist: $PLAYLIST_URL"
echo "[INFO] Downloading videos from the last $DAYS day(s)..."

# Run yt-dlp
~/.local/bin/yt-dlp \
  --dateafter "now-${DAYS}days" \
  --match-title "${MATCH_TITLE}" \
  --write-thumbnail \
  --output "${OUTPUT_DIR}/%(uploader)s/%(playlist_title)s/%(title)s.%(ext)s" \
  "$PLAYLIST_URL"

echo "[INFO] Download complete"
