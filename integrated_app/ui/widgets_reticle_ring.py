"""
widgets_reticle_ring.py

AXIOM UI se liya gaya circular progress ring - confusion score, quiz score,
mastery % dikhane ke liye achha hai (jaise QuizPage/ProgressPage/ProfilePage
mein). Sirf ek naya widget hai - koi existing page abhi isse use nahi
karti, jab chaho tab apni page mein import karke use karo.

Example use (kisi page ke andar):
    from widgets_reticle_ring import ReticleRing
    ring = ReticleRing(value=72, size=90, color="#4FD1FF")
    layout.addWidget(ring)
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QRectF

from .theme_extras import BORDER, CYAN, TEXT_PRIMARY, FONT_DISPLAY


class ReticleRing(QWidget):
    """Dark circular ring with a colored progress arc, and a label in the
    center. value: 0-100, or None to show a dash '-' (unknown/not-live)."""

    def __init__(self, value=0, size=110, thickness=8, color=CYAN, unit="%",
                 center_text=None, parent=None):
        super().__init__(parent)
        self._value = value
        self._color = QColor(color)
        self._thickness = thickness
        self._unit = unit
        self._center_text = center_text
        self.setFixedSize(size, size)

    def setValue(self, value):
        self._value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pad = self._thickness
        rect = QRectF(pad, pad, w - 2 * pad, h - 2 * pad)

        track_pen = QPen(QColor(BORDER))
        track_pen.setWidth(self._thickness)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self._value is not None:
            arc_pen = QPen(self._color)
            arc_pen.setWidth(self._thickness)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            span = int(360 * 16 * (self._value / 100.0))
            painter.drawArc(rect, 90 * 16, -span)

        painter.setPen(QColor(TEXT_PRIMARY))
        if self._center_text is not None:
            text = self._center_text
        elif self._value is None:
            text = "-"
        else:
            text = f"{int(self._value)}{self._unit}"

        font = QFont(FONT_DISPLAY.split(",")[0])
        font.setPointSize(max(10, int(w / 6)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
