from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from functools import wraps
import random
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = 'skripsi_unair_hebat' 

# --- KONFIGURASI EMAIL BOT ---
EMAIL_SENDER = "smartdoor.unair@gmail.com" # <--- GANTI JIKA PERLU
EMAIL_PASSWORD = "plfcwufhkgijwzjr"        # <--- SANDI APLIKASI (Tanpa Spasi)

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
        cursor.execute("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if admin:
            # BLOKIR JIKA STATUS MASIH PENDING
            if admin.get('status') == 'PENDING':
                return render_template("login.html", error="Akun PENDING! Silakan tap Master Card lalu tap kartu Anda di alat untuk aktivasi.")
                
            session['logged_in'] = True
            session['admin_user'] = admin['username']
            session['role'] = admin['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template("login.html", error="Username atau Password Salah!")
            
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
        
        # TAHAP 1: KIRIM OTP KE EMAIL
        if action == "send_otp":
            email = request.form.get("email")
            role = request.form.get("role")
            
            # Buat 6 angka acak
            otp = str(random.randint(100000, 999999))
            session['otp'] = otp
            session['reg_email'] = email
            session['reg_role'] = role
            
            # Kirim Email
            msg = MIMEText(f"Halo!\n\nKode rahasia (OTP) pendaftaran Smart Door Anda adalah: {otp}\n\nJangan berikan kode ini ke siapapun.")
            msg['Subject'] = 'Kode OTP Registrasi Smart Door'
            msg['From'] = EMAIL_SENDER
            msg['To'] = email
            
            try:
                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.send_message(msg)
                server.quit()
                return render_template("register.html", step="verify", email=email)
            except Exception as e:
                return render_template("register.html", step="email", error=f"Gagal mengirim email: {e}")
                
        # TAHAP 2: VERIFIKASI OTP & BUAT AKUN
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
                    # Masukkan ke database dengan status PENDING
                    cursor.execute("INSERT INTO admins (username, password, role, email, status) VALUES (%s, %s, %s, %s, 'PENDING')", 
                                   (username, password, role, email))
                    conn.commit()
                    session.clear() # Bersihkan memori session
                    return render_template("login.html", success="Pendaftaran berhasil! Akun berstatus PENDING. Silakan aktivasi di mesin menggunakan Master Card.")
                except Exception as e:
                    return render_template("register.html", step="verify", email=email, error="Username atau Email sudah terdaftar!")
                finally:
                    cursor.close()
                    conn.close()
            else:
                return render_template("register.html", step="verify", email=session.get('reg_email'), error="Kode OTP Salah!")

    # Default: Tampilkan form isi email
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
    
    if role == 'admin':
        cursor.execute("SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 50")
        logs = cursor.fetchall()
        cursor.execute("SELECT door_id, is_open FROM remote_control")
        bypass_data = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM access_logs WHERE door_id = %s ORDER BY timestamp DESC LIMIT 50", (role,))
        logs = cursor.fetchall()
        cursor.execute("SELECT door_id, is_open FROM remote_control WHERE door_id = %s", (role,))
        bypass_data = cursor.fetchall()
    
    bypass_status = {item['door_id']: item['is_open'] for item in bypass_data}
    cursor.close()
    conn.close()
    return render_template("index.html", logs=logs, bypass_status=bypass_status, role=role, username=session.get('admin_user'))


# ==========================================
# 4. API & KONTROL PINTU
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
    door_id = request.args.get("door_id", "door1")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_open FROM remote_control WHERE door_id = %s", (door_id,))
        status = cursor.fetchone()
        if status and status['is_open']:
            cursor.execute("UPDATE remote_control SET is_open = FALSE WHERE door_id = %s", (door_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "OPEN"}), 200
        cursor.close()
        conn.close()
        return jsonify({"status": "CLOSED"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/log_access", methods=["POST"])
def log_access():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO access_logs (door_id, name, card_uid, method, status) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (data.get("door_id"), data.get("name"), data.get("card_uid"), data.get("method"), data.get("status")))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Log tersimpan!"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
