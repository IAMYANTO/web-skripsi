from flask import Flask, request, jsonify
import face_recognition
import numpy as np
import cv2
import mysql.connector
import json 
from waitress import serve # 🚨 PENTING: Jangan lupa pip install waitress

app = Flask(__name__)

# --- 1. FUNGSI UNTUK MENGHUBUNGKAN KE CLEVER CLOUD ---
def get_db_connection():
    return mysql.connector.connect(
        host="brtes9fxxbfuwuurhjfx-mysql.services.clever-cloud.com",
        user="ujiqps88uip6czmm",
        password="QViN9QYtHk0D1E2eIQUP",
        database="brtes9fxxbfuwuurhjfx",
        port=3306
    )

# Tempat menyimpan memori wajah dan HAK AKSES PINTU sementara di RAM
known_encodings = []
known_names = []
known_doors = [] # 🚨 SUNTIKAN: List baru untuk mengingat akses pintu

# --- 2. FUNGSI UNTUK MENGAMBIL WAJAH & AKSES DARI DATABASE ---
def load_encodings_from_db():
    global known_encodings, known_names, known_doors
    known_encodings.clear()
    known_names.clear()
    known_doors.clear()
    
    print("[INFO] Mengambil data wajah dan hak akses dari Clever Cloud...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 🚨 SUNTIKAN: Sekarang kita juga menarik kolom 'allowed_door'
        cursor.execute("SELECT nama, face_encoding, allowed_door FROM users WHERE face_encoding IS NOT NULL")
        users = cursor.fetchall()

        for user in users:
            nama = user['nama']
            izin_pintu = user['allowed_door'] # Tangkap data pintunya
            
            # Ubah Teks dari DB ke bentuk Numpy Array
            encoding_list = json.loads(user['face_encoding'])
            encoding_np = np.array(encoding_list)
            
            known_names.append(nama)
            known_encodings.append(encoding_np)
            known_doors.append(izin_pintu) # Masukkan ke ingatan RAM
            
        print(f"[INFO] Berhasil memuat {len(known_encodings)} wajah beserta hak akses pintunya!")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Gagal mengambil data: {e}")

# Jalankan fungsi ambil data saat server pertama nyala
load_encodings_from_db()

@app.route("/")
def home():
    return "Face Recognition Server Lokal Aktif (Mode Produksi: Multi-Door)"

@app.route("/reload_faces", methods=["GET"])
def reload_faces():
    load_encodings_from_db()
    return jsonify({
        "status": "SUCCESS", 
        "message": f"Berhasil memuat ulang {len(known_encodings)} wajah dari Database!"
    })

# ==========================================
# JALUR KHUSUS: PENGENALAN WAJAH (S3 CAM)
# ==========================================
@app.route("/check_face", methods=["POST"])
def check_face():
    # 🚨 1. Tangkap "KTP" Pintu dari ESP32-S3 CAM 
    # (Pastikan ESP32 kirim ?door_id=door1 atau ?door_id=door2)
    door_id_kamera = request.args.get('door_id', 'door1')

    img_bytes = request.data
    if not img_bytes or len(img_bytes) < 100:
        return jsonify({"result": "NO_IMAGE", "name": "Unknown"})

    np_img = np.frombuffer(img_bytes, np.uint8)
    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    if image is None:
        return jsonify({"result": "ERROR", "name": "Unknown"})

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb, model="hog")
    encodings = face_recognition.face_encodings(rgb, boxes)

    if len(encodings) == 0:
        return jsonify({"result": "NO_FACE", "name": "Unknown"})

    encoding = encodings[0]

    if len(known_encodings) == 0:
         return jsonify({"result": "DB_EMPTY", "name": "Unknown"})

    distances = face_recognition.face_distance(known_encodings, encoding)
    best_match_index = np.argmin(distances)

    if distances[best_match_index] < 0.5:
        name = known_names[best_match_index]
        pintu_izin_user = known_doors[best_match_index] # 🚨 2. Cek ingatan RAM
        
        # 🚨 3. LOGIKA PEMBATAS PINTU
        # Kalau aksesnya bukan untuk pintu ini, dan bukan 'all' (Admin), maka TOLAK!
        if pintu_izin_user != door_id_kamera and pintu_izin_user != 'all':
            print(f"⛔ [PENYUSUP WAJAH] {name} mencoba masuk ke {door_id_kamera} (Izin: {pintu_izin_user})")
            return jsonify({
                "result": "UNKNOWN",
                "name": "Unknown"
            })
            
        # Kalau lolos validasi pintu
        print(f"✅ [FACE MATCH] {name} diizinkan masuk ke {door_id_kamera}")
        return jsonify({
            "result": "FACE_OK",
            "name": name
        })
    else:
        print("👤 [UNKNOWN FACE]")
        return jsonify({
            "result": "UNKNOWN",
            "name": "Unknown"
        })

# ==========================================
# JALUR KHUSUS: VALIDASI KARTU (ESP32 RFID)
# ==========================================
@app.route("/check_rfid", methods=["POST"])
def check_rfid():
    data = request.json
    uid_sent = data.get("uid")
    door_request = data.get("door_id", "door1") 
    print(f"\n💳 [Menerima Tap Kartu] UID: {uid_sent} dari {door_request}")
    
    try:
        conn = mysql.connector.connect(
            host="brtes9fxxbfuwuurhjfx-mysql.services.clever-cloud.com",
            user="ujiqps88uip6czmm",
            password="QViN9QYtHk0D1E2eIQUP",
            database="brtes9fxxbfuwuurhjfx",
            port=3306,
            connection_timeout=5
        )
        cursor = conn.cursor(dictionary=True)
        
        # 1. Cari di tabel users (Pegawai Biasa)
        cursor.execute("SELECT nama, allowed_door FROM users WHERE rfid_uid = %s", (uid_sent,))
        user = cursor.fetchone()
        
        # 2. Kalau gak ada, cari di tabel admins (Manajer)
        if not user:
            cursor.execute("SELECT username as nama, 'all' as allowed_door FROM admins WHERE rfid_uid = %s AND status = 'ACTIVE'", (uid_sent,))
            user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if user:
            # 🚨 LOGIKA PEMBATAS PINTU RFID (Kodingan Aslimu Udah Bener!)
            if user['allowed_door'] == door_request or user['allowed_door'] == 'all':
                print(f"✅ [Akses Ditemukan] Atas nama: {user['nama']} di {door_request}")
                return jsonify({
                    "status": "VALID",
                    "name": str(user['nama']).title() 
                })
            else:
                print(f"⛔ [Akses Ditolak] {user['nama']} salah pintu! Mencoba di {door_request}")
                return jsonify({"status": "INVALID", "name": "unknown"})
        else:
            print("❌ [Akses Ditolak] UID Kartu belum terdaftar atau masih PENDING!")
            return jsonify({"status": "INVALID", "name": "unknown"})
            
    except Exception as e:
        print(f"❌ [CRITICAL ERROR DB] {e}")
        return jsonify({"status": "ERROR", "name": "unknown"}), 500

# ==========================================
# JALUR KHUSUS: AKTIVASI KARTU MANAJER BARU
# ==========================================
@app.route("/activate_admin", methods=["POST"])
def activate_admin():
    # ... (Kodingan aslimu aman 100%, biarkan saja) ...
    data = request.json
    new_uid = data.get("new_uid")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username FROM admins WHERE status = 'PENDING' ORDER BY id DESC LIMIT 1")
        pending_admin = cursor.fetchone()
        
        if pending_admin:
            cursor.execute("UPDATE admins SET rfid_uid = %s, status = 'ACTIVE' WHERE id = %s", 
                           (new_uid, pending_admin['id']))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✅ [AKTIVASI SUKSES] Kartu {new_uid} didaftarkan untuk Manajer: {pending_admin['username']}")
            return jsonify({"status": "SUCCESS", "message": "Aktivasi Berhasil"})
        else:
            cursor.close()
            conn.close()
            return jsonify({"status": "FAILED", "message": "Tidak ada akun PENDING"})
            
    except Exception as e:
        return jsonify({"status": "ERROR"}), 500

if __name__ == "__main__":
    print("====================================================")
    print("🚀 SERVER AI BERJALAN DI MODE PRODUKSI (WAITRESS) 🚀")
    print("====================================================")
    # 🚨 SUNTIKAN: Buka 4 Kasir sekaligus biar gempuran 2 pintu gak bikin antre/error
    serve(app, host="0.0.0.0", port=5000, threads=4)