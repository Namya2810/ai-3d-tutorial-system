"""
task_voice_thread.py

AvatarCheckinThread jaisa hi pattern (background thread, kyunki speak()/
listen() blocking calls hain aur GUI freeze nahi karni). Fark itna hai:
ye avatar ka generic "clear ho gaya?" nahi poochta - ye current TASK ka
asli question poochta hai aur uska jawaab answer_checker.py se check
karta hai.

app_window.py isse tabhi chalata hai jab task_engine.current_task()['type']
== 'voice_question' ho.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from speech_to_text import SpeechRecognizer
from text_to_speech import speak
from answer_checker import check_answer


class PromptSpeechThread(QThread):
    """Read a non-voice task prompt without blocking the GUI/camera loop."""

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        speak(self.text)


class TaskVoiceThread(QThread):
    # (correct: bool, heard_text: str) - heard_text UI mein dikhane ke
    # liye useful hai ("Tumne kaha: ...")
    result_ready = pyqtSignal(bool, str)
    transcript_updated = pyqtSignal(str)
    listening_started = pyqtSignal()

    def __init__(self, task):
        super().__init__()
        self.task = task
        self.recognizer = SpeechRecognizer()

    def run(self):
        speak(self.task["prompt"])
        self.transcript_updated.emit("Listening...")
        self.listening_started.emit()

        # Silence from one short microphone window is not a wrong answer.
        # Keep listening until the learner speaks or the UI timer requests
        # interruption. The timer owns the actual no-response decision.
        while not self.isInterruptionRequested():
            try:
                text = self.recognizer.listen()
            except Exception:
                text = ""
            if not text:
                self.msleep(150)
                continue

            self.transcript_updated.emit(f"You said: {text}")
            correct = check_answer(text, self.task)
            self.result_ready.emit(correct, text)
            return
