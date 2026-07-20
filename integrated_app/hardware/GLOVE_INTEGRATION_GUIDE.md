# ESP32 Glove → AI 3D Tutor integration

## 1. Hardware wiring

The MPU6050 and MAX30102 can share the ESP32 I²C bus:

| Module | ESP32 |
|---|---|
| MPU6050 SDA | GPIO 21 |
| MPU6050 SCL | GPIO 22 |
| MAX30102 SDA | GPIO 21 |
| MAX30102 SCL | GPIO 22 |
| Both GND | GND |
| Both VCC | 3.3 V (use the voltage supported by the specific breakout) |

Keep flex sensors on ADC1 pins GPIO 32, 33, 34, 35 and 36. Do not move them
to ADC2 pins because ADC2 is unreliable while ESP32 Bluetooth/Wi-Fi is active.

The MAX30102 optical window must press gently and steadily against skin. Place it
on the inner wrist or a fingertip pad, block ambient light with soft dark foam,
and avoid overtightening it. A sensor facing away from skin cannot measure BPM.

## 2. Install Arduino software

1. Install Arduino IDE 2.x.
2. Add Espressif's ESP32 board package in Boards Manager.
3. In Library Manager install:
   - Adafruit MPU6050
   - Adafruit Unified Sensor
   - Adafruit BusIO
   - SparkFun MAX3010x Sensor Library
4. Open `glove_firmware.ino` from this folder.
5. Select the appropriate ESP32 Dev Module and its COM port.
6. Compile, then upload.

## 3. First calibration

1. Open Serial Monitor at 115200 baud and reset the ESP32.
2. Hold all five fingers fully straight when prompted.
3. Make a comfortable closed fist when prompted.
4. Calibration is saved in ESP32 non-volatile memory.
5. To recalibrate, hold the ESP32 BOOT button during power-on/reset.

Calibration must be performed while wearing the glove. Do not manually copy the
placeholder ADC values from another person because glove fit and flex resistance vary.

## 4. BLE protocol

The ESP32 advertises as `GestureGlove` and notifies characteristic
`6e400002-b5a3-f393-e0a9-e50e24dcca9e` approximately 30 times per second.

The new packet is 13 bytes, little-endian: `<5B3hH`:

- 5 bytes: thumb, index, middle, ring, pinky curl percentages (0–100)
- 3 signed int16: yaw, pitch and roll angular velocity ×100
- 1 uint16: smoothed BPM; zero means no valid skin contact

The application still accepts the older 11-byte packet, but it cannot obtain BPM
from that version.

## 5. Run the application

1. Turn the glove on first.
2. Enable Bluetooth on the laptop. Manual Windows pairing is normally unnecessary
   because the application scans and connects using BLE.
3. Activate the project's Python environment.
4. Run `python main.py` from `integrated_app`.
5. Watch the terminal for `[Glove] Connected over BLE`.
6. The tutorial status line should change from `camera` to `glove` and show BPM
   after stable skin contact and several detected beats.

If the glove disconnects, the application temporarily uses camera gestures and
automatically rescans every two seconds.

## 6. Current gesture contract

| Physical action | Application action |
|---|---|
| Index straight, other fingers bent | POINT/select anatomy |
| Thumb and index bent, remaining fingers relaxed | PRECISION GRAB/tool pickup |
| Closed fist plus wrist movement | Rotate the 3D model |
| Open hand | Release/cancel |
| Wrist yaw/pitch | Move the relative tool cursor |

Use an open-hand hold as the neutral/rest pose between actions. Tool pickup is
confirmed only after several matching packets to prevent accidental activation.

## 7. Pulse troubleshooting

- `0 BPM`: no skin contact, sensor reversed, wiring issue, or insufficient time.
- Unrealistically high/low BPM: motion artefacts; secure the sensor and keep the
  wrist still for the first 10–15 seconds.
- MAX30102 not found: run an I²C scanner; expected addresses are commonly 0x57
  for MAX30102 and 0x68/0x69 for MPU6050.
- App connects but reports no pulse: confirm the firmware is the 13-byte version.
- Do not treat this prototype as a medical device. BPM is used only as a noisy
  learning-adaptation signal and should be combined with interaction history.

## 8. Recommended validation sequence

Test one layer at a time:

1. Serial Monitor: verify five curl percentages and MAX30102 detection.
2. BLE: verify `[Glove] Connected over BLE` in the application terminal.
3. Neutral pose: confirm OPEN/RELEASE is stable.
4. POINT and PRECISION GRAB: test each ten times and record false activations.
5. Cursor: recenter, then test slow yaw/pitch movement.
6. BPM: hold still until four valid beats populate the moving average.
7. Finally run the kidney dissection task end to end.

