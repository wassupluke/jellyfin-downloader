# Standard Imports
from os import remove
from shutil import move
from subprocess import run

# Third-party Imports
from flask import Flask, render_template, request
from pytubefix import YouTube
from pytubefix.cli import on_progress

app = Flask(__name__)


@app.route("/download")
def form():
    return render_template("form.html")


@app.route("/data", methods=["POST", "GET"])
def data():
    if request.method == "GET":
        return "The URL /data is accessed directly. Try going to '/download'"
    if request.method == "POST":
        form_data = request.form
        url = request.form["url"]
        dest = request.form["destination"]
        # from here we can feed these two variables to the download function
        filename = use_pytubefix(url)
        dest = dest + filename  # update destination to full path
        use_ffmpeg(filename)
        cleanup_sort(filename, dest)

        #return render_template("form.html")
        return render_template("data.html", form_data=form_data)


def use_pytubefix(u):
    yt = YouTube(u, on_progress_callback=on_progress)
    title = yt.title + ".mp4"

    video_stream = (
        yt.streams.filter(adaptive=True, file_extension="mp4", only_video=True)
        .order_by("resolution")
        .desc()
        .first()
    )
    audio_stream = (
        yt.streams.filter(adaptive=True, file_extension="mp4", only_audio=True)
        .order_by("abr")
        .desc()
        .first()
    )

    video_stream.download(filename="video.mp4")
    audio_stream.download(filename="audio.mp4")

    return title


def use_ffmpeg(f):
    run(["ffmpeg", "-y", "-i", "video.mp4", "-i", "audio.mp4", "-c", "copy", f], check=False)


def cleanup_sort(f, d):
    remove("video.mp4")
    remove("audio.mp4")
    move(f, d)  # moves file f to destination directory d
