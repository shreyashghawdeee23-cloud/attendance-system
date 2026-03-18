print("PostgreSQL VERSION LOADED")

import os
import psycopg2
import csv
import math
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, session, send_file
import io

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ==============================
# College Coordinates
# ==============================
COLLEGE_LAT = 21.212938
COLLEGE_LON = 78.973262
RADIUS_METERS = 250

# ==============================
# Admin Credentials
# ==============================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# ==============================
# Database Connection
# ==============================
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://attendance_db_h7f7_user:F4ejWXtUjuchTIHIP4Pedwe9z3hLJrap@dpg-d6r7sec50q8c73btn090-a/attendance_db_h7f7')

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            datetime TEXT NOT NULL,
            photo TEXT,
            department TEXT,
            usn TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==============================
# Distance Function (Haversine)
# ==============================
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ==============================
# Home Page
# ==============================
@app.route('/')
def home():
    return render_template('index.html')

# ==============================
# Mark Attendance
# ==============================
@app.route('/mark', methods=['POST'])
def mark_attendance():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    name = data.get('name')
    lat = data.get('latitude')
    lon = data.get('longitude')
    department = data.get('department', '')
    usn = data.get('usn', '')

    if not name or lat is None or lon is None:
        return jsonify({"status": "error", "message": "Incomplete data"}), 400

    lat = float(lat)
    lon = float(lon)

    distance = calculate_distance(lat, lon, COLLEGE_LAT, COLLEGE_LON)
    print("User Location:", lat, lon)
    print("Distance:", distance)

    if distance > RADIUS_METERS:
        return jsonify({"status": "fail", "distance": round(distance)})

    today_date = datetime.now().strftime("%Y-%m-%d")
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    cursor = conn.cursor()

    # Duplicate Check
    cursor.execute('''
        SELECT * FROM attendance
        WHERE name = %s AND DATE(datetime) = %s
    ''', (name, today_date))

    existing = cursor.fetchone()
    if existing:
        conn.close()
        return jsonify({"status": "duplicate"})

    # Photo Save
    photo_filename = ""
    photo = data.get('photo')
    if photo:
        photo_filename = photo

    # Save Attendance
    cursor.execute('''
        INSERT INTO attendance (name, latitude, longitude, datetime, photo, department, usn)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (name, lat, lon, current_datetime, photo_filename, department, usn))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

# ==============================
# Admin Login
# ==============================
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/dashboard')
        else:
            return "Invalid Credentials"

    return render_template('admin.html')

# ==============================
# Dashboard
# ==============================
@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect('/admin')

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT name, latitude, longitude, datetime, photo, department, usn FROM attendance ORDER BY datetime DESC')
    raw_records = cursor.fetchall()
    records = list(enumerate(raw_records, start=1))

    cursor.execute('''
        SELECT DATE(datetime), COUNT(*)
        FROM attendance
        GROUP BY DATE(datetime)
        ORDER BY DATE(datetime)
    ''')
    date_data = cursor.fetchall()
    conn.close()

    labels = [str(row[0]) for row in date_data]
    values = [row[1] for row in date_data]

    return render_template('dashboard.html', records=records, labels=labels, values=values)

# ==============================
# Download CSV
# ==============================
@app.route('/download')
def download_excel():
    if not session.get('admin'):
        return redirect('/admin')

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT name, latitude, longitude, datetime FROM attendance')
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Latitude", "Longitude", "Date Time"])
    writer.writerows(rows)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='attendance.csv'
    )

# ==============================
# Logout
# ==============================
@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/admin')

# ==============================
# Run
# ==============================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=False)