# Smart Door System - Microservices Architecture

Sistem Smart Door berbasis AI Face Recognition dan RFID menggunakan arsitektur Microservices yang dikemas dalam Docker.

## 📂 Struktur Project

| File / Folder | Peran | Deskripsi |
| :--- | :--- | :--- |
| `templates/` | **Frontend** | Berisi file HTML (Jinja2) untuk interface dashboard web. |
| `app.py` | **Web Backend** | Main server untuk dashboard, manajemen user, dan log akses. |
| `server.py` | **Access Control** | Service AI untuk validasi Wajah dan RFID. Bertindak sebagai Gatekeeper. |
| `tambah_wajah.py`| **Service Registrasi** | Tool interaktif untuk mengambil sampel wajah dan menyimpannya ke database. |
| `Dockerfile.*` | **Container Config** | Konfigurasi isolasi environment untuk masing-masing service. |
| `docker-compose.yml`| **Orchestrator** | Menjalankan seluruh sistem dalam satu command. |

---

## ⚙️ Alur Kerja (Workflow)

### 1. Registrasi User
1. Admin membuka `tambah_wajah.py` (melalui service `face-registration`).
2. Kamera akan aktif, user memosisikan wajah, dan menekan tombol 'S'.
3. Sistem menghitung *Face Encoding* (matriks wajah) dan menyimpannya ke MySQL (Clever Cloud) beserta hak akses pintu.
4. Service akan otomatis memicu `server.py` untuk me-reload memori wajah dari database.

### 2. Proses Masuk (Face Recognition)
1. ESP32-S3 CAM mengirimkan gambar ke endpoint `server.py` (`/check_face`).
2. `server.py` mencocokkan wajah dengan database lokal (RAM).
3. Jika wajah dikenal dan memiliki hak akses pada `door_id` tersebut, server mengembalikan `FACE_OK`.
4. Log akses akan tercatat secara otomatis ke database.

### 3. Proses Masuk (RFID)
1. ESP32 RFID mengirimkan UID kartu ke `server.py` (`/check_rfid`).
2. Server mengecek validitas kartu dan izin pintu.
3. Jika kartu terdaftar dan sesuai pintu, akses diberikan (`VALID`).

### 4. Monitoring & Management
1. Admin mengakses Dashboard melalui `app.py` (Port 5000).
2. Admin bisa melihat log real-time, membuka pintu jarak jauh (Remote Bypass), dan mengelola data user/admin.

---

## 🚀 Cara Menjalankan

### Prasyarat
- Docker & Docker Compose terinstall.
- Koneksi Internet (untuk database Clever Cloud).

### Menjalankan Seluruh Sistem
```bash
docker-compose up --build
```

### Akses
- **Dashboard Web**: `http://localhost:5000`
- **Access Control API**: `http://localhost:5001`

---

## 🛠️ Catatan Penting
- **Database**: Project ini menggunakan MySQL di Clever Cloud. Pastikan kredensial di dalam file `.py` sudah benar.
- **Hardware**: ESP32 harus diarahkan ke IP Host/Server yang menjalankan Docker ini pada port 5001.
