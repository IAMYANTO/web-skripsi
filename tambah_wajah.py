import cv2
import face_recognition
import mysql.connector
import json
import requests

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

print("="*40)
print("SISTEM REGISTRASI WAJAH AI (LOKAL)")
print("="*40)

nama = input("Masukkan Nama User: ")
allowed_door = input("Masukkan Akses Pintu (door1 / door2): ")

print("\n[INFO] Menyalakan Kamera...")
print("[INFO] Posisikan wajah di tengah layar.")
print("[INFO] Tekan tombol 'S' pada keyboard untuk Memotret.")
print("[INFO] Tekan tombol 'Q' untuk Batal.")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
        
    cv2.imshow('Registrasi Wajah - Tekan S untuk Foto', frame)
    
    key = cv2.waitKey(1)
    if key == ord('s'):
        print("\n[PROSES] Memindai struktur wajah...")
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if len(face_locations) == 0:
            print("❌ Wajah tidak terdeteksi! Pastikan cahaya cukup. Coba foto lagi.")
        elif len(face_locations) > 1:
            print("❌ Terdeteksi lebih dari 1 wajah! Tolong sendirian di depan kamera.")
        else:
            print("[PROSES] Wajah ditemukan! Menghitung Encoding matriks...")
            face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
            encoding_str = json.dumps(face_encoding.tolist())
            
            print("[PROSES] Mengirim data ke Clever Cloud...")
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # CATATAN: aku asumsikan nama tabel wajah adalah "users"
                # dengan kolom (name, face_encoding, allowed_door). 
                cursor.execute("INSERT INTO users (nama, face_encoding, allowed_door) VALUES (%s, %s, %s)", 
                               (nama, encoding_str, allowed_door))
                conn.commit()
                print(f"✅ Wajah '{nama}' berhasil didaftarkan untuk akses {allowed_door.upper()}!")
                print("Menyuruh server lokal untuk memuat ulang memori wajah...")
                try:
                    # Nembak API di server.py untuk refresh
                    response = requests.get("http://localhost:5000/reload_faces", timeout=5)
                    if response.status_code == 200:
                        print("✅ SERVER BERHASIL DI-REFRESH OTOMATIS!")
                    else:
                        print("⚠️ Server membalas dengan error.")
                except Exception as e:
                    print("⚠️ Gagal menghubungi server.py! Apakah server sedang menyala?")
                # ======================================================
            except Exception as e:
                print(f"❌ Error Database: {e}")
            finally:
                if 'cursor' in locals(): cursor.close()
                if 'conn' in locals(): conn.close()
            break
            
    elif key == ord('q'):
        print("Registrasi dibatalkan.")
        break

cap.release()
cv2.destroyAllWindows()