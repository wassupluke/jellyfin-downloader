# jellyfin-downloader

### Notes for use:
- The templates/form.html contains hardcoded links to the directories into which downloaded files should be organized. Please review to ensure they match your organization structure.
- Ensure the ffmpeg package is installed on your system (e.g., via something like pacman or apt, not pip)

### To run:
`flask --app jellyfin-downloader run`
