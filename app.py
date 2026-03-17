from flask import Flask, request, redirect, url_for, session, send_file, render_template
from datetime import datetime
import sqlite3
import math
import csv

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# -------- CLASSROOM LOCATION --------
CLASS_LAT = 28.423591
CLASS_LON = 77.065827
ALLOWED_RADIUS = 30

TEACHER_PASSWORD = "admin123"

# -------- DATABASE SETUP --------
def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

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

# -------- HOME (FRONTEND CONNECTED) --------
@app.route("/")
def home():
    return render_template("index.html")

# -------- SUBMIT --------
@app.route("/submit", methods=["POST"])
def submit():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Check attendance open or closed
    cursor.execute("SELECT attendance_open FROM settings WHERE id=1")
    status = cursor.fetchone()[0]

    if status == 0:
        conn.close()
        return "<h3>⚠️ Attendance is CLOSED</h3>"

    roll = request.form["roll"]
    name = request.form["name"]
    lat = request.form["lat"]
    lon = request.form["lon"]

    if not lat or not lon:
        conn.close()
        return "<h3>❌ Please enable location</h3>"

    distance = calculate_distance(float(lat), float(lon), CLASS_LAT, CLASS_LON)

    if distance > ALLOWED_RADIUS:
        conn.close()
        return "<h3>❌ You are outside classroom (50m)</h3>"

    today = datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.now().strftime("%H:%M:%S")
    ip = request.remote_addr

    # Roll check
    cursor.execute("SELECT * FROM attendance WHERE roll=? AND date=?", (roll, today))
    if cursor.fetchone():
        conn.close()
        return "<h3>⚠️ Roll already marked</h3>"

    # IP check
    cursor.execute("SELECT * FROM attendance WHERE ip=? AND date=?", (ip, today))
    if cursor.fetchone():
        conn.close()
        return "<h3>⚠️ Device already used today</h3>"

    cursor.execute(
        "INSERT INTO attendance (roll, name, ip, time, date) VALUES (?, ?, ?, ?, ?)",
        (roll, name, ip, time_now, today)
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

    return render_template("login.html")

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

    return render_template("dashboard.html",
                           today=today,
                           status=status,
                           records=records)

# -------- OPEN --------
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

# -------- CLOSE --------
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

# -------- DOWNLOAD --------
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
    app.run()
