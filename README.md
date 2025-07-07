# Luke's Media Downloader

This runs a simple url input page on port 5000 at the IP of the device running the script.

## Usage

1. `docker compose up -d`
2. Navigate to <ip>:5000 (where <ip> is the local IP address of the machine running the docker image).

## Scheduling the autodownloader.sh

`crontab -e`

**Example:**

Runs the script six times at minute 0 and 30 past hours 19, 20, and 21 (check what timezone the system is using with `date`).

```bash
0,30 19,20,21 * * * docker exec jellyfin-downloader-flask_app-1 /app/autodownloader.sh  >> /root/jellyfin-downloader/logs/autodownloader.log 2>&1
```
