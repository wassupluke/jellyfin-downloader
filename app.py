import os

from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def download():
    if request.method == "POST":
        url = request.form["url"]
        exit_code = os.system(f"yt-dlp {url}")

        if exit_code == 0:
            status = "✅ Download complete!"
            os.system(
                    'curl -H "X-MediaBrowser-Token: 17ff6890cbfe4a95899120a1bf06ff8c" '
                    '-H "Content-Type: application/json" '
                    '-d \'{{"Updates": [{{"Path":"/mnt/ceph-videos/YouTube/","UpdateType":"scan"}}]}}\' '
                    'http://192.168.5.39:8096/Library/Media/Updated'
                    )
        else:
            status = "❌ Download failed. Please check the URL or try again."

        return render_template("result.html", status=status)

    return render_template("download.html")


if __name__ == "__main__":
    # comment the next line if running with "gunicorn -w 4 -b 0.0.0.0:5000 app:app"
    app.run(host="0.0.0.0", port=5000)
