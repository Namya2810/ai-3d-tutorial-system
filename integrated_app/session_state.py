"""
session_state.py

Sabhi modules (face, gesture, voice, quiz) yahi ek shared object update karte
hain. Confusion engine isi object ko padh kar score nikalta hai. Isse har
module ko doosre module ke internals jaanne ki zaroorat nahi - sirf isi
"blackboard" object se likho/padho.

CHANGE (task-based interactive session ke liye):
  - mini_tutorials_played: set -> dict (task_id -> play_count). Pehle sirf
    "khula ya nahi" pata chalta tha, ab "KITNI baar khula" bhi pata chalega
    (roadmap requirement: "kitni baar mini tut khula record hona chahiye").
  - current_task_id add kiya - task_engine.py isko set karta hai, avatar
    check-in aur quiz isko padhte hain.

Updates can also arrive from BLE, camera and voice worker threads. A re-entrant
lock protects compound history/counter updates while preserving the existing
simple attribute API used by the UI.
"""

from collections import deque
from dataclasses import dataclass, field
from time import time
from threading import RLock
from app_config import setting


@dataclass
class SessionState:
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    # ---- Kaun / kaunsa content ----
    student_id: str = None
    student_name: str = None
    current_subject_id: int = None
    current_topic_id: int = None
    current_subtopic_id: int = None

    # ---- Face module se (live) ----
    attention_state: str = "neutral"       # "attentive" | "neutral" | "non_attentive"
    emotion: str = "Neutral"

    # ---- Gesture module se (live) ----
    last_gesture: str = "none"
    wrong_gesture_count: int = 0            # expected gesture na milne par teammate isko increment kare

    # ---- Glove hardware se (pulse) ----
    # BLE glove se live value; sensor/contact unavailable ho to None rehta
    # hai aur confusion engine emotion-only fallback par chala jaata hai.
    pulse_bpm: float = None
    _pulse_history: deque = field(default_factory=lambda: deque(maxlen=150))  # ~5s @30Hz

    # ---- Voice module se ----
    help_requests: int = 0
    repeat_requests: int = 0
    voice_hesitation_count: int = 0         # "umm", lambi khamoshi, etc. (abhi manual increment)
    timeout_count: int = 0                  # "late response" trigger (task_engine.handle_timeout)

    # ---- Quiz se ----
    quiz_response_times: list = field(default_factory=list)   # seconds per question
    quiz_wrong_answers: int = 0
    quiz_total_answers: int = 0

    # ---- Main tutorial ke segments/tasks (task_engine.py) ----
    current_segment_id: str = None
    current_task_id: str = None
    # task_id -> kitni baar us task ka mini-tutorial khula (pehle set tha,
    # ab dict hai taaki count bhi track ho)
    mini_tutorials_played: dict = field(default_factory=dict)
    # task_id -> [scores...] - jab bhi current_task_id set hote hue confusion
    # engine compute() chalta hai, us task ke against score yahan jama hota
    # hai. Quiz ki difficulty PER MINI-TUT isi se nikalti hai (roadmap
    # correction: session-wide average nahi, us particular mini-tut ka score).
    task_confusion_scores: dict = field(default_factory=dict)

    # ---- AI Avatar check-in (avatar_checkin.py) ----
    last_checkin_at: float = 0.0            # cooldown taaki avatar baar-baar na tokey
    checkin_in_progress: bool = False

    # ---- Rolling history (confusion engine ke liye) ----
    _emotion_history: deque = field(default_factory=lambda: deque(maxlen=150))  # ~5s @30fps
    _attention_history: deque = field(default_factory=lambda: deque(maxlen=150))
    _live_score_history: deque = field(default_factory=lambda: deque(maxlen=1800))  # ~30 min @1/s

    # ---- Confusion engine ka output (dusre modules yahi padhenge) ----
    # LIVE score - har second update hota hai, avatar check-in trigger karne ke liye
    confusion_score: float = 0.0            # 0.0 (samajh gaya) - 1.0 (bahut confused)
    confusion_score_updated_at: float = field(default_factory=time)

    # ------------------------------------------------------------------
    # Update helpers - VR module ka on_tick() aur Voice module isi ko call karein
    # ------------------------------------------------------------------

    def update_face(self, face_result):
        """face_result: VR module ke FaceModule.process() se mila FaceResult (ya None)."""
        if face_result is None:
            return
        with self._lock:
            self.attention_state = face_result.state
            self.emotion = face_result.emotion
            self._emotion_history.append(face_result.emotion)
            self._attention_history.append(face_result.state)

    def update_gesture(self, gesture_event, expected_gesture=None):
        """gesture_event: VR module ke GestureModule.process() se mila GestureEvent (ya None).
        expected_gesture: agar tutorial step ko pata hai is waqt kaunsa gesture sahi hai
        (jaise "point" tutorial ke is step ke liye), to mismatch count badhta hai.
        """
        if gesture_event is None:
            return
        with self._lock:
            self.last_gesture = gesture_event.gesture
            if expected_gesture and gesture_event.gesture not in (expected_gesture, "none"):
                self.wrong_gesture_count += 1

    def update_pulse(self, bpm):
        """Glove hardware isko call karega (ESP32 se). bpm=None safe hai -
        confusion engine automatically emotion-only fallback pe chala jaata hai."""
        if bpm is None:
            return
        with self._lock:
            self.pulse_bpm = bpm
            self._pulse_history.append(bpm)

    def register_help_request(self):
        with self._lock:
            self.help_requests += 1

    def register_repeat_request(self):
        with self._lock:
            self.repeat_requests += 1

    def register_timeout(self):
        with self._lock:
            self.timeout_count += 1

    def register_quiz_answer(self, correct: bool, response_time_seconds: float):
        with self._lock:
            self.quiz_total_answers += 1
            if not correct:
                self.quiz_wrong_answers += 1
            self.quiz_response_times.append(response_time_seconds)

    def reset_quiz_counters(self):
        """Naya quiz/subtopic shuru hone par purane counters saaf karo, taaki
        purane topic ka confusion naye topic pe carry-over na ho."""
        with self._lock:
            self.quiz_response_times = []
            self.quiz_wrong_answers = 0
            self.quiz_total_answers = 0
            self.wrong_gesture_count = 0
            self.help_requests = 0
            self.repeat_requests = 0

    # ------------------------------------------------------------------
    # Confusion engine yeh helper properties padhta hai
    # ------------------------------------------------------------------

    @property
    def recent_negative_emotion_ratio(self):
        """Pichle ~5 second mein kitna % samay "Confused" ya "Bored/Drowsy/Sad" raha."""
        if not self._emotion_history:
            return 0.0
        negative = sum(
            1 for e in self._emotion_history if e in ("Confused", "Bored/Drowsy/Sad")
        )
        return negative / len(self._emotion_history)

    @property
    def recent_non_attentive_ratio(self):
        if not self._attention_history:
            return 0.0
        non_attentive = sum(1 for a in self._attention_history if a == "non_attentive")
        return non_attentive / len(self._attention_history)

    # Resting/elevated bpm baseline - rough starting point (roadmap: tune
    # once real glove data comes in from students, same as WEIGHTS elsewhere).
    RESTING_BPM = float(setting("pulse", "resting_bpm"))
    ELEVATED_BPM = float(setting("pulse", "elevated_bpm"))

    @property
    def pulse_stress_ratio(self):
        """0.0 (resting) - 1.0 (elevated/stressed). None if glove not connected yet -
        confusion_engine treats None specially (emotion-only fallback)."""
        if self.pulse_bpm is None:
            return None
        span = self.ELEVATED_BPM - self.RESTING_BPM
        ratio = (self.pulse_bpm - self.RESTING_BPM) / span
        return max(0.0, min(1.0, ratio))

    def record_task_confusion(self, task_id, score):
        """confusion_engine.compute() ke har tick pe, jo bhi task abhi active hai
        uske against score jama karo. Isi se PER-MINI-TUT confusion niklega."""
        if not task_id:
            return
        with self._lock:
            self.task_confusion_scores.setdefault(task_id, []).append(score)

    def task_confusion_score(self, task_id, default=0.5):
        """Ek particular task/mini-tut ka confusion score (0.0-1.0), uske saare
        recorded ticks ka average. Kabhi record hi nahi hua to neutral default (0.5)."""
        with self._lock:
            scores = list(self.task_confusion_scores.get(task_id, ()))
            if not scores:
                return default
            return sum(scores) / len(scores)

    @property
    def quiz_accuracy(self):
        if self.quiz_total_answers == 0:
            return 1.0  # abhi data nahi hai - assume theek hai (confusion mein add mat karo)
        return 1.0 - (self.quiz_wrong_answers / self.quiz_total_answers)

    @property
    def avg_response_time(self):
        if not self.quiz_response_times:
            return 0.0
        return sum(self.quiz_response_times) / len(self.quiz_response_times)

    def mini_tutorials_played_ratio(self, total_tasks):
        """Kitne fraction tasks ke mini-tutorials khulne pade - session ke
        end mein overall confusion summary ke liye use hota hai (live score
        se alag - live score sirf abhi ke signals dekhta hai)."""
        if not total_tasks:
            return 0.0
        return len(self.mini_tutorials_played) / total_tasks

    def total_mini_tutorial_plays(self):
        """Total kitni baar (sab tasks milaake) koi mini-tutorial khula -
        roadmap ka 'kitni baar khule' wala raw count."""
        with self._lock:
            return sum(self.mini_tutorials_played.values())

    def record_live_score(self, score):
        with self._lock:
            self._live_score_history.append(score)

    @property
    def avg_live_score(self):
        if not self._live_score_history:
            return 0.0
        return sum(self._live_score_history) / len(self._live_score_history)
