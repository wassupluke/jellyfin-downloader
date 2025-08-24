#!/bin/bash
wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O ~/.local/bin/yt-dlp
chmod a+rx ~/.local/bin/yt-dlp  # Make executable
~/.local/bin/yt-dlp -U
