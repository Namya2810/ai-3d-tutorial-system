from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel
)

from gemini_ai import ask_ai
from intent_detector import IntentDetector
from voice_thread import VoiceConversationThread


class AssistantPanel(QWidget):
    def __init__(self, session_state=None):
        super().__init__()
        self.setObjectName("AssistantPanel")

        self.session_state = session_state
        self.voice_thread = None
        self.intent = IntentDetector()

        layout = QVBoxLayout(self)

        title = QLabel("AI Assistant")
        title.setObjectName("PageTitle")

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setObjectName("ChatBox")

        input_row = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type your question...")
        self.send_btn = QPushButton("Send")
        self.mic_btn = QPushButton("Mic (one question)")
        self.conversation_btn = QPushButton("Start Voice Conversation")

        input_row.addWidget(self.input_box)
        input_row.addWidget(self.send_btn)
        input_row.addWidget(self.mic_btn)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.chat)
        layout.addLayout(input_row)
        layout.addWidget(self.conversation_btn)

        self.send_btn.clicked.connect(self.handle_send)
        self.input_box.returnPressed.connect(self.handle_send)
        self.mic_btn.clicked.connect(self.handle_mic)
        self.conversation_btn.clicked.connect(self.toggle_conversation)

    def add_message(self, sender, message):
        self.chat.append(f"{sender}: {message}")

    # ---- Shared intent handling (used by typed input AND one-shot mic) ----

    def handle_text_input(self, text):
        self.add_message("You", text)

        result = self.intent.detect(text)

        if result == "YES":
            self.add_message("AI", "Opening next lesson.")
        elif result == "NO":
            self.add_message("AI", "Okay. Please ask your question.")
        elif result == "REPEAT":
            if self.session_state:
                self.session_state.register_repeat_request()
            self.add_message("AI", "Repeating the previous lesson.")
        elif result == "STOP":
            self.add_message("AI", "Goodbye.")
        else:  # HELP or EXPLAIN
            if self.session_state and result == "HELP":
                self.session_state.register_help_request()
            try:
                answer = ask_ai(text)
            except Exception as e:
                answer = f"Sorry, I couldn't reach the AI service. ({e})"
            self.add_message("AI", answer)

    def handle_send(self):
        question = self.input_box.text().strip()
        if not question:
            return
        self.input_box.clear()
        self.handle_text_input(question)

    def handle_mic(self):
        try:
            from speech_to_text import SpeechRecognizer
            recognizer = SpeechRecognizer()
            text = recognizer.listen()
            if text:
                self.handle_text_input(text)
            else:
                self.add_message("System", "Didn't catch that, please try again.")
        except Exception as e:
            self.add_message("System", f"Microphone error: {e}")

    # ---- Continuous voice conversation flow ----

    def toggle_conversation(self):
        if self.voice_thread is not None and self.voice_thread.isRunning():
            self.status_label.setText("Stopping...")
            self.conversation_btn.setEnabled(False)
            self.voice_thread.stop()
        else:
            self.start_conversation()

    def start_conversation(self):
        self.voice_thread = VoiceConversationThread(session_state=self.session_state)
        self.voice_thread.message_received.connect(lambda text: self.add_message("You", text))
        self.voice_thread.ai_response.connect(lambda text: self.add_message("AI", text))
        self.voice_thread.status_update.connect(self.status_label.setText)
        self.voice_thread.stopped.connect(self.on_conversation_stopped)

        self.voice_thread.start()

        self.conversation_btn.setText("Stop Voice Conversation")
        self.mic_btn.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.input_box.setEnabled(False)

    def on_conversation_stopped(self):
        self.conversation_btn.setText("Start Voice Conversation")
        self.conversation_btn.setEnabled(True)
        self.mic_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setEnabled(True)
        self.status_label.setText("")
        self.voice_thread = None
