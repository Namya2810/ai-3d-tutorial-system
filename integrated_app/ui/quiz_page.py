"""
quiz_page.py

Roadmap Phase 8 ka UI. Quiz backend (FastAPI, alag se run hota hai - README
dekho) se subjects/topics/subtopics fetch karta hai.

CHANGE (roadmap correction - session-wide quiz, per-mini-tut difficulty):
  - Jab task_engine available hai (normal flow - quiz interactive session ke
    baad chalta hai), "Generate Quiz" ab ek hi topic ke SAARE mini-tuts se
    banta hai - har mini-tut ko uske apne replay-count aur uske apne
    confusion-score ke hisaab se questions milte hain (backend:
    generate-session-quiz). Ye ab manual subtopic-pick pe depend nahi karta.
  - Subject/Topic/Subtopic pickers ab bhi maujood hain taaki (a) topic select
    kiya ja sake session-quiz ke liye, aur (b) quiz page standalone khulne pe
    (task_engine=None, jaise testing ke waqt) purana single-subtopic flow
    fallback ke roop mein kaam kare.
  - Quiz complete hone par: har mini-tut ke apne score ke saath alag-alag
    submit-quiz call jaati hai (ek hi confusion_score sabke liye lagana galat
    hota - har subtopic ka apna tha). Ek session-end average confusion score
    bhi dashboard ko jaata hai (log_confusion_summary).
"""

import time
import re
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QRadioButton, QButtonGroup, QScrollArea
)

import api_client
import confusion_engine


class QuizPage(QWidget):
    def __init__(self, session_state=None, task_engine=None):
        super().__init__()
        self.setObjectName("QuizPage")
        self.session_state = session_state
        # task_engine present -> session-wide quiz (normal flow, after the
        # interactive tutorial). task_engine=None -> old single-subtopic
        # fallback (manual pick), useful for standalone testing of this page.
        self.task_engine = task_engine

        self.questions = []            # each item: QuestionOut dict + "subtopic_id"
        self.current_index = 0
        self.score = 0
        self.question_started_at = None
        self.selected_subtopic_id = None
        self._subtopic_confusion = {}  # subtopic_id -> confusion score (0..1), set at generate time

        # subtopic_id -> {"correct": int, "total": int} - per-mini-tut score,
        # since each mini-tut has its own confusion score to submit against.
        self._subtopic_results = defaultdict(lambda: {"correct": 0, "total": 0})

        layout = QVBoxLayout(self)

        title = QLabel("Quiz")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # ---- Subject / Topic / Subtopic pickers ----
        picker_row = QHBoxLayout()
        self.subject_box = QComboBox()
        self.topic_box = QComboBox()
        self.subtopic_box = QComboBox()
        picker_row.addWidget(self.subject_box)
        picker_row.addWidget(self.topic_box)
        picker_row.addWidget(self.subtopic_box)
        layout.addLayout(picker_row)

        self.confusion_label = QLabel("Session confusion score: -")
        layout.addWidget(self.confusion_label)

        self.generate_btn = QPushButton("Generate Quiz")
        self.generate_btn.clicked.connect(self.generate_quiz)
        layout.addWidget(self.generate_btn)

        # ---- Question area ----
        self.question_label = QLabel("")
        self.question_label.setWordWrap(True)
        self.question_label.setObjectName("PageTitle")
        layout.addWidget(self.question_label)

        self.options_group = QButtonGroup(self)
        self.option_buttons = []
        for _ in range(4):
            btn = QRadioButton("")
            self.option_buttons.append(btn)
            self.options_group.addButton(btn)
            layout.addWidget(btn)

        self.next_btn = QPushButton("Submit Answer")
        self.next_btn.clicked.connect(self.submit_answer)
        self.next_btn.setEnabled(False)
        layout.addWidget(self.next_btn)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        layout.addStretch()

        self.subject_box.currentIndexChanged.connect(self._on_subject_changed)
        self.topic_box.currentIndexChanged.connect(self._on_topic_changed)
        self.subtopic_box.currentIndexChanged.connect(self._on_subtopic_changed)

        self._load_subjects()

    # ---- Loading dropdowns from the quiz backend ----

    def _load_subjects(self):
        subjects = api_client.get_subjects()
        self.subject_box.clear()
        for s in subjects:
            self.subject_box.addItem(s["name"], s["id"])

    def _on_subject_changed(self):
        subject_id = self.subject_box.currentData()
        self.topic_box.clear()
        self.subtopic_box.clear()
        if subject_id is None:
            return
        topics = api_client.get_topics(subject_id)
        for t in topics:
            self.topic_box.addItem(t["name"], t["id"])

    def _on_topic_changed(self):
        topic_id = self.topic_box.currentData()
        self.subtopic_box.clear()
        if topic_id is None:
            return
        subtopics = api_client.get_subtopics(topic_id)
        for st in subtopics:
            self.subtopic_box.addItem(st["name"], st["id"])

    def _on_subtopic_changed(self):
        self.selected_subtopic_id = self.subtopic_box.currentData()
        if self.session_state and self.selected_subtopic_id is not None:
            self.session_state.current_subtopic_id = self.selected_subtopic_id
            self.session_state.reset_quiz_counters()

    # ---- Quiz flow ----

    def generate_quiz(self):
        if self.task_engine is not None:
            self._generate_session_quiz()
        else:
            self._generate_single_subtopic_quiz()

    def _generate_session_quiz(self):
        """Normal flow: whole topic, every mini-tut weighted by replay count,
        difficulty per mini-tut's own confusion score (backend does the mix)."""
        topic_id = self.topic_box.currentData()
        if topic_id is None:
            self.result_label.setText("Pick a topic first.")
            return

        subtopics = api_client.get_subtopics(topic_id)
        if not subtopics:
            self.result_label.setText("Couldn't load mini-tuts for this topic - is the quiz backend running?")
            return
        # mini_tutorial_title in tasks.json == Subtopic.name in the quiz DB
        # (both come from the same xlsx "Topic" column) - match on name.
        def normalise_title(value):
            value = re.sub(r"\([^)]*\)", "", value.lower())
            value = value.replace("kidneys", "kidney")
            value = re.sub(r"\bof\s+the\s+kidney\b|\bof\s+kidney\b", "", value)
            return re.sub(r"[^a-z0-9]+", " ", value).strip()

        normalised_subtopics = {normalise_title(st["name"]): st for st in subtopics}

        mini_summary = self.task_engine.mini_tutorial_session_summary()
        subtopic_sessions = []
        self._subtopic_confusion = {}
        # Only active task JSON titles participate. Obsolete/removed lesson
        # topics are excluded even if an older backend DB still contains them.
        for name, info in mini_summary.items():
            subtopic = normalised_subtopics.get(normalise_title(name))
            if not subtopic:
                continue
            subtopic_id = subtopic["id"]
            confusion_0_to_1 = info.get("confusion_score", 0.5)
            self._subtopic_confusion[subtopic_id] = confusion_0_to_1
            subtopic_sessions.append({
                "subtopic_id": subtopic_id,
                "play_count": info.get("play_count", 0),
                "confusion_score": confusion_0_to_1 * 100,
            })

        avg_confusion = confusion_engine.compute_session_average(self.session_state).score if self.session_state else 0.0
        self.confusion_label.setText(f"Session confusion score: {avg_confusion * 100:.0f}%")

        grouped = api_client.generate_session_quiz(topic_id, subtopic_sessions)
        self.questions = []
        for group in grouped:
            for q in group["questions"]:
                q = dict(q)
                q["subtopic_id"] = group["subtopic_id"]
                self.questions.append(q)

        self._start_quiz()

    def _generate_single_subtopic_quiz(self):
        """Fallback flow (no task_engine wired in - e.g. standalone testing):
        old behaviour, one manually-picked mini-tut, live snapshot confusion."""
        if self.selected_subtopic_id is None:
            self.result_label.setText("Pick a subject / topic / subtopic first.")
            return

        confusion_score = self.session_state.confusion_score if self.session_state else 0.0
        self.confusion_label.setText(f"Live confusion score: {confusion_score * 100:.0f}%")

        questions = api_client.generate_quiz(self.selected_subtopic_id, confusion_score)
        self.questions = [dict(q, subtopic_id=self.selected_subtopic_id) for q in questions]
        self._subtopic_confusion = {self.selected_subtopic_id: confusion_score}

        self._start_quiz()

    def _start_quiz(self):
        self.current_index = 0
        self.score = 0
        self._subtopic_results = defaultdict(lambda: {"correct": 0, "total": 0})
        self.result_label.setText("")

        if not self.questions:
            self.question_label.setText("Couldn't load questions - is the quiz backend running?")
            return

        self._show_question()

    def _show_question(self):
        if self.current_index >= len(self.questions):
            self._finish_quiz()
            return

        q = self.questions[self.current_index]
        self.question_label.setText(f"Q{self.current_index + 1}. {q['question']}")

        options = [q["optionA"], q["optionB"], q["optionC"], q["optionD"]]
        for btn, text in zip(self.option_buttons, options):
            btn.setText(text)
            btn.setChecked(False)

        self.next_btn.setEnabled(True)
        self.question_started_at = time.time()

    def submit_answer(self):
        q = self.questions[self.current_index]
        labels = ["A", "B", "C", "D"]

        selected_label = None
        for label, btn in zip(labels, self.option_buttons):
            if btn.isChecked():
                selected_label = label

        response_time = time.time() - (self.question_started_at or time.time())
        correct = selected_label == q["correct_answer"]
        if correct:
            self.score += 1

        result = self._subtopic_results[q["subtopic_id"]]
        result["total"] += 1
        if correct:
            result["correct"] += 1

        if self.session_state:
            self.session_state.register_quiz_answer(correct, response_time)

        self.current_index += 1
        self._show_question()

    def _finish_quiz(self):
        total = len(self.questions)
        self.question_label.setText("Quiz complete!")
        for btn in self.option_buttons:
            btn.setText("")
        self.next_btn.setEnabled(False)
        self.result_label.setText(f"Score: {self.score} / {total}")

        avg_response_time = (
            sum(self.session_state.quiz_response_times) / len(self.session_state.quiz_response_times)
            if self.session_state and self.session_state.quiz_response_times else 0.0
        )

        # Each mini-tut gets its own submit call with its own score and its
        # own confusion score - one blended number for all of them would be
        # wrong now that difficulty is per-mini-tut.
        for subtopic_id, result in self._subtopic_results.items():
            confusion_score = self._subtopic_confusion.get(subtopic_id, 0.5)
            api_client.submit_quiz(subtopic_id, confusion_score, result["correct"], avg_response_time)

        if self.session_state and self.session_state.student_id:
            api_client.log_quiz_score(
                self.session_state.student_id,
                self.topic_box.currentText() if self.task_engine is not None else self.subtopic_box.currentText(),
                self.score,
                total,
            )
            if self.task_engine is not None:
                avg_confusion = confusion_engine.compute_session_average(self.session_state).score
                api_client.log_confusion_summary(self.session_state.student_id, avg_confusion)
