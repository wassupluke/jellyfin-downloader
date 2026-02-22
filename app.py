import json
import os
import re
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import date, datetime, timezone

import requests
from flask import Flask, Response, redirect, render_template, request, url_for

app = Flask(__name__)

JELLYFIN_TOKEN = os.environ.get("JELLYFIN_TOKEN")
JELLYFIN_URL = "http://192.168.5.39:8096"
YOUTUBE_PATH = "/mnt/ceph-videos/YouTube/"
WATCHES_FILE = "/app/watches.json"
ARCHIVES_DIR = "/app/archives"
WATCHES_LOCK = threading.Lock()

# ── Download job tracking ──────────────────────────────────────
# Jobs persist in memory; keyed by job_id string.
# Each job: {"status": "running"|"done"|"error", "progress": 0-100,
#            "log": deque(maxlen=50), "title": str}

_jobs = {}
_jobs_lock = threading.Lock()

# ── Shared helpers ──────────────────────────────────────────────

def run_ytdlp(url, extra_args=None):
    """Run yt-dlp with given URL and optional extra args. Returns True on success."""
    cmd = ["yt-dlp"] + (extra_args or []) + [url]
    print(f"[yt-dlp] {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, shell=False)  # noqa: S603
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
    with WATCHES_LOCK:
        if not os.path.isfile(WATCHES_FILE):
            _save_watches_unlocked([])
            return []
        try:
            with open(WATCHES_FILE) as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except (json.JSONDecodeError, OSError):
            return []


def save_watches(watches):
    with WATCHES_LOCK:
        _save_watches_unlocked(watches)


def _save_watches_unlocked(watches):
    with open(WATCHES_FILE, "w") as f:
        json.dump(watches, f, indent=2)


def find_watch(watches, watch_id):
    return next((w for w in watches if w["id"] == watch_id), None)


# ── Background download helpers ────────────────────────────────

_PROGRESS_RE = re.compile(r"\[download\]\s+([\d.]+)%")


def _parse_progress(line):
    """Extract download percentage from a yt-dlp output line."""
    m = _PROGRESS_RE.search(line)
    return float(m.group(1)) if m else None


def _run_download_job(job_id, url):
    """Run yt-dlp in background, updating job state as output arrives."""
    job = _jobs[job_id]
    cmd = ["yt-dlp", "--newline", "--config-locations", "/app/yt-dlp.conf", url]
    print(f"[yt-dlp] job {job_id}: {' '.join(cmd)}", flush=True)

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip("\n")
            job["log"].append(line)
            pct = _parse_progress(line)
            if pct is not None:
                job["progress"] = pct
            # Try to grab title from metadata
            if line.startswith("[info]") and ":" in line and not job["title"]:
                job["title"] = line.split(":", 1)[1].strip()[:120]
        proc.wait()
        if proc.returncode == 0:
            job["status"] = "done"
            job["progress"] = 100
            trigger_jellyfin_scan()
        else:
            job["status"] = "error"
    except Exception as e:
        job["log"].append(f"ERROR: {e}")
        job["status"] = "error"


# ── Manual download routes ──────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def download():
    if request.method == "POST":
        url = request.form["url"]
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {
            "status": "running",
            "progress": 0,
            "log": deque(maxlen=50),
            "title": "",
        }
        t = threading.Thread(target=_run_download_job, args=(job_id, url), daemon=True)
        t.start()
        return redirect(url_for("download_progress", job_id=job_id))

    return render_template("download.html")


@app.route("/progress/<job_id>")
def download_progress(job_id):
    if job_id not in _jobs:
        return redirect(url_for("download"))
    return render_template("progress.html", job_id=job_id)


@app.route("/progress/<job_id>/stream")
def progress_stream(job_id):
    """SSE endpoint that pushes job progress updates to the browser."""
    def generate():
        if job_id not in _jobs:
            yield f"data: {json.dumps({'status': 'error', 'progress': 0, 'log': [], 'title': ''})}\n\n"
            return
        job = _jobs[job_id]
        last_sent = None
        while True:
            snapshot = json.dumps({
                "status": job["status"],
                "progress": job["progress"],
                "log": list(job["log"])[-3:],
                "title": job["title"],
            })
            if snapshot != last_sent:
                yield f"data: {snapshot}\n\n"
                last_sent = snapshot
            if job["status"] in ("done", "error"):
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
        watch["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
                    try:
                        last_run_dt = datetime.fromisoformat(last_run)
                    except (TypeError, ValueError):
                        last_run_dt = None
                    if last_run_dt is not None:
                        elapsed = (now - last_run_dt).total_seconds() / 3600
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
