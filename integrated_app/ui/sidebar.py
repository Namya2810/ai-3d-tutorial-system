from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal


class Sidebar(QWidget):
    home_clicked = pyqtSignal()
    tutorial_clicked = pyqtSignal()
    assistant_clicked = pyqtSignal()
    quiz_clicked = pyqtSignal()
    profile_clicked = pyqtSignal()
    anaglyph_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(10)

        title = QPushButton("AI 3D Tutor")
        title.setEnabled(False)
        title.setObjectName("SidebarTitle")

        home_btn = QPushButton("Home")
        tutorial_btn = QPushButton("3D Tutorial")
        assistant_btn = QPushButton("AI Assistant")
        quiz_btn = QPushButton("Quiz")
        profile_btn = QPushButton("Profile")
        self.anaglyph_btn = QPushButton("3D Glasses: OFF")
        self.anaglyph_btn.setCheckable(True)
        self.anaglyph_btn.toggled.connect(self._on_anaglyph_toggled)

        for btn in (home_btn, tutorial_btn, assistant_btn, quiz_btn, profile_btn):
            btn.setObjectName("SidebarButton")

        home_btn.clicked.connect(self.home_clicked.emit)
        tutorial_btn.clicked.connect(self.tutorial_clicked.emit)
        assistant_btn.clicked.connect(self.assistant_clicked.emit)
        quiz_btn.clicked.connect(self.quiz_clicked.emit)
        profile_btn.clicked.connect(self.profile_clicked.emit)

        layout.addWidget(title)
        layout.addWidget(home_btn)
        layout.addWidget(tutorial_btn)
        layout.addWidget(assistant_btn)
        layout.addWidget(quiz_btn)
        layout.addWidget(profile_btn)
        layout.addStretch()
        layout.addWidget(self.anaglyph_btn)

        self.setLayout(layout)

    def _on_anaglyph_toggled(self, enabled):
        self.anaglyph_btn.setText("3D Glasses: ON" if enabled else "3D Glasses: OFF")
        self.anaglyph_toggled.emit(enabled)
