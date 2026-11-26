# SERTOS ESP32 REST bench controller

This is a separate, authenticated REST firmware for a supervised, low-voltage bench demonstration. The original sensor-only firmware remains unchanged at `hardware/esp32_traffic_node/esp32_traffic_node.ino`.

This controller drives three indicator LEDs only. It is not certified for traffic control and must never be wired to public-road signals or a real traffic controller.

## Pin map

| Part | ESP32 GPIO / connection |
| --- | --- |
| Red LED | GPIO 25, through a current-limiting resistor |
| Yellow LED | GPIO 26, through a current-limiting resistor |
| Green LED | GPIO 27, through a current-limiting resistor |
| Entry IR sensor output | GPIO 32, active LOW |
| Exit IR sensor output | GPIO 33, active LOW |
| LCD SDA | GPIO 21 |
| LCD SCL | GPIO 22 |
| LCD I2C address | `0x27`, 16×2 |

Connect LED cathodes and sensor grounds to ESP32 ground. Confirm each sensor works at 3.3 V; protect ESP32 inputs from any 5 V output. If the LCD backpack is powered at 5 V, use a bidirectional I2C level shifter unless the backpack pull-ups are confirmed safe at 3.3 V. ESP32 GPIO is not 5 V tolerant.

## Firmware behavior

- IR entry/exit inputs are sampled every 10 ms in the main loop, independently of emergency mode. `sensor_1_detected` reports the entry sensor and `sensor_2_detected` reports the exit sensor.
- These IR sensors detect obstacles. They do not identify an ambulance or confirm that a specific incident passed the junction.
- Normal mode holds the red indicator on. The sketch does not simulate an ordinary signal cycle.
- A valid `PREPARE_GREEN_CORRIDOR` command switches through yellow and an all-off clearance interval using the command's backend safety values, then sets the green LED. `EXTEND_GREEN` extends an already-green bench state. `RESTORE_NORMAL_CYCLE` transitions through yellow and all-off clearance back to red.
- The device acknowledges receipt before changing outputs. It reports `EXECUTED` only after the corresponding LED output state is set. This is firmware-reported GPIO state, not independent physical lamp verification.
- Green holds are bounded by backend command safety constraints and local validation. A stale or malformed command is never executed.
- Network requests use HTTPS certificate validation and the device's `X-Device-ID` / `X-Device-Token` headers. There is no MQTT connection or public broker.

The sketch fetches `GET /api/traffic/esp32/config/` before polling or reporting. The workspace backend currently returns a 30-second heartbeat interval, 5-second command poll interval, 15-second minimum green, 4-second yellow, 2-second all-red, 45-second maximum preemption, and 60-second failsafe timeout. The firmware reads these values at runtime and refuses configuration outside conservative local bounds. Live config was not readable without a registered device token.

## Prepare credentials

1. Sign in as an authorized administrator and register a unique device using `POST /api/traffic/devices/register/` or the Administrator → Traffic Controllers screen. The endpoint returns the raw device token once. Store it privately; it cannot be retrieved later.
2. Rotate any Wi-Fi password that may have appeared in previously shared firmware or chat.
3. Copy `secrets.h.example` to `secrets.h` beside the sketch. Set your Wi-Fi name/password, backend HTTPS origin, registered device ID, and one-time token.
4. Add the trusted root CA certificate for the backend's current TLS certificate chain to `API_ROOT_CA`. Get the PEM from the certificate issuer's official source and verify the issuer/chain before using it. The sample intentionally has no working certificate. The firmware refuses credential-bearing requests until a trusted CA is configured; it never disables certificate checks.
5. Do not put the device token, Wi-Fi password, Django secret, or private API key in the frontend or a committed file. `secrets.h` is ignored by Git.

## Arduino IDE

1. Install Arduino IDE 2.x and the Espressif ESP32 board package.
2. Install ArduinoJson 6.x and a `LiquidCrystal_I2C` library compatible with the common `lcd.init()` API.
3. Open `esp32_traffic_node_rest_control.ino`, select the matching ESP32 Dev Module and serial port, then compile and upload manually.
4. Open Serial Monitor at 115200 baud. The firmware logs HTTP result codes and never prints credentials or response bodies.

The request flow is `config → heartbeat/status/signal-state → pending command → ACKNOWLEDGED → local transition → EXECUTED/FAILED`. If Wi-Fi, trusted TLS, NTP clock synchronization, device authentication, or backend configuration is unavailable, the firmware stays in normal red mode, reports an offline state on the LCD, and does not accept commands.

This firmware has not been compiled with an ESP32 toolchain or tested on physical hardware in this workspace. Do not flash it until the board, wiring, library versions, CA certificate, and credentials have been checked by the operator.
