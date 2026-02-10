from flask import Flask, request
from datetime import datetime
import os

app = Flask(__name__)

# ---------- DAILY FILE NAME FUNCTION ----------
def get_filename():
    today = datetime.now().strftime("%Y-%m-%d")
    return f"attendance_{today}.csv"

# ---------- HOME PAGE ----------
@app.route("/", methods=["GET"])
def home():
    return """
    <h2>Class Attendance</h2>
    <form method="POST" action="/submit">
        Roll Number:<br>
        <input name="roll" required><br><br>

        Name:<br>
        <input name="name" required><br><br>

        <button type="submit">Submit Attendance</button>
    </form>
    """

# ---------- SUBMIT ATTENDANCE ----------
@app.route("/submit", methods=["POST"])
def submit():
    roll = request.form["roll"]
    name = request.form["name"]
    time = datetime.now().strftime("%H:%M:%S")

    filename = get_filename()

    # If file does not exist, create it with header
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("Roll,Name,Time")

    # Save attendance
    with open(filename, "a") as f:
        f.write(f"\n{roll},{name},{time}")

    return "<h3>✅ Attendance Marked Successfully</h3>"

# ---------- RUN SERVER ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
