from flask import Flask, render_template, request, jsonify
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# --- KONEKSI DATABASE CLEVER CLOUD ---
def get_db_connection():
    return mysql.connector.connect(
        host="brtes9fxxbfuwuurhjfx-mysql.services.clever-cloud.com",
        user="ujiqps88uip6czmm",
        password="QViN9QYtHk0D1E2eIQUP",
        database="brtes9fxxbfuwuurhjfx",
        port=3306,
        ssl_disabled=True # <--- TAMBAHKAN BARIS INI
    )

# --- FUNGSI TUKANG KAYU (BUAT TABEL LOG & BYPASS) ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Tabel Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            door_id VARCHAR(50),
            name VARCHAR(100),
            card_uid VARCHAR(50),
            method VARCHAR(50),
            status VARCHAR(50),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Tabel Bypass Jarak Jauh
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remote_control (
            id INT AUTO_INCREMENT PRIMARY KEY,
            door_id VARCHAR(50) UNIQUE,
            is_open BOOLEAN DEFAULT FALSE
        )
    """)
    # Masukkan data default pintu 1 jika belum ada
    cursor.execute("INSERT IGNORE INTO remote_control (door_id, is_open) VALUES ('door1', FALSE)")
    conn.commit()
    cursor.close()
    conn.close()

# Inisialisasi tabel saat web pertama kali jalan
try:
    init_db()
except Exception as e:
    print(f"Gagal inisialisasi DB: {e}")

# ==========================================
# 1. HALAMAN UTAMA (DASHBOARD)
# ==========================================
@app.route("/")
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Ambil 50 log terakhir
    cursor.execute("SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 50")
    logs = cursor.fetchall()
    
    # Ambil status bypass
    cursor.execute("SELECT is_open FROM remote_control WHERE door_id = 'door1'")
    bypass_status = cursor.fetchone()['is_open']
    
    cursor.close()
    conn.close()
    return render_template("index.html", logs=logs, bypass_status=bypass_status)


# ==========================================
# 2. API UNTUK ESP32 MENGIRIM LOG (MENJAWAB ERROR -11)
# ==========================================
@app.route("/log_access", methods=["POST"])
def log_access():
    try:
        data = request.json
        door_id = data.get("door_id")
        name = data.get("name")
        card_uid = data.get("card_uid")
        method = data.get("method")
        status = data.get("status")

        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO access_logs (door_id, name, card_uid, method, status) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (door_id, name, card_uid, method, status))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Log tersimpan!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API saat admin menekan tombol "Buka Pintu" di Web
@app.route("/trigger_bypass", methods=["POST"])
def trigger_bypass():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE remote_control SET is_open = TRUE WHERE door_id = 'door1'")
        conn.commit()
        cursor.close()
        conn.close()
        return "Perintah Bypass Aktif", 200
    except Exception as e:
        return str(e), 500

# API untuk dibaca oleh ESP32-RFID (apakah pintu harus dibuka?)
@app.route("/check_bypass_status", methods=["GET"])
def check_bypass_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_open FROM remote_control WHERE door_id = 'door1'")
        status = cursor.fetchone()
        
        # Jika statusnya TRUE (admin baru saja menekan tombol)
        if status and status['is_open']:
            # Kembalikan ke FALSE agar pintu tidak terbuka terus-menerus
            cursor.execute("UPDATE remote_control SET is_open = FALSE WHERE door_id = 'door1'")
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "OPEN"}), 200
            
        cursor.close()
        conn.close()
        return jsonify({"status": "CLOSED"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)