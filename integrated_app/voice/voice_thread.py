from PyQt6.QtCore import QThread, pyqtSignal

from speech_to_text import SpeechRecognizer
from intent_detector import IntentDetector
from gemini_ai import ask_ai
from text_to_speech import speak


class VoiceConversationThread(QThread):
    """Runs listen -> detect intent -> respond -> speak, on repeat,
    in the background so the GUI stays responsive.

    session_state: shared SessionState instance (optional). Har HELP/REPEAT
    intent detect hone par isko register kiya jaata hai, taaki
    confusion_engine.py isko dekh sake.
    """

    message_received = pyqtSignal(str)   # what the user said
    ai_response = pyqtSignal(str)        # what the AI replied
    status_update = pyqtSignal(str)      # e.g. "Listening...", mic errors
    stopped = pyqtSignal()               # emitted when the loop has fully ended

    def __init__(self, session_state=None):
        super().__init__()
        self.recognizer = SpeechRecognizer()
        self.intent = IntentDetector()
        self.session_state = session_state
        self._running = False

    def run(self):
        self._running = True
        self.status_update.emit("Listening...")

        while self._running:
            try:
                text = self.recognizer.listen()
            except Exception as e:
                self.status_update.emit(f"Microphone error: {e}")
                continue

            if not self._running:
                break

            if not text:
                # Nothing understood this cycle; keep listening
                continue

            self.message_received.emit(text)
            result = self.intent.detect(text)

            if result == "STOP":
                reply = "Goodbye."
                self.ai_response.emit(reply)
                speak(reply)
                break

            elif result == "YES":
                reply = "Opening next lesson."
                self.ai_response.emit(reply)
                speak(reply)

            elif result == "NO":
                reply = "Okay. Please ask your question."
                self.ai_response.emit(reply)
                speak(reply)

            elif result == "REPEAT":
                if self.session_state:
                    self.session_state.register_repeat_request()
                reply = "Repeating the previous lesson."
                self.ai_response.emit(reply)
                speak(reply)

            else:  # HELP or EXPLAIN
                if self.session_state and result == "HELP":
                    self.session_state.register_help_request()
                try:
                    reply = ask_ai(text)
                except Exception as e:
                    reply = f"Sorry, I couldn't reach the AI service. ({e})"
                self.ai_response.emit(reply)
                speak(reply)

            if self._running:
                self.status_update.emit("Listening...")

        self._running = False
        self.stopped.emit()

    def stop(self):
        """Ask the loop to stop. It will finish after the current
        listen/respond cycle (up to a few seconds)."""
        self._running = False
