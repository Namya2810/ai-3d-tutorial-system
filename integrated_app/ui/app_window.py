from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from ui.sidebar import Sidebar
from ui.home_page import HomePage
from ui.tutorial_3d_page import Tutorial3DPage
from ui.quiz_page import QuizPage
from ui.profile_page import ProfilePage
from ui.mini_tutorial_page import MiniTutorialPage
from ui.prompt_banner import PromptBanner
from ui.numeric_input_dialog import TitrationCalculationDialog
from voice.assistant_panel import AssistantPanel
from voice.avatar_checkin import AvatarCheckinThread
from voice.task_voice_thread import PromptSpeechThread, TaskVoiceThread
from voice.text_to_speech import stop_speaking
from task_engine import TaskEngine

import confusion_engine
from app_config import setting
import time

CHECKIN_THRESHOLD = float(setting("confusion", "checkin_threshold"))
CHECKIN_COOLDOWN_SECONDS = float(setting("confusion", "checkin_cooldown_seconds"))
CHECKIN_SUSTAINED_SECONDS = int(setting("confusion", "checkin_sustained_seconds"))

# Gesture_task ke liye: expected gesture na milne par kitni "galat" frames
# ke baad hi mini-tutorial khole (isolated ek-do glitch frames pe turant
# fail mat karo - MediaPipe detection thoda noisy hota hai).
GESTURE_MISMATCH_LIMIT = 150  # sustained wrong gesture only; ignore camera flicker

# Task type "gesture_task" mein banner sirf itni der dikhta hai, phir
# khud vanish ho jaata hai taaki interactive 3D/gesture session ke liye
# poori jagah mil jaye (jaisa Namya ne bataya: "task ho toh image vanish").
TASK_BANNER_VISIBLE_MS = 6000

# NAYA: agar student 30 sec tak kuch bhi respond na kare (na voice answer,
# na gesture), to bhi mini-tutorial khul jaana chahiye - pehle koi timeout
# hi nahi tha, gesture_task ke case mein to student infinite wait kar
# sakta tha (mismatch counter sirf GALAT gesture pe badhta hai, "kuch
# nahi kiya" pe nahi).
TASK_WAIT_TIMEOUT_MS = 60000
VOICE_QUESTION_TIMEOUT_MS = 45000
SINGLE_TARGET_TIMEOUT_MS = 45000
MULTI_TARGET_BASE_TIMEOUT_MS = 60000
SEQUENCE_SECONDS_PER_TARGET = 12
DISSECTION_TIMEOUT_MS = 90000

# Subject selector (HomePage se) - key -> tasks.json file
SUBJECT_TASKS_FILES = {
    "biology": "tasks_kidney.json",
    "physics": "tasks_physics.json",
    "chemistry": "tasks_chemistry.json",
}

# SUBJECT_TASKS_FILES ki keys ("biology"/"physics"/"chemistry") se
# mini_tutorial_page.py / prompt_banner.py ke SUBJECT_BACKGROUNDS keys
# ("bio"/"phy"/"chem") tak - ye do jagah alag naming convention use kar
# rahi thi, isliye ek chhota mapping chahiye tha.
SUBJECT_KEY_TO_BG = {
    "biology": "bio",
    "physics": "phy",
    "chemistry": "chem",
}


class MainWindow(QMainWindow):
    def __init__(self, session_state):
        super().__init__()
        self.session_state = session_state
        self.setWindowTitle("AI 3D Tutorial System")
        self.resize(1100, 750)

        # QWebEngineView consumes Escape before QMainWindow.keyPressEvent can
        # see it. Application-scoped shortcuts make fullscreen toggling and
        # emergency exit reliable regardless of which embedded widget owns
        # keyboard focus.
        self._fullscreen_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._fullscreen_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._fullscreen_shortcut.activated.connect(self._toggle_immersive_mode)
        self._quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self._quit_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._quit_shortcut.activated.connect(self.close)
        self._yes_shortcut = QShortcut(QKeySequence("Y"), self)
        self._yes_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._yes_shortcut.activated.connect(
            lambda: self._resolve_avatar_checkin_locally("yes")
        )
        self._no_shortcut = QShortcut(QKeySequence("N"), self)
        self._no_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._no_shortcut.activated.connect(
            lambda: self._resolve_avatar_checkin_locally("no")
        )
        self._recenter_shortcut = QShortcut(QKeySequence("R"), self)
        self._recenter_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._recenter_shortcut.activated.connect(self._recenter_glove)

        central = QWidget()
        outer_layout = QHBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # A small always-visible readout of the live confusion score, so the
        # team can see Phase 6 working no matter which page is open.
        self.confusion_banner = QLabel("Confusion score: -")
        self.confusion_banner.setObjectName("StatusLabel")
        right_layout.addWidget(self.confusion_banner)

        self.stack = QStackedWidget()

        self.home_page = HomePage(session_state=session_state)
        self.tutorial_page = Tutorial3DPage(session_state=session_state)
        self.tutorial_page.on_gesture_event = self._on_gesture_event
        self.assistant_panel = AssistantPanel(session_state=session_state)
        # Quiz needs task-level progress (attempts / mini-tutorial play
        # counts per task) to turn the session history into a
        # session-level confusion score + segment-weighted questions.
        self.quiz_page = QuizPage(session_state=session_state, task_engine=self.tutorial_page.task_engine)
        self.profile_page = ProfilePage(session_state=session_state)
        self.profile_page.login_succeeded.connect(
            lambda _student_id: self._show(self.home_page)
        )
        self.mini_tutorial_page = MiniTutorialPage()
        self.mini_tutorial_page.continue_clicked.connect(self._on_mini_tutorial_continue)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.tutorial_page)
        self.stack.addWidget(self.assistant_panel)
        self.stack.addWidget(self.quiz_page)
        self.stack.addWidget(self.profile_page)
        self.stack.addWidget(self.mini_tutorial_page)

        right_layout.addWidget(self.stack)

        # Avatar + speech-bubble banner - stack ke UPAR floats (raw child,
        # QStackedWidget ke addWidget se nahi joda - warna wo khud ek
        # "page" ban jaata aur baaki pages ko replace kar deta). Geometry
        # resizeEvent mein stack ke rect se sync hoti hai.
        self.prompt_banner = PromptBanner(self.stack)
        self.prompt_banner.choice_selected.connect(
            self._resolve_avatar_checkin_locally
        )
        self.prompt_banner.hide()

        self.sidebar = Sidebar()
        self.sidebar.home_clicked.connect(lambda: self._show(self.home_page))
        self.sidebar.tutorial_clicked.connect(lambda: self._show(self.tutorial_page))
        self.sidebar.assistant_clicked.connect(lambda: self._show(self.assistant_panel))
        self.sidebar.quiz_clicked.connect(lambda: self._show(self.quiz_page))
        self.sidebar.profile_clicked.connect(lambda: self._show(self.profile_page))
        self.sidebar.anaglyph_toggled.connect(self._set_anaglyph_enabled)

        self.home_page.subject_selected.connect(self._on_subject_selected)

        outer_layout.addWidget(self.sidebar)
        outer_layout.addWidget(right_side)

        self.setCentralWidget(central)
        self._load_styles()

        # Voice HELP/REPEAT ke counts yaad rakhte hain, taaki naya request
        # detect hote hi seedha mini-tutorial khol sakein (roadmap point #3).
        self._last_help_count = 0
        self._last_repeat_count = 0

        self._avatar_thread = None
        self._task_voice_thread = None
        self._prompt_speech_thread = None
        self._feedback_speech_thread = None
        self._failure_transition_in_progress = False
        self._success_transition_in_progress = False
        self._confusion_high_ticks = 0
        self._countdown_was_active_before_checkin = False
        self._immersive_active = False
        self._immersive_dismissed = False
        self._flow_generation = 0
        self._retired_threads = []

        # Task flow state guards - taaki har _tick() pe dobara trigger na ho
        self._task_flow_started_for = None   # task_id jiske liye ASKING already trigger ho chuki hai
        self._gesture_mismatch_count = 0
        self._wrong_target_count = 0
        self._mini_tutorial_open_for = None  # task_id jiske liye mini-tutorial page already khula hai

        # NAYA: har baar jab koi task "asked" hota hai (voice ya gesture),
        # token badh jaata hai. 30-sec timeout fire hone par is token ko
        # check karte hain - agar tab tak task already resolve/change ho
        # chuka hai to purana (stale) timer koi asar nahi karta.
        self._task_wait_token = 0
        self._task_seconds_remaining = 0
        self._task_countdown_timer = QTimer(self)
        self._task_countdown_timer.setInterval(1000)
        self._task_countdown_timer.timeout.connect(self._tick_task_countdown)
        # NAYA: mini-tutorial khulte waqt sahi reason dikhane ke liye -
        # "wrong_answer" (galat jawaab/gesture) vs "timeout" (koi response
        # hi nahi aaya) - _open_mini_tutorial_for_task isi ko padhta hai.
        self._last_fail_reason = "wrong_answer"

        # Abhi kaunsa subject chal raha hai ("biology"/"physics"/"chemistry")
        # - HomePage se subject choose hote hi set hota hai. Mini-tutorial
        # background (bio/chem/phy classroom image) isi se decide hota hai.
        self._current_subject_key = None

        # Confusion engine tick - independent of which page is open, as long
        # as the 3D tutorial page's camera loop is feeding the session state.
        self._confusion_timer = QTimer(self)
        self._confusion_timer.timeout.connect(self._tick)
        self._confusion_timer.start(1000)  # recompute once a second

        self._login_required = bool(setting("ui", "require_login"))
        self._show(self.profile_page if self._login_required else self.home_page)

    def _set_anaglyph_enabled(self, enabled):
        """Enable true red/cyan stereo rendering for the 3D scene."""
        value = "true" if enabled else "false"
        self.tutorial_page.view.page().runJavaScript(f"setAnaglyphEnabled({value});")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # prompt_banner stack ke UPAR floating overlay hai, isliye geometry
        # ko manually stack ke rect se sync rakhna padta hai.
        self.prompt_banner.setGeometry(self.stack.rect())

    def keyPressEvent(self, event):
        # Escape is handled by the application-scoped QShortcut above.
        super().keyPressEvent(event)

    def _recenter_glove(self):
        if not hasattr(self, "tutorial_page"):
            return
        self.tutorial_page.gesture.recenter()
        self.tutorial_page.set_learning_state("Glove pointer recentered", "active")

    def _toggle_immersive_mode(self):
        if self._immersive_active or self.isFullScreen():
            self._leave_immersive_mode()
        else:
            self._enter_immersive_mode(force=True)

    def _enter_immersive_mode(self, force=False):
        if self._immersive_dismissed and not force:
            return
        self._immersive_active = True
        self.sidebar.hide()
        self.confusion_banner.hide()
        self.showFullScreen()

    def _leave_immersive_mode(self):
        self._immersive_active = False
        self._immersive_dismissed = True
        self.sidebar.show()
        self.confusion_banner.show()
        # Explicitly leave the native fullscreen state before maximising;
        # calling showMaximized alone is unreliable on some Windows/Qt builds.
        self.showNormal()
        self.showMaximized()

    def _retire_thread(self, attribute):
        thread = getattr(self, attribute, None)
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.requestInterruption()
                self._retired_threads.append(thread)
                thread.finished.connect(
                    lambda old=thread: self._release_retired_thread(old)
                )
        except RuntimeError:
            pass
        setattr(self, attribute, None)

    def _release_retired_thread(self, thread):
        if thread in self._retired_threads:
            self._retired_threads.remove(thread)

    def _cancel_active_lesson_media(self):
        """Make page/subject changes atomic: one lesson and one voice only."""
        self._flow_generation += 1
        self._task_wait_token += 1
        self._stop_task_countdown()
        self.mini_tutorial_page.stop_playback()
        stop_speaking()
        for attribute in (
            "_avatar_thread",
            "_task_voice_thread",
            "_prompt_speech_thread",
            "_feedback_speech_thread",
        ):
            self._retire_thread(attribute)
        self.prompt_banner.hide_banner()
        self.session_state.checkin_in_progress = False
        self._failure_transition_in_progress = False
        self._success_transition_in_progress = False

    def _on_subject_selected(self, subject_key):
        """HomePage se subject-card click hone par yahan aata hai - naya
        tasks.json load karo, saare 'kaunsa task chal raha hai' guards
        reset karo, aur 3D tutorial page pe le jao."""
        if self._login_required and not self.session_state.student_id:
            QMessageBox.information(
                self, "Sign in required", "Please sign in before starting a lesson."
            )
            self._show(self.profile_page)
            return
        tasks_file = SUBJECT_TASKS_FILES.get(subject_key)
        if not tasks_file:
            return
        self._cancel_active_lesson_media()
        self._immersive_dismissed = False
        self.tutorial_page.load_subject(tasks_file)
        self._current_subject_key = subject_key

        # Ye sab guards isliye reset karne zaroori hain - warna app soch
        # sakta hai "is task ke liye already ASK ho chuka hai" ya "iske
        # liye mini-tutorial already khula hai" jab ki naya subject shuru
        # hua hai.
        self._task_flow_started_for = None
        self._gesture_mismatch_count = 0
        self._mini_tutorial_open_for = None

        self._show(self.tutorial_page)
        self._enter_immersive_mode()

    def _show(self, page):
        previous = self.stack.currentWidget()
        if page is self.home_page:
            self.home_page.refresh_stats()
        lesson_pages = (self.tutorial_page, self.mini_tutorial_page)
        if previous in lesson_pages and page not in lesson_pages:
            self._cancel_active_lesson_media()
            self.tutorial_page.task_engine.retry_current_task()
            self._task_flow_started_for = None
            self._mini_tutorial_open_for = None
            if self._immersive_active:
                self._leave_immersive_mode()
        if previous is self.mini_tutorial_page and page is not self.mini_tutorial_page:
            self.mini_tutorial_page.stop_playback()
        # Only run the camera loop while the 3D tutorial page is actually
        # visible - saves CPU/webcam resources on the other pages.
        if page is self.tutorial_page:
            self.tutorial_page.start()
        else:
            self.tutorial_page.stop()
        self.stack.setCurrentWidget(page)

        # Banner sirf tutorial_page ke upar dikhta hai - kisi aur page pe
        # switch hote hi hide kar do (warna quiz/profile/home ke upar bhi
        # tair raha rahega).
        if page is not self.tutorial_page:
            self.prompt_banner.hide_banner()
            self._stop_task_countdown()

        if page is self.tutorial_page:
            self._drive_task_flow()

    def _tick(self):
        self._update_confusion_score()
        self._check_voice_triggers()
        self._check_avatar_checkin()
        if self.stack.currentWidget() is self.tutorial_page:
            self._drive_task_flow()

    def _update_confusion_score(self):
        result = confusion_engine.compute(self.session_state)
        self.session_state.confusion_score = result.score
        self.confusion_banner.setText(
            f"Confusion score: {result.score * 100:.0f}%  ({result.label})"
        )

    def _check_voice_triggers(self):
        """Voice module mein 'help'/'repeat' bolne se session_state ke
        counters badhte hain (assistant_panel.py / voice_thread.py mein) -
        yahan sirf dekh rahe hain ki naya request aaya kya, taaki seedha
        mini-tutorial khul jaye, confusion score ka wait kiye bina."""
        help_count = self.session_state.help_requests
        repeat_count = self.session_state.repeat_requests

        new_request = help_count > self._last_help_count or repeat_count > self._last_repeat_count
        self._last_help_count = help_count
        self._last_repeat_count = repeat_count

        if new_request and self.stack.currentWidget() is self.tutorial_page:
            self._open_mini_tutorial(reason="voice_request")

    # ------------------------------------------------------------------
    # TASK FLOW - ye naya hissa hai. Ye task_engine.state dekh kar decide
    # karta hai ki abhi kya karna hai (question poochna / gesture wait
    # karna / mini-tutorial kholna).
    # ------------------------------------------------------------------

    def _drive_task_flow(self):
        engine = self.tutorial_page.task_engine

        if self._failure_transition_in_progress or self._success_transition_in_progress:
            return

        if engine.state == TaskEngine.STATE_DONE:
            self.prompt_banner.hide_banner()
            self.tutorial_page.set_learning_state("Lesson complete", "success")
            self.home_page.refresh_stats()
            return

        if engine.state == TaskEngine.STATE_MINI_TUTORIAL:
            self._open_mini_tutorial_for_task()
            return

        if engine.state != TaskEngine.STATE_ASKING:
            return  # WAITING - kisi cheez ka wait chal raha hai, kuch mat karo

        task = engine.current_task()
        if self._task_flow_started_for == task["task_id"]:
            return  # is task ke liye already ASK ho chuka hai
        self._task_flow_started_for = task["task_id"]
        self._gesture_mismatch_count = 0
        self._wrong_target_count = 0

        if task["type"] == "voice_question":
            self.tutorial_page.set_learning_state("Teacher speaking", "speaking")
            self._start_task_voice(task)
        elif task["type"] == "numeric_question":
            self._start_numeric_question(task)
        elif task["type"] == "gesture_task":
            # Banner dikhao (prompt bataane ke liye), phir thodi der baad
            # khud vanish ho jaayega taaki gesture/3D session ke liye poori
            # jagah mil jaye - student ko instruction padhne ka time bhi
            # mil jaata hai.
            self.prompt_banner.show_prompt(
                task["prompt"], mode="task", context_label=self._task_context_label()
            )
            self.tutorial_page.set_learning_state("Teacher speaking", "speaking")
            self._task_wait_token += 1
            token = self._task_wait_token
            generation = self._flow_generation
            self._prompt_speech_thread = PromptSpeechThread(task["prompt"])
            self._prompt_speech_thread.finished.connect(
                lambda task_id=task["task_id"], task_token=token, flow=generation:
                    self._on_gesture_prompt_finished(task_id, task_token, flow)
            )
            self._prompt_speech_thread.start()

    def _start_numeric_question(self, task):
        """Use deterministic local input for values speech recognition mangles."""
        self.prompt_banner.show_prompt(
            task["prompt"], mode="question", context_label=self._task_context_label()
        )
        self.tutorial_page.task_engine.mark_asked()
        dialog = TitrationCalculationDialog(task, self)
        accepted = dialog.exec() == dialog.DialogCode.Accepted
        self.prompt_banner.hide_banner()
        if not accepted:
            self.tutorial_page.task_engine.record_result(False)
            self._begin_failure_transition(
                "wrong_answer", "No calculation was submitted. Let me show the method."
            )
            return
        expected = float(task["expected_numeric_answer"])
        tolerance = float(task.get("numeric_tolerance", 0.05))
        correct = abs(dialog.calculated_value() - expected) <= tolerance
        self.tutorial_page.task_engine.record_result(correct)
        if correct:
            self._begin_success_transition("Correct calculation - well done.")
        else:
            self._begin_failure_transition(
                "wrong_answer", "Check final reading minus initial reading."
            )

    def _on_gesture_prompt_finished(self, task_id, token, generation):
        if generation != self._flow_generation:
            return
        self._prompt_speech_thread = None
        # A short visual beat after narration makes the transition feel
        # intentional and ensures the timer never consumes speaking time.
        QTimer.singleShot(900, lambda: self._activate_gesture_task(task_id, token))

    def _task_context_label(self):
        current, total = self.tutorial_page.task_engine.current_task_position()
        return f"Task {current} of {total}"

    def _activate_gesture_task(self, task_id, token):
        """Start gesture timing only after the teacher prompt was readable."""
        engine = self.tutorial_page.task_engine
        if self.stack.currentWidget() is not self.tutorial_page:
            return
        if engine.state != TaskEngine.STATE_ASKING:
            return
        if engine.current_task()["task_id"] != task_id:
            return
        self.prompt_banner.hide_banner()
        engine.mark_asked()
        self.tutorial_page.set_learning_state("Your turn - tracking", "active")
        self._start_task_countdown(
            token, self._adaptive_timeout_ms(engine.current_task())
        )

    def _adaptive_timeout_ms(self, task):
        """Choose a fair response window from the cognitive/motor workload."""
        if task.get("timeout_ms"):
            return int(task["timeout_ms"])
        if task.get("type") in ("voice_question", "numeric_question"):
            return VOICE_QUESTION_TIMEOUT_MS
        interaction = task.get("interaction") or {}
        if interaction.get("type") == "grab_drag_path":
            return DISSECTION_TIMEOUT_MS
        target_count = max(1, len(task.get("expected_targets") or []))
        if task.get("selection_mode") == "sequence":
            return max(
                MULTI_TARGET_BASE_TIMEOUT_MS,
                (25 + target_count * SEQUENCE_SECONDS_PER_TARGET) * 1000,
            )
        if target_count > 1:
            return MULTI_TARGET_BASE_TIMEOUT_MS + (target_count - 2) * 10000
        return SINGLE_TARGET_TIMEOUT_MS

    def _start_task_countdown(self, token, timeout_ms=TASK_WAIT_TIMEOUT_MS):
        self._task_wait_token = token
        self._task_seconds_remaining = max(1, int(timeout_ms) // 1000)
        self.tutorial_page.show_task_timer(self._task_seconds_remaining)
        self._task_countdown_timer.start()

    def _stop_task_countdown(self):
        if hasattr(self, "_task_countdown_timer"):
            self._task_countdown_timer.stop()
        if hasattr(self, "tutorial_page"):
            self.tutorial_page.hide_task_timer()

    def _pause_task_countdown(self):
        self._countdown_was_active_before_checkin = self._task_countdown_timer.isActive()
        self._task_countdown_timer.stop()

    def _resume_task_countdown(self):
        if (
            self._countdown_was_active_before_checkin
            and self._task_seconds_remaining > 0
            and self.tutorial_page.task_engine.state == TaskEngine.STATE_WAITING
            and self.stack.currentWidget() is self.tutorial_page
        ):
            self.tutorial_page.show_task_timer(self._task_seconds_remaining)
            self._task_countdown_timer.start()
        self._countdown_was_active_before_checkin = False

    def _tick_task_countdown(self):
        self._task_seconds_remaining -= 1
        self.tutorial_page.show_task_timer(self._task_seconds_remaining)
        if self._task_seconds_remaining <= 0:
            token = self._task_wait_token
            self._stop_task_countdown()
            self._on_task_wait_timeout(token)

    def _start_task_voice(self, task):
        # Question mode - banner CONSTANT rehta hai jab tak voice-answer ka
        # result na aa jaye (live STT caption ke liye
        # self.prompt_banner.update_transcript(...) ko voice thread ke
        # partial-result signal se jodna hai - TaskVoiceThread abhi sirf
        # result_ready deta hai, partial-transcript signal nahi. Agar wo
        # thread partial text emit karta hai to yahan connect kar dena.
        self.prompt_banner.show_prompt(
            task["prompt"], mode="question", context_label=self._task_context_label()
        )
        self.tutorial_page.task_engine.mark_asked()

        self._task_voice_thread = TaskVoiceThread(task)
        generation = self._flow_generation
        self._task_voice_thread.transcript_updated.connect(
            lambda text, flow=generation: self._on_task_transcript(text, flow)
        )
        self._task_wait_token += 1
        token = self._task_wait_token
        timeout_ms = self._adaptive_timeout_ms(task)
        self._task_voice_thread.listening_started.connect(
            lambda task_token=token, duration=timeout_ms, flow=self._flow_generation:
                self._on_voice_listening_started(task_token, duration, flow)
        )
        self._task_voice_thread.result_ready.connect(
            lambda correct, heard, flow=generation:
                self._on_task_voice_result(correct, heard, flow)
        )
        self._task_voice_thread.finished.connect(
            lambda flow=generation: self._on_task_voice_thread_finished(flow)
        )
        self._task_voice_thread.start()

    def _on_task_transcript(self, text, generation):
        if generation == self._flow_generation:
            self.prompt_banner.update_transcript(text)

    def _on_voice_listening_started(self, token, timeout_ms, generation=None):
        if generation is not None and generation != self._flow_generation:
            return
        if self.tutorial_page.task_engine.state != TaskEngine.STATE_WAITING:
            return
        self.tutorial_page.set_learning_state("Your turn - listening", "active")
        self._start_task_countdown(token, timeout_ms)

    def _on_task_voice_result(self, correct, heard_text, generation=None):
        if generation is not None and generation != self._flow_generation:
            return
        if self.tutorial_page.task_engine.state != TaskEngine.STATE_WAITING:
            return
        self._stop_task_countdown()
        self.prompt_banner.hide_banner()
        if not correct:
            self._last_fail_reason = "wrong_answer"
        self.tutorial_page.task_engine.record_result(correct)
        if correct:
            self._begin_success_transition("Correct answer — well done.")
        else:
            self._begin_failure_transition(
                "wrong_answer",
                "That answer was not quite right. Let me explain it with a quick visual.",
            )

    def _on_task_voice_thread_finished(self, generation=None):
        if generation is not None and generation != self._flow_generation:
            return
        self._task_voice_thread = None

    def _on_task_wait_timeout(self, token):
        """NAYA: 30 sec tak koi response (voice ya gesture) na aaye to
        yahan aata hai. token check isliye zaroori hai - agar student ne
        already jawaab de diya tha ya task badal chuka hai, to ye purana
        (stale) timer koi asar nahi karega."""
        if token != self._task_wait_token:
            return
        self._stop_task_countdown()
        engine = self.tutorial_page.task_engine
        if engine.state != TaskEngine.STATE_WAITING:
            return  # already resolve ho chuka hai

        if self._task_voice_thread is not None:
            self._task_voice_thread.requestInterruption()

        self._last_fail_reason = "timeout"
        self.session_state.register_timeout()
        engine.record_result(False)
        if self.session_state.confusion_score >= CHECKIN_THRESHOLD:
            message = "You seem to be taking time to think, and I notice some confusion. Let me help with a quick explanation."
        else:
            message = "Time is up. That is okay — let me help with a quick explanation before you try again."
        self._begin_failure_transition("timeout", message)

    def _on_gesture_event(self, event):
        """tutorial_3d_page.py se aata hai jab current task gesture_task hai
        aur engine WAITING state mein hai."""
        if (
            self.session_state.checkin_in_progress
            or self._failure_transition_in_progress
            or self._success_transition_in_progress
        ):
            return
        engine = self.tutorial_page.task_engine
        if engine.state != TaskEngine.STATE_WAITING:
            return
        task = engine.current_task()
        expected = task.get("expected_gesture")

        expected_targets = task.get("expected_targets", [])
        if expected_targets:
            target_id = getattr(event, "target_id", "")
            if getattr(event, "all_targets_complete", False):
                self._stop_task_countdown()
                self.prompt_banner.hide_banner()
                self.tutorial_page.complete_interaction_ui()
                self.tutorial_page.show_interaction_feedback(
                    task.get("success_message", "Correct! Moving to the next task."), True
                )
                engine.record_result(True)
                self._begin_success_transition(
                    task.get("success_message", "Correct action — well done.")
                )
            elif target_id and target_id not in expected_targets:
                self._gesture_mismatch_count += 1
                self._wrong_target_count += 1
                selected = list(getattr(event, "selected_targets", ()) or ())
                if task.get("selection_mode") in ("sequence", "ordered"):
                    guide_target = expected_targets[
                        min(len(selected), len(expected_targets) - 1)
                    ]
                else:
                    guide_target = next(
                        (item for item in expected_targets if item not in selected),
                        expected_targets[0],
                    )
                self.tutorial_page.show_interaction_feedback(
                    task.get("retry_message", "That is not the requested object. Try again."), False
                )
                if self._wrong_target_count >= 2:
                    self.tutorial_page.show_target_guidance(guide_target)
                    self._wrong_target_count = 0
                if self._gesture_mismatch_count >= GESTURE_MISMATCH_LIMIT:
                    self._stop_task_countdown()
                    self.prompt_banner.hide_banner()
                    self._last_fail_reason = "wrong_answer"
                    engine.record_result(False)
                    self._begin_failure_transition(
                        "wrong_answer",
                        "That gesture was not quite right. Let us review the action, then you can try again.",
                    )
            elif target_id in expected_targets:
                # A correct first/partial target is progress, not a mismatch.
                # Persist it so a confusion check-in/re-ASK does not erase it.
                self._gesture_mismatch_count = 0
                selected = getattr(event, "selected_targets", ()) or (target_id,)
                for selected_target in selected:
                    engine.record_selected_target(selected_target)
                remaining = [t for t in expected_targets if t not in selected]
                if remaining:
                    self.tutorial_page.show_interaction_feedback(
                        f"Good. {len(remaining)} target(s) remaining.", True
                    )
            return

        if event.gesture == expected:
            self._stop_task_countdown()
            self.prompt_banner.hide_banner()
            engine.record_result(True)
            self._begin_success_transition("Correct gesture — well done.")
        elif event.gesture not in ("none", expected):
            self._gesture_mismatch_count += 1
            if self._gesture_mismatch_count >= GESTURE_MISMATCH_LIMIT:
                self._stop_task_countdown()
                self.prompt_banner.hide_banner()
                self._last_fail_reason = "wrong_answer"
                engine.record_result(False)
                self._begin_failure_transition(
                    "wrong_answer",
                    "That gesture was not quite right. Let us review it before you try again.",
                )

    def _begin_failure_transition(self, reason, message):
        if self._failure_transition_in_progress or self._success_transition_in_progress:
            return
        self._failure_transition_in_progress = True
        self._last_fail_reason = reason
        self._stop_task_countdown()
        self.tutorial_page.set_learning_state("Needs help", "help")
        self.prompt_banner.show_prompt(message, mode="task", context_label="Feedback")
        self._feedback_speech_thread = PromptSpeechThread(message)
        generation = self._flow_generation
        self._feedback_speech_thread.finished.connect(
            lambda flow=generation: self._finish_failure_transition(flow)
        )
        self._feedback_speech_thread.start()

    def _begin_success_transition(self, message):
        if self._success_transition_in_progress:
            return
        self._success_transition_in_progress = True
        self._stop_task_countdown()
        self.prompt_banner.hide_banner()
        self.tutorial_page.set_learning_state("Correct", "success")
        self.tutorial_page.show_interaction_feedback(message, True)
        QTimer.singleShot(1200, self._finish_success_transition)

    def _finish_success_transition(self):
        self._success_transition_in_progress = False
        self._task_flow_started_for = None
        self.tutorial_page.refresh_task_ui()
        self._drive_task_flow()

    def _finish_failure_transition(self, generation=None):
        if generation is not None and generation != self._flow_generation:
            return
        self._feedback_speech_thread = None
        QTimer.singleShot(700, self._open_pending_failure_tutorial)

    def _open_pending_failure_tutorial(self):
        if not self._failure_transition_in_progress:
            return
        self._failure_transition_in_progress = False
        self.prompt_banner.hide_banner()
        self.tutorial_page.set_learning_state("Quick explanation", "checking")
        self._open_mini_tutorial_for_task(reason=self._last_fail_reason)

    def _on_mini_tutorial_continue(self):
        self.tutorial_page.task_engine.retry_current_task()
        self._task_flow_started_for = None  # taaki wapas ASK trigger ho
        self._mini_tutorial_open_for = None
        self._show(self.tutorial_page)

    def _open_mini_tutorial_for_task(self, reason=None):
        engine = self.tutorial_page.task_engine
        task_id = engine.current_task()["task_id"]
        if self._mini_tutorial_open_for == task_id:
            return  # already khula hua hai, dobara mat kholo
        self._mini_tutorial_open_for = task_id
        # reason explicitly diya ho (jaise avatar_checkin) to wahi use karo,
        # warna abhi-abhi jo actually hua tha wo (_last_fail_reason -
        # "wrong_answer" ya "timeout") - _on_task_voice_result /
        # _on_gesture_event / _on_task_wait_timeout mein set hota hai.
        self._open_mini_tutorial(reason=reason or self._last_fail_reason)

    # ------------------------------------------------------------------
    # AVATAR CHECK-IN (confusion-triggered) - ab bhi wahi PromptBanner use
    # karta hai jo naya task assign hone par bhi dikhta hai.
    # ------------------------------------------------------------------

    def _check_avatar_checkin(self):
        if self.stack.currentWidget() is not self.tutorial_page:
            return
        if self._failure_transition_in_progress or self._success_transition_in_progress:
            return
        if self.session_state.checkin_in_progress:
            return
        # Do not interrupt the teacher narration or an active voice answer.
        if self._prompt_speech_thread is not None or self._task_voice_thread is not None:
            return
        if self.tutorial_page.task_engine.state != TaskEngine.STATE_WAITING:
            self._confusion_high_ticks = 0
            return
        if self.session_state.confusion_score < CHECKIN_THRESHOLD:
            self._confusion_high_ticks = 0
            return
        self._confusion_high_ticks += 1
        # Require a sustained threshold crossing, not one noisy face frame.
        if self._confusion_high_ticks < CHECKIN_SUSTAINED_SECONDS:
            return
        if time.time() - self.session_state.last_checkin_at < CHECKIN_COOLDOWN_SECONDS:
            return

        self._confusion_high_ticks = 0
        self._start_avatar_checkin()

    def _start_avatar_checkin(self):
        self.session_state.checkin_in_progress = True
        self.session_state.last_checkin_at = time.time()

        self._pause_task_countdown()
        self.tutorial_page.set_learning_state("Checking in", "checking")
        question_text = (
            "AI thinks you may be having some confusion. "
            "Would you like a quick explanation? Please say yes or no."
        )

        self._avatar_thread = AvatarCheckinThread(question_text=question_text)
        generation = self._flow_generation
        self._avatar_thread.transcript_updated.connect(
            lambda text, flow=generation: self._on_avatar_transcript(text, flow)
        )
        self._avatar_thread.listening_started.connect(
            lambda flow=generation: self._on_avatar_listening_started(flow)
        )
        self._avatar_thread.result_ready.connect(
            lambda result, flow=generation:
                self._on_avatar_checkin_result(result, flow)
        )
        self.prompt_banner.show_prompt(
            question_text, mode="question", context_label="AI check-in",
            choices=True,
        )
        self._avatar_thread.start()

    def _resolve_avatar_checkin_locally(self, answer):
        """Deterministic local fallback for unreliable microphone/STT.

        The learner may click a button or press Y/N.  This path never sends
        the answer to an online model and therefore cannot swap yes and no.
        """
        if not self.session_state.checkin_in_progress:
            return
        if answer not in ("yes", "no"):
            return
        if self._avatar_thread is not None and self._avatar_thread.isRunning():
            self._avatar_thread.requestInterruption()
        self._on_avatar_checkin_result(answer, self._flow_generation)

    def _on_avatar_listening_started(self, generation):
        if generation != self._flow_generation:
            return
        self.tutorial_page.set_learning_state(
            "Your turn - say yes or no", "active"
        )

    def _on_avatar_transcript(self, text, generation):
        if generation == self._flow_generation:
            self.prompt_banner.update_transcript(text)

    def _on_avatar_checkin_result(self, result, generation=None):
        if generation is not None and generation != self._flow_generation:
            return
        if not self.session_state.checkin_in_progress:
            return
        if result == "no_response":
            # Never guess a learner's intent. Keep the timer paused and the
            # local buttons/Y/N shortcuts available until an explicit choice.
            self.prompt_banner.update_transcript(
                "I could not hear a clear answer. Click Yes/No or press Y/N."
            )
            self.tutorial_page.set_learning_state(
                "Waiting for your Yes/No choice", "checking"
            )
            return
        caption = {
            "yes": "YES understood - opening a quick explanation...",
            "no": "NO understood - continuing your task...",
        }.get(result, "Continuing your task...")
        self.prompt_banner.update_transcript(caption)
        QTimer.singleShot(
            1100,
            lambda answer=result, flow=self._flow_generation:
                self._finish_avatar_checkin(answer, flow),
        )

    def _finish_avatar_checkin(self, result, generation):
        if generation != self._flow_generation:
            return
        if not self.session_state.checkin_in_progress:
            return
        self.session_state.checkin_in_progress = False
        self.prompt_banner.hide_banner()
        if result == "yes":
            self._countdown_was_active_before_checkin = False
            self.tutorial_page.set_learning_state("Quick explanation", "checking")
            self._open_mini_tutorial_for_task(reason="avatar_checkin")
        else:
            # "no" means the learner wants to continue. A missed/unclear
            # reply also resumes rather than forcing help unexpectedly.
            self.tutorial_page.set_learning_state("Your turn - tracking", "active")
            self._resume_task_countdown()
        self._avatar_thread = None

    def _open_mini_tutorial(self, reason):
        self._stop_task_countdown()
        engine = self.tutorial_page.task_engine
        mini_id, mini_title = engine.get_mini_tutorial_for_current()
        video_path = engine.get_mini_tutorial_video_for_current()
        engine.mark_mini_tutorial_played()
        self.prompt_banner.hide_banner()
        bg_subject = SUBJECT_KEY_TO_BG.get(self._current_subject_key)
        self.mini_tutorial_page.show_mini_tutorial(mini_title, reason, video_path, subject=bg_subject)
        self._show(self.mini_tutorial_page)

    def _load_styles(self):
        try:
            with open("styles.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    def closeEvent(self, event):
        self.tutorial_page.stop()
        self.tutorial_page.camera.release()
        self.tutorial_page.face.close()
        self.tutorial_page.gesture.close()
        super().closeEvent(event)
