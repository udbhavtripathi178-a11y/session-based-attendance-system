from flask import Flask, request, redirect, url_for, session, send_file
from datetime import datetime
import sqlite3
import math
import csv
import os

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# -------- CLASSROOM LOCATION --------
CLASS_LAT = 28.425335
CLASS_LON = 77.326069
ALLOWED_RADIUS = 50   # ✅ 50 meters

TEACHER_PASSWORD = "admin123"

# -------- DATABASE SETUP --------
def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Attendance Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll TEXT,
            name TEXT,
            ip TEXT,
            time TEXT,
            date TEXT
        )
    """)

    # Settings Table (Open/Close Control)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            attendance_open INTEGER
        )
    """)

    cursor.execute("SELECT * FROM settings WHERE id=1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (id, attendance_open) VALUES (1, 0)")

    conn.commit()
    conn.close()

init_db()

# -------- DISTANCE FUNCTION --------
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# -------- STUDENT PAGE --------
@app.route("/")
def home():
    return """
    <h2>Class Attendance</h2>

    <p id="locationStatus" style="color:red;">⚠️ Checking Location...</p>

    <form method="POST" action="/submit" onsubmit="return checkLocation()">
        Roll Number:<br>
        <input name="roll" required><br><br>

        Name:<br>
        <input name="name" required><br><br>

        <input type="hidden" name="lat" id="lat">
        <input type="hidden" name="lon" id="lon">

        <button type="submit" id="submitBtn" disabled>
            Submit Attendance
        </button>
    </form>

    <script>
    function checkLocation() {
        if (!document.getElementById("lat").value) {
            alert("❌ Please enable location first!");
            return false;
        }
        return true;
    }

    navigator.geolocation.getCurrentPosition(
        function(position) {
            document.getElementById("lat").value = position.coords.latitude;
            document.getElementById("lon").value = position.coords.longitude;
            document.getElementById("locationStatus").innerHTML = "✅ Location Verified";
            document.getElementById("locationStatus").style.color = "green";
            document.getElementById("submitBtn").disabled = false;
        },
        function() {
            document.getElementById("locationStatus").innerHTML = "❌ Location access required!";
            document.getElementById("submitBtn").disabled = true;
        }
    );
    </script>
    """

# -------- SUBMIT ATTENDANCE --------
@app.route("/submit", methods=["POST"])
def submit():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Check attendance status
    cursor.execute("SELECT attendance_open FROM settings WHERE id=1")
    status = cursor.fetchone()[0]

    if status == 0:
        conn.close()
        return "<h3>⚠️ Attendance is currently CLOSED by teacher.</h3>"

    roll = request.form["roll"].strip()
    name = request.form["name"].strip()
    lat = request.form["lat"]
    lon = request.form["lon"]

    if not lat or not lon:
        conn.close()
        return "<h3>❌ Please enable location and refresh page.</h3>"

    distance = calculate_distance(float(lat), float(lon), CLASS_LAT, CLASS_LON)

    if distance > ALLOWED_RADIUS:
        conn.close()
        return "<h3>❌ You are outside classroom (50m limit)</h3>"

    today = datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.now().strftime("%H:%M:%S")
    ip_address = request.remote_addr

    # Roll duplicate check
    cursor.execute("SELECT * FROM attendance WHERE roll=? AND date=?", (roll, today))
    if cursor.fetchone():
        conn.close()
        return "<h3>⚠️ Attendance already marked for this Roll today.</h3>"

    # IP duplicate check
    cursor.execute("SELECT * FROM attendance WHERE ip=? AND date=?", (ip_address, today))
    if cursor.fetchone():
        conn.close()
        return "<h3>⚠️ Attendance already submitted from this device today.</h3>"

    cursor.execute(
        "INSERT INTO attendance (roll, name, ip, time, date) VALUES (?, ?, ?, ?, ?)",
        (roll, name, ip_address, time_now, today)
    )

    conn.commit()
    conn.close()

    return "<h3>✅ Attendance Marked Successfully</h3>"

# -------- TEACHER LOGIN --------
@app.route("/teacher", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        if request.form["password"] == TEACHER_PASSWORD:
            session["teacher"] = True
            return redirect(url_for("dashboard"))
        else:
            return "<h3>❌ Wrong Password</h3>"

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
        return redirect(url_for("teacher_login"))

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute("SELECT attendance_open FROM settings WHERE id=1")
    status = cursor.fetchone()[0]

    cursor.execute("SELECT roll, name, time, ip FROM attendance WHERE date=?", (today,))
    records = cursor.fetchall()

    conn.close()

    html = "<h2>Today's Attendance</h2>"

    if status == 0:
        html += '<a href="/open"><button>Open Attendance</button></a><br><br>'
    else:
        html += '<a href="/close"><button>Close Attendance</button></a><br><br>'

    html += "<table border=1><tr><th>Roll</th><th>Name</th><th>Time</th><th>IP</th></tr>"

    for r in records:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    html += "</table><br>"
    html += '<a href="/download">Download CSV</a><br><br>'
    html += '<a href="/logout">Logout</a>'

    return html

# -------- OPEN ATTENDANCE --------
@app.route("/open")
def open_attendance():
    if not session.get("teacher"):
        return redirect(url_for("teacher_login"))

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET attendance_open=1 WHERE id=1")
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# -------- CLOSE ATTENDANCE --------
@app.route("/close")
def close_attendance():
    if not session.get("teacher"):
        return redirect(url_for("teacher_login"))

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET attendance_open=0 WHERE id=1")
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# -------- DOWNLOAD CSV --------
@app.route("/download")
def download():
    if not session.get("teacher"):
        return redirect(url_for("teacher_login"))

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"attendance_{today}.csv"

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT roll, name, time, ip FROM attendance WHERE date=?", (today,))
    records = cursor.fetchall()
    conn.close()

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Roll", "Name", "Time", "IP"])
        writer.writerows(records)

    return send_file(filename, as_attachment=True)

# -------- LOGOUT --------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("teacher_login"))

# -------- RUN --------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
