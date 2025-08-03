from flask import Flask, render_template, request
import qrcode
import uuid
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
DB_NAME = 'qr.db'

os.makedirs('static', exist_ok=True)

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qr_codes (
                id TEXT PRIMARY KEY,
                data TEXT,
                max_scans INTEGER,
                scan_count INTEGER,
                expires_at TEXT,
                active INTEGER
            )
        """)
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_qr():
    data = request.form['data']
    max_scans = int(request.form['max_scans'])
    minutes_valid = int(request.form['minutes_valid'])

    qr_id = str(uuid.uuid4())
    expire_time = (datetime.now() + timedelta(minutes=minutes_valid)).isoformat()

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO qr_codes (id, data, max_scans, scan_count, expires_at, active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (qr_id, data, max_scans, 0, expire_time, 1))
        conn.commit()

    qr_url = request.host_url + 'scan/' + qr_id
    img = qrcode.make(qr_url)
    img_path = f'static/{qr_id}.png'
    img.save(img_path)

    return f"""<h2>QR Code Generated!</h2>
    <p><strong>Scannable Link:</strong> <a href='/scan/{qr_id}'>{qr_url}</a></p>
    <img src='/{img_path}' width='200'>
    <p><a href='/'>← Back</a></p>"""

@app.route('/scan/<qr_id>')
def scan_qr(qr_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT data, max_scans, scan_count, expires_at, active FROM qr_codes WHERE id=?', (qr_id,))
        row = cursor.fetchone()

        if not row:
            return "❌ Invalid QR code."

        data, max_scans, scan_count, expires_at_str, active = row
        expires_at = datetime.fromisoformat(expires_at_str)

        if not active:
            return "❌ QR code is inactive."

        if datetime.now() > expires_at:
            cursor.execute('UPDATE qr_codes SET active = 0 WHERE id=?', (qr_id,))
            conn.commit()
            return "❌ QR code has expired."

        if scan_count >= max_scans:
            cursor.execute('UPDATE qr_codes SET active = 0 WHERE id=?', (qr_id,))
            conn.commit()
            return "❌ QR code scan limit exceeded."

        scan_count += 1
        cursor.execute('UPDATE qr_codes SET scan_count = ? WHERE id=?', (scan_count, qr_id))
        conn.commit()

        return render_template('scan_result.html', data=data, count=scan_count, remaining=max_scans - scan_count)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)