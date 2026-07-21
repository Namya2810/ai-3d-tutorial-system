"""
tutorial_3d_page.py  (v3 - task-based interactive session)

CHANGE FROM v2: SegmentTracker (time-based auto-advance) replaced with
TaskEngine (task-completion based). Ye page ab khud koi "sahi/galat"
decide nahi karta - wo kaam app_window.py karta hai (voice answer ke liye
TaskVoiceThread chalata hai, gesture ke liye yahan se aane wale events
dekhta hai). Ye page sirf:
  1. Current task ka animation JS ko bataata hai (playAnimation)
  2. Current task ka title/prompt banner mein dikhata hai
  3. Agar current task gesture_task hai, to gesture events ko
     app_window.py tak bhi expose karta hai (on_gesture_event callback)
     taaki wo match/mismatch decide kar sake.
"""

import os
import json
import time
from dataclasses import dataclass

import cv2
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from camera_manager import CameraManager
from face_module import FaceModule
from gesture_sources import GestureManager
from task_engine import TaskEngine

DEBUG_DRAW = True  # False karo final demo ke liye - status panel hide ho jayega

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "tutorial_3d.html")

# Abhi tak sab tasks sirf isi ek heart model ko use karte hain, jiske ANDAR
# Blender se multiple named animations bake hui hain (Idle, CutAorta,
# PointVentricle, ...) - naya model load nahi hota, sirf animation
# switch hoti hai (playAnimation JS call).
GLB_PATH = "static/models/Biology_Kidney_Lab_Table.glb"

# Default subject jab tak koi HomePage se subject select nahi karta -
# purana "tasks.json" ab zaroori nahi (delete kar sakte ho), kyunki har
# subject apni file use karta hai (SUBJECT_TASKS_FILES app_window.py mein).
APP_DIR = os.path.dirname(BASE_DIR)
TASKS_CONFIG_PATH = os.path.join(APP_DIR, "tasks_kidney.json")


@dataclass
class ObjectInteractionEvent:
    """A gesture plus the actual 3D object hit by the pointer."""
    gesture: str
    target_id: str
    all_targets_complete: bool
    selected_targets: tuple = ()


class Tutorial3DPage(QWidget):
    def __init__(self, session_state=None):
        super().__init__()
        self.setObjectName("Tutorial3DPage")
        self.session_state = session_state

        self.camera = CameraManager()
        self.face = FaceModule()
        self.gesture = GestureManager()  # glove primary (stub), camera fallback (working)
        self.face.debug_draw = DEBUG_DRAW

        self.task_engine = TaskEngine(TASKS_CONFIG_PATH, session_state)
        self._last_shown_task_id = None
        self._interaction_query_pending = False
        self._interaction_query_serial = 0
        self._last_interaction_query_at = 0.0
        self._task_rotation_progress = 0.0

        # app_window.py isko set karta hai - jab is page ko gesture_task ke
        # liye ek event mila, wahan bhej dete hain taaki wo match/mismatch
        # decide kare aur task_engine.record_result() call kare.
        self.on_gesture_event = None

        self.view = QWebEngineView()
        self.view.loadFinished.connect(self._on_page_loaded)
        self.view.load(QUrl.fromLocalFile(HTML_PATH))

        self.status_label = QLabel("Action: -")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setVisible(DEBUG_DRAW)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumWidth(0)
        self.status_label.setMaximumHeight(54)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )

        self.task_timer_label = QLabel("60s", self)
        self.task_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.task_timer_label.setStyleSheet(
            "color:#071018; background:#4FD1FF; border:2px solid #B9F2FF; "
            "border-radius:18px; padding:8px 14px; font-weight:800; font-size:18px;"
        )
        self.task_timer_label.setFixedSize(112, 48)
        self.task_timer_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(self.status_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.task_timer_label.move(max(12, self.width() - 132), 18)
        self.task_timer_label.raise_()

    def show_task_timer(self, seconds):
        self.task_timer_label.setText(f"{max(0, int(seconds))}s")
        self.task_timer_label.show()
        self.task_timer_label.raise_()

    def hide_task_timer(self):
        self.task_timer_label.hide()

    def set_learning_state(self, text, tone=""):
        self.view.page().runJavaScript(
            f"setLearningState({json.dumps(text)}, {json.dumps(tone)});"
        )

    def _on_page_loaded(self, ok):
        if not ok:
            return
        self.view.page().runJavaScript(f"loadModel('{GLB_PATH}');")

    # Sirf jab page visible ho tab camera loop chalao - baaki pages pe camera
    # ko idle rakhne se CPU/webcam resources bachte hain.
    def start(self):
        if not self._timer.isActive():
            self._timer.start(30)

    def load_subject(self, tasks_path):
        """Naya subject (Biology/Physics/Chemistry) select hone par
        app_window.py isse call karta hai - poora task-flow reset ho jaata
        hai, naye tasks.json ke saath fresh start."""
        if not os.path.isabs(tasks_path):
            tasks_path = os.path.join(APP_DIR, tasks_path)
        self.task_engine.load(tasks_path)
        self.task_engine.start()
        self._last_shown_task_id = None
        filename = os.path.basename(tasks_path).lower()
        subject = "chemistry" if "chemistry" in filename else "physics" if "physics" in filename else "biology"
        self.view.page().runJavaScript(f"loadSubjectScene({json.dumps(subject)});")

    def stop(self):
        self._timer.stop()

    def _on_tick(self):
        frame = self.camera.get_frame()
        if frame is None:
            return

        self._update_task_banner_and_animation()

        face_result = self.face.process(frame)
        event = self.gesture.process(frame)

        current_task = self.task_engine.current_task()
        expects_gesture = (
            current_task["type"] == "gesture_task"
            and self.task_engine.state == TaskEngine.STATE_WAITING
        )
        expected_gesture = current_task.get("expected_gesture") if expects_gesture else None

        if self.session_state:
            self.session_state.update_face(face_result)
            self.session_state.update_gesture(event, expected_gesture=expected_gesture)
            self.session_state.update_pulse(self.gesture.pulse_bpm)

        status_lines = [
            f"Task: {current_task['prompt']}",
            f"Gesture source: {self.gesture.active_source}"
            + ("" if self.gesture.active_source == "glove" else " (glove not connected)"),
        ]

        if event:
            rotation_target = current_task.get("rotation_target")
            if rotation_target and event.gesture == current_task.get("expected_gesture"):
                delta_degrees = float(event.dx) * 60.0
                self.view.page().runJavaScript(
                    f"rotateTaskObject({json.dumps(rotation_target)}, {delta_degrees});"
                )
                self._task_rotation_progress += abs(delta_degrees)
                status_lines.append(
                    f"Gesture: GRAB + TURN ({self._task_rotation_progress:.0f} degrees)"
                )
                if self._task_rotation_progress >= float(
                    current_task.get("rotation_required_degrees", 35)
                ):
                    self._task_rotation_progress = 0.0
                    if self.on_gesture_event:
                        self.on_gesture_event(ObjectInteractionEvent(
                            gesture=event.gesture,
                            target_id=rotation_target,
                            all_targets_complete=True,
                            selected_targets=(rotation_target,),
                        ))
                js = "void 0;"
            elif expects_gesture and current_task.get("expected_targets"):
                # During object tasks POINT remains selection, while PINCH
                # zooms and GRAB-drag rotates the model for inspection.
                if event.gesture == "pinch" and expected_gesture != "pinch":
                    # Once thumb/index are touching their distance barely
                    # changes, so finger-distance alone cannot provide useful
                    # continuous zoom. Pinch + vertical hand travel is the
                    # natural camera control; distance remains a fine trim.
                    zoom_delta = float(event.scale_delta) - float(event.dy) * 1.6
                    js = f"applyGestureZoom({zoom_delta});"
                    direction = "IN" if zoom_delta > 0 else "OUT"
                    status_lines.append(f"Gesture: PINCH + MOVE (zoom {direction})")
                elif event.gesture == "grab" and expected_gesture != "grab":
                    js = f"applyGestureRotate({event.dx * 60}, true);"
                    status_lines.append("Gesture: GRAB (navigation rotate)")
                else:
                    self._send_object_interaction(event)
                    interaction_type = (current_task.get("interaction") or {}).get("type")
                    if interaction_type == "precision_grip_dissection" and event.gesture == "pinch":
                        status_lines.append("Gesture: PRECISION GRAB (scalpel interaction)")
                    else:
                        status_lines.append(f"Gesture: {event.gesture.upper()} (object selection mode)")
                    js = "void 0;"
            elif event.gesture == "point":
                js = f"applyGestureRotate({event.dx * 60});"
                status_lines.append(f"Gesture: POINT (rotating)  delta={event.dx:+.3f}")
            elif event.gesture == "pinch":
                zoom_delta = float(event.scale_delta) - float(event.dy) * 1.6
                js = f"applyGestureZoom({zoom_delta});"
                direction = "ZOOM IN" if zoom_delta > 0 else "ZOOM OUT"
                status_lines.append(f"Gesture: PINCH ({direction})")
            elif event.gesture == "grab":
                js = "applyGestureGrab(true);"
                status_lines.append("Gesture: GRAB (holding)")
            else:
                js = "applyGestureGrab(false);"
                status_lines.append(f"Gesture: {event.gesture.upper()}")

            self.view.page().runJavaScript(js)
            self.view.page().runJavaScript(
                f"setGestureStatus('Gesture source: {self.gesture.active_source} | {status_lines[-1]}');"
            )

            # Gesture_task waiting ho to app_window.py ko bata do - wahi
            # match/mismatch decide karke task_engine.record_result() bulata hai.
            if expects_gesture and self.on_gesture_event and not rotation_target:
                if (
                    not current_task.get("expected_targets")
                    or event.gesture not in ("none", expected_gesture)
                ):
                    self.on_gesture_event(event)

        if face_result:
            status_lines.append(f"Face: {face_result.state} | {face_result.emotion}")
        if self.gesture.pulse_bpm is not None:
            status_lines.append(f"Pulse: {self.gesture.pulse_bpm:.0f} BPM")

        if DEBUG_DRAW and status_lines:
            self.status_label.setText("   |   ".join(status_lines))

    def _update_task_banner_and_animation(self):
        task = self.task_engine.current_task()
        if task["task_id"] != self._last_shown_task_id:
            self._last_shown_task_id = task["task_id"]
            self._task_rotation_progress = 0.0
            title = task["prompt"].replace("'", "\\'")
            current_no, total_tasks = self.task_engine.current_task_position()
            self.view.page().runJavaScript(f"setSegmentInfo('{title}');")
            self.view.page().runJavaScript(f"setTaskPosition({current_no}, {total_tasks});")
            self.view.page().runJavaScript(f"playAnimation('{task['animation']}');")
            interaction = {
                "task_id": task["task_id"],
                "enabled": bool(task.get("expected_targets")),
                "expected_targets": task.get("expected_targets", []),
                "selection_mode": task.get("selection_mode", "all"),
                "dwell_ms": task.get("dwell_ms", 900),
                "expected_gesture": task.get("expected_gesture", "point"),
                "interaction": task.get("interaction"),
                "scene_state": task.get("scene_state"),
                "success_state": task.get("success_state"),
                "selected_targets": self.task_engine.selected_targets_for_current(),
            }
            self.view.page().runJavaScript(
                f"configureInteractionTask({json.dumps(interaction)});"
            )

    def _send_object_interaction(self, event):
        """Move the 3D cursor and receive a completed raycast selection."""
        now = time.monotonic()
        # 10 Hz is smooth enough for the cursor and avoids 30 synchronous
        # Python <-> WebEngine round-trips per second on slower laptops.
        if now - self._last_interaction_query_at < 0.1:
            return
        if self._interaction_query_pending:
            return
        self._last_interaction_query_at = now
        x = getattr(event, "pointer_x", None)
        y = getattr(event, "pointer_y", None)
        x_js = "null" if x is None else str(float(x))
        y_js = "null" if y is None else str(float(y))
        self._interaction_query_pending = True
        self._interaction_query_serial += 1
        query_serial = self._interaction_query_serial
        js = f"updateInteractionPointer({x_js}, {y_js}, '{event.gesture}', {event.dx}, {event.dy});"

        def release_stale_query():
            if self._interaction_query_serial == query_serial:
                self._interaction_query_pending = False

        QTimer.singleShot(350, release_stale_query)

        def receive(result):
            self._interaction_query_pending = False
            if not result or result.get("status") not in ("selected", "wrong"):
                return
            if self.on_gesture_event:
                self.on_gesture_event(ObjectInteractionEvent(
                    gesture=event.gesture,
                    target_id=result.get("target", ""),
                    all_targets_complete=bool(result.get("complete")),
                    selected_targets=tuple(result.get("selected_targets") or ()),
                ))

        self.view.page().runJavaScript(js, receive)

    # ---- Teacher overlay helpers (app_window.py calls these) --------------

    def show_teacher_prompt(self, text):
        text = text.replace("'", "\\'")
        self.view.page().runJavaScript(f"showTeacherPrompt('{text}');")

    def hide_teacher_prompt(self):
        self.view.page().runJavaScript("hideTeacherPrompt();")

    def show_interaction_feedback(self, text, success):
        self.view.page().runJavaScript(
            f"showInteractionFeedback({json.dumps(text)}, {str(bool(success)).lower()});"
        )

    def show_target_guidance(self, target, duration_ms=2800):
        self.view.page().runJavaScript(
            f"showTargetGuidance({json.dumps(target)}, {int(duration_ms)});"
        )

    def complete_interaction_ui(self):
        self.view.page().runJavaScript("completeInteractionUI();")

    def refresh_task_ui(self):
        """Synchronise the WebGL banner immediately after engine advances."""
        if self.task_engine.state == self.task_engine.STATE_DONE:
            self.view.page().runJavaScript(
                "completeInteractionUI(); setSegmentInfo('Session complete'); "
                "setLearningState('Complete', 'success');"
            )
            return
        self._last_shown_task_id = None
        self._update_task_banner_and_animation()
