"""
widgets_common.py

AXIOM UI se liye gaye chhote reusable widgets - badges, subject-tags,
status-pills, HUD-style corner brackets. Ye sab optional hain - kisi
existing page mein use karna ho to import karke lagao, warna kuch nahi
badlega.
"""
from PyQt6.QtWidgets import QLabel, QFrame, QHBoxLayout
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, pyqtSignal

from .theme_extras import CYAN, SUBJECT_COLORS


class ClickableCard(QFrame):
    """QFrame jo click-able hai - mouse hover pe hand-cursor dikhata hai aur
    click hone par 'clicked' signal emit karta hai. tutorial_card() (subject
    selector cards) isi se banti hai."""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def make_badge(text: str, kind: str = "sample") -> QLabel:
    """kind: 'sample' (amber) ya 'live' (green). QSS mein #BadgeSample/#BadgeLive
    object names use hote hain (styles_addon.qss mein defined)."""
    lbl = QLabel(text)
    lbl.setObjectName("BadgeSample" if kind == "sample" else "BadgeLive")
    return lbl


def make_subject_tag(subject: str) -> QLabel:
    """Physics/Chemistry/Biology jaisa chhota colored tag - subject-selector
    ya tutorial cards ke liye."""
    color = SUBJECT_COLORS.get(subject.upper(), CYAN)
    lbl = QLabel(subject.upper())
    lbl.setObjectName("SubjectTag")
    c = QColor(color)
    lbl.setStyleSheet(
        f"color: {color}; background-color: rgba({c.red()},{c.green()},{c.blue()},0.14);"
        f"border: 1px solid {color};"
    )
    return lbl


def make_status_dot(color: str, size: int = 8) -> QLabel:
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet(f"background-color: {color}; border-radius: {size // 2}px;")
    return lbl


class StatusPill(QFrame):
    """Chhoti rounded pill, colored dot + label - jaise topbar mein
    'Confusion: Low' ya 'Gesture source: camera' dikhane ke liye."""

    def __init__(self, text: str, dot_color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPill")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(6)
        lay.addWidget(make_status_dot(dot_color))
        label = QLabel(text)
        label.setObjectName("StatusPillText")
        lay.addWidget(label)


class CornerBracketFrame(QFrame):
    """Viewfinder-style corner brackets - 3D viewer ke around HUD look ke
    liye use kiya ja sakta hai (purely decorative, koi logic nahi)."""

    def __init__(self, color=CYAN, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setStyleSheet("background-color: #05070c; border-radius: 8px;")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color)
        pen.setWidth(2)
        painter.setPen(pen)

        L, m = 22, 10
        w, h = self.width(), self.height()

        painter.drawLine(m, m, m + L, m)
        painter.drawLine(m, m, m, m + L)
        painter.drawLine(w - m, m, w - m - L, m)
        painter.drawLine(w - m, m, w - m, m + L)
        painter.drawLine(m, h - m, m + L, h - m)
        painter.drawLine(m, h - m, m, h - m - L)
        painter.drawLine(w - m, h - m, w - m - L, h - m)
        painter.drawLine(w - m, h - m, w - m, h - m - L)
