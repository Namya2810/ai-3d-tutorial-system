"""
mini_tutorial_page.py  (v2 - classroom background + dynamic video box)

CHANGE FROM v1: Video ab plain QVideoWidget ke bajaye subject-specific
classroom background (bio/chem/phy) ke andar bane blackboard "box" ke
andar play hota hai. Box ke coordinates teeno classroom images ko
measure karke nikale gaye hain - teeno same template se bane hain isliye
fraction consistent hai:
    x: 42.0% -> 63.0%   y: 7.1% -> 78.3%   (background image ke andar)

Video apna asli aspect ratio maintain karta hai us box ke andar
(letterboxed - crop kabhi nahi hota, chahe video ka ratio box se thoda
alag ho). Aspect ratio cv2 se pehle probe kar lete hain.

v1 ka error-handling (InvalidMedia -> continue_btn enable, taaki missing/
corrupt video pe student stuck na ho) as-it-is rakha hai - isse chhua
nahi.

Trigger karne wala code (app_window.py) mein sirf itna change hai:
show_mini_tutorial() ab ek optional 5th arg "subject" leta hai
("bio"/"chem"/"phy") - agar nahi doge to last-used subject use hoga.
"""

import os

import cv2
from PyQt6.QtCore import QRect, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Blackboard box ka position, background image ke fraction mein (teeno
# classroom images - bio/chem/phy - isi ek template se bane hain)
# Pre-drawn rounded video panel in the classroom artwork. A small inset keeps
# the rectangular QVideoWidget away from the rounded corners. The video then
# uses the largest possible KeepAspectRatio fit inside this exact panel.
BOX_FRACT = {"x0": 0.410, "y0": 0.055, "x1": 0.636, "y1": 0.800}

# NOTE: task_engine.py ke "mini_tutorial_video" jaisa hi convention -
# project ROOT ke relative path (CWD se resolve hota hai jab app chalti
# hai), na ki is file (ui/mini_tutorial_page.py) ke relative. BASE_DIR
# jaan-boojh kar use nahi kiya, warna galat folder (ui/static/...) mein
# dhoondega.
SUBJECT_BACKGROUNDS = {
    "bio": "static/img/classroom_bio.jpg",
    "chem": "static/img/classroom_chem.jpg",
    "phy": "static/img/classroom_phy.jpg",
}

UI_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_asset_path(path):
    """Resolve task assets consistently, independent of launch directory."""
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    candidates = (
        os.path.join(UI_DIR, path),
        os.path.join(os.path.dirname(UI_DIR), path),
        os.path.abspath(path),
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.normpath(candidate)
    return os.path.normpath(candidates[0])


class MiniTutorialPage(QWidget):
    continue_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("MiniTutorialPage")

        self._bg_pixmap = None
        self._current_subject = "bio"
        self._video_aspect = 16 / 9  # default; cv2 probe se real value se update hota hai

        layout = QVBoxLayout(self)
        # Keep the complete classroom artwork visibly inside the application
        # frame instead of letting it sit flush against (and appear clipped by)
        # the right screen edge.
        layout.setContentsMargins(8, 6, 8, 8)

        self.reason_label = QLabel("")
        self.reason_label.setObjectName("StatusLabel")
        self.reason_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Mini Tutorial")
        self.title_label.setObjectName("PageTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Background classroom image - poore stage area ko fill karta hai
        self.background_label = QLabel(self)
        self.background_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.background_label.setMinimumHeight(360)
        self.background_label.setMinimumWidth(0)
        self.background_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )

        # Video ab background_label ke UPAR floats (child widget hai, layout
        # mein add nahi hota) - geometry hamesha _reposition_video() se set
        # hoti hai taaki box ke andar hi rahe, uske aspect ratio ke saath
        # A plain black backdrop deliberately covers the white rounded panel
        # baked into the classroom JPG.  The video is fitted inside it with
        # KeepAspectRatio math, so portrait and landscape lessons both remain
        # uncropped while the old white boundary cannot show through.
        self.video_backdrop = QWidget(self.background_label)
        self.video_backdrop.setStyleSheet("background-color: black; border: none;")
        self.video_widget = QVideoWidget(self.video_backdrop)
        self.video_widget.setStyleSheet("background-color: black;")

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_media_error)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.replay_btn = QPushButton("Replay")
        self.continue_btn = QPushButton("Got it - Continue")
        for button in (self.replay_btn, self.continue_btn):
            button.setMinimumWidth(0)
            button.setMinimumHeight(46)
            button.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
            )
        self.replay_btn.clicked.connect(self._replay)
        self.continue_btn.clicked.connect(self._on_continue)
        btn_row.addWidget(self.replay_btn, 1)
        btn_row.addWidget(self.continue_btn, 1)

        layout.addWidget(self.reason_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.background_label, stretch=1)
        layout.addLayout(btn_row)

        self.continue_btn.setEnabled(False)

    # ---- Public API (app_window.py calls this) --------------------------

    def show_mini_tutorial(self, title, reason, video_path, subject=None):
        """video_path: absolute ya relative local path to the .mp4 file
        (task_engine.py ke get_mini_tutorial_video_for_current() se aata hai).
        subject: "bio"/"chem"/"phy" - app_window.py current segment id se
        nikal ke pass karega (seg_bio -> "bio" waghera). Agar nahi diya,
        pichla subject hi use hota rahega (default "bio")."""
        reason_text = {
            "avatar_checkin": "The AI tutor noticed you might be confused here.",
            "voice_request": "You asked for help/repeat.",
            "wrong_answer": "That wasn't quite right - let's go over it again.",
            "timeout": "No response in time - let's go over it together.",
        }.get(reason, "")
        self.reason_label.setText(reason_text)
        self.title_label.setText(title)

        if subject and subject in SUBJECT_BACKGROUNDS:
            self._current_subject = subject
        video_path = _resolve_asset_path(video_path)
        self._load_background(self._current_subject)
        self._video_aspect = self._probe_video_aspect(video_path) or self._video_aspect

        self.continue_btn.setEnabled(False)
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.video_backdrop.show()
        self.video_backdrop.raise_()
        self.video_widget.show()
        self.video_widget.raise_()
        self.player.play()
        self._reposition_video()

    # ---- Background + dynamic box sizing ---------------------------------

    def _load_background(self, subject):
        path = _resolve_asset_path(
            SUBJECT_BACKGROUNDS.get(subject, SUBJECT_BACKGROUNDS["bio"])
        )
        self._bg_pixmap = QPixmap(path)
        self._update_background_pixmap()

    def _probe_video_aspect(self, video_path):
        """cv2 se video ka width/height nikalta hai (fast, ek frame read
        karta hai) - box ke andar letterbox karne ke liye chahiye taaki
        video kabhi crop na ho."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()
        if w and h:
            return w / h
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_background_pixmap()
        self._reposition_video()

    def _update_background_pixmap(self):
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            scaled = self._bg_pixmap.scaled(
                self.background_label.width(),
                self.background_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.background_label.setPixmap(scaled)

    def _reposition_video(self):
        """background_label ke andar jahan actually image draw hui hai
        (KeepAspectRatio letterbox ki wajah se poora label cover nahi
        hota) - us image-rect ke andar BOX_FRACT se blackboard-box
        nikalo, phir us box ke andar video ko uske apne aspect ratio ke
        saath letterbox karke fit karo (crop kabhi nahi hoga)."""
        pm = self.background_label.pixmap()
        if pm is None or pm.isNull():
            return

        label_w, label_h = self.background_label.width(), self.background_label.height()
        img_w, img_h = pm.width(), pm.height()
        off_x = 0  # background artwork is intentionally left-aligned
        off_y = (label_h - img_h) / 2

        box_x0 = off_x + BOX_FRACT["x0"] * img_w
        box_y0 = off_y + BOX_FRACT["y0"] * img_h
        box_x1 = off_x + BOX_FRACT["x1"] * img_w
        box_y1 = off_y + BOX_FRACT["y1"] * img_h
        box_w = box_x1 - box_x0
        box_h = box_y1 - box_y0
        if box_w <= 0 or box_h <= 0:
            return

        box_aspect = box_w / box_h
        if self._video_aspect > box_aspect:
            vid_w = box_w
            vid_h = box_w / self._video_aspect
        else:
            vid_h = box_h
            vid_w = box_h * self._video_aspect

        self.video_backdrop.setGeometry(
            QRect(int(box_x0), int(box_y0), int(box_w), int(box_h))
        )
        vid_x = (box_w - vid_w) / 2
        vid_y = (box_h - vid_h) / 2
        self.video_widget.setGeometry(
            QRect(int(vid_x), int(vid_y), int(vid_w), int(vid_h))
        )
        self.video_backdrop.raise_()
        self.video_widget.raise_()

    # ---- existing behaviour (unchanged from the real file) ---------------

    def _replay(self):
        self.player.setPosition(0)
        self.player.play()

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.continue_btn.setEnabled(True)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            # Video file missing/corrupt - don't trap the student here,
            # let them continue anyway (better than a permanently stuck page).
            self.continue_btn.setEnabled(True)

    def _on_media_error(self, error, error_string):
        self.continue_btn.setEnabled(True)

    def _on_continue(self):
        self.stop_playback()
        self.continue_clicked.emit()

    def stop_playback(self):
        """Stop both audio and video when another subject/page takes over."""
        self.player.stop()
        self.video_widget.hide()
        self.video_backdrop.hide()
