from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from functools import wraps

app = Flask(__name__)
app.secret_key = 'skripsi_unair_hebat' 

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
            session['logged_in'] = True
            session['admin_user'] = admin['username']
            session['role'] = admin['role'] # SIMPAN ROLE-NYA (admin / door1 / door2)
            return redirect(url_for('dashboard'))
        else:
            return render_template("login.html", error="Username atau Password Salah!")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# 2. DASHBOARD (UTAMA)
# ==========================================
@app.route("/")
@login_required
def dashboard():
    role = session.get('role', 'admin')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # FILTERING LOGIKA BERDASARKAN ROLE
    if role == 'admin':
        # Super Admin: Lihat semua pintu
        cursor.execute("SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 50")
        logs = cursor.fetchall()
        cursor.execute("SELECT door_id, is_open FROM remote_control")
        bypass_data = cursor.fetchall()
    else:
        # Manajer: Hanya lihat pintu miliknya (contoh: door1)
        cursor.execute("SELECT * FROM access_logs WHERE door_id = %s ORDER BY timestamp DESC LIMIT 50", (role,))
        logs = cursor.fetchall()
        cursor.execute("SELECT door_id, is_open FROM remote_control WHERE door_id = %s", (role,))
        bypass_data = cursor.fetchall()
    
    bypass_status = {item['door_id']: item['is_open'] for item in bypass_data}
    
    cursor.close()
    conn.close()
    return render_template("index.html", logs=logs, bypass_status=bypass_status, role=role, username=session.get('admin_user'))

# ==========================================
# 3. API & KONTROL PINTU
# ==========================================
@app.route("/trigger_bypass", methods=["POST"])
@login_required
def trigger_bypass():
    door_id = request.json.get("door_id")
    action = request.json.get("action", "open") # Bisa open / reset
    
    role = session.get('role')
    # Keamanan Ekstra: Cegah manajer 1 meretas pintu 2
    if role != 'admin' and role != door_id:
        return jsonify({"error": "Akses Ditolak"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if action == "reset":
            cursor.execute("UPDATE remote_control SET is_open = FALSE WHERE door_id = %s", (door_id,))
        else:
            cursor.execute("UPDATE remote_control SET is_open = TRUE WHERE door_id = %s", (door_id,))
            
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Sukses"}), 200
    except Exception as e:
        return str(e), 500

# (Biarkan /check_bypass_status dan /log_access persis sama seperti kodingan sebelumnya)
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
