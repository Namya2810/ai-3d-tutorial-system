"""
gesture_module.py  (Phase 4 - Gesture Interaction)

Yeh bhi apna camera nahi kholta - CameraManager se aayi hui frame use karta hai.
Isme teen kaam ho rahe hain (ek hi file mein, simple rakhne ke liye):
  1. GestureEvent      -> gesture ka result (grab/rotate/pinch/release) store karta hai
  2. classify()        -> hand landmarks dekh kar decide karta hai kaunsa gesture hai
  3. GestureDebouncer   -> camera thoda kaanpta hai, isliye 4-5 frame consistent hone
                           par hi final maanta hai (varna gesture flicker karega)
  4. GestureModule      -> upar teeno ko jodta hai, CameraManager se frame leke
                           final debounced gesture return karta hai
"""

import math
from collections import deque
from dataclasses import dataclass
from time import time

import cv2
import mediapipe as mp


# ---------- 1. Gesture ka result ----------

@dataclass
class GestureEvent:
    gesture: str              # "grab" | "release" | "rotate" | "pinch"
    dx: float = 0.0            # left-right movement (rotate ke liye)
    dy: float = 0.0            # up-down movement (rotate ke liye)
    scale_delta: float = 0.0   # zoom in/out (pinch ke liye)
    rotation_deg: float = 0.0  # TRUE 3D rotation magnitude - sirf glove (MPU6050
                               # gyroscope) isse populate karta hai; camera ke
                               # liye hamesha 0.0 hi rehta hai (2D hand tracking
                               # se real rotation angle nahi milta). Purely
                               # additive field - kahin bhi existing code isse
                               # todta nahi kyunki default 0.0 hai.
    pointer_x: float = None     # normalized screen position (0..1), camera hand only
    pointer_y: float = None     # normalized screen position (0..1), camera hand only
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time()


# ---------- 2. Landmarks dekh kar gesture pehchano ----------

FINGER_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
FINGER_PIPS = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def _fingers_curled(landmarks):
    """Kitni fingers mudi hui hain (thumb chhod kar), yeh count karta hai."""
    curled = 0
    wrist = landmarks[0]
    for name in FINGER_TIPS:
        tip = landmarks[FINGER_TIPS[name]]
        pip = landmarks[FINGER_PIPS[name]]
        if _dist(tip, wrist) < _dist(pip, wrist):
            curled += 1
    return curled


def _is_finger_curled(landmarks, name):
    """Single finger ke liye same check (POINT detect karne ke liye chahiye)."""
    wrist = landmarks[0]
    tip = landmarks[FINGER_TIPS[name]]
    pip = landmarks[FINGER_PIPS[name]]
    return _dist(tip, wrist) < _dist(pip, wrist)


def _hand_scale(landmarks):
    """Wrist se middle-finger-base ki distance - yeh hath ka 'size' batata hai.
    Isse pinch ko hand-size/camera-distance ke hisaab se relative bana dete hain,
    warna camera se paas/door hone par fixed number kabhi sahi nahi baithta."""
    return _dist(landmarks[0], landmarks[9]) or 1e-6


PINCH_ENTER = 0.35   # itna paas aane par pinch shuru maana jaayega
PINCH_EXIT = 0.55     # itna door jaane tak pinch mein hi rahoge (0.9 bahut loose tha -
                      # usse pinch se bahar nikalna hi nahi hota tha, isliye rotate
                      # trigger nahi ho raha tha)


def classify(landmarks, previous_state="none"):
    """21 landmarks dekh kar batata hai: pinch / grab / release / none.
    previous_state batata hai pichle frame mein kya tha - isse pinch mein
    "hysteresis" milta hai: andar aana strict hai, bahar nikalna loose hai,
    taaki ek hi pinch gesture ke andar zoom in aur zoom out dono ho sakein."""
    thumb_tip, index_tip = landmarks[4], landmarks[8]
    scale = _hand_scale(landmarks)
    pinch_ratio = _dist(thumb_tip, index_tip) / scale
    curled = _fingers_curled(landmarks)

    # IMPORTANT: fist (grab) ko pinch check se PEHLE karo. Mutthi banate waqt
    # thumb aur index bhi naturally paas aa jaate hain, isliye pehle pinch
    # check karne se fist hamesha "pinch" hi classify ho raha tha aur "grab"
    # (rotate) kabhi trigger hi nahi hota tha.
    #
    # threshold curled==4 (sirf poori mutthi) rakha hai, curled>=3 nahi -
    # kyunki POINT gesture (index seedhi, baaki 3 mudi) mein bhi curled==3
    # hota hai. >=3 rakhne se POINT hamesha "grab" ban jaata tha aur neeche
    # wala point-specific check kabhi chalta hi nahi tha.
    if curled == 4:
        return "grab", 1.0

    # POINT: index finger khuli honi chahiye, aur teen fingers (middle/ring/
    # pinky) mein se KAM SE KAM 2 curled honi chahiye - teeno perfectly curled
    # maangna bahut strict tha (real haath mein ek finger thoda seedha reh
    # jaata hai), isliye POINT flicker karke "none" ban jaata tha.
    index_curled = _is_finger_curled(landmarks, "index")
    middle_curled = _is_finger_curled(landmarks, "middle")
    ring_curled = _is_finger_curled(landmarks, "ring")
    pinky_curled = _is_finger_curled(landmarks, "pinky")
    other_curled_count = sum([middle_curled, ring_curled, pinky_curled])
    if (not index_curled) and other_curled_count >= 2:
        return "point", 1.0

    pinch_threshold = PINCH_EXIT if previous_state == "pinch" else PINCH_ENTER
    if pinch_ratio < pinch_threshold:
        return "pinch", 1.0 - min(pinch_ratio, 1.0)

    if curled == 0:
        return "release", 1.0
    return "none", 0.0


# ---------- 3. Flicker rokne wala layer ----------

class GestureDebouncer:
    def __init__(self, window=3, min_agreement=2):
        self.history = deque(maxlen=window)
        self.min_agreement = min_agreement
        self.current_state = "none"

    def update(self, label):
        self.history.append(label)
        if len(self.history) < self.history.maxlen:
            return None  # abhi enough frames nahi aaye

        most_common = max(set(self.history), key=self.history.count)
        count = self.history.count(most_common)

        if count >= self.min_agreement and most_common != self.current_state:
            self.current_state = most_common
            return most_common  # yeh ek real, confirmed gesture change hai
        return None


# ---------- 4. Sab kuch jodne wala module ----------

class GestureModule:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self.debouncer = GestureDebouncer()
        self._prev_landmarks = None
        self.debug_draw = False  # True karo to hand ke points/lines frame pe dikhenge

        # Grace period: agar MediaPipe ek-do frame ke liye haath "miss" kar
        # de (halka blur/angle), turant "no hand" maan ke movement history
        # bhula dena jerky lagta hai. Isliye kuch frames tak purana event
        # hi dobara bhej dete hain (dx/dy=0, movement pause lekin gesture
        # state bana rehta hai) - asli "haath hata liya" tabhi maanenge jab
        # ye grace period bhi khatam ho jaye.
        self._missed_frames = 0
        self._max_missed_frames = 5
        self._last_event = None

        # Smoothing: raw frame-to-frame delta hamesha thoda jittery hota hai
        # (camera/MediaPipe ka noise floor). Exponential smoothing se har naya
        # delta purane smoothed value ke saath thoda mix hota hai - chhoti
        # jitter average ho jaati hai, lekin genuine movement fir bhi jaldi
        # dikhta hai (0.4 = kaafi responsive, phir bhi smooth).
        self._smooth_alpha = 0.4
        self._dx_smooth = 0.0
        self._dy_smooth = 0.0
        self._scale_smooth = 0.0

    def process(self, frame):
        """
        frame: CameraManager.get_frame() se mila hua BGR image
        return: GestureEvent har frame jab hand dikh raha ho, warna None.

        Note: "rotate" alag gesture nahi hai - jab tak "grab" pakda hua hai
        aur haath move ho raha hai, wahi movement (dx, dy) rotation ban jaata hai.
        Isliye state (grab/pinch/release) debounced hai (flicker na ho), lekin
        dx/dy/scale_delta har frame fresh calculate hote hain (taaki movement smooth ho).
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        if not results.multi_hand_landmarks:
            self._missed_frames += 1
            if self._last_event is not None and self._missed_frames <= self._max_missed_frames:
                # Chhota sa dropout - purana gesture state hi dobara bhej do
                # (dx/dy=0 taaki koi achanak jump na ho), taaki 1-2 frame ka
                # miss poori movement ko na roke.
                return GestureEvent(gesture=self._last_event.gesture, dx=0.0, dy=0.0, scale_delta=0.0)
            self._prev_landmarks = None  # hand sach mein gayab ho gaya, purana movement bhula do
            self._last_event = None
            self._dx_smooth = self._dy_smooth = self._scale_smooth = 0.0
            return None

        self._missed_frames = 0
        hand_landmarks_obj = results.multi_hand_landmarks[0]
        landmarks = hand_landmarks_obj.landmark

        if self.debug_draw:
            self.mp_drawing.draw_landmarks(frame, hand_landmarks_obj, self.mp_hands.HAND_CONNECTIONS)

        label, confidence = classify(landmarks, previous_state=self.debouncer.current_state)
        self.debouncer.update(label)  # sirf stable state track karne ke liye

        active_state = self.debouncer.current_state
        dx, dy, scale_delta = self._compute_deltas(landmarks)
        index_tip = landmarks[8]
        event = GestureEvent(
            gesture=active_state,
            dx=dx,
            dy=dy,
            scale_delta=scale_delta,
            pointer_x=max(0.0, min(1.0, 1.0 - index_tip.x)),
            pointer_y=max(0.0, min(1.0, index_tip.y)),
        )
        self._last_event = event
        return event

    def _compute_deltas(self, landmarks):
        """Pichle frame se compare karke movement (rotate ke liye) aur
        pinch-distance ka change (zoom ke liye) nikalta hai."""
        wrist = landmarks[0]
        dx = dy = scale_delta = 0.0

        if self._prev_landmarks is not None:
            prev_wrist = self._prev_landmarks[0]
            dx = wrist.x - prev_wrist.x
            dy = wrist.y - prev_wrist.y

            # Zoom: thumb-index doori badh rahi hai to zoom in, ghat rahi hai to zoom out
            curr_pinch = _dist(landmarks[4], landmarks[8])
            prev_pinch = _dist(self._prev_landmarks[4], self._prev_landmarks[8])
            scale_delta = (curr_pinch - prev_pinch) * 3.0  # 3.0 = sensitivity, tune kar sakte ho

            # Kabhi-kabhi MediaPipe ek single frame mein landmark thoda "uchak"
            # jaata hai (jitter) - bina clamp ke, wo ek hi frame mein zoom ko
            # seedha min/max limit tak bhej deta tha aur wahi atak jaata tha
            # (isliye "zoom kaam hi nahi karta" jaisa feel aata tha). Clamp
            # karne se ek frame ka jitter zyada se zyada itna hi move karega.
            MAX_SCALE_DELTA_PER_FRAME = 0.05
            scale_delta = max(-MAX_SCALE_DELTA_PER_FRAME, min(MAX_SCALE_DELTA_PER_FRAME, scale_delta))

            # Exponential smoothing - purane smoothed value ke saath mix karo,
            # taaki ek-do frame ka noise poore movement ko jerky na banaye.
            a = self._smooth_alpha
            self._dx_smooth = a * dx + (1 - a) * self._dx_smooth
            self._dy_smooth = a * dy + (1 - a) * self._dy_smooth
            self._scale_smooth = a * scale_delta + (1 - a) * self._scale_smooth
            dx, dy, scale_delta = self._dx_smooth, self._dy_smooth, self._scale_smooth

        self._prev_landmarks = landmarks
        return dx, dy, scale_delta

    def close(self):
        self.hands.close()
