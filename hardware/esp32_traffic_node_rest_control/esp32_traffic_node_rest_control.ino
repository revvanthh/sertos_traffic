/*
 * SERTOS ESP32 REST bench controller
 *
 * Drives low-voltage indicator LEDs only. It is not a certified traffic
 * controller and must never be connected to public-road signal equipment.
 */
#include <Arduino.h>
#include <ArduinoJson.h>  // ArduinoJson 6.x
#include <HTTPClient.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <time.h>

#include "secrets.h"

constexpr uint8_t RED_LED_PIN = 25;
constexpr uint8_t YELLOW_LED_PIN = 26;
constexpr uint8_t GREEN_LED_PIN = 27;
constexpr uint8_t ENTRY_IR_PIN = 32;
constexpr uint8_t EXIT_IR_PIN = 33;
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr uint32_t SENSOR_SAMPLE_INTERVAL_MS = 10;
constexpr uint32_t LCD_REFRESH_INTERVAL_MS = 500;
constexpr uint32_t CONFIG_RETRY_INTERVAL_MS = 15000;
constexpr uint32_t CONFIG_REFRESH_INTERVAL_MS = 300000;
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 10000;
constexpr size_t COMMAND_QUEUE_LENGTH = 8;
constexpr size_t RESULT_QUEUE_LENGTH = 8;

LiquidCrystal_I2C lcd(0x27, 16, 2);

enum ControlMode : uint8_t {
  MODE_NORMAL,
  MODE_EMERGENCY_PREP,
  MODE_EMERGENCY_GREEN,
  MODE_EMERGENCY_RESET,
};

enum SignalPhase : uint8_t {
  PHASE_RED,
  PHASE_YELLOW,
  PHASE_GREEN,
  PHASE_ALL_RED,
  PHASE_FAULT,
};

enum CommandAction : uint8_t {
  ACTION_PREPARE_GREEN,
  ACTION_EXTEND_GREEN,
  ACTION_RESTORE_NORMAL,
};

struct DeviceConfig {
  uint32_t heartbeatSeconds;
  uint32_t commandPollSeconds;
  uint32_t minGreenSeconds;
  uint32_t yellowSeconds;
  uint32_t allRedSeconds;
  uint32_t maxPreemptionSeconds;
  uint32_t failsafeSeconds;
};

struct PendingCommand {
  char id[40];
  CommandAction action;
  time_t expiresAt;
  uint32_t minGreenSeconds;
  uint32_t yellowSeconds;
  uint32_t allRedSeconds;
  uint32_t maxPreemptionSeconds;
  uint32_t failsafeSeconds;
};

struct CommandResult {
  char id[40];
  char status[16];
  char notes[240];
  char failureReason[240];
};

struct TelemetrySnapshot {
  bool entryDetected;
  bool exitDetected;
  bool preempted;
  SignalPhase phase;
  ControlMode mode;
  uint32_t phaseElapsedSeconds;
  int wifiRssi;
  bool wifiConnected;
};

QueueHandle_t commandQueue = nullptr;
QueueHandle_t resultQueue = nullptr;
portMUX_TYPE telemetryMux = portMUX_INITIALIZER_UNLOCKED;
portMUX_TYPE configMux = portMUX_INITIALIZER_UNLOCKED;
TelemetrySnapshot telemetrySnapshot = {};

DeviceConfig deviceConfig = {};
ControlMode controlMode = MODE_NORMAL;
SignalPhase signalPhase = PHASE_RED;
bool entryDetected = false;
bool exitDetected = false;
bool configReady = false;
volatile bool transportConfigured = false;
bool queuesReady = false;
bool hasActiveAcknowledgement = false;
bool emergencyHoldActive = false;
PendingCommand activeAcknowledgement = {};

uint32_t phaseStartedAt = 0;
uint32_t greenStartedAt = 0;
uint32_t activeGreenHoldSeconds = 0;
uint32_t lastSensorSampleAt = 0;
uint32_t lastLcdRefreshAt = 0;
uint32_t lastConfigRequestAt = 0;
uint32_t lastHeartbeatAt = 0;
uint32_t lastStatusAt = 0;
uint32_t lastCommandPollAt = 0;
String apiBase;

bool detected(uint8_t pin) {
  // Supplied IR boards are active LOW. A detection means an obstacle only.
  return digitalRead(pin) == LOW;
}

const char *phaseName(SignalPhase phase) {
  switch (phase) {
    case PHASE_RED: return "RED";
    case PHASE_YELLOW: return "YELLOW";
    case PHASE_GREEN: return "GREEN";
    case PHASE_ALL_RED: return "ALL_RED";
    default: return "FAULT";
  }
}

const char *modeDisplay(ControlMode mode) {
  switch (mode) {
    case MODE_EMERGENCY_PREP: return "EMERGENCY PREP";
    case MODE_EMERGENCY_GREEN: return "EMERGENCY GREEN";
    case MODE_EMERGENCY_RESET: return "EMERGENCY RESET";
    default: return "NORMAL";
  }
}

void storeDeviceConfig(const DeviceConfig &config) {
  portENTER_CRITICAL(&configMux);
  deviceConfig = config;
  portEXIT_CRITICAL(&configMux);
}

DeviceConfig readDeviceConfig() {
  DeviceConfig copy;
  portENTER_CRITICAL(&configMux);
  copy = deviceConfig;
  portEXIT_CRITICAL(&configMux);
  return copy;
}

void setPhase(SignalPhase next) {
  signalPhase = next;
  phaseStartedAt = millis();
  digitalWrite(RED_LED_PIN, next == PHASE_RED ? HIGH : LOW);
  digitalWrite(YELLOW_LED_PIN, next == PHASE_YELLOW ? HIGH : LOW);
  digitalWrite(GREEN_LED_PIN, next == PHASE_GREEN ? HIGH : LOW);
}

void publishTelemetrySnapshot() {
  const bool wifiConnected = WiFi.status() == WL_CONNECTED;
  const int wifiRssi = wifiConnected ? WiFi.RSSI() : 0;
  portENTER_CRITICAL(&telemetryMux);
  telemetrySnapshot.entryDetected = entryDetected;
  telemetrySnapshot.exitDetected = exitDetected;
  telemetrySnapshot.preempted = controlMode != MODE_NORMAL;
  telemetrySnapshot.phase = signalPhase;
  telemetrySnapshot.mode = controlMode;
  telemetrySnapshot.phaseElapsedSeconds = (millis() - phaseStartedAt) / 1000;
  telemetrySnapshot.wifiConnected = wifiConnected;
  telemetrySnapshot.wifiRssi = wifiRssi;
  portEXIT_CRITICAL(&telemetryMux);
}

TelemetrySnapshot readTelemetrySnapshot() {
  TelemetrySnapshot copy;
  portENTER_CRITICAL(&telemetryMux);
  copy = telemetrySnapshot;
  portEXIT_CRITICAL(&telemetryMux);
  return copy;
}

void refreshLcd() {
  const uint32_t now = millis();
  if (now - lastLcdRefreshAt < LCD_REFRESH_INTERVAL_MS) return;
  lastLcdRefreshAt = now;

  lcd.setCursor(0, 0);
  lcd.print("                ");
  lcd.setCursor(0, 0);
  String top = String(modeDisplay(controlMode));
  lcd.print(top.substring(0, 16));

  lcd.setCursor(0, 1);
  lcd.print("                ");
  lcd.setCursor(0, 1);
  String bottom = String("E:") + (entryDetected ? "OBS" : "CLR") +
    " X:" + (exitDetected ? "OBS" : "CLR") +
    (WiFi.status() == WL_CONNECTED ? " ON" : " OFF");
  lcd.print(bottom.substring(0, 16));
}

bool looksConfigured(const char *value) {
  if (!value || strlen(value) < 3) return false;
  return strstr(value, "YOUR_") == nullptr &&
    strstr(value, "PASTE_") == nullptr &&
    strstr(value, "CHANGE_ME") == nullptr &&
    strstr(value, "SET_AFTER") == nullptr;
}

bool credentialsReady() {
  return looksConfigured(WIFI_SSID) &&
    looksConfigured(WIFI_PASSWORD) &&
    looksConfigured(DEVICE_ID) &&
    looksConfigured(DEVICE_TOKEN) &&
    strlen(API_ROOT_CA) > 500 &&
    apiBase.startsWith("https://");
}

String endpoint(const char *path) {
  String url = apiBase;
  while (url.endsWith("/")) url.remove(url.length() - 1);
  return url + path;
}

int authenticatedRequest(const char *method, const String &path,
                         const String &payload, String &responseBody) {
  if (!transportConfigured || WiFi.status() != WL_CONNECTED) return -1;

  WiFiClientSecure client;
  client.setCACert(API_ROOT_CA);
  HTTPClient http;
  http.setTimeout(5000);
  if (!http.begin(client, endpoint(path.c_str()))) return -2;

  http.addHeader("Accept", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  int statusCode = -3;
  if (strcmp(method, "GET") == 0) {
    statusCode = http.GET();
  } else {
    http.addHeader("Content-Type", "application/json");
    statusCode = http.POST(payload);
  }

  if (statusCode > 0) responseBody = http.getString();
  http.end();
  return statusCode;
}

bool parseUtcTimestamp(const char *value, time_t &result) {
  int year, month, day, hour, minute, second;
  if (!value || sscanf(value, "%d-%d-%dT%d:%d:%d", &year, &month, &day, &hour, &minute, &second) != 6) {
    return false;
  }

  struct tm parsed = {};
  parsed.tm_year = year - 1900;
  parsed.tm_mon = month - 1;
  parsed.tm_mday = day;
  parsed.tm_hour = hour;
  parsed.tm_min = minute;
  parsed.tm_sec = second;
  setenv("TZ", "UTC0", 1);
  tzset();
  result = mktime(&parsed);
  return result > 0;
}

bool clockIsSynchronized() {
  return time(nullptr) > 1700000000;
}

bool validInterval(uint32_t value, uint32_t minValue, uint32_t maxValue) {
  return value >= minValue && value <= maxValue;
}

bool fetchConfiguration() {
  String body;
  const int code = authenticatedRequest("GET", "/api/traffic/esp32/config/", "", body);
  if (code != 200) {
    Serial.printf("Configuration request failed (HTTP %d).\n", code);
    return false;
  }

  StaticJsonDocument<1536> document;
  if (deserializeJson(document, body)) {
    Serial.println("Configuration response was not valid JSON.");
    return false;
  }

  DeviceConfig next = {
    document["heartbeat_interval_seconds"] | 0U,
    document["command_poll_interval_seconds"] | 0U,
    document["safety_min_green_seconds"] | 0U,
    document["safety_yellow_seconds"] | 0U,
    document["safety_all_red_seconds"] | 0U,
    document["max_preemption_seconds"] | 0U,
    document["failsafe_reversion_timeout_seconds"] | 0U,
  };

  if (!validInterval(next.heartbeatSeconds, 5, 3600) ||
      !validInterval(next.commandPollSeconds, 1, 120) ||
      !validInterval(next.minGreenSeconds, 1, 300) ||
      !validInterval(next.yellowSeconds, 1, 60) ||
      !validInterval(next.allRedSeconds, 1, 30) ||
      !validInterval(next.maxPreemptionSeconds, next.minGreenSeconds, 600) ||
      !validInterval(next.failsafeSeconds, next.minGreenSeconds, 3600)) {
    Serial.println("Configuration timing values were missing or outside safe local bounds.");
    return false;
  }

  storeDeviceConfig(next);
  configReady = true;
  Serial.printf("Configuration loaded: heartbeat=%lus poll=%lus yellow=%lus all-red=%lus.\n",
    (unsigned long)deviceConfig.heartbeatSeconds,
    (unsigned long)deviceConfig.commandPollSeconds,
    (unsigned long)deviceConfig.yellowSeconds,
    (unsigned long)deviceConfig.allRedSeconds);
  return true;
}

bool readSafetyValue(JsonObjectConst source, const char *key,
                     uint32_t fallback, uint32_t minValue,
                     uint32_t maxValue, uint32_t &out) {
  if (!source.containsKey(key)) {
    out = fallback;
    return validInterval(out, minValue, maxValue);
  }
  if (!source[key].is<uint32_t>()) return false;
  out = source[key].as<uint32_t>();
  return validInterval(out, minValue, maxValue);
}

bool parsePendingCommand(JsonObjectConst json, PendingCommand &command,
                         String &failure) {
  const char *id = json["id"] | "";
  const char *action = json["action"] | "";
  const char *status = json["status"] | "";
  const char *expires = json["expires_at"] | "";
  if (strlen(id) < 32 || strlen(id) >= sizeof(command.id)) {
    failure = "Command ID is missing or malformed.";
    return false;
  }
  if (strcmp(status, "PENDING") != 0) return false;

  if (strcmp(action, "PREPARE_GREEN_CORRIDOR") == 0) command.action = ACTION_PREPARE_GREEN;
  else if (strcmp(action, "EXTEND_GREEN") == 0) command.action = ACTION_EXTEND_GREEN;
  else if (strcmp(action, "RESTORE_NORMAL_CYCLE") == 0) command.action = ACTION_RESTORE_NORMAL;
  else {
    failure = "Unsupported traffic command action.";
    strlcpy(command.id, id, sizeof(command.id));
    return false;
  }

  strlcpy(command.id, id, sizeof(command.id));
  if (!parseUtcTimestamp(expires, command.expiresAt)) {
    failure = "Command expiry could not be validated against synchronized UTC time.";
    return false;
  }
  if (command.expiresAt <= time(nullptr)) {
    failure = "Command expired before the ESP32 received it.";
    return false;
  }

  const DeviceConfig config = readDeviceConfig();
  JsonObjectConst safety = json["safety_constraints"].as<JsonObjectConst>();
  if (!readSafetyValue(safety, "min_green_seconds", config.minGreenSeconds, 1, 300, command.minGreenSeconds) ||
      !readSafetyValue(safety, "min_yellow_seconds", config.yellowSeconds, 1, 60, command.yellowSeconds) ||
      !readSafetyValue(safety, "min_all_red_seconds", config.allRedSeconds, 1, 30, command.allRedSeconds) ||
      !readSafetyValue(safety, "max_preemption_seconds", config.maxPreemptionSeconds, command.minGreenSeconds, 600, command.maxPreemptionSeconds)) {
    failure = "Command safety timing values are missing or outside local limits.";
    return false;
  }
  command.failsafeSeconds = config.failsafeSeconds;
  return true;
}

bool sendCommandResult(const CommandResult &result) {
  StaticJsonDocument<768> document;
  document["status"] = result.status;
  if (result.notes[0]) document["execution_notes"] = result.notes;
  if (result.failureReason[0]) document["failure_reason"] = result.failureReason;
  String payload;
  serializeJson(document, payload);
  String path = String("/api/traffic/esp32/commands/") + result.id + "/ack/";
  String body;
  const int code = authenticatedRequest("POST", path, payload, body);
  if (code < 200 || code >= 300) {
    Serial.printf("Command result delivery failed (HTTP %d).\n", code);
    return false;
  }
  StaticJsonDocument<1536> response;
  if (deserializeJson(response, body)) {
    Serial.println("Command acknowledgement response could not be validated.");
    return false;
  }
  const char *returnedId = response["id"] | "";
  const char *returnedStatus = response["status"] | "";
  if (strcmp(returnedId, result.id) != 0 || !returnedStatus[0]) {
    Serial.println("Command acknowledgement ID or status did not match the response.");
    return false;
  }
  if (strcmp(returnedStatus, result.status) == 0) {
    Serial.printf("Command result confirmed by backend: %s.\n", result.status);
    return true;
  }
  if (strcmp(result.status, "ACKNOWLEDGED") == 0) {
    Serial.printf("Command was not acknowledged for execution (backend status %s).\n", returnedStatus);
    return false;
  }
  if (strcmp(returnedStatus, "EXPIRED") == 0 ||
      strcmp(returnedStatus, "FAILED") == 0 ||
      strcmp(returnedStatus, "CANCELLED") == 0) {
    Serial.printf("Backend kept command terminal as %s; no further update will be retried.\n", returnedStatus);
    return true;
  }
  Serial.printf("Unexpected command state in acknowledgement response: %s.\n", returnedStatus);
  return false;
}

void queueCommandResult(const PendingCommand &command, const char *status,
                        const char *notes, const char *failureReason) {
  CommandResult result = {};
  strlcpy(result.id, command.id, sizeof(result.id));
  strlcpy(result.status, status, sizeof(result.status));
  if (notes) strlcpy(result.notes, notes, sizeof(result.notes));
  if (failureReason) strlcpy(result.failureReason, failureReason, sizeof(result.failureReason));
  if (xQueueSend(resultQueue, &result, 0) != pdTRUE) {
    Serial.println("Command result queue is full; report could not be retained.");
  }
}

bool postAcknowledgement(const PendingCommand &command) {
  CommandResult ack = {};
  strlcpy(ack.id, command.id, sizeof(ack.id));
  strlcpy(ack.status, "ACKNOWLEDGED", sizeof(ack.status));
  strlcpy(ack.notes, "Authenticated command accepted by the ESP32 bench controller; output transition is pending.", sizeof(ack.notes));
  return sendCommandResult(ack);
}

void startReset(const PendingCommand *restoreCommand, const char *reason) {
  if (hasActiveAcknowledgement) {
    queueCommandResult(activeAcknowledgement, "FAILED", nullptr, reason);
    hasActiveAcknowledgement = false;
  }
  if (restoreCommand) {
    activeAcknowledgement = *restoreCommand;
    hasActiveAcknowledgement = true;
  }
  emergencyHoldActive = false;
  activeGreenHoldSeconds = 0;
  controlMode = MODE_EMERGENCY_RESET;
  setPhase(PHASE_YELLOW);
}

void beginCommand(const PendingCommand &command) {
  if (command.expiresAt <= time(nullptr)) {
    queueCommandResult(command, "FAILED", nullptr, "Command expired before local execution began.");
    return;
  }

  if (command.action == ACTION_RESTORE_NORMAL) {
    startReset(&command, "Superseded by an authorized restore-to-normal command.");
    return;
  }

  if (controlMode == MODE_EMERGENCY_GREEN) {
    // The green GPIO output is already set. Treat EXTEND_GREEN/PREPARE as a
    // bounded extension and report execution only after observing that state.
    emergencyHoldActive = true;
    activeGreenHoldSeconds = min(command.maxPreemptionSeconds, command.failsafeSeconds);
    greenStartedAt = millis();
    queueCommandResult(command, "EXECUTED", "Bench GPIO 27 green output is set. IR sensors remain obstacle-only telemetry.", nullptr);
    return;
  }

  if (controlMode != MODE_NORMAL || hasActiveAcknowledgement) {
    queueCommandResult(command, "FAILED", nullptr, "Another local signal transition is already in progress.");
    return;
  }

  activeAcknowledgement = command;
  hasActiveAcknowledgement = true;
  emergencyHoldActive = true;
  activeGreenHoldSeconds = min(command.maxPreemptionSeconds, command.failsafeSeconds);
  controlMode = MODE_EMERGENCY_PREP;
  setPhase(PHASE_YELLOW);
}

void advanceSignalState() {
  const uint32_t now = millis();
  const uint32_t phaseAgeSeconds = (now - phaseStartedAt) / 1000;
  const DeviceConfig config = readDeviceConfig();

  if (controlMode == MODE_EMERGENCY_PREP) {
    if (hasActiveAcknowledgement && activeAcknowledgement.expiresAt <= time(nullptr)) {
      startReset(nullptr, "Command expired during the local clearance transition.");
      return;
    }
    if (signalPhase == PHASE_YELLOW && phaseAgeSeconds >= activeAcknowledgement.yellowSeconds) {
      setPhase(PHASE_ALL_RED);
    } else if (signalPhase == PHASE_ALL_RED && phaseAgeSeconds >= activeAcknowledgement.allRedSeconds) {
      controlMode = MODE_EMERGENCY_GREEN;
      setPhase(PHASE_GREEN);
      greenStartedAt = now;
      if (hasActiveAcknowledgement) {
        queueCommandResult(activeAcknowledgement, "EXECUTED",
          "Bench firmware set GPIO 27 green after backend-configured yellow and all-red clearance. LED demonstration only.", nullptr);
        hasActiveAcknowledgement = false;
      }
    }
    return;
  }

  if (controlMode == MODE_EMERGENCY_GREEN && emergencyHoldActive) {
    const uint32_t heldSeconds = (now - greenStartedAt) / 1000;
    const uint32_t requiredHold = activeGreenHoldSeconds;
    if (heldSeconds >= requiredHold) startReset(nullptr, "Local bounded green hold completed.");
    return;
  }

  if (controlMode == MODE_EMERGENCY_RESET) {
    if (signalPhase == PHASE_YELLOW && phaseAgeSeconds >= config.yellowSeconds) {
      setPhase(PHASE_ALL_RED);
    } else if (signalPhase == PHASE_ALL_RED && phaseAgeSeconds >= config.allRedSeconds) {
      setPhase(PHASE_RED);
      controlMode = MODE_NORMAL;
      emergencyHoldActive = false;
      if (hasActiveAcknowledgement) {
        queueCommandResult(activeAcknowledgement, "EXECUTED",
          "Restore-to-normal completed; GPIO 25 red indicator is set and other signal LEDs are off.", nullptr);
        hasActiveAcknowledgement = false;
      }
    }
  }
}

String statusPayload(const TelemetrySnapshot &snapshot) {
  StaticJsonDocument<384> document;
  document["firmware_version"] = "1.0.0-rest-bench";
  document["wifi_rssi"] = snapshot.wifiConnected ? snapshot.wifiRssi : 0;
  document["operational_mode"] = !transportConfigured ? "FAILSAFE" :
    (snapshot.mode == MODE_NORMAL ? "NORMAL" : "PREEMPTION");
  document["sensor_1_detected"] = snapshot.entryDetected;
  document["sensor_2_detected"] = snapshot.exitDetected;
  String payload;
  serializeJson(document, payload);
  return payload;
}

String signalPayload(const TelemetrySnapshot &snapshot) {
  StaticJsonDocument<384> document;
  document["current_phase"] = phaseName(snapshot.phase);
  // The bench sketch has no normal fixed-duration traffic cycle.
  document["cycle_duration_seconds"] = 0;
  document["current_phase_elapsed_seconds"] = snapshot.phaseElapsedSeconds;
  document["is_preempted"] = snapshot.preempted;
  JsonObject raw = document.createNestedObject("raw_telemetry");
  raw["bench_demo_only"] = true;
  raw["entry_sensor_is_obstacle_only"] = true;
  raw["exit_sensor_is_obstacle_only"] = true;
  String payload;
  serializeJson(document, payload);
  return payload;
}

bool reportDeviceStatus() {
  const TelemetrySnapshot snapshot = readTelemetrySnapshot();
  String response;
  const int statusCode = authenticatedRequest("POST", "/api/traffic/esp32/status/", statusPayload(snapshot), response);
  if (statusCode < 200 || statusCode >= 300) {
    Serial.printf("Telemetry report failed (HTTP %d).\n", statusCode);
    return false;
  }
  const int signalCode = authenticatedRequest("POST", "/api/traffic/esp32/signal-state/", signalPayload(snapshot), response);
  if (signalCode < 200 || signalCode >= 300) {
    Serial.printf("Signal-state report failed (HTTP %d).\n", signalCode);
    return false;
  }
  return true;
}

void pollCommands() {
  String body;
  const int code = authenticatedRequest("GET", "/api/traffic/esp32/commands/pending/", "", body);
  if (code != 200) {
    Serial.printf("Command poll failed (HTTP %d).\n", code);
    return;
  }

  StaticJsonDocument<4096> document;
  if (deserializeJson(document, body)) {
    Serial.println("Pending-command response was not valid JSON.");
    return;
  }
  if (!document.is<JsonArray>()) {
    Serial.println("Pending-command response was not the expected JSON array.");
    return;
  }

  for (JsonObjectConst row : document.as<JsonArrayConst>()) {
    PendingCommand command = {};
    String rejection;
    if (!parsePendingCommand(row, command, rejection)) {
      if (command.id[0] && rejection.length()) {
        queueCommandResult(command, "FAILED", nullptr, rejection.c_str());
      }
      continue;
    }
    if (!postAcknowledgement(command)) continue;
    if (xQueueSend(commandQueue, &command, 0) != pdTRUE) {
      queueCommandResult(command, "FAILED", nullptr, "Local command queue is full; no signal output was changed.");
    }
  }
}

void serviceQueuedResults() {
  CommandResult result = {};
  if (xQueuePeek(resultQueue, &result, 0) != pdTRUE) return;
  if (sendCommandResult(result)) {
    xQueueReceive(resultQueue, &result, 0);
  } else {
    vTaskDelay(pdMS_TO_TICKS(1500));
  }
}

void networkTask(void *parameter) {
  (void)parameter;
  uint32_t nextWifiRetryAt = 0;
  bool ntpStarted = false;

  while (true) {
    const uint32_t now = millis();
    if (!credentialsReady()) {
      transportConfigured = false;
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }
    transportConfigured = true;

    if (WiFi.status() != WL_CONNECTED) {
      if (now - nextWifiRetryAt >= WIFI_RETRY_INTERVAL_MS) {
        nextWifiRetryAt = now;
        WiFi.reconnect();
        Serial.println("Wi-Fi unavailable; attempting reconnection.");
      }
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }

    if (!ntpStarted) {
      configTime(0, 0, "pool.ntp.org", "time.nist.gov");
      ntpStarted = true;
    }
    if (!clockIsSynchronized()) {
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }

    serviceQueuedResults();

    if (!configReady || now - lastConfigRequestAt >= CONFIG_REFRESH_INTERVAL_MS) {
      if (now - lastConfigRequestAt >= CONFIG_RETRY_INTERVAL_MS) {
        lastConfigRequestAt = now;
        if (fetchConfiguration()) {
          lastHeartbeatAt = now - deviceConfig.heartbeatSeconds * 1000;
          lastStatusAt = now - deviceConfig.heartbeatSeconds * 1000;
          lastCommandPollAt = now - deviceConfig.commandPollSeconds * 1000;
        } else {
          configReady = false;
        }
      }
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }

    if (now - lastHeartbeatAt >= deviceConfig.heartbeatSeconds * 1000) {
      lastHeartbeatAt = now;
      String response;
      const int code = authenticatedRequest("POST", "/api/traffic/esp32/heartbeat/", "{}", response);
      if (code < 200 || code >= 300) Serial.printf("Heartbeat failed (HTTP %d).\n", code);
    }

    if (now - lastStatusAt >= deviceConfig.heartbeatSeconds * 1000) {
      lastStatusAt = now;
      reportDeviceStatus();
    }

    if (now - lastCommandPollAt >= deviceConfig.commandPollSeconds * 1000) {
      lastCommandPollAt = now;
      pollCommands();
    }
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(YELLOW_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(ENTRY_IR_PIN, INPUT_PULLUP);
  pinMode(EXIT_IR_PIN, INPUT_PULLUP);
  setPhase(PHASE_RED);

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SERTOS BENCH");
  lcd.setCursor(0, 1);
  lcd.print("REST controller");

  apiBase = API_BASE_URL;
  while (apiBase.endsWith("/")) apiBase.remove(apiBase.length() - 1);
  transportConfigured = credentialsReady();

  commandQueue = xQueueCreate(COMMAND_QUEUE_LENGTH, sizeof(PendingCommand));
  resultQueue = xQueueCreate(RESULT_QUEUE_LENGTH, sizeof(CommandResult));
  if (!commandQueue || !resultQueue) {
    controlMode = MODE_NORMAL;
    setPhase(PHASE_FAULT);
    Serial.println("Could not allocate command queues. Controller remains in fault state.");
    return;
  }
  queuesReady = true;

  WiFi.mode(WIFI_STA);
  if (looksConfigured(WIFI_SSID) && looksConfigured(WIFI_PASSWORD)) {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }

  publishTelemetrySnapshot();
  xTaskCreatePinnedToCore(networkTask, "sertos-network", 10000, nullptr, 1, nullptr, 0);
  Serial.println("REST bench controller started. No public-road equipment is supported.");
}

void loop() {
  const uint32_t now = millis();
  if (now - lastSensorSampleAt >= SENSOR_SAMPLE_INTERVAL_MS) {
    lastSensorSampleAt = now;
    entryDetected = detected(ENTRY_IR_PIN);
    exitDetected = detected(EXIT_IR_PIN);
  }

  if (!queuesReady) {
    refreshLcd();
    delay(10);
    return;
  }

  PendingCommand command = {};
  while (xQueueReceive(commandQueue, &command, 0) == pdTRUE) {
    beginCommand(command);
  }

  advanceSignalState();
  publishTelemetrySnapshot();
  refreshLcd();
  delay(5);
}
