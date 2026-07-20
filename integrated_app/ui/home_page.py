from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from .widgets_cards import stat_card, tutorial_card


class HomePage(QWidget):
    # app_window.py isko sunta hai - "biology" | "physics" | "chemistry"
    subject_selected = pyqtSignal(str)

    def __init__(self, session_state=None):
        super().__init__()
        self.setObjectName("HomePage")
        self.session_state = session_state

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        title = QLabel("Welcome to the AI 3D Tutorial System")
        title.setObjectName("HomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            "Watch the 3D model, control it with gestures, ask questions with\n"
            "your voice, and take adaptive quizzes - all in one place."
        )
        subtitle.setObjectName("HomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        self.confusion_card = stat_card("CONFUSION SCORE", "-", "session average", ring_value=0, ring_color="#4FD1FF")
        self.mini_card = stat_card("MINI-TUTORIALS", "0", "played this session")
        self.quiz_card = stat_card("QUIZ ACCURACY", "-", "last attempt", ring_value=0, ring_color="#34d399")
        stats_row.addWidget(self.confusion_card)
        stats_row.addWidget(self.mini_card)
        stats_row.addWidget(self.quiz_card)
        layout.addLayout(stats_row)

        section_label = QLabel("Choose a subject to start")
        section_label.setObjectName("SectionTitle")
        layout.addWidget(section_label)

        subjects_row = QHBoxLayout()
        subjects_row.setSpacing(16)

        biology_card = tutorial_card("BIOLOGY", "Kidney Dissection", "🫘", progress=0)
        biology_card.clicked.connect(lambda: self.subject_selected.emit("biology"))
        subjects_row.addWidget(biology_card)

        physics_card = tutorial_card("PHYSICS", "Gearbox Dissection", "⚙️", progress=0)
        physics_card.clicked.connect(lambda: self.subject_selected.emit("physics"))
        subjects_row.addWidget(physics_card)

        chemistry_card = tutorial_card("CHEMISTRY", "Acid-Base Titration", "🧪", progress=0)
        chemistry_card.clicked.connect(lambda: self.subject_selected.emit("chemistry"))
        subjects_row.addWidget(chemistry_card)

        layout.addLayout(subjects_row)

        self.refresh_stats()

    def refresh_stats(self):
        """Render current in-memory session results whenever Home is shown."""
        state = self.session_state
        if state is None:
            return

        has_confusion = bool(state._live_score_history)
        confusion = round(state.avg_live_score * 100) if has_confusion else None
        self.confusion_card.value_label.setText(
            f"{confusion}%" if confusion is not None else "-"
        )
        if self.confusion_card.ring is not None:
            self.confusion_card.ring.setValue(confusion)

        self.mini_card.value_label.setText(str(state.total_mini_tutorial_plays()))

        has_quiz = state.quiz_total_answers > 0
        accuracy = round(state.quiz_accuracy * 100) if has_quiz else None
        self.quiz_card.value_label.setText(
            f"{accuracy}%" if accuracy is not None else "-"
        )
        if self.quiz_card.ring is not None:
            self.quiz_card.ring.setValue(accuracy)
