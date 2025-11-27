from flask import Flask, render_template, request, redirect, url_for
from generator import generate_video
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        topic = request.form["topic"]
        success, result = generate_video(topic)

        if success:
            video_file = os.path.basename(result)
            return redirect(url_for("result", filename=video_file))
        else:
            return render_template("index.html", error=result)

    return render_template("index.html")

@app.route("/result/<filename>")
def result(filename):
    return render_template("result.html", filename=filename)

if __name__ == "__main__":
    app.run(debug=True)
