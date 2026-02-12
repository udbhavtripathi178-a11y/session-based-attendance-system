from flask import Flask, request, redirect, url_for, session, send_file
from datetime import datetime
import sqlite3
import csv
import math

app = Flask(__name__)
app.secret_key = "secret123"

# -------- SETTINGS --------
CLASS_LAT = 28.425335
CLASS_LON = 77.326069
ALLOWED_RADIUS = 20
TEACHER_PASSWORD = "admin123"

# -------- DATABASE INIT --------
def init_db():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            roll TEXT,
            name TEXT,
            time TEXT,
            date TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS control (
            id INTEGER PRIMARY KEY,
            status TEXT
        )
    """)

    c.execute("INSERT OR IGNORE INTO control (id, status) VALUES (1, 'closed')")

    conn.commit()
    conn.close()

init_db()

# -------- HELPERS --------
def get_status():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("SELECT status FROM control WHERE id=1")
    status = c.fetchone()[0]
    conn.close()
    return status

def set_status(new_status):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("UPDATE control SET status=? WHERE id=1", (new_status,))
    conn.commit()
    conn.close()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# -------- STUDENT PAGE --------
@app.route("/")
def home():
    if get_status() == "closed":
        return "<h3>❌ Attendance is CLOSED by teacher.</h3>"

    return """
    <h2>Class Attendance</h2>
    <form method="POST" action="/submit" onsubmit="return checkLocation()">
        Roll:<br>
        <input name="roll" required><br><br>

        Name:<br>
        <input name="name" required><br><br>

        <input type="hidden" name="lat" id="lat">
        <input type="hidden" name="lon" id="lon">

        <button type="submit">Submit</button>
    </form>

    <script>
    let locationReady = false;

    navigator.geolocation.getCurrentPosition(
        function(position) {
            document.getElementById("lat").value = position.coords.latitude;
            document.getElementById("lon").value = position.coords.longitude;
            locationReady = true;
        },
        function(error) {
            alert("Please allow location access.");
        }
    );

    function checkLocation() {
        if (!locationReady) {
            alert("Waiting for location...");
            return false;
        }
        return true;
    }
    </script>
    """

# -------- SUBMIT --------
@app.route("/submit", methods=["POST"])
def submit():

    if get_status() == "closed":
        return "<h3>❌ Attendance Closed</h3>"

    roll = request.form["roll"]
    name = request.form["name"]
    lat = request.form["lat"]
    lon = request.form["lon"]

    if not lat or not lon:
        return "<h3>❌ Location Required</h3>"

    distance = calculate_distance(float(lat), float(lon), CLASS_LAT, CLASS_LON)

    if distance > ALLOWED_RADIUS:
        return "<h3>❌ Outside classroom (20m limit)</h3>"

    today = datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.now().strftime("%H:%M:%S")

    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    c.execute("SELECT * FROM attendance WHERE roll=? AND date=?", (roll, today))
    if c.fetchone():
        conn.close()
        return "<h3>⚠️ Roll already marked today</h3>"

    c.execute("INSERT INTO attendance VALUES (?, ?, ?, ?)",
              (roll, name, time_now, today))

    conn.commit()
    conn.close()

    return "<h3>✅ Attendance Marked</h3>"

# -------- TEACHER LOGIN --------
@app.route("/teacher", methods=["GET", "POST"])
def teacher():
    if request.method == "POST":
        if request.form["password"] == TEACHER_PASSWORD:
            session["teacher"] = True
            return redirect(url_for("dashboard"))
        else:
            return "<h3>Wrong Password</h3>"

    return """
    <h2>Teacher Login</h2>
    <form method="POST">
        Password:<br>
        <input type="password" name="password"><br><br>
        <button type="submit">Login</button>
    </form>
    """

# -------- DASHBOARD --------
@app.route("/dashboard")
def dashboard():
    if not session.get("teacher"):
        return redirect(url_for("teacher"))

    today = datetime.now().strftime("%Y-%m-%d")
    status = get_status()

    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("SELECT roll, name, time FROM attendance WHERE date=?", (today,))
    records = c.fetchall()
    conn.close()

    html = f"<h2>Dashboard (Status: {status.upper()})</h2>"
    html += "<a href='/open'>Open</a> | <a href='/close'>Close</a><br><br>"

    html += "<table border=1><tr><th>Roll</th><th>Name</th><th>Time</th></tr>"
    for r in records:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>"
    html += "</table><br>"

    html += "<a href='/download'>Download CSV</a><br><br>"
    html += "<a href='/logout'>Logout</a>"

    return html

# -------- OPEN/CLOSE --------
@app.route("/open")
def open_attendance():
    if not session.get("teacher"):
        return redirect(url_for("teacher"))
    set_status("open")
    return redirect(url_for("dashboard"))

@app.route("/close")
def close_attendance():
    if not session.get("teacher"):
        return redirect(url_for("teacher"))
    set_status("closed")
    return redirect(url_for("dashboard"))

# -------- DOWNLOAD --------
@app.route("/download")
def download():
    if not session.get("teacher"):
        return redirect(url_for("teacher"))

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"attendance_{today}.csv"

    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("SELECT roll, name, time FROM attendance WHERE date=?", (today,))
    records = c.fetchall()
    conn.close()

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Roll", "Name", "Time"])
        writer.writerows(records)

    return send_file(filename, as_attachment=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("teacher"))

if __name__ == "__main__":
    app.run()
