print("PostgreSQL VERSION LOADED")

import os
import pg8000.native
import csv
import math
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, session, send_file
import io
import urllib.parse

app = Flask(__name__)
app.secret_key = "supersecretkey"

COLLEGE_LAT = 21.212938
COLLEGE_LON = 78.973262
RADIUS_METERS = 250

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://attendance_db_h7f7_user:F4ejWXtUjuchTIHIP4Pedwe9z3hLJrap@dpg-d6r7sec50q8c73btn090-a/attendance_db_h7f7')

def get_conn():
    url = urllib.parse.urlparse(DATABASE_URL)
    return pg8000.native.Connection(
        host=url.hostname,
        port=url.port or 5432,
        database=url.path[1:],
        user=url.username,
        password=url.password,
        ssl_context=True
    )

def init_db():
    conn = get_conn()
    conn.run('''
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
    conn.close()

init_db()

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

@app.route('/')
def home():
    return render_template('index.html')

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

    # Duplicate Check
    existing = conn.run(
        "SELECT * FROM attendance WHERE name = :name AND DATE(datetime::timestamp) = :date",
        name=name, date=today_date
    )
    if existing:
        conn.close()
        return jsonify({"status": "duplicate"})

    # Photo Save
    photo_filename = data.get('photo', '')

    # Save Attendance
    conn.run(
        "INSERT INTO attendance (name, latitude, longitude, datetime, photo, department, usn) VALUES (:name, :lat, :lon, :dt, :photo, :dept, :usn)",
        name=name, lat=lat, lon=lon, dt=current_datetime, photo=photo_filename, dept=department, usn=usn
    )
    conn.close()
    return jsonify({"status": "success"})

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

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect('/admin')

    conn = get_conn()
    raw_records = conn.run('SELECT name, latitude, longitude, datetime, photo, department, usn FROM attendance ORDER BY datetime DESC')
    records = list(enumerate(raw_records, start=1))

    date_data = conn.run('''
        SELECT DATE(datetime::timestamp), COUNT(*)
        FROM attendance
        GROUP BY DATE(datetime::timestamp)
        ORDER BY DATE(datetime::timestamp)
    ''')
    conn.close()

    labels = [str(row[0]) for row in date_data]
    values = [row[1] for row in date_data]

    return render_template('dashboard.html', records=records, labels=labels, values=values)

@app.route('/download')
def download_excel():
    if not session.get('admin'):
        return redirect('/admin')

    conn = get_conn()
    rows = conn.run('SELECT name, latitude, longitude, datetime FROM attendance')
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

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=False)