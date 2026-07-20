"""
widgets_cards.py

AXIOM UI se liye gaye card-style widgets - HomePage/ProgressPage/ProfilePage
ko polish karne ke liye. tutorial_card() ab CLICKABLE hai (subject selector
ke liye) - clicked hone par uska `clicked` signal fire hota hai, jisse
home_page.py subject_selected signal aage bhejta hai.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt

from .theme_extras import TEXT_SECONDARY, SUBJECT_COLORS
from .widgets_common import make_badge, make_subject_tag, ClickableCard
from .widgets_reticle_ring import ReticleRing


def stat_card(label: str, value: str, caption: str, ring_value=None, ring_color="#4FD1FF"):
    """Chhota stat box - ek number/percentage highlight karne ke liye
    (jaise confusion score, quiz accuracy, mini-tutorials played count).
    Fixed height rakhi gayi hai taaki teeno cards ek row mein same size
    dikhein, chahe text chhota ho ya bada."""
    card = QFrame()
    card.setObjectName("Card")
    card.setFixedHeight(140)

    outer = QHBoxLayout(card)
    outer.setContentsMargins(18, 16, 18, 16)
    outer.setSpacing(14)

    if ring_value is not None:
        ring = ReticleRing(value=ring_value, size=90, thickness=7, color=ring_color)
        outer.addWidget(ring, alignment=Qt.AlignmentFlag.AlignVCenter)

    text_col = QVBoxLayout()
    text_col.setSpacing(4)
    text_col.addStretch(1)

    lbl = QLabel(label)
    lbl.setObjectName("CardLabel")
    text_col.addWidget(lbl)

    v = QLabel(value)
    v.setObjectName("CardValue")
    text_col.addWidget(v)

    c = QLabel(caption)
    c.setObjectName("CardCaption")
    text_col.addWidget(c)

    text_col.addStretch(1)
    outer.addLayout(text_col, stretch=1)

    # Expose the display widgets to dashboard pages so the card can remain a
    # reusable component while its live value/ring are updated in-place.
    card.value_label = v
    card.ring = ring if ring_value is not None else None

    return card


def tutorial_card(subject: str, title: str, icon: str, progress: int = 0):
    """Physics/Chemistry/Biology subject-select cards - CLICKABLE hai,
    click karne par `card.clicked` signal fire hota hai. home_page.py
    isse `subject_selected` signal aage bhejta hai."""
    color = SUBJECT_COLORS.get(subject.upper(), "#4FD1FF")
    card = ClickableCard()
    card.setObjectName("Card")
    card.setFixedHeight(230)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(0, 0, 0, 14)
    lay.setSpacing(10)

    thumb = QFrame()
    thumb.setFixedHeight(96)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    thumb.setStyleSheet(
        f"background-color: rgba({r},{g},{b},0.10);"
        f"border-top-left-radius: 12px; border-top-right-radius: 12px; border: none;"
    )
    thumb_lay = QVBoxLayout(thumb)
    icon_lbl = QLabel(icon)
    icon_lbl.setStyleSheet(f"color: {color}; font-size: 34px; border: none; background: transparent;")
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    thumb_lay.addWidget(icon_lbl)
    lay.addWidget(thumb)

    body = QVBoxLayout()
    body.setContentsMargins(16, 0, 16, 0)
    body.setSpacing(6)
    body.addWidget(make_subject_tag(subject), alignment=Qt.AlignmentFlag.AlignLeft)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-weight: 700; font-size: 13px; border: none; background: transparent;")
    body.addWidget(title_lbl)

    bar = QProgressBar()
    bar.setValue(progress)
    bar.setTextVisible(False)
    body.addWidget(bar)

    pct_lbl = QLabel(f"{progress}% complete")
    pct_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; border: none; background: transparent;")
    body.addWidget(pct_lbl)

    lay.addLayout(body)
    return card


def empty_state_panel(title: str, message: str, icon: str = "o", height: int = 160):
    """Jab kisi section mein abhi data nahi hai - polished 'kuch nahi hai'
    state dikhane ke liye."""
    frame = QFrame()
    frame.setObjectName("Card")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(18, 16, 18, 16)

    header = QHBoxLayout()
    t = QLabel(title)
    t.setObjectName("SectionTitle")
    header.addWidget(t)
    header.addStretch(1)
    outer.addLayout(header)

    body = QFrame()
    body.setMinimumHeight(height)
    body_lay = QVBoxLayout(body)
    icon_lbl = QLabel(icon)
    icon_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 28px; border: none; background: transparent;")
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    msg_lbl = QLabel(message)
    msg_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; letter-spacing: 1px; border: none; background: transparent;")
    msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    body_lay.addStretch(1)
    body_lay.addWidget(icon_lbl)
    body_lay.addWidget(msg_lbl)
    body_lay.addStretch(1)
    outer.addWidget(body)

    return frame
