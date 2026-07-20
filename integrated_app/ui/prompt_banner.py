"""
prompt_banner.py  (NEW FILE - additive, koi existing file touch nahi hui)

Avatar + speech-bubble banner jo har task/question ke START mein dikhta
hai. Image already-drawn bubble ke saath aati hai (avatar_banner.png,
transparent bg) - hum sirf us bubble ke andar text overlay karte hain
(bubble ke coordinates image ko measure karke nikale gaye hain, isliye
fraction-based hain, resize par bhi sahi rehte hain).

Flow (jaisa Namya ne bataya):
  1. Task/question start -> show_prompt(text, mode) call karo
  2. mode="question" -> banner CONSTANT rehta hai jab tak voice answer
     na aa jaye. Saath hi update_transcript() se live STT caption
     avatar ke NEECHE dikhti rehti hai.
  3. mode="task" -> banner dikhne ke turant baad, jab interactive
     gesture session actually shuru ho jaye, caller khud hide_banner()
     call kare (is widget ko khud pata nahi ki gesture session kab
     shuru hua - wo app_window.py/tutorial_3d_page.py decide karega).
  4. Jab galat answer/gesture aaye aur mini-tutorial dikhana ho, is
     banner ko hide_banner() karke MiniTutorialPage dikhao.

Integration (app_window.py mein, koi guess nahi kiya isse zyada
kyunki wo file abhi mere paas nahi hai):
    self.prompt_banner = PromptBanner()
    # kahin bhi stack/overlay mein add karo (QStackedLayout ya
    # ek transparent overlay widget ke andar current page ke upar)
    self.prompt_banner.show_prompt(task["prompt"], mode="question")
    ...
    self.prompt_banner.update_transcript(partial_stt_text)   # STT thread se
    ...
    self.prompt_banner.hide_banner()   # task interactive session shuru hote hi
"""

import os

from PyQt6.QtCore import Qt, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)

# NOTE: project ROOT ke relative path (jaisa task_engine.py ke
# "mini_tutorial_video" mein hai) - CWD se resolve hota hai, is file
# (ui/prompt_banner.py) ke relative NAHI, warna galat folder dhoondega.
UI_DIR = os.path.dirname(os.path.abspath(__file__))
AVATAR_PATH = os.path.join(UI_DIR, "static", "img", "avatar_banner.png")

# avatar_banner.png (1600x900) ke andar speech-bubble ka text-safe area,
# image ke fraction mein (measure karke nikala gaya - tail/pointer ke
# liye neeche thoda extra inset diya hai)
# Keep text inside the rectangular body of the speech bubble.  The old x0
# included the left-pointing tail, which is why long task text escaped across
# the teacher's face even though QLabel word-wrap was enabled.
BUBBLE_TEXT_FRACT = {"x0": 0.485, "y0": 0.105, "x1": 0.855, "y1": 0.310}


class PromptBanner(QWidget):
    choice_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PromptBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._avatar_pixmap = QPixmap(AVATAR_PATH)
        self._mode = "question"

        # Avatar image (bubble bhi isi image ke andar bana hua hai)
        self.avatar_label = QLabel(self)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setMinimumSize(0, 0)
        self.avatar_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )

        # Bubble ke andar text - avatar_label ke UPAR floats (geometry
        # resizeEvent mein set hoti hai, layout mein nahi)
        self.bubble_text_label = QLabel(self)
        self.bubble_text_label.setWordWrap(True)
        self.bubble_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble_text_label.setStyleSheet(
            "color: #1a1a2e; font-family: 'Segoe UI'; font-size: 20px; font-weight: 650; background: transparent;"
        )

        self.context_label = QLabel("", self)
        self.context_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.context_label.setStyleSheet(
            "color:#315B86; font-family:'JetBrains Mono'; font-size:13px; "
            "font-weight:800; letter-spacing:1px; background:transparent;"
        )

        # Live STT caption - avatar ke NEECHE, sirf question mode mein
        self.transcript_label = QLabel("", self)
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label.setObjectName("TranscriptLabel")
        self.transcript_label.setStyleSheet(
            "color: #E7ECF2; background: rgba(17,24,35,0.75); border-radius: 8px; "
            "padding: 8px 14px; font-family: 'JetBrains Mono'; font-size: 13px;"
        )
        self.transcript_label.setVisible(False)

        self.choice_widget = QWidget(self)
        choice_layout = QHBoxLayout(self.choice_widget)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(14)
        self.yes_button = QPushButton("Yes - show explanation")
        self.no_button = QPushButton("No - continue task")
        for button in (self.yes_button, self.no_button):
            button.setMinimumHeight(46)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { color:#06111B; background:#4CC9F0; "
                "border:2px solid #9BE7FF; border-radius:12px; "
                "font:700 15px 'Segoe UI'; padding:8px 18px; }"
                "QPushButton:hover { background:#83DCF7; }"
                "QPushButton:pressed { background:#27AAD5; }"
            )
            choice_layout.addWidget(button)
        self.yes_button.clicked.connect(lambda: self.choice_selected.emit("yes"))
        self.no_button.clicked.connect(lambda: self.choice_selected.emit("no"))
        self.choice_widget.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.addWidget(self.avatar_label, stretch=1)
        layout.addWidget(self.transcript_label)
        layout.addWidget(self.choice_widget)

        self.hide()

    # ---- Public API ------------------------------------------------

    def show_prompt(
        self, text: str, mode: str = "question", context_label: str = "",
        choices: bool = False,
    ):
        """mode: 'question' -> transcript area bhi dikhega aur banner
        tab tak rahega jab tak caller khud hide na kare.
        mode: 'task' -> sirf prompt dikhta hai, transcript area chhupa
        rehta hai; caller interactive session shuru hote hi hide_banner()
        bulaye."""
        self._mode = mode
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.bubble_text_label.setText(text)
        self.context_label.setText(context_label.upper() if context_label else "")
        self.context_label.setVisible(bool(context_label))
        self.transcript_label.setVisible(mode == "question")
        self.choice_widget.setVisible(bool(choices))
        if mode == "question":
            self.transcript_label.setText("Listening...")
        self.show()
        self.raise_()
        # Showing/hiding the transcript changes avatar_label's height. Wait
        # until Qt completes that layout pass, then rescale the PNG to the
        # actual available rectangle so its right edge cannot be clipped.
        self.layout().activate()
        QTimer.singleShot(0, self._refresh_avatar_layout)

    def update_transcript(self, partial_text: str):
        """Voice/STT thread se baar-baar call karo jab tak student bol
        raha hai - live caption avatar ke neeche update hoti rahegi."""
        if self._mode != "question":
            return
        self.transcript_label.setText(partial_text if partial_text else "Listening...")

    def hide_banner(self):
        self.choice_widget.setVisible(False)
        self.hide()

    # ---- Positioning (bubble text ko image ke andar sahi jagah rakhna) --

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_avatar_layout()

    def _refresh_avatar_layout(self):
        """Scale and position against the avatar label's current geometry."""
        if not self._avatar_pixmap.isNull():
            # Extra safety margin: the overlay must never inherit a width that
            # visually touches the screen edge, even at Windows display scale.
            target_w = max(1, int(self.avatar_label.width() * 0.86))
            target_h = max(1, int(self.avatar_label.height() * 0.92))
            scaled = self._avatar_pixmap.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.avatar_label.setPixmap(scaled)
        self._reposition_bubble_text()

    def _reposition_bubble_text(self):
        pm = self.avatar_label.pixmap()
        if pm is None or pm.isNull():
            return

        label_area = self.avatar_label.geometry()
        img_w, img_h = pm.width(), pm.height()
        # Pixmap is centered with KeepAspectRatio, so use the real painted
        # image rectangle rather than assuming top/right alignment.
        off_x = label_area.x() + (label_area.width() - img_w) / 2
        off_y = label_area.y() + (label_area.height() - img_h) / 2

        x0 = off_x + BUBBLE_TEXT_FRACT["x0"] * img_w
        y0 = off_y + BUBBLE_TEXT_FRACT["y0"] * img_h
        x1 = off_x + BUBBLE_TEXT_FRACT["x1"] * img_w
        y1 = off_y + BUBBLE_TEXT_FRACT["y1"] * img_h

        box_h = y1 - y0
        context_h = box_h * 0.20 if self.context_label.isVisible() else 0
        self.context_label.setGeometry(
            QRect(int(x0), int(y0), int(x1 - x0), int(context_h))
        )
        rect = QRect(
            int(x0), int(y0 + context_h), int(x1 - x0), int(box_h - context_h)
        )
        self.bubble_text_label.setGeometry(rect)
        # font size image ke scale ke hisaab se thoda adjust karo (chhoti
        # window mein text overflow na ho)
        font = self.bubble_text_label.font()
        font_px = max(17, min(22, int(img_h * 0.034)))
        font.setPixelSize(font_px)
        self.bubble_text_label.setFont(font)
