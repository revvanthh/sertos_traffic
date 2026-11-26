# SERTOS ESP32 sensor prototype

This prototype reads two IR obstacle sensors, displays their state on a 16x2 I2C LCD, and sends the readings to the SERTOS backend. It does **not** control a traffic signal. Keep it as a low-voltage bench demonstration.

## Parts in the photos

- ESP32 DevKit board: Wi-Fi microcontroller and Arduino IDE target.
- Two IR modules marked HW-201 / MH-B: digital obstacle-detection outputs.
- RG1602A 16x2 LCD with HW-61 I2C backpack.
- USB data cable and jumper wires (not shown).

Arduino IDE is the programming application. You do not need an Arduino Uno for this ESP32 build. An Uno by itself cannot connect to Wi-Fi; the ESP32 is the board this firmware targets.

## Wiring

Disconnect USB power before changing any wires. Use the labels printed on each module to identify pins; the photos show both sides and pin order can be reversed when viewed from the back.

| Module pin | ESP32 pin |
| --- | --- |
| IR sensor 1 `OUT` | GPIO 25 |
| IR sensor 2 `OUT` | GPIO 26 |
| Both sensors `GND` | `GND` |
| Both sensors `VCC` | `3V3` only if that module is specified to work at 3.3 V |
| LCD backpack `SDA` | GPIO 21 through a bidirectional I2C level shifter when the backpack is powered at 5 V |
| LCD backpack `SCL` | GPIO 22 through that same level shifter when powered at 5 V |
| LCD backpack `GND` | `GND` (common ground with ESP32) |
| LCD backpack `VCC` | Backpack's marked/rated supply; verify the board before connecting |

ESP32 GPIO is **not 5 V tolerant**. Many LCD I2C backpacks pull SDA/SCL up to their VCC, so do not connect a 5 V-powered backpack directly to ESP32 I2C pins. Use a bidirectional level shifter, or confirm that the backpack and its pullups are safe at 3.3 V. Do not guess based on wire color. Check the sensor board supply rating too; if its output may be 5 V, use a level shifter on `OUT` or power it at a verified 3.3 V.

The common HW-201/MH-B behavior is active-low detection, but module variants exist. If the Serial Monitor/LCD reads backwards, change `digitalRead(pin) == LOW` in the sketch to `digitalRead(pin) == HIGH`.

## Arduino IDE setup

1. Install Arduino IDE 2.x and add the Espressif ESP32 board package through Boards Manager (search for **esp32 by Espressif Systems**).
2. In Library Manager install **LiquidCrystal I2C** (the sketch uses the common `LiquidCrystal_I2C` API).
3. Open `esp32_traffic_node.ino`, choose the matching ESP32 Dev Module board and the USB serial port, then select the upload speed supported by your board.
4. If upload fails, try holding the board's `BOOT` button while the IDE shows “Connecting”.
5. If the LCD stays blank, confirm power and contrast, then scan I2C addresses; change `0x27` in the sketch to `0x3F` if that is the detected address.

## Configure and upload

1. Register a device in the deployed backend using an administrator account at `POST /api/traffic/devices/register/`. Use a unique ID such as `ESP32-SERTOS-01`, an intersection label like `SERTOS Bench Prototype`, and valid latitude/longitude. The API returns a raw device token once. Store it privately; it cannot be retrieved later.
2. Copy `secrets.h.example` to `secrets.h` in the same folder, then set `WIFI_SSID`, `WIFI_PASSWORD`, `API_BASE_URL` (the backend's HTTPS origin only, e.g. `https://your-service.onrender.com`), `DEVICE_ID`, and `DEVICE_TOKEN` to your values.
3. `secrets.h` is excluded from Git. Do not remove that protection or share the file; it contains your Wi-Fi password and device token.
4. Upload, open Serial Monitor at 115200 baud, and watch for `heartbeat=ok status=ok`. The backend device record's status payload should then contain `sensor_1_detected` and `sensor_2_detected`.

The API device authentication expects `X-Device-ID` and `X-Device-Token`. Heartbeat is posted to `/api/traffic/esp32/heartbeat/`; sensor status is posted to `/api/traffic/esp32/status/` every 30 seconds. The status endpoint only accepts these reports after the backend changes in this checkout have been deployed to the separate backend repository.

## Secure REST controller

This folder preserves the original sensor-only sketch and its pin mapping. The original sketch uses `WiFiClientSecure::setInsecure()`, so it does **not** validate the backend certificate. Do not use it with real Wi-Fi credentials or a device token. For the secure REST bench demo, use the separate sketch in `../esp32_traffic_node_rest_control/`; it requires a trusted CA and refuses to send credentials when one is missing.

## Backend and frontend deployment

The frontend and backend source are in the same workspace, but deployment services may be separate. Deploy the backend changes before using new administrator or firmware endpoints. Configure the frontend build's `VITE_API_BASE_URL` to the backend HTTPS origin. On Render, add only the exact frontend origin (scheme and host, no path) to `CORS_ALLOWED_ORIGINS`. Firmware requests do not use browser CORS but require the deployed backend API and a registered device. Neither sketch is suitable for public-road traffic equipment.
