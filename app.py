from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import mysql.connector
from functools import wraps
import random
import urllib.request
import json
import csv
import io
import smtplib
import datetime
from email.mime.text import MIMEText
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'skripsi_unair_hebat' 
app.permanent_session_lifetime = timedelta(minutes=15) 

# --- VARIABLE JANTUNG GLOBAL HARDWARE TRACKING ---
LAST_SEEN_HARDWARE = {}

# --- KONFIGURASI EMAIL BOT ---
EMAIL_SENDER = "smartdoor.unair@gmail.com" 
EMAIL_PASSWORD = "plfcwufhkgijwzjr"        

# --- KONEKSI DATABASE ---
def get_db_connection():
    return mysql.connector.connect(
        host="brtes9fxxbfuwuurhjfx-mysql.services.clever-cloud.com",
        user="ujiqps88uip6czmm",
        password="QViN9QYtHk0D1E2eIQUP",
        database="brtes9fxxbfuwuurhjfx",
        port=3306,
        ssl_disabled=True
    )

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# 1. HALAMAN LOGIN & LOGOUT
# ==========================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        
        if admin:
            now = datetime.datetime.now()
            
            if admin['login_attempts'] >= 3:
                if admin['last_attempt']:
                    time_diff = (now - admin['last_attempt']).total_seconds()
                    if time_diff < 300: 
                        sisa_waktu = int((300 - time_diff) / 60) + 1
                        return render_template("login.html", error=f"Akun terkunci sementara! Terlalu banyak percobaan salah. Coba lagi dalam {sisa_waktu} menit.")
                    else:
                        cursor.execute("UPDATE admins SET login_attempts = 0 WHERE username = %s", (username,))
                        conn.commit()

            if admin['password'] == password:
                cursor.execute("UPDATE admins SET login_attempts = 0 WHERE username = %s", (username,))
                conn.commit()
                cursor.close()
                conn.close()
                
                if admin.get('status') == 'PENDING':
                    return render_template("login.html", error="Akun PENDING! Silakan tap Master Card lalu tap kartu Anda di alat untuk aktivasi.")
                    
                session.permanent = True 
                session['logged_in'] = True
                session['admin_user'] = admin['username']
                session['role'] = admin['role']
                return redirect(url_for('dashboard'))
            else:
                cursor.execute("UPDATE admins SET login_attempts = login_attempts + 1, last_attempt = %s WHERE username = %s", (now, username))
                conn.commit()
                cursor.close()
                conn.close()
                return render_template("login.html", error="Username atau Password Salah!")
        else:
            cursor.close()
            conn.close()
            return render_template("login.html", error="Akun tidak ditemukan atau Password salah! Silakan daftar akun baru.")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==========================================
# 2. HALAMAN REGISTRASI & OTP
# ==========================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "send_otp":
            email = request.form.get("email")
            role = request.form.get("role")
            
            otp = str(random.randint(100000, 999999))
            session['otp'] = otp
            session['reg_email'] = email
            session['reg_role'] = role
            
            WEBHOOK_URL = "https://script.google.com/macros/s/AKfycby3GBJrsIE7HJ_ZV_9xoSUtFbZ08U26gZP2rG86I13TwDE_ZgWTWY-8hqCZTRSkGJw0sg/exec"
            payload = {
                "to": email,
                "subject": "Kode OTP Registrasi Smart Door",
                "text": f"Halo!\n\nKode rahasia (OTP) pendaftaran Smart Door Anda adalah: {otp}\n\nJangan berikan kode ini ke siapapun."
            }

            req = urllib.request.Request(
                WEBHOOK_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            try:
                urllib.request.urlopen(req, timeout=10) 
                return render_template("register.html", step="verify", email=email)
            except Exception as e:
                return render_template("register.html", step="email", error=f"Gagal via API: {e}")
        
        elif action == "verify_otp":
            user_otp = request.form.get("otp")
            if user_otp == session.get('otp'):
                username = request.form.get("username")
                password = request.form.get("password")
                email = session.get('reg_email')
                role = session.get('reg_role')
                
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO admins (username, password, role, email, status) VALUES (%s, %s, %s, %s, 'PENDING')", 
                                   (username, password, role, email))
                    conn.commit()
                    session.clear() 
                    return render_template("login.html", success="Pendaftaran berhasil! Akun berstatus PENDING. Silakan aktivasi di mesin menggunakan Master Card.")
                except Exception as e:
                    return render_template("register.html", step="verify", email=email, error="Username atau Email sudah terdaftar!")
                finally:
                    cursor.close()
                    conn.close()
            else:
                return render_template("register.html", step="verify", email=session.get('reg_email'), error="Kode OTP Salah!")

    return render_template("register.html", step="email")


# ==========================================
# 3. DASHBOARD (UTAMA)
# ==========================================
@app.route("/")
@login_required
def dashboard():
    role = session.get('role', 'admin')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SET time_zone = '+07:00'")
    
    if role == 'admin':
        cursor.execute("SELECT * FROM access_logs WHERE DATE(timestamp) = CURDATE() ORDER BY timestamp DESC LIMIT 50")
        logs = cursor.fetchall()
        cursor.execute("SELECT door_id, is_open FROM remote_control")
        bypass_data = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM access_logs WHERE door_id = %s AND DATE(timestamp) = CURDATE() ORDER BY timestamp DESC LIMIT 50", (role,))
        logs = cursor.fetchall()
        cursor.execute("SELECT door_id, is_open FROM remote_control WHERE door_id = %s", (role,))
        bypass_data = cursor.fetchall()
    
    bypass_status = {item['door_id']: item['is_open'] for item in bypass_data}
    cursor.close()
    conn.close()
    
    return render_template("index.html", logs=logs, bypass_status=bypass_status, role=role, username=session.get('admin_user'))


# ==========================================
# 4. API KONTROL PINTU & HEARTBEAT + ENDPOINT SAKTI AKTIVASI
# ==========================================
@app.route("/trigger_bypass", methods=["POST"])
@login_required
def trigger_bypass():
    door_id = request.json.get("door_id")
    action = request.json.get("action", "open")
    role = session.get('role')
    if role != 'admin' and role != door_id: return jsonify({"error": "Akses Ditolak"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if action == "reset": cursor.execute("UPDATE remote_control SET is_open = FALSE WHERE door_id = %s", (door_id,))
        else: cursor.execute("UPDATE remote_control SET is_open = TRUE WHERE door_id = %s", (door_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Sukses"}), 200
    except Exception as e: return str(e), 500

@app.route("/check_bypass_status", methods=["GET"])
def check_bypass_status():
    door_id = request.args.get("door_id", "door1").lower() # Paksa lowercase untuk detak jantung
    
    global LAST_SEEN_HARDWARE
    LAST_SEEN_HARDWARE[door_id] = datetime.datetime.now()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_open FROM remote_control WHERE LOWER(door_id) = %s", (door_id,))
        status = cursor.fetchone()
        if status and status['is_open']:
            cursor.execute("UPDATE remote_control SET is_open = FALSE WHERE LOWER(door_id) = %s", (door_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "OPEN"}), 200
        cursor.close()
        conn.close()
        return jsonify({"status": "CLOSED"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

# === API SAKTI AKTIVASI KARTU BARU (LINK ANTARA USERNAME WEB DAN NAMA WAJAH) ===
@app.route("/activate_admin", methods=["POST"])
def activate_admin():
    data = request.json
    new_uid = data.get("new_uid")
    if not new_uid:
        return jsonify({"status": "FAILED", "error": "UID Kosong!"}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Cari Akun Web (admins) yang statusnya PENDING paling baru dibuat
        cursor.execute("SELECT username FROM admins WHERE status = 'PENDING' ORDER BY id DESC LIMIT 1")
        pending_admin = cursor.fetchone()
        
        # 2. Cari Pegawai Fisik (users) yang rfid_uid-nya kosong / belum terisi paling baru didaftar
        cursor.execute("SELECT id, nama FROM users WHERE rfid_uid IS NULL OR rfid_uid = '' OR rfid_uid = '-' ORDER BY id DESC LIMIT 1")
        pending_user = cursor.fetchone()
        
        if not pending_admin and not pending_user:
            cursor.close()
            conn.close()
            return jsonify({"status": "FAILED", "error": "Tidak ada antrean pendaftaran!"}), 200
            
        # Jika akun web pending ditemukan, pasangkan UID-nya dan aktifkan!
        if pending_admin:
            cursor.execute("UPDATE admins SET rfid_uid = %s, status = 'AKTIF' WHERE username = %s", 
                           (new_uid, pending_admin['username']))
            print(f"[SINKRONISASI] Akun Web '{pending_admin['username']}' Berhasil Diaktifkan!")

        # Jika profile wajah fisik ditemukan, pasangkan UID kartu yang sama!
        if pending_user:
            cursor.execute("UPDATE users SET rfid_uid = %s WHERE id = %s", 
                           (new_uid, pending_user['id']))
            print(f"[SINKRONISASI] Profil Wajah '{pending_user['nama']}' Berhasil Dipasangkan Kartu!")
            
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "SUCCESS"}), 200
        
    except Exception as e:
        print(f"[ERROR AKTIVASI AMAN] {e}")
        return jsonify({"status": "FAILED", "error": str(e)}), 500

@app.route("/api/hardware_status", methods=["GET"])
def api_hardware_status():
    door_id = request.args.get("door_id", "door1").lower() # Paksa lowercase
    global LAST_SEEN_HARDWARE
    
    last_seen = LAST_SEEN_HARDWARE.get(door_id)
    if last_seen:
        time_diff = (datetime.datetime.now() - last_seen).total_seconds()
        if time_diff < 35:
            return jsonify({"status": "ONLINE"}), 200
            
    return jsonify({"status": "OFFLINE"}), 200

@app.route("/log_access", methods=["POST"])
def log_access():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET time_zone = '+07:00'")
        sql = "INSERT INTO access_logs (door_id, name, card_uid, method, status, timestamp) VALUES (%s, %s, %s, %s, %s, NOW())"
        cursor.execute(sql, (data.get("door_id"), data.get("name"), data.get("card_uid"), data.get("method"), data.get("status")))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Log tersimpan akurat pakai jam WIB!"}), 200
    except Exception as e: 
        print(f"[ERROR SIMPAN LOG] {e}")
        return jsonify({"error": str(e)}), 500


# ==========================================
# 5. API LIVE REFRESH & EXPORT EXCEL
# ==========================================
@app.route("/api/logs")
@login_required
def api_logs():
    role = session.get('role', 'admin')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SET time_zone = '+07:00'")
    
    if role == 'admin':
        cursor.execute("SELECT * FROM access_logs WHERE DATE(timestamp) = CURDATE() ORDER BY timestamp DESC LIMIT 50")
    else:
        cursor.execute("SELECT * FROM access_logs WHERE door_id = %s AND DATE(timestamp) = CURDATE() ORDER BY timestamp DESC LIMIT 50", (role,))
    
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    
    for log in logs:
        log['timestamp'] = str(log['timestamp'])
        
    return jsonify(logs)

@app.route("/export_csv")
@login_required
def export_csv():
    role = session.get('role', 'admin')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if role == 'admin':
        cursor.execute("SELECT door_id, timestamp, name, method, status FROM access_logs ORDER BY timestamp DESC")
    else:
        cursor.execute("SELECT door_id, timestamp, name, method, status FROM access_logs WHERE door_id = %s ORDER BY timestamp DESC", (role,))
    
    logs = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    output.write('\ufeff') 
    writer = csv.writer(output, delimiter=';') 
    writer.writerow(['Pintu', 'Waktu', 'Nama', 'Metode', 'Status']) 
    
    for log in logs:
        writer.writerow([log['door_id'], log['timestamp'], log['name'], log['method'], log['status']])

    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Laporan_Akses_SmartDoor.csv"})


# ==========================================
# 6. PROFIL & GANTI PASSWORD
# ==========================================
@app.route("/profile")
@login_required
def profile():
    username = session.get('admin_user')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT email FROM admins WHERE username = %s", (username,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    
    email = user_data['email'] if user_data else ""
    return render_template("profile.html", username=username, role=session.get('role'), email=email)
    
@app.route("/forgot_password", methods=["POST"])
@login_required
def forgot_password():
    email = request.json.get("email")
    otp = str(random.randint(100000, 999999))
    session['reset_otp'] = otp
    
    try:
        msg = MIMEText(f"Kode OTP untuk mengganti password Smart Door Anda adalah: {otp}")
        msg['Subject'] = 'Reset Password Smart Door'
        msg['From'] = EMAIL_SENDER
        msg['To'] = email
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return jsonify({"message": "OTP Terkirim"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_password", methods=["POST"])
@login_required
def update_password():
    data = request.json
    if data.get("otp") == session.get("reset_otp"):
        new_password = data.get("new_password")
        username = session.get('admin_user')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE admins SET password = %s WHERE username = %s", (new_password, username))
        conn.commit()
        cursor.close()
        conn.close()
        session.pop('reset_otp', None)
        return jsonify({"message": "Sukses"}), 200
    return jsonify({"error": "OTP Salah"}), 400


# ==========================================
# 7. MANAJEMEN PEGAWAI & AKUN WEB
# ==========================================
@app.route("/manage_users")
@login_required
def manage_users():
    if session.get('role') != 'admin':
        return "Akses Ditolak! Halaman ini khusus Admin Utama.", 403
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nama, rfid_uid, allowed_door FROM users ORDER BY id DESC")
    users_data = cursor.fetchall()
    cursor.execute("SELECT id, username, email, role, status, rfid_uid FROM admins WHERE username != %s ORDER BY id DESC", (session.get('admin_user'),))
    admins_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template("users.html", username=session.get('admin_user'), role=session.get('role'), users=users_data, admins=admins_data)

@app.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Akses Pintu (Wajah+RFID) dihapus!"}), 200

@app.route("/delete_admin/<int:admin_id>", methods=["POST"])
@login_required
def delete_admin(admin_id):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE id = %s", (admin_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Akun Login Web berhasil dihapus!"}), 200


# ==========================================
# 8. RIWAYAT AKSES (LOGS)
# ==========================================
@app.route("/logs")
@login_required
def view_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 100")
    logs_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template("logs.html", username=session.get('admin_user'), role=session.get('role'), logs=logs_data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
