/*
  SERTOS ESP32 sensor prototype
  Reports two IR obstacle sensor readings to the authenticated SERTOS API.
  This sketch does not control traffic lamps.
*/
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "secrets.h"

constexpr uint8_t SENSOR_1_PIN = 25;
constexpr uint8_t SENSOR_2_PIN = 26;
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr uint32_t REPORT_INTERVAL_MS = 30000;

// Common LCD backpack address is 0x27; some boards use 0x3F.
LiquidCrystal_I2C lcd(0x27, 16, 2);
uint32_t lastReportAt = 0;

// HW-201/MH-B modules commonly pull OUT LOW on detection. Verify your boards.
bool detected(uint8_t pin) { return digitalRead(pin) == LOW; }

String endpoint(const char *path) {
  String base(API_BASE_URL);
  while (base.endsWith("/")) base.remove(base.length() - 1);
  return base + path;
}

void showReadings(bool first, bool second, const String &message) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("IR1:"); lcd.print(first ? "DETECT" : "clear");
  lcd.print(" IR2:"); lcd.print(second ? "D" : "-");
  lcd.setCursor(0, 1);
  lcd.print(message.substring(0, 16));
}

bool postJson(const char *path, const String &payload) {
  if (WiFi.status() != WL_CONNECTED) return false;
  WiFiClientSecure client;
  // Prototype convenience only. Validate the server certificate before production.
  client.setInsecure();
  HTTPClient http;
  if (!http.begin(client, endpoint(path))) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  int code = http.POST(payload);
  http.end();
  return code >= 200 && code < 300;
}

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_1_PIN, INPUT_PULLUP);
  pinMode(SENSOR_2_PIN, INPUT_PULLUP);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  lcd.init();
  lcd.backlight();
  showReadings(false, false, "Connecting WiFi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) delay(300);
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("ESP32 IP: "); Serial.println(WiFi.localIP());
    showReadings(false, false, "WiFi connected");
    lastReportAt = millis() - REPORT_INTERVAL_MS;
  } else {
    showReadings(false, false, "WiFi unavailable");
  }
}

void loop() {
  bool first = detected(SENSOR_1_PIN);
  bool second = detected(SENSOR_2_PIN);
  if (millis() - lastReportAt >= REPORT_INTERVAL_MS) {
    lastReportAt = millis();
    if (WiFi.status() != WL_CONNECTED) {
      WiFi.reconnect();
      showReadings(first, second, "WiFi disconnected");
    } else {
      String status = String("{\"firmware_version\":\"0.1.0\",\"wifi_rssi\":") +
        WiFi.RSSI() + ",\"operational_mode\":\"NORMAL\",\"sensor_1_detected\":" +
        (first ? "true" : "false") + ",\"sensor_2_detected\":" +
        (second ? "true" : "false") + "}";
      bool heartbeatOk = postJson("/api/traffic/esp32/heartbeat/", "{}");
      bool statusOk = postJson("/api/traffic/esp32/status/", status);
      Serial.printf("heartbeat=%s status=%s payload=%s\n",
        heartbeatOk ? "ok" : "failed", statusOk ? "ok" : "failed", status.c_str());
      showReadings(first, second, statusOk ? "Reported to API" : "API report failed");
    }
  } else {
    showReadings(first, second, WiFi.status() == WL_CONNECTED ? "SERTOS prototype" : "WiFi offline");
  }
  delay(1000);
}
