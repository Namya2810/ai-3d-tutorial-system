"""
gesture_sources.py

Glove hardware ka firmware (glove_firmware.ino) ready hai - isme wahi BLE
protocol use kiya gaya hai jo firmware bhejta hai (device name, UUIDs,
packet format). Camera abhi bhi fallback hai agar glove connect na ho paye.

Design: GestureManager.process(frame) hamesha ek GestureEvent (ya None)
deta hai, chahe wo glove se aaya ho ya camera se - dono taraf se shape same
rehta hai (.gesture, .dx, .dy, .scale_delta, .rotation_deg).
"""

import struct
import threading
import asyncio
import time
import csv
from datetime import datetime, timezone
from pathlib import Path

from bleak import BleakClient, BleakScanner

from gesture_module import GestureModule, GestureEvent  # existing camera-based MediaPipe module
from app_config import setting

# ---- Firmware (glove_firmware.ino) ke saath EXACTLY match hona chahiye ----
BLE_DEVICE_NAME = "GestureGlove"
CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
# V1: 5 flex bytes + 3 gyro int16 = 11 bytes.
# V2: the same payload followed by uint16 BPM = 13 bytes. Accepting both
# formats lets an older glove firmware connect during a staged upgrade.
PACKET_FORMAT_V1 = "<5B3h"
PACKET_FORMAT_V2 = "<5B3hH"
SCAN_TIMEOUT_SECONDS = 10.0
RECONNECT_DELAY_SECONDS = 2.0


class GloveGestureSource:
    """Background thread mein BLE se glove ko dhoondta hai aur connect karta
    hai. Agar glove nahi milta (band hai, dur hai, ya abhi tak banaya hi
    nahi gaya), turant/10-sec baad give-up karke camera fallback pe reh
    jaata hai - koi crash nahi hota, GUI kabhi block nahi hoti."""

    FLEX_CURLED_THRESHOLD = 72
    FLEX_STRAIGHT_THRESHOLD = 28
    PRECISION_GRIP_THRESHOLD = 55
    ROTATION_NOISE_FLOOR = 4.0
    PACKET_STALE_SECONDS = 0.75
    SENSOR_SMOOTHING = 0.35
    POINTER_GAIN = 0.0026
    GESTURE_CONFIRM_FRAMES = 3

    def __init__(self):
        self.connected = False
        self._thread = None
        self._latest_flex = [0, 0, 0, 0, 0]
        self._latest_gyro = (0.0, 0.0, 0.0)
        self.pulse_bpm = None
        self._last_packet_at = 0.0
        self._last_notification_at = None
        self._lock = threading.Lock()
        self._stop_requested = False
        self._candidate_gesture = "none"
        self._candidate_frames = 0
        self._stable_gesture = "none"
        self._pointer_x = 0.5
        self._pointer_y = 0.5
        self._log_file = None
        self._log_writer = None
        self._log_rows_since_flush = 0

    def _log_packet(self, now, flex, gyro, bpm):
        if not bool(setting("glove_logging", "enabled")):
            return
        if self._log_file is None:
            log_dir = Path(__file__).with_name("data") / "glove_sessions"
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._log_file = (log_dir / f"glove_{stamp}.csv").open(
                "w", newline="", encoding="utf-8"
            )
            fields = [
                "timestamp_utc", "monotonic_seconds", "thumb", "index",
                "middle", "ring", "pinky", "yaw_dps", "pitch_dps",
                "roll_dps", "pulse_bpm",
            ]
            self._log_writer = csv.DictWriter(self._log_file, fieldnames=fields)
            self._log_writer.writeheader()
        self._log_writer.writerow({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_seconds": f"{now:.6f}",
            "thumb": flex[0], "index": flex[1], "middle": flex[2],
            "ring": flex[3], "pinky": flex[4],
            "yaw_dps": gyro[0], "pitch_dps": gyro[1], "roll_dps": gyro[2],
            "pulse_bpm": bpm if bpm else "",
        })
        self._log_rows_since_flush += 1
        if self._log_rows_since_flush >= int(setting("glove_logging", "flush_every_rows")):
            self._log_file.flush()
            self._log_rows_since_flush = 0

    def is_available(self):
        return self.connected and (time.monotonic() - self._last_packet_at) < self.PACKET_STALE_SECONDS

    def connect(self):
        """Non-blocking - ek background thread spawn karta hai jo BLE scan
        + connect karta hai. GUI thread yahin se turant aage badh jaata hai."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while not self._stop_requested:
                try:
                    loop.run_until_complete(self._connect_and_listen())
                except Exception as e:
                    print(f"[Glove] BLE error: {e} - retrying")
                self.connected = False
                if not self._stop_requested:
                    loop.run_until_complete(asyncio.sleep(RECONNECT_DELAY_SECONDS))
        finally:
            self.connected = False
            loop.close()

    async def _connect_and_listen(self):
        print("[Glove] Scanning for 'GestureGlove'...")
        device = await BleakScanner.find_device_by_name(
            BLE_DEVICE_NAME, timeout=SCAN_TIMEOUT_SECONDS
        )
        if device is None:
            print("[Glove] Not found within timeout - camera fallback active; rescanning")
            return

        async with BleakClient(device) as client:
            await client.start_notify(CHARACTERISTIC_UUID, self._on_notification)
            self.connected = True
            print("[Glove] Connected over BLE")
            # Connected rehte hue yahin ruko - jab tak disconnect na ho
            while client.is_connected and not self._stop_requested:
                await asyncio.sleep(0.2)
        print("[Glove] Disconnected")

    def _on_notification(self, sender, data: bytearray):
        """Firmware har ~33ms mein ye 11-byte packet bhejta hai. Yahan sirf
        latest values store karte hain - process() jab bhi poochega tab tak
        ka sabse recent reading use hoga."""
        try:
            if len(data) == struct.calcsize(PACKET_FORMAT_V2):
                thumb, index, middle, ring, pinky, yaw16, pitch16, roll16, bpm = struct.unpack(
                    PACKET_FORMAT_V2, bytes(data)
                )
            elif len(data) == struct.calcsize(PACKET_FORMAT_V1):
                thumb, index, middle, ring, pinky, yaw16, pitch16, roll16 = struct.unpack(
                    PACKET_FORMAT_V1, bytes(data)
                )
                bpm = 0
            else:
                return
        except struct.error:
            return  # corrupt/incomplete packet - ignore, agla wait karo
        now = time.monotonic()
        gyro = (yaw16 / 100.0, pitch16 / 100.0, roll16 / 100.0)
        raw_flex = (thumb, index, middle, ring, pinky)
        self._log_packet(now, raw_flex, gyro, bpm)
        with self._lock:
            alpha = self.SENSOR_SMOOTHING
            self._latest_flex = [
                old + alpha * (new - old)
                for old, new in zip(self._latest_flex, (thumb, index, middle, ring, pinky))
            ]
            self._latest_gyro = tuple(
                old + alpha * (new - old) for old, new in zip(self._latest_gyro, gyro)
            )
            dt = 0.0 if self._last_notification_at is None else min(now - self._last_notification_at, 0.08)
            self._last_notification_at = now
            self._last_packet_at = now
            valid_min = float(setting("pulse", "valid_min"))
            valid_max = float(setting("pulse", "valid_max"))
            self.pulse_bpm = float(bpm) if valid_min <= bpm <= valid_max else None
            # MPU6050 angular velocity drives a relative on-screen tool cursor.
            # This avoids needing the camera for pointing while the glove is worn.
            self._pointer_x = max(0.03, min(0.97, self._pointer_x + gyro[0] * dt * self.POINTER_GAIN))
            self._pointer_y = max(0.03, min(0.97, self._pointer_y + gyro[1] * dt * self.POINTER_GAIN))

    def process(self, frame=None):
        # frame yahan use nahi hota - glove ko camera image ki zaroorat nahi
        if not self.connected:
            return None
        with self._lock:
            flex = list(self._latest_flex)
            gyro = tuple(self._latest_gyro)
            pointer = (self._pointer_x, self._pointer_y)
        if time.monotonic() - self._last_packet_at >= self.PACKET_STALE_SECONDS:
            return None
        return self._classify(flex, gyro, pointer)

    def _classify(self, flex_values, gyro, pointer=(0.5, 0.5)):
        """flex_values: list of 5 ints (0-100), order [thumb, index, middle, ring, pinky]
        gyro: (yaw_delta, pitch_delta, roll_delta) in deg/sec since last reading

        Returns a GestureEvent - SAME shape as the camera's, taaki
        GestureManager/app_window.py mein kahin bhi "glove se aaya ya camera
        se" ka fark check na karna pade.
        """
        thumb, index, middle, ring, pinky = flex_values
        curled = sum(1 for v in (index, middle, ring, pinky) if v > self.FLEX_CURLED_THRESHOLD)
        straight = sum(1 for v in (index, middle, ring, pinky) if v < self.FLEX_STRAIGHT_THRESHOLD)

        yaw, pitch, roll = gyro
        # True rotation - glove ka sabse bada advantage camera se. Total
        # angular movement teeno axes milake (rough magnitude).
        rotation_deg = (abs(yaw) + abs(pitch) + abs(roll))
        if rotation_deg < self.ROTATION_NOISE_FLOOR:
            rotation_deg = 0.0

        # Precision grip is thumb+index flexion while the remaining fingers
        # stay relaxed. It is intentionally different from a closed fist.
        if curled == 4:
            raw_gesture = "grab"
        elif (
            thumb > self.PRECISION_GRIP_THRESHOLD
            and index > self.PRECISION_GRIP_THRESHOLD
            and sum(v > self.FLEX_CURLED_THRESHOLD for v in (middle, ring, pinky)) <= 1
        ):
            raw_gesture = "pinch"
        elif (index < self.FLEX_STRAIGHT_THRESHOLD) and sum(
            v > self.PRECISION_GRIP_THRESHOLD for v in (middle, ring, pinky)
        ) >= 2:
            # index seedhi, baaki curled -> POINT (isi se model rotate/point
            # hota hai screen pe, jaise camera mein hota hai)
            raw_gesture = "point"
        elif straight == 4:
            raw_gesture = "release"
        else:
            raw_gesture = "none"

        if raw_gesture == self._candidate_gesture:
            self._candidate_frames += 1
        else:
            self._candidate_gesture = raw_gesture
            self._candidate_frames = 1
        if self._candidate_frames >= self.GESTURE_CONFIRM_FRAMES:
            self._stable_gesture = raw_gesture

        return GestureEvent(
            gesture=self._stable_gesture,
            dx=yaw / 90.0,   # camera ke dx jaisa hi scale (-1 se 1 ke aas-paas)
            dy=pitch / 90.0,
            scale_delta=0.0,
            rotation_deg=rotation_deg,
            pointer_x=pointer[0],
            pointer_y=pointer[1],
        )

    def close(self):
        self._stop_requested = True
        self.connected = False
        if self._log_file is not None:
            self._log_file.flush()
            self._log_file.close()
            self._log_file = None

    def recenter_pointer(self):
        with self._lock:
            self._pointer_x = 0.5
            self._pointer_y = 0.5
            self._latest_gyro = (0.0, 0.0, 0.0)


class GestureManager:
    """Glove primary, camera fallback. Face detection isse independent hai -
    camera hamesha face ke liye chalta rehta hai chahe gesture kahin se bhi aaye."""

    def __init__(self):
        self.glove = GloveGestureSource()
        self.camera_gesture = GestureModule()
        self.active_source = "camera"  # glove connect hote hi "glove" ho jayega
        self.glove.connect()  # background mein scan/connect try karta hai - non-blocking

    def process(self, frame):
        if self.glove.is_available():
            if self.active_source != "glove":
                self.glove.recenter_pointer()
            self.active_source = "glove"
            return self.glove.process(frame)
        self.active_source = "camera"
        return self.camera_gesture.process(frame)

    @property
    def pulse_bpm(self):
        return self.glove.pulse_bpm if self.glove.is_available() else None

    def close(self):
        self.glove.close()
        self.camera_gesture.close()

    def recenter(self):
        """Reset relative glove pointer after drift or a source switch."""
        self.glove.recenter_pointer()
