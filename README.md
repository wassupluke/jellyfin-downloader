# Luke's Media Downloader

This runs a simple url input page on port 5000 at the IP of the device running the script.

## Usage

0. Place the following line in a file called `.env`
> `JELLYFIN_TOKEN=<your_api_token_here>`
> optionally secure the .env file on your system with `chmod 0600 .env`
1. `docker compose build && docker compose up -d`
2. Navigate to <ip>:5000 (where <ip> is the local IP address or hostname of the machine running the docker container).

## Scheduling the autodownloader.sh

`crontab -e`

**Example:**

Runs the script six times at minute 0 and 30 past hours 19, 20, and 21 (check what timezone the system is using with `date`).

```bash
0,30 19,20,21 * * * docker exec jellyfin-downloader-flask_app-1 /app/autodownloader.sh  >> /root/jellyfin-downloader/logs/autodownloader.log 2>&1
```

```bash
# Edit this file to introduce tasks to be run by cron.
#
# Each task to run has to be defined through a single line
# indicating with different fields when the task will be run
# and what command to run for the task
#
# To define the time you can provide concrete values for
# minute (m), hour (h), day of month (dom), month (mon),
# and day of week (dow) or use '*' in these fields (for 'any').
#
# Notice that tasks will be started based on the cron's system
# daemon's notion of time and timezones.
#
# Output of the crontab jobs (including errors) is sent through
# email to the user the crontab file belongs to (unless redirected).
#
# For example, you can run a backup of all your user accounts
# at 5 a.m every week with:
# 0 5 * * 1 tar -zcf /var/backups/home.tgz /home/
#
# For more information see the manual pages of crontab(5) and cron(8)
#
# m h  dom mon dow   command
0,30 12,13,14,15,16,17 * * * /home/wassu/code/jellyfin-downloader/autodownloader.sh > /home/wassu/code/jellyfin-downloader/autodownloader.logs 2>&1
```
