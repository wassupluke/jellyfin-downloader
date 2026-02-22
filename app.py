import json
import os
import subprocess
import threading
import time
import uuid
from datetime import date, datetime

import requests
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

JELLYFIN_TOKEN = os.environ.get("JELLYFIN_TOKEN")
JELLYFIN_URL = "http://192.168.5.39:8096"
YOUTUBE_PATH = "/mnt/ceph-videos/YouTube/"
WATCHES_FILE = "/app/watches.json"
ARCHIVES_DIR = "/app/archives"

# ── Shared helpers ──────────────────────────────────────────────

def run_ytdlp(url, extra_args=None):
    """Run yt-dlp with given URL and optional extra args. Returns True on success."""
    cmd = ["yt-dlp"] + (extra_args or []) + [url]
    print(f"[yt-dlp] {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd)
    return result.returncode == 0


def trigger_jellyfin_scan():
    """Trigger a Jellyfin library scan for the YouTube path."""
    try:
        response = requests.post(
            f"{JELLYFIN_URL}/Library/Media/Updated",
            headers={
                "X-MediaBrowser-Token": JELLYFIN_TOKEN,
                "Content-Type": "application/json",
            },
            json={
                "dto": {
                    "Updates": [
                        {"Path": YOUTUBE_PATH, "UpdateType": "scan"}
                    ]
                }
            },
            timeout=5,
        )
        print(
            f"[jellyfin] HTTP {response.status_code} | bytes={len(response.content)}",
            flush=True,
        )
    except Exception as e:
        print(f"[jellyfin] scan failed: {e}", flush=True)


# ── Watches persistence ─────────────────────────────────────────

def load_watches():
    if not os.path.isfile(WATCHES_FILE):
        save_watches([])
        return []
    try:
        with open(WATCHES_FILE) as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, OSError):
        return []


def save_watches(watches):
    with open(WATCHES_FILE, "w") as f:
        json.dump(watches, f, indent=2)


def find_watch(watches, watch_id):
    return next((w for w in watches if w["id"] == watch_id), None)


# ── Manual download routes ──────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def download():
    if request.method == "POST":
        url = request.form["url"]
        success = run_ytdlp(url, ["--config-locations", "/app/yt-dlp.conf"])

        if success:
            status = "✅ Download complete!"
            trigger_jellyfin_scan()
        else:
            status = "❌ Download failed. Please check the URL or try again."

        return render_template("result.html", status=status)

    return render_template("download.html")


# ── Watch CRUD routes ───────────────────────────────────────────

@app.route("/watches")
def watches_list():
    watches = load_watches()
    today = date.today().isoformat()
    for w in watches:
        w["_active"] = w.get("start_date", "") <= today <= w.get("end_date", "")
    return render_template("watches.html", watches=watches)


@app.route("/watches/add", methods=["GET", "POST"])
def watches_add():
    if request.method == "POST":
        watches = load_watches()
        watches.append(_watch_from_form(request.form))
        save_watches(watches)
        return redirect(url_for("watches_list"))
    return render_template("watch_form.html", watch=None)


@app.route("/watches/<watch_id>/edit", methods=["GET", "POST"])
def watches_edit(watch_id):
    watches = load_watches()
    watch = find_watch(watches, watch_id)
    if not watch:
        return redirect(url_for("watches_list"))

    if request.method == "POST":
        updated = _watch_from_form(request.form)
        updated["id"] = watch["id"]
        updated["last_run"] = watch.get("last_run")
        watches = [updated if w["id"] == watch_id else w for w in watches]
        save_watches(watches)
        return redirect(url_for("watches_list"))

    return render_template("watch_form.html", watch=watch)


@app.route("/watches/<watch_id>/delete", methods=["POST"])
def watches_delete(watch_id):
    watches = load_watches()
    watches = [w for w in watches if w["id"] != watch_id]
    save_watches(watches)
    return redirect(url_for("watches_list"))


@app.route("/watches/<watch_id>/run", methods=["POST"])
def watches_run(watch_id):
    watches = load_watches()
    watch = find_watch(watches, watch_id)
    if watch:
        _run_watch(watch)
        watch["last_run"] = datetime.now().isoformat(timespec="seconds")
        save_watches(watches)
    return redirect(url_for("watches_list"))


def _watch_from_form(form):
    return {
        "id": str(uuid.uuid4()),
        "name": form["name"],
        "playlist_url": form["playlist_url"],
        "title_filter": form.get("title_filter", "").strip(),
        "start_date": form["start_date"],
        "end_date": form["end_date"],
        "interval_hours": int(form["interval_hours"]),
        "enabled": "enabled" in form,
        "last_run": None,
    }


# ── Watch execution ─────────────────────────────────────────────

def _run_watch(watch):
    """Execute yt-dlp for a single watch."""
    os.makedirs(ARCHIVES_DIR, exist_ok=True)
    archive_file = os.path.join(ARCHIVES_DIR, f"{watch['id']}.txt")

    args = [
        "--download-archive", archive_file,
        "--dateafter", watch["start_date"].replace("-", ""),
        "--datebefore", watch["end_date"].replace("-", ""),
        "--write-thumbnail",
        "--format", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--parse-metadata", "%(upload_date>%Y)s:%(meta_date)s",
        "--embed-metadata",
        "--embed-thumbnail",
        "--embed-subs",
        "--sub-langs", "en,en-US",
        "--ignore-errors",
        "--no-overwrites",
        "--output", f"{YOUTUBE_PATH}%(uploader)s/%(playlist_title)s/%(title)s.%(ext)s",
    ]

    title_filter = watch.get("title_filter", "").strip()
    if title_filter:
        args += ["--match-title", title_filter]

    print(f"[scheduler] running watch '{watch['name']}'", flush=True)
    success = run_ytdlp(watch["playlist_url"], args)
    if success:
        trigger_jellyfin_scan()


# ── Background scheduler ────────────────────────────────────────

def _scheduler_loop():
    print("[scheduler] started", flush=True)
    while True:
        time.sleep(300)  # check every 5 minutes
        try:
            watches = load_watches()
            now = datetime.now()
            today = date.today().isoformat()
            changed = False

            for watch in watches:
                if not watch.get("enabled"):
                    continue
                if not (watch.get("start_date", "") <= today <= watch.get("end_date", "")):
                    continue

                last_run = watch.get("last_run")
                if last_run:
                    elapsed = (now - datetime.fromisoformat(last_run)).total_seconds() / 3600
                    if elapsed < watch.get("interval_hours", 4):
                        continue

                _run_watch(watch)
                watch["last_run"] = now.isoformat(timespec="seconds")
                changed = True

            if changed:
                save_watches(watches)

        except Exception as e:
            print(f"[scheduler] error: {e}", flush=True)


def start_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()


# ── Main ────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=5000)
