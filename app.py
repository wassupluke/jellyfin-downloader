import os
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

JELLYFIN_TOKEN = os.environ.get("JELLYFIN_TOKEN")
JELLYFIN_URL = "http://192.168.5.39:8096"
YOUTUBE_PATH = "/mnt/ceph-videos/YouTube/" 

@app.route("/", methods=["GET", "POST"])
def download():
    if request.method == "POST":
        url = request.form["url"]

        exit_code = os.system(
            f"yt-dlp --config-locations /app/yt-dlp.conf {url}"
        )

        if exit_code == 0:
            status = "✅ Download complete!"

            response = requests.post(
                f"{JELLYFIN_URL}/Library/Media/Updated",
                headers={
                    "X-MediaBrowser-Token": JELLYFIN_TOKEN,
                    "Content-Type": "application/json",
                },
                json={
                    "dto": {
                        "Updates": [
                            {
                                "Path": YOUTUBE_PATH,
                                "UpdateType": "scan"
                            }
                        ]
                    }
                },
                timeout=5,
            )

            print(
                f"🟢 Jellyfin response: HTTP {response.status_code} | "
                f"bytes={len(response.content)}",
                flush=True
            )

        else:
            status = "❌ Download failed. Please check the URL or try again."

        return render_template("result.html", status=status)

    return render_template("download.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
