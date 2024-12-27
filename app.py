import os

from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def download():
    if request.method == "POST":
        url = request.form["url"]
        os.system(f"yt-dlp {url} --config-locations yt-dlp.conf")
        return "Download complete!"
    return render_template("download.html")


if __name__ == "__main__":
    # comment the next line if running with "gunicorn -w 4 -b 0.0.0.0:5000 app:app"
    app.run(host="0.0.0.0", port=5000)
