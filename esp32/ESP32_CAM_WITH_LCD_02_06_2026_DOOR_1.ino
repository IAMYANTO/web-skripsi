#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>

// ================= PETA PIN LCD =================
#define TFT_SCK  39
#define TFT_SDA  40
#define TFT_CS   41
#define TFT_DC   42
#define TFT_RST  47

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);
uint16_t* lcd_buffer; 

// ================= WIFI & SERVER =================
const char* ssid = "RISOL MAYO";
const char* password = "acaradimulaijam8pagi";
const char* serverUrl = "https://access-control-iot.vps.prakhya.id/check_face?door_id=door1";

// ================= SIGNAL PINS & UART =================
#define FACE_OK_PIN    21
#define RFID_DONE_PIN  14
#define UART_RX 3 
#define UART_TX 2 

bool faceSent = false;
enum CamState { SCANNING, WAIT_RFID_DONE, WAIT_FACE_CLEAR };
CamState camState = SCANNING;
int noFaceCounter = 0;
unsigned long rfidWaitStartTime = 0;

// ================= VARIABLES TIMER SENSOR IR =================
const unsigned long DURASI_TUNGGU = 20000; // ⏱️ Kamera mati 8 detik setelah area kosong
bool isKameraAktif = false;                // Status kamera (nyala/mati)
unsigned long waktuTerakhirTerdeteksi = 0; // Catatan waktu detak jantung IR
bool layarSudahMati = false;               // Pengaman biar LCD gak kedip-kedip

// Frame Skipping 
unsigned long waktuTerakhirUpload = 0;

// ================= FUNGSI UI (KOSMETIK LAYAR) =================
void showStatusLCD(String msg, uint16_t color) {
  tft.fillRect(0, 105, 160, 15, ST77XX_BLACK);
  tft.setTextColor(color);
  tft.setTextSize(1);
  tft.setCursor(5, 108);
  tft.print(msg);
}

void showBigText(String line1, String line2, uint16_t color) {
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(color);
  tft.setTextSize(2);
  tft.setCursor(10, 40);
  tft.print(line1);
  tft.setCursor(10, 70);
  tft.print(line2);
}

void drawPhotoToLCD(camera_fb_t *fb) {
  if (lcd_buffer == NULL) return;
  bool converted = jpg2rgb565(fb->buf, fb->len, (uint8_t *)lcd_buffer, JPG_SCALE_NONE);
  if (converted) {
    tft.drawRGBBitmap(0, 0, lcd_buffer, 160, 120);
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, UART_RX, UART_TX);
  delay(2000);

  Serial.println("\n[S3 CAM] MEMULAI SISTEM UTAMA..."); 

  SPI.begin(TFT_SCK, -1, TFT_SDA, TFT_CS);
  tft.initR(INITR_BLACKTAB); 
  tft.invertDisplay(false);  
  tft.setRotation(1); 
  tft.fillScreen(ST77XX_BLACK);
  
  lcd_buffer = (uint16_t*) ps_malloc(160 * 120 * 2);
  
  showBigText("MEMULAI", "SISTEM...", ST77XX_WHITE);

  pinMode(FACE_OK_PIN, OUTPUT);
  digitalWrite(FACE_OK_PIN, LOW);
  pinMode(RFID_DONE_PIN, INPUT_PULLDOWN);

  Serial.println("[S3 CAM] Menghubungkan ke WiFi..."); 
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  Serial.println("[S3 CAM] WiFi Terhubung!"); 
  showBigText("WIFI", "KONEK!", ST77XX_CYAN);
  delay(1000);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = 11; config.pin_d1 = 9; config.pin_d2 = 8;  config.pin_d3 = 10;
  config.pin_d4 = 12; config.pin_d5 = 18; config.pin_d6 = 17; config.pin_d7 = 16;
  config.pin_xclk = 15; config.pin_pclk = 13; config.pin_vsync = 6; config.pin_href = 7;
  config.pin_sccb_sda = 4; config.pin_sccb_scl = 5; config.pin_pwdn  = -1; config.pin_reset = -1;
  config.xclk_freq_hz = 10000000; 
  config.pixel_format = PIXFORMAT_JPEG; 
  config.frame_size = FRAMESIZE_QQVGA;
  config.jpeg_quality = 20;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  esp_camera_init(&config);
  Serial.println("[S3 CAM] Kamera Konfigurasi Sukses!"); 
  
  // Awal masuk langsung standby menunggu dipanggil IR
  Serial.println("[S3 CAM] 进入 STANDBY MODE - Menunggu Trigger IR...");
  showBigText("STANDBY", "MODE", ST77XX_CYAN);
  layarSudahMati = true;
}

void sendFaceOkPulse() {
  digitalWrite(FACE_OK_PIN, HIGH);
  delay(200);
  digitalWrite(FACE_OK_PIN, LOW);
}

void connectWiFi() {
  Serial.print("Connecting WiFi");
  showBigText("KONEKSI", "TERPUTUS!", ST77XX_RED);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
  showBigText("WIFI", "KONEK!", ST77XX_CYAN);
  delay(1000);
}

// ================= LOOP =================
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // ===== 1. TELINGA UNIVERSAL (MENERIMA PUSH DATA DARI RFID) =====
  while (Serial2.available()) { // TETAP PAKAI WHILE SEBAGAI VACUUM CLEANER
    String msg = Serial2.readStringUntil('\n');
    msg.trim();
    if (msg.length() == 0) continue;

    // --- LOGIKA PENCEGAT "WAKEUP" (PERSIS KAYA TESTING) ---
    if (msg == "WAKEUP") {
      waktuTerakhirTerdeteksi = millis(); // Reset waktu hitung mundur!
      if (!isKameraAktif) {
        Serial.println("\n🚀 [S3 CAM] IR MENDETEKSI OBJEK! KAMERA BANGUN!");
        isKameraAktif = true;
        layarSudahMati = false;
      }
      continue; // PENTING: Langsung sedot antrean berikutnya, jangan lanjut ke bawah
    }

    // --- JIKA BUKAN WAKEUP, PROSES SEBAGAI PESAN UI ---
    Serial.print("[📩 PESAN MASUK] Dari RFID: "); 
    Serial.println(msg);                          

    if (msg == "UI:REG") {
      showBigText("MODE", "REGISTRASI", ST77XX_YELLOW);
      delay(50);
      showBigText("MENUNGGU", "KARTU BARU", ST77XX_ORANGE);
      camState = WAIT_RFID_DONE; 
      rfidWaitStartTime = millis(); 
    } 
    else if (msg == "UI:PENDING") {
      showBigText("PENDING", "CEK WEB!", ST77XX_ORANGE);
      delay(50);
      showBigText("SELESAI", "KEMBALI...", ST77XX_YELLOW);
      camState = WAIT_FACE_CLEAR; 
      noFaceCounter = 0;
      delay(1000);
    }
    else if (msg == "UI:REG_OK") { 
      showBigText("AKTIVASI", "BERHASIL!", ST77XX_GREEN);
      delay(50); 
      showBigText("SELESAI", "KEMBALI...", ST77XX_YELLOW);
      camState = WAIT_FACE_CLEAR; 
      noFaceCounter = 0;
      delay(1000);
    }
    else if (msg == "UI:OPEN") {
      showBigText("PINTU", "DIBUKA", ST77XX_GREEN);
    } 
    else if (msg.startsWith("UI:FAIL")) {
      String attempt = msg.substring(8);
      showBigText("GAGAL TAP", attempt + "/3", ST77XX_RED);
      delay(1500);
      if (attempt != "3") showBigText("SILAKAN", "TAP KARTU", ST77XX_CYAN);
    }
    else if (msg == "UI:TIMEOUT") {
      showBigText("WAKTU HABIS!", "BATAL", ST77XX_RED);
      delay(50);
    }
  }

  // ===== 2. LOGIKA STATE =====
  
  // A. KONDISI LAGI NUNGGU RFID SELESAI
  if (camState == WAIT_RFID_DONE) {
    if (digitalRead(RFID_DONE_PIN) == HIGH) {
      Serial.println("[S3 CAM] RFID Selesai (Pin 14 HIGH), Mengunci..."); 
      faceSent = false;
      showBigText("SELESAI", "MENGUNCI...", ST77XX_YELLOW);
      camState = WAIT_FACE_CLEAR;
      noFaceCounter = 0;
      delay(1000);
    }
    else if (millis() - rfidWaitStartTime > 30000) { 
      Serial.println("[S3 CAM] ⏱️ TIMEOUT 30 Detik Tap Kartu!"); 
      faceSent = false;
      showBigText("TIMEOUT!", "KEMBALI", ST77XX_RED);
      delay(2000);
      camState = SCANNING;
    }
    return; 
  }

  // B. KONDISI MEMBERSIHKAN WAJAH LAMA
  if (camState == WAIT_FACE_CLEAR) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return;
    HTTPClient http; http.begin(serverUrl);
    http.addHeader("Content-Type", "application/octet-stream");
    int httpCode = http.POST(fb->buf, fb->len);
    if (httpCode > 0) {
      String payload = http.getString();
      if (payload.indexOf("NO_FACE") >= 0 || payload.indexOf("UNKNOWN") >= 0) noFaceCounter++;
      else noFaceCounter = 0;
      if (noFaceCounter >= 2) {
        Serial.println("[S3 CAM] Wajah bersih! Kembali ke SCANNING."); 
        camState = SCANNING;
      }
    }
    esp_camera_fb_return(fb); http.end();
    delay(300); return;
  }

// C. KONDISI NORMAL SCANNING (DIKERANGKENG OLEH TIMER SENSOR IR)
  if (camState == SCANNING) {
    
    if (isKameraAktif) { // 🟢 KAMERA JALAN KALAU IR WAKEUP AKTIF
      
      unsigned long waktuSekarang = millis();
      
      // Deteksi Timeout: Apakah orangnya sudah pergi selama 8 detik?
      if (waktuSekarang - waktuTerakhirTerdeteksi >= DURASI_TUNGGU) {
        Serial.println("\n⏱️ [S3 CAM] Sudah 8 detik sepi. Kamera masuk mode STANDBY.");
        isKameraAktif = false;
      } else {
        
        // --- 1. JALANIN TUGAS JEPRET & LCD (SECEPAT KILAT TANPA DELAY) ---
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) return;

        drawPhotoToLCD(fb);
        showStatusLCD("MENUNGGU WAJAH", ST77XX_WHITE);

        // --- 2. LOGIKA FRAME SKIPPING (KIRIM SERVER TIAP 1.5 DETIK SAJA) ---
        if (waktuSekarang - waktuTerakhirUpload >= 1500) { 
          
          HTTPClient http; http.begin(serverUrl);
          http.addHeader("Content-Type", "application/octet-stream");
          int httpCode = http.POST(fb->buf, fb->len);

          if (httpCode > 0) {
            String payload = http.getString();
            
            Serial.println("\n----------------------------------");
            Serial.print("📡 BALASAN SERVER: ");
            Serial.println(payload);

            if (payload.indexOf("NO_FACE") >= 0) {
              Serial.println("❌ STATUS: WAJAH TIDAK DITEMUKAN (NO FACE)");
            } 
            else if (payload.indexOf("UNKNOWN") >= 0) {
              Serial.println("⛔ STATUS: WAJAH TIDAK DIKENAL (PENYUSUP)");
            } 
            else if (payload.indexOf("FACE_OK") >= 0 && !faceSent) {
              Serial.println("✅ STATUS: WAJAH DIKENAL! (FACE_OK)");
            }
            Serial.println("----------------------------------\n");

            if (payload.indexOf("FACE_OK") >= 0 && !faceSent) {
              faceSent = true;
              String name = "Unknown";
              int nameIndex = payload.indexOf("name");
              if (nameIndex >= 0) {
                int start = payload.indexOf(":", nameIndex) + 2;
                int end = payload.indexOf("\"", start);
                name = payload.substring(start, end);
              }
              
              Serial.print("👤 NAMA USER: "); 
              Serial.println(name);           
              
              showBigText("USER:", name, ST77XX_GREEN);
              delay(2000);
              showBigText("SILAKAN", "TAP KARTU", ST77XX_CYAN);

              Serial2.print("NAME:"); Serial2.println(name);
              delay(200); 
              sendFaceOkPulse();
              camState = WAIT_RFID_DONE;
              rfidWaitStartTime = millis();
            } else if (payload.indexOf("UNKNOWN") >= 0) {
              showBigText("WAJAH", "DITOLAK!", ST77XX_RED);
              delay(1000);
            } 
          }
          http.end();
          
          // Reset timer upload setelah selesai ngirim ke server
          waktuTerakhirUpload = millis(); 
        }

        esp_camera_fb_return(fb); 
        
        // --- 3. SEDOT SISA KATA 'W' DI SERIAL BIAR GAK LAG ---
        while (Serial2.available()) {
          char c = Serial2.read();
          if (c == 'W') waktuTerakhirTerdeteksi = millis(); // Reset waktu sensor IR
        }
        
        // 🚨 PERHATIKAN: TIDAK ADA LAGI delay(500) DI SINI! LOOP AKAN MUTER NGEBUT!
      }

    } else { 
      // 🔴 KAMERA MATI (MODE HEMAT ENERGI / STANDBY)
      if (!layarSudahMati) {
        showBigText("STANDBY", "MODE", ST77XX_CYAN);
        layarSudahMati = true;
      }
      delay(200); // Istirahat processor biar ga panas
    }
  }
}