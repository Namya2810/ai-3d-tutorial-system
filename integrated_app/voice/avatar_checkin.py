"""
avatar_checkin.py

Roadmap point #3 - "confusion detect hote hi AI teacher poochta hai
'clear ho?'". Teacher avatar khud static hai (movement/animation nahi
chahiye - Namya ne clarify kiya) - sirf voice + on-screen text bubble
badalta hai. Us text-bubble ka call tutorial_3d.html mein hai
(showTeacherPrompt/hideTeacherPrompt) - is thread ka result us JS ko
trigger karta hai (app_window.py se).

CHANGE: pehle ye generic "Are you clear with {segment_title}?" poochta
tha. Ab current TASK ka concept poochta hai (jaise "Do you know what the
aorta is?"), taaki confusion-checkin aur naya-task-assign dono ek jaisा
"teacher" experience dें, jaisa Namya ne bola.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from speech_to_text import SpeechRecognizer
from intent_detector import IntentDetector
from text_to_speech import speak


class AvatarCheckinThread(QThread):
    """Ek baar chalta hai: poochta hai "Do you know X?", sunta hai,
    result emit karke khatam ho jaata hai (VoiceConversationThread jaisa loop
    nahi hai - ye ek single check-in hai)."""

    result_ready = pyqtSignal(str)  # "yes" | "no" | "no_response"
    transcript_updated = pyqtSignal(str)
    listening_started = pyqtSignal()

    def __init__(self, concept_hint="", question_text=None):
        super().__init__()
        # question_text diya ho to seedha wahi bolo (task-specific check-in).
        # Warna concept_hint se ek generic sawaal bana lo (backward-compatible
        # fallback agar kahin purana call bacha ho).
        self.question_text = question_text or (
            f"Do you know about {concept_hint}?" if concept_hint else "Are you clear with this?"
        )
        self.recognizer = SpeechRecognizer(timeout=4, phrase_time_limit=5)
        self.intent = IntentDetector()

    def run(self):
        speak(self.question_text)
        self.transcript_updated.emit("Listening for yes or no...")
        self.listening_started.emit()

        # A single noisy/empty microphone window should not silently dismiss
        # the check-in. Give the learner up to three short attempts and show
        # exactly what was recognised after each one.
        for attempt in range(3):
            if self.isInterruptionRequested():
                self.result_ready.emit("no_response")
                return
            try:
                text = self.recognizer.listen()
            except Exception:
                text = ""
            if not text:
                self.transcript_updated.emit(
                    "I didn't hear that. Please say YES or NO."
                )
                continue
            self.transcript_updated.emit(f"You said: {text}")
            result = self.intent.detect_yes_no(text)
            if result == "YES":
                self.result_ready.emit("yes")
                return
            if result == "NO":
                self.result_ready.emit("no")
                return
            self.transcript_updated.emit(
                f"Heard: {text}. Please answer only YES or NO."
            )
        self.result_ready.emit("no_response")
