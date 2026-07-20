/*
  glove_firmware.ino

  Runs on the ESP32 Dev Board in the glove. Reads 5 flex sensors (analog)
  the MPU6050 gyroscope and MAX30102 pulse sensor (I2C), packs them into
  a 13-byte binary
  packet, and streams it over BLE notifications ~30x/sec.

  The packet format here MUST match PACKET_FORMAT in gesture_sources.py
  ("<5B3hH" = 5 unsigned bytes + 3 signed int16 + BPM uint16,
  little-endian). If you
  change one side, change the other.

  ---- Libraries needed (Arduino Library Manager / PlatformIO) ----
    - "Adafruit MPU6050"        (pulls in Adafruit Unified Sensor + BusIO)
    - "SparkFun MAX3010x Sensor Library" (provides MAX30105.h + heartRate.h)
  BLE (BLEDevice/BLEServer/...) ships with the ESP32 board core, no
  separate install needed.

  ---- Board setting ----
  Tools > Board > any "ESP32 Dev Module" (or your specific board variant).

  ---- Actual glove wiring ----
  Flex sensors, logical order thumb/index/middle/ring/pinky:
  GPIO25, GPIO33, GPIO32, GPIO35, GPIO34.
  GPIO25 is ADC2. This firmware uses BLE only (not Wi-Fi), so that fixed
  hardware connection is supported. Do not enable ESP32 Wi-Fi while using
  the thumb flex sensor on GPIO25 because Wi-Fi competes for ADC2.
  MPU6050 -> I2C: SDA=GPIO21, SCL=GPIO22 (ESP32 default I2C pins).
*/

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Preferences.h>
#include <MAX30105.h>
#include "heartRate.h"

// ---- BLE identifiers (must match gesture_sources.py exactly) ----
#define BLE_DEVICE_NAME      "GestureGlove"
#define SERVICE_UUID         "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHARACTERISTIC_UUID  "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

// ---- Flex sensor analog pins: thumb, index, middle, ring, pinky ----
const int FLEX_PINS[5] = {25, 33, 32, 35, 34};

// ---- Calibration: raw ADC (0-4095) at straight vs fully curled ----
// PLACEHOLDER VALUES. Upload calibrate_flex_test() below first (or just
// Serial.print(analogRead(pin)) in loop()), wear the glove, print with
// finger straight and finger fully curled, then fill these arrays in.
int FLEX_STRAIGHT_RAW[5] = {1800, 1800, 1800, 1800, 1800};
int FLEX_CURLED_RAW[5]   = {3000, 3000, 3000, 3000, 3000};
float filteredFlexRaw[5] = {0, 0, 0, 0, 0};
const float FLEX_FILTER_ALPHA = 0.28f;
const int CALIBRATION_BUTTON_PIN = 0;  // hold ESP32 BOOT while powering on
Preferences preferences;

Adafruit_MPU6050 mpu;
MAX30105 pulseSensor;
bool pulseSensorAvailable = false;
uint16_t currentBpm = 0;
byte bpmHistory[4] = {0, 0, 0, 0};
byte bpmHistoryIndex = 0;
unsigned long lastBeatAt = 0;
BLECharacteristic *pCharacteristic;
bool deviceConnected = false;

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *pServer) override {
    deviceConnected = true;
  }
  void onDisconnect(BLEServer *pServer) override {
    deviceConnected = false;
    BLEDevice::startAdvertising();  // so the laptop can reconnect after a drop
  }
};

uint8_t mapFlexToPercent(int raw, int straightRaw, int curledRaw) {
  long pct = map(raw, straightRaw, curledRaw, 0, 100);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return (uint8_t)pct;
}

int readFlexAveraged(int pin) {
  long total = 0;
  for (int sample = 0; sample < 4; sample++) total += analogRead(pin);
  return (int)(total / 4);
}

void captureFlexPose(int output[5], const char *message) {
  Serial.println(message);
  delay(2500);
  long totals[5] = {0, 0, 0, 0, 0};
  const int samples = 80;
  for (int sample = 0; sample < samples; sample++) {
    for (int finger = 0; finger < 5; finger++) totals[finger] += readFlexAveraged(FLEX_PINS[finger]);
    delay(20);
  }
  for (int finger = 0; finger < 5; finger++) output[finger] = totals[finger] / samples;
}

void saveCalibration() {
  // Namespace v2 belongs to the physical mapping above. Keeping it separate
  // prevents calibration captured with an older pin order being reused.
  preferences.begin("glove-cal-v2", false);
  preferences.putBytes("straight", FLEX_STRAIGHT_RAW, sizeof(FLEX_STRAIGHT_RAW));
  preferences.putBytes("curled", FLEX_CURLED_RAW, sizeof(FLEX_CURLED_RAW));
  preferences.putBool("valid", true);
  preferences.end();
}

bool loadCalibration() {
  preferences.begin("glove-cal-v2", true);
  bool valid = preferences.getBool("valid", false);
  if (valid) {
    preferences.getBytes("straight", FLEX_STRAIGHT_RAW, sizeof(FLEX_STRAIGHT_RAW));
    preferences.getBytes("curled", FLEX_CURLED_RAW, sizeof(FLEX_CURLED_RAW));
  }
  preferences.end();
  return valid;
}

void calibrateFlexSensors() {
  captureFlexPose(FLEX_STRAIGHT_RAW, "CALIBRATION 1/2: hold every finger fully STRAIGHT...");
  captureFlexPose(FLEX_CURLED_RAW, "CALIBRATION 2/2: make a comfortable CLOSED FIST...");
  saveCalibration();
  Serial.println("Calibration saved. Restarting normal glove stream.");
}

void updatePulseSensor() {
  if (!pulseSensorAvailable) {
    currentBpm = 0;
    return;
  }
  long irValue = pulseSensor.getIR();
  // Low IR means no finger/wrist contact. Do not feed fabricated BPM into
  // the confusion score when the optical sensor is not touching skin.
  if (irValue < 50000) {
    currentBpm = 0;
    return;
  }
  if (!checkForBeat(irValue)) return;
  unsigned long now = millis();
  if (lastBeatAt != 0) {
    float bpm = 60.0f / ((now - lastBeatAt) / 1000.0f);
    if (bpm >= 35.0f && bpm <= 220.0f) {
      bpmHistory[bpmHistoryIndex++] = (byte)bpm;
      bpmHistoryIndex %= 4;
      int total = 0;
      for (byte i = 0; i < 4; i++) total += bpmHistory[i];
      currentBpm = total / 4;
    }
  }
  lastBeatAt = now;
}

void setup() {
  Serial.begin(115200);
  pinMode(CALIBRATION_BUTTON_PIN, INPUT_PULLUP);
  analogReadResolution(12);
  for (int i = 0; i < 5; i++) analogSetPinAttenuation(FLEX_PINS[i], ADC_11db);

  bool calibrated = loadCalibration();
  if (!calibrated || digitalRead(CALIBRATION_BUTTON_PIN) == LOW) calibrateFlexSensors();
  for (int i = 0; i < 5; i++) filteredFlexRaw[i] = readFlexAveraged(FLEX_PINS[i]);

  Wire.begin(21, 22);
  Wire.setClock(100000);  // SDA=21, SCL=22 by default on ESP32
  if (!mpu.begin()) {
    Serial.println("MPU6050 not found - check wiring (SDA/SCL/VCC/GND)");
    while (1) delay(10);
  }
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  pulseSensorAvailable = pulseSensor.begin(Wire, I2C_SPEED_STANDARD);
  if (pulseSensorAvailable) {
    // brightness, averaging, LED mode (red+IR), sample rate, pulse width, ADC range
    pulseSensor.setup(60, 4, 2, 100, 411, 4096);
    pulseSensor.setPulseAmplitudeRed(0x0A);
    pulseSensor.setPulseAmplitudeGreen(0);
    Serial.println("MAX30102 ready");
  } else {
    Serial.println("MAX30102 not found - gesture streaming will continue without BPM");
  }

  BLEDevice::init(BLE_DEVICE_NAME);
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->addDescriptor(new BLE2902());
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->start();

  Serial.println("Glove BLE advertising as 'GestureGlove', waiting for laptop...");
}

void loop() {
  if (!deviceConnected) {
    delay(50);
    return;
  }

  // ---- 1. Flex sensors -> 0-100 curl percentage each ----
  uint8_t flexPct[5];
  for (int i = 0; i < 5; i++) {
    int raw = readFlexAveraged(FLEX_PINS[i]);
    filteredFlexRaw[i] += FLEX_FILTER_ALPHA * (raw - filteredFlexRaw[i]);
    flexPct[i] = mapFlexToPercent((int)filteredFlexRaw[i], FLEX_STRAIGHT_RAW[i], FLEX_CURLED_RAW[i]);
  }

  // ---- 2. Gyro -> yaw/pitch/roll angular velocity (deg/sec) ----
  sensors_event_t accel, gyro, temp;
  mpu.getEvent(&accel, &gyro, &temp);
  // Adafruit_MPU6050 reports rad/s -> convert to deg/s to match
  // gesture_sources.py's expected units (and the .md doc).
  float yaw   = gyro.gyro.z * 57.2958;
  float pitch = gyro.gyro.y * 57.2958;
  float roll  = gyro.gyro.x * 57.2958;
  // Exact axis -> yaw/pitch/roll mapping depends on how the MPU6050 sits
  // on the glove - if rotate feels swapped/inverted when testing, swap
  // which gyro axis feeds yaw/pitch/roll above.

  // Scale by 100 so we can send as int16 (2 decimal places) instead of a
  // 4-byte float per axis - keeps the packet small enough to skip BLE MTU
  // negotiation.
  int16_t yaw16   = (int16_t)(yaw * 100);
  int16_t pitch16 = (int16_t)(pitch * 100);
  int16_t roll16  = (int16_t)(roll * 100);

  // ---- 3. MAX30102 -> smoothed heart rate (0 means unavailable/no contact) ----
  updatePulseSensor();

  // ---- 4. Pack: 5 flex + 3x int16 gyro + uint16 BPM = 13 bytes ----
  // Layout MUST match gesture_sources.py's PACKET_FORMAT_V2 = "<5B3hH"
  uint8_t packet[13];
  memcpy(packet, flexPct, 5);
  memcpy(packet + 5, &yaw16, 2);
  memcpy(packet + 7, &pitch16, 2);
  memcpy(packet + 9, &roll16, 2);
  memcpy(packet + 11, &currentBpm, 2);

  pCharacteristic->setValue(packet, sizeof(packet));
  pCharacteristic->notify();

  delay(33);  // ~30Hz, matches the 30ms camera tick in tutorial_3d_page.py
}

/*
  ---- One-time calibration helper ----
  Comment out loop() above and use this instead to find real
  FLEX_STRAIGHT_RAW / FLEX_CURLED_RAW values: open Serial Monitor, hold each
  finger straight and note the 5 numbers, then hold fully curled and note
  them again.

  void loop() {
    for (int i = 0; i < 5; i++) {
      Serial.print(analogRead(FLEX_PINS[i]));
      Serial.print("\t");
    }
    Serial.println();
    delay(200);
  }
*/
