# ESP32 glove to AI 3D Tutor integration

## Fixed hardware map

Do not rewire the completed glove. The firmware uses its existing mapping:

| Input | ESP32 pin |
|---|---|
| Thumb flex | GPIO 25 |
| Index flex | GPIO 33 |
| Middle flex | GPIO 32 |
| Ring flex | GPIO 35 |
| Pinky flex | GPIO 34 |
| MPU6050 + MAX30102 SDA | GPIO 21 |
| MPU6050 + MAX30102 SCL | GPIO 22 |

GPIO25 is ADC2. The supplied firmware uses BLE and does not enable Wi-Fi, so
the existing thumb connection is supported. Do not add ESP32 Wi-Fi while
reading it. Both I2C modules share ground and the voltage supported by their
breakout boards (normally 3.3 V for this build).

## Arduino setup and upload

Install the ESP32 board package and these libraries:

- Adafruit MPU6050 (plus Unified Sensor and BusIO dependencies)
- SparkFun MAX3010x Sensor Library

Open `glove_firmware/glove_firmware.ino`, select ESP32 Dev Module and the
correct COM port, Verify, then Upload. Serial Monitor must use 115200 baud.

## First calibration

On first boot, wear the glove and follow the Serial Monitor prompts: first hold
all fingers straight, then make a comfortable closed fist. Values are saved in
ESP32 Preferences. Hold the BOOT button while resetting to recalibrate later.

## BLE protocol

The ESP32 advertises as `GestureGlove` and notifies characteristic
`6e400002-b5a3-f393-e0a9-e50e24dcca9e` at about 30 Hz.

Current packet: 15-byte little-endian `<BB5B3hH`:

- protocol version byte (`3`)
- event flags byte (`0x01` means recenter pointer)
- five curl percentages: thumb, index, middle, ring, pinky
- yaw, pitch, roll signed int16 values in degrees/second times 100
- uint16 BPM; zero means unavailable/no skin contact

The desktop app remains compatible with legacy 11-byte, 13-byte, and
versioned 14-byte packets.

## Gesture contract

| Physical action | App action |
|---|---|
| Index straight, other fingers bent | Point/select |
| Thumb-index precision grip | Pick up/use a tool |
| Closed fist plus wrist movement | Rotate model |
| Pinch plus vertical movement | Zoom |
| Open hand | Release |
| Open hand held still for 1.5 seconds | Recenter pointer |

## Run and validate

1. Turn on the glove and laptop Bluetooth.
2. Start the full app from the project root with `python run_all.py`.
3. Confirm `[Glove] Connected over BLE` in the terminal.
4. Test release, point, precision grip, rotate, zoom and recenter in that order.
5. Hold the pulse sensor steadily against skin for several beats.
6. Run the kidney dissection end to end.

Raw packets are stored under `integrated_app/data/glove_sessions/` when
`glove_logging.enabled` is true in `runtime_config.json`. From
`integrated_app`, run `python tools/glove_log_summary.py` to inspect the latest
session. This prototype is not a medical device; BPM is only an adaptation
signal.

If MAX30102 is not found, run an I2C scanner. Expected addresses are commonly
0x57 for MAX30102 and 0x68/0x69 for MPU6050. If only 0x68 appears, check the
repaired MAX30102 joints before changing software.
