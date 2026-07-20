"""
camera_manager.py

Ek hi camera khulta hai poore app mein. Face module ho ya gesture module,
dono isi CameraManager se frame maangte hain - khud camera nahi kholte.
Isse do modules ek saath camera use karne ki koshish nahi karenge (crash avoid hota hai).
"""

import cv2
import threading


class CameraManager:
    # Singleton: chahe jitni baar CameraManager() call karo, camera sirf ek hi baar khulega
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, camera_index=0, width=640, height=480):
        if self._initialized:
            return  # camera pehle se khula hua hai, dobara kholne ki zaroorat nahi

        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not self.cap.isOpened():
            raise RuntimeError(
                "Camera nahi khul paaya. Camera_index check karo ya permissions dekho."
            )

        self._initialized = True

    def get_frame(self):
        """Latest frame (BGR image) return karta hai. Agar fail ho to None."""
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def release(self):
        """Program band karte waqt camera release karo."""
        if self.cap.isOpened():
            self.cap.release()
