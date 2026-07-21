"""
face_module.py  (Phase 3 - Face Analysis) - INTEGRATED VERSION

Tumhare camera-manager architecture + smoothing/debounce + dost ke
richer multi-signal emotion classification ko jod ke bana hai.

Do cheezein return hoti hain FaceResult mein:
    1. state   -> "attentive" / "neutral" / "non_attentive"  (Confusion Detection ke liye)
    2. emotion -> "Happy/Excited", "Bored/Drowsy/Sad", "Confused", "Focused/Attentive", "Neutral"
                  (dost ke multi-signal rule se: eyes + mouth + eyebrows + head-drop)
"""

import math
from collections import deque, Counter
from dataclasses import dataclass

import cv2
import mediapipe as mp

# ---------- Landmark indices (MediaPipe Face Mesh, refine_landmarks=False) ----------

LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
MOUTH_TOP_BOTTOM = (13, 14)
MOUTH_CORNERS = (61, 291)
LEFT_EYEBROW_INNER, LEFT_EYE_TOP = 105, 159
RIGHT_EYEBROW_INNER, RIGHT_EYE_TOP = 334, 386
INNER_BROW_L, INNER_BROW_R = 55, 285
NOSE_TIP, CHIN = 1, 152
LEFT_FACE_EDGE, RIGHT_FACE_EDGE = 234, 454

# ---------- Thresholds (attentive/non_attentive state ke liye) ----------

EAR_CLOSED_THRESHOLD = 0.19
EAR_HISTORY_LEN = 5
BLINK_MAX_FRAMES = 6
CLOSED_SUSTAINED_FRAMES = 15
YAW_ATTENTIVE_RANGE = (0.6, 1.65)
YAW_NEUTRAL_RANGE = (0.4, 2.2)

# Emotion label ko stabilize karne ke liye majority-vote window
EMOTION_VOTE_WINDOW = 15


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def _eye_aspect_ratio(landmarks, eye_indices):
    p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in eye_indices]
    vertical = _dist(p2, p6) + _dist(p3, p5)
    horizontal = _dist(p1, p4)
    return vertical / (2.0 * horizontal) if horizontal else 0.3


def _head_yaw_ratio(landmarks):
    nose = landmarks[NOSE_TIP]
    left = landmarks[LEFT_FACE_EDGE]
    right = landmarks[RIGHT_FACE_EDGE]
    d_left = _dist(nose, left) or 1e-6
    d_right = _dist(nose, right) or 1e-6
    return d_left / d_right


def _classify_emotion(landmarks, ear):
    """Dost ka multi-signal emotion classifier - mouth, eyebrow, furrow, head-drop
    milakar ek zyada nuanced emotion label deta hai (sirf attentive/non-attentive
    se aage)."""
    face_width = _dist(landmarks[LEFT_FACE_EDGE], landmarks[RIGHT_FACE_EDGE]) or 1e-6

    top, bottom = landmarks[MOUTH_TOP_BOTTOM[0]], landmarks[MOUTH_TOP_BOTTOM[1]]
    mar = _dist(top, bottom) / face_width  # mouth open kitna hai

    left_corner, right_corner = landmarks[MOUTH_CORNERS[0]], landmarks[MOUTH_CORNERS[1]]
    mouth_width = _dist(left_corner, right_corner) / face_width

    brow_raise = (
        _dist(landmarks[LEFT_EYEBROW_INNER], landmarks[LEFT_EYE_TOP]) +
        _dist(landmarks[RIGHT_EYEBROW_INNER], landmarks[RIGHT_EYE_TOP])
    ) / (2.0 * face_width)

    furrow = _dist(landmarks[INNER_BROW_L], landmarks[INNER_BROW_R]) / face_width

    head_drop = (landmarks[CHIN].y - landmarks[NOSE_TIP].y) / face_width

    if ear < 0.18:
        return "Bored/Drowsy/Sad"
    if mar > 0.055 and (brow_raise > 0.30 or mouth_width > 0.42):
        return "Happy/Excited/Surprised"
    if furrow < 0.24 and brow_raise < 0.26:
        return "Confused"
    if ear < 0.24 and head_drop < 0.22:
        return "Bored/Drowsy/Sad"
    if 0.24 <= ear <= 0.34 and head_drop >= 0.22:
        return "Focused/Attentive"
    return "Neutral"


@dataclass
class FaceResult:
    landmarks: object
    ear: float = 0.0
    yaw_ratio: float = 1.0
    eyes_closed: bool = False
    state: str = "neutral"          # "attentive" | "non_attentive" | "neutral"
    emotion: str = "Neutral"        # richer emotion label


class FaceModule:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,  # iris model unreliable is mediapipe version pe - off
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3,
        )
        self.debug_draw = False
        self._last_status = None

        self._ear_history = deque(maxlen=EAR_HISTORY_LEN)
        self._closed_frame_count = 0
        self._last_state = "neutral"
        self._last_reported_state = None

        self._emotion_history = deque(maxlen=EMOTION_VOTE_WINDOW)
        self._confirmed_emotion = "Neutral"

    def process(self, frame):
        """
        frame: CameraManager.get_frame() se mila hua BGR image
        return: FaceResult. Face na mile to explicit ``face_lost`` state,
        so poor lighting/camera loss is distinguishable from neutral attention.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            if self._last_status is not False:
                print("[FaceModule] Face NOT detected")
                self._last_status = False
            self._closed_frame_count = 0
            self._ear_history.clear()
            return FaceResult(
                landmarks=None,
                state="face_lost",
                emotion="Face not detected",
            )

        if self._last_status is not True:
            print("[FaceModule] Face detected")
            self._last_status = True

        face_landmarks_obj = results.multi_face_landmarks[0]
        landmarks = face_landmarks_obj.landmark

        face_result = self._classify_attention(landmarks)

        if self.debug_draw:
            self._draw_debug(frame, face_landmarks_obj, face_result)

        if face_result.state != self._last_reported_state:
            print(f"[FaceModule] Attention: {face_result.state}  "
                  f"(EAR={face_result.ear:.3f}, yaw={face_result.yaw_ratio:.2f})")
            self._last_reported_state = face_result.state

        return face_result

    def _classify_attention(self, landmarks):
        left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE)
        right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE)
        ear = (left_ear + right_ear) / 2.0
        self._ear_history.append(ear)
        smoothed_ear = sum(self._ear_history) / len(self._ear_history)

        yaw_ratio = _head_yaw_ratio(landmarks)

        eyes_closed_now = smoothed_ear < EAR_CLOSED_THRESHOLD
        if eyes_closed_now:
            self._closed_frame_count += 1
        else:
            self._closed_frame_count = 0

        yaw_lo, yaw_hi = YAW_ATTENTIVE_RANGE
        neutral_lo, neutral_hi = YAW_NEUTRAL_RANGE

        if not (neutral_lo <= yaw_ratio <= neutral_hi):
            state = "non_attentive"
        elif self._closed_frame_count > CLOSED_SUSTAINED_FRAMES:
            state = "non_attentive"
        elif not (yaw_lo <= yaw_ratio <= yaw_hi):
            state = "neutral"
        elif eyes_closed_now and self._closed_frame_count <= BLINK_MAX_FRAMES:
            state = self._last_state
        else:
            state = "attentive"

        self._last_state = state

        # Emotion label - dost ke multi-signal rule se, majority-vote se stabilize kiya
        raw_emotion = _classify_emotion(landmarks, smoothed_ear)
        self._emotion_history.append(raw_emotion)
        if len(self._emotion_history) == EMOTION_VOTE_WINDOW:
            self._confirmed_emotion = Counter(self._emotion_history).most_common(1)[0][0]

        return FaceResult(
            landmarks=landmarks,
            ear=ear,
            yaw_ratio=yaw_ratio,
            eyes_closed=eyes_closed_now,
            state=state,
            emotion=self._confirmed_emotion,
        )

    def _draw_debug(self, frame, face_landmarks_obj, face_result):
        self.mp_drawing.draw_landmarks(
            image=frame,
            landmark_list=face_landmarks_obj,
            connections=self.mp_face_mesh.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self.mp_drawing.DrawingSpec(thickness=1, circle_radius=1),
        )
        h, w, _ = frame.shape
        label = f"{face_result.state.upper()} | {face_result.emotion}  EAR:{face_result.ear:.2f}"
        color = {
            "attentive": (0, 220, 0),
            "neutral": (0, 200, 220),
            "non_attentive": (0, 0, 230),
        }.get(face_result.state, (255, 255, 255))
        cv2.putText(frame, label, (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    def close(self):
        self.face_mesh.close()
