#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h> 
#include <esp_task_wdt.h>
#include "DFRobotDFPlayerMini.h" // 🚨 TAMBAHAN: Library MP3

#define SCK_PIN       12
#define MISO_PIN      13
#define MOSI_PIN      11
#define SS_PIN        10
#define RST_PIN       9

#define PIN_RELAY     4
#define RFID_DONE_PIN 5
#define BUZZER_PIN    6
#define PIN_IR        7

#define UART_RX       17
#define UART_TX       18
#define MP3_RX        15
#define MP3_TX        16

#define MAX_FAILED    3
#define COOLDOWN_TIME 5000
String currentUser = "unknown";

// --- TIMER SENSOR IR & RFID ---
unsigned long waktuKirimWakeup = 0;
unsigned long rfidWaitStartTime = 0; 

// ===== WIFI & SERVER (KEMBALI KE ASLI) =====
const char* ssid = "RISOL MAYO";
const char* password = "acaradimulaijam8pagi";

const char* localServerURL = "https://access-control-iot.vps.prakhya.id/check_rfid"; 
const char* activateURL = "https://access-control-iot.vps.prakhya.id/activate_admin"; 
const char* logURL = "https://iot.vps.prakhya.id/log_access";
const char* bypassURL = "https://iot.vps.prakhya.id/check_bypass_status?door_id=door1";

MFRC522 rfid(SS_PIN, RST_PIN);
WiFiClientSecure secureClient;

// 🚨 TAMBAHAN: Objek untuk modul MP3
DFRobotDFPlayerMini myDFPlayer;

enum State {
  WAIT_FACE,
  WAIT_RFID,
  REGISTER_MODE, 
  COOLDOWN
};

State systemState = WAIT_FACE;
unsigned long stateUntil = 0;
unsigned long registerTimeout = 0;
int failedAttempts = 0;

unsigned long relayOpenTime = 0;
bool isRelayOpen = false;

void beepSuccess() {
  digitalWrite(BUZZER_PIN, HIGH); delay(100);
  digitalWrite(BUZZER_PIN, LOW); delay(100);
  digitalWrite(BUZZER_PIN, HIGH); delay(100);
  digitalWrite(BUZZER_PIN, LOW);
}

void beepFail() {
  digitalWrite(BUZZER_PIN, HIGH); delay(700);
  digitalWrite(BUZZER_PIN, LOW);
}

void beepRegisterMode() {
  digitalWrite(BUZZER_PIN, HIGH); delay(50);
  digitalWrite(BUZZER_PIN, LOW); delay(50);
  digitalWrite(BUZZER_PIN, HIGH); delay(50);
  digitalWrite(BUZZER_PIN, LOW);
}

void sendRfidDonePulse() {
  digitalWrite(RFID_DONE_PIN, HIGH); delay(200);
  digitalWrite(RFID_DONE_PIN, LOW);
}

// ===== 1. FUNGSI CEK NAMA (WAJIB PAKAI SECURECLIENT) =====
String getValidNameFromServer(String uidString) {
  if (WiFi.status() != WL_CONNECTED) return "unknown";
  HTTPClient http;
  
  // 🚨 ILMU HITAM: Wajib bawa secureClient agar RAM tidak bocor!
  http.begin(secureClient, localServerURL); 
  http.setTimeout(4000); 
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<200> doc; doc["uid"] = uidString; doc["door_id"] = "door1"; 
  String requestBody; serializeJson(doc, requestBody);
  int httpCode = http.POST(requestBody);
  String resultName = "unknown";

  if (httpCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<200> responseDoc; deserializeJson(responseDoc, payload);
    if (responseDoc["status"] == "VALID") resultName = responseDoc["name"].as<String>();
  }
  http.end(); return resultName;
}

// ===== 2. FUNGSI AKTIVASI KARTU (WAJIB PAKAI SECURECLIENT) =====
bool activateNewCardOnServer(String newUid) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  
  // 🚨 ILMU HITAM: Wajib bawa secureClient
  http.begin(secureClient, activateURL); 
  http.setTimeout(4000); 
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<200> doc; doc["new_uid"] = newUid;
  String requestBody; serializeJson(doc, requestBody);
  int httpCode = http.POST(requestBody);
  bool isSuccess = false;
  
  if (httpCode == 200) {
    String payload = http.getString();
    if (payload.indexOf("\"SUCCESS\"") >= 0) isSuccess = true;
  }
  http.end(); return isSuccess;
}

// ===== 3. FUNGSI KIRIM LOG (TAMBAH REUSE RAM) =====
void sendAccessLog(String name, String cardUID, String method, String status) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  
  http.setReuse(true); // 🚨 HEMAT RAM: Gunakan koneksi lama, jangan bikin baru!
  http.begin(secureClient, logURL); 
  http.setTimeout(4000);
  http.addHeader("Content-Type", "application/json");
  
  StaticJsonDocument<200> doc;
  doc["door_id"] = "door1"; doc["name"] = name; doc["card_uid"] = cardUID; doc["method"] = method; doc["status"] = status;
  String jsonStr; serializeJson(doc, jsonStr);
  http.POST(jsonStr); http.end();
}

void setup() {
  Serial.begin(115200);
  
  // 🚨 KASIH WAKTU 2 DETIK BUAT LAPTOP NGEBUKA SERIAL MONITOR!
  delay(2000); 
  Serial.println("\n\n===================================");
  Serial.println("🚀 [SYSTEM] MEMULAI PROSES BOOTING...");
  Serial.println("===================================");

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RFID_DONE_PIN, OUTPUT);
  digitalWrite(RFID_DONE_PIN, LOW);
  
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, HIGH);
  pinMode(PIN_IR, INPUT);

  Serial.println("📡 [SYSTEM] Setup Serial Kamera & MP3...");
  Serial2.begin(115200, SERIAL_8N1, UART_RX, UART_TX);
  Serial2.setTimeout(50); 
  Serial1.begin(9600, SERIAL_8N1, MP3_RX, MP3_TX);

  // 🚨 JEBAKAN WIFI KITA BIKIN CEREWET!
  Serial.println("🌐 [SYSTEM] Mencari WiFi RISOL MAYO...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { 
    delay(500); 
    Serial.print("."); // Biar kelihatan dia lagi mikir!
  }
  Serial.println("\n✅ [SYSTEM] WiFi Terhubung!");

  secureClient.setInsecure(); 

  // 🚨 JEBAKAN RFID KITA PANTAU
  Serial.println("🔍 [SYSTEM] Inisialisasi Pin SPI & RFID...");
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);
  rfid.PCD_Init();
  Serial.println("✅ [SYSTEM] RFID Selesai di-Init (Hardware dicolok/tidak)");
  
  Serial.println("🌟 RFID, IR & WIFI READY. ANTI-LEAK SYSTEM ON!");
  
  Serial.println("🎵 [SYSTEM] Menghubungkan ke Modul MP3...");
  delay(3000); 
  if (myDFPlayer.begin(Serial1, false)) { 
    Serial.println("✅ MP3 Siap!");
    myDFPlayer.volume(25);
    delay(500);
    myDFPlayer.playMp3Folder(5); 
  } else {
    Serial.println("❌ MP3 Tidak Terdeteksi!");
  }

  esp_task_wdt_init(45, true); 
  esp_task_wdt_add(NULL);
  
  Serial.println("▶️ [SYSTEM] MASUK KE LOOP UTAMA...");
}

void loop() {
  esp_task_wdt_reset();
  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi Terputus! Mencoba menyambung kembali...");
    WiFi.disconnect();
    WiFi.reconnect();

    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 5000) {
      esp_task_wdt_reset(); 
      delay(500);
      Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\n✅ WiFi Berhasil Tersambung Kembali!");
    } else {
      Serial.println("\n❌ Gagal Nyambung. Lanjut loop...");
    }
  }

  // ========================================================
  // 1. LOGIKA WAKE-UP SENSOR IR
  // ========================================================
  int statusIR = digitalRead(PIN_IR); 
  if (statusIR == LOW) { 
    if (now - waktuKirimWakeup > 500) { 
      Serial2.println("WAKEUP"); 
      waktuKirimWakeup = now;
    }
  }

  // ========================================================
  // 2. CEK BYPASS DARI WEB (Setiap 5 Detik)
  // ========================================================
  static unsigned long lastBypassCheck = 0;
  if (systemState == WAIT_FACE && now - lastBypassCheck > 5000 && WiFi.status() == WL_CONNECTED) {
    lastBypassCheck = now;
    HTTPClient http;

    http.setReuse(true);
    http.begin(secureClient, bypassURL); 
    http.setTimeout(3000);
    if (http.GET() == 200) {
      String payload = http.getString();
      if (payload.indexOf("\"OPEN\"") >= 0) {
        Serial.println("BYPASS WEB DITERIMA!");
        myDFPlayer.playMp3Folder(3); // 🚨 TAMBAHAN MP3: Suara Pintu Dibuka Web
        sendAccessLog("ADMIN (REMOTE)", "WEB-BTN", "BYPASS", "ACCESS_GRANTED");
        beepSuccess();
        sendRfidDonePulse();
        digitalWrite(PIN_RELAY, LOW);
        isRelayOpen = true; relayOpenTime = now;
        systemState = COOLDOWN; stateUntil = now + COOLDOWN_TIME;
      }
    }
    http.end();
  }

  // ========================================================
  // 3. TERIMA NAMA DARI CAM VIA UART
  // ========================================================
  if (Serial2.available()) {
    String data = Serial2.readStringUntil('\n');
    data.trim();
    if (data.startsWith("NAME:") && systemState == WAIT_FACE) {
      currentUser = data.substring(5);
      currentUser.trim();
      Serial.println("FACE OK -> WAIT RFID: " + currentUser);
      failedAttempts = 0;
      systemState = WAIT_RFID;
      
      rfidWaitStartTime = now; 
      rfid.PCD_Init();         
      
      beepSuccess(); 
    }
  }

  // ========================================================
  // 4. BACA KARTU RFID
  // ========================================================
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String rawUid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
      if (rfid.uid.uidByte[i] < 0x10) rawUid += "0"; 
      rawUid += String(rfid.uid.uidByte[i], HEX);
    }
    rawUid.toUpperCase(); 
    rfid.PICC_HaltA(); 
    
    Serial.println("KARTU DI-TAP: " + rawUid);

    // --- MODE REGISTRASI ---
    if (systemState == REGISTER_MODE) {
      Serial.println("MENCOBA AKTIVASI AKUN PENDING DENGAN KARTU INI...");
      if (activateNewCardOnServer(rawUid)) {
        Serial.println("AKTIVASI BERHASIL!");
        Serial2.println("UI:REG_OK"); 
        beepSuccess(); delay(200); beepSuccess();
      } else {
        Serial.println("AKTIVASI GAGAL (TIDAK ADA AKUN PENDING / SERVER DOWN).");
        Serial2.println("UI:PENDING"); 
        beepFail();
      }
      systemState = WAIT_FACE; 
      rfid.PCD_Init();
      return;
    }

    // --- HARDWARE MASTER KEY ---
    if (rawUid == "04355E1A5A1890") {
      Serial.println("HARDWARE MASTER CARD DETECTED! MEMBUKA PINTU & MASUK MODE REGISTRASI.");
      sendAccessLog("MASTER (HARDWARE)", rawUid, "RFID_ONLY", "ACCESS_GRANTED");
      beepRegisterMode(); 
      sendRfidDonePulse();
      systemState = REGISTER_MODE;
      Serial2.println("UI:REG");
      registerTimeout = now + 10000; 
      return;
    }

    // --- CEK KARTU KE SERVER (MODE NORMAL) ---
    if (systemState == WAIT_RFID) {
      String cardName = getValidNameFromServer(rawUid);
      
      if (currentUser.equalsIgnoreCase(cardName) && cardName != "unknown") {
        Serial.println("MULTI-AUTH BERHASIL!");
        Serial.println("[RFID] 🔓 AKSES DITERIMA! Membuka Kunci Pintu...");
        Serial2.println("UI:OPEN");
        
        myDFPlayer.playMp3Folder(1); // 🚨 TAMBAHAN MP3: Akses Diterima
        
        digitalWrite(PIN_RELAY, LOW);
        isRelayOpen = true;
        relayOpenTime = millis();

        Serial.println("[RELAY] 🔴 CETEK! Saklar ON");
        sendAccessLog(currentUser, rawUid, "FACE+RFID", "ACCESS_GRANTED");
        beepSuccess();
        sendRfidDonePulse();
        systemState = COOLDOWN;
        stateUntil = now + COOLDOWN_TIME;
      } else {
        failedAttempts++;
        Serial.println("KARTU DITOLAK ATAU SERVER DOWN!");
        
        myDFPlayer.playMp3Folder(2); // 🚨 TAMBAHAN MP3: Akses Ditolak
        
        Serial2.print("UI:FAIL,"); 
        Serial2.println(failedAttempts);
        sendAccessLog(currentUser, rawUid, "FACE+RFID", "ACCESS_DENIED");
        beepFail();
        if (failedAttempts >= 3) {
          sendRfidDonePulse();
          systemState = COOLDOWN;
          stateUntil = now + COOLDOWN_TIME;
        }
      }
    } 
    else if (systemState == WAIT_FACE) {
      Serial.println("TOLAK: Harap scan wajah terlebih dahulu!");
      myDFPlayer.playMp3Folder(2); // 🚨 TAMBAHAN MP3: Akses Ditolak Wajah Belum Scan
      beepFail();
      rfid.PCD_Init();
    }
  }

  // ========================================================
  // 5. TIMEOUT & COOLDOWN LOGIC
  // ========================================================
  
  if (systemState == REGISTER_MODE && now > registerTimeout) {
    Serial.println("MODE REGISTRASI TIMEOUT. KEMBALI NORMAL.");
    sendRfidDonePulse(); 
    Serial2.println("UI:TIMEOUT");
    beepFail(); 
    systemState = WAIT_FACE;
  }

  if (systemState == WAIT_RFID && now - rfidWaitStartTime > 30000) {
    Serial.println("⏱️ TIMEOUT! 30 Detik tidak ada kartu di-tap. Kembali ke STANDBY.");
    myDFPlayer.playMp3Folder(2); // 🚨 TAMBAHAN MP3: Akses Ditolak Kelamaan Nunggu
    sendRfidDonePulse(); 
    Serial2.println("UI:TIMEOUT");
    beepFail();
    systemState = WAIT_FACE; 
    currentUser = "unknown";
  }

  // 🚨 PENUTUP PINTU OTOMATIS NON-BLOCKING (Tanpa Delay)
  if (isRelayOpen && (millis() - relayOpenTime >= 4000)) {
      digitalWrite(PIN_RELAY, HIGH); // Kunci lagi
      isRelayOpen = false;
      Serial.println("[RELAY] 🟢 Waktu habis. Saklar OFF (Mengunci Kembali)");
  }

  if (systemState == COOLDOWN && now >= stateUntil) {
    systemState = WAIT_FACE;
    currentUser = "unknown";
    Serial.println("SISTEM SIAP ULANG");
  }
}