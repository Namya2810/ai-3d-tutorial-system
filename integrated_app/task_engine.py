"""
task_engine.py

segment_tracker.py ki jagah. Purana wala sirf TIME dekhta tha (25 sec ho
gaye -> agla segment). Ye wala TASK COMPLETION dekhta hai - jab tak
current task sahi se complete nahi hota (voice se sahi jawaab, ya sahi
gesture), agla task nahi aata.

State machine (per task):
    ASKING        -> task ka prompt "poocha" jaana chahiye (app_window.py
                     isko dekh kar TaskVoiceThread chalata hai, ya gesture
                     ka wait shuru karta hai)
    WAITING       -> answer/gesture ka wait ho raha hai
    MINI_TUTORIAL -> galat jawaab/gesture -> mini-tutorial khulna chahiye
    DONE          -> saare segments/tasks khatam

Is class ka kaam SIRF state track karna hai - voice bolna, gesture padhna,
UI dikhana - ye sab app_window.py/tutorial_3d_page.py karte hain. Isse
engine ko test karna aasan hai aur UI se independent rehta hai.
"""

import json


# Chemistry and Physics currently use lightweight procedural Three.js scenes.
# Keep their interaction contract here so every gesture task has an actual,
# named object to hit even before final Blender assets arrive.
PRE_HARDWARE_TARGETS = {
    "chem_t1_introduction_to_titration": ["Burette", "Pipette", "Conical_Flask"],
    "chem_t3_rule_1_of_titration": ["Burette"],
    "chem_t4_burette_demonstration": ["Burette"],
    "chem_t6_conical_flask": ["Conical_Flask"],
    "chem_t7_phenolphthalein_indicator": ["Phenolphthalein"],
    "chem_t8_filling_the_burette": ["Burette"],
    "chem_t9_pipetting_the_sample": ["Pipette"],
    "chem_t10_starting_the_titration": ["Burette_Stopcock", "Conical_Flask"],
    "chem_t11_endpoint_detection": ["Conical_Flask"],
    "chem_t12_colour_change": ["Conical_Flask"],
    "chem_t13_reading_the_burette": ["Burette"],
    "phy_t2_bike_power_flow_explained": ["Engine", "Clutch", "Gearbox", "Chain", "Rear_Wheel"],
    "phy_t3_clutch_engage_disengage": ["Clutch"],
    "phy_t5_clutch_plate_stack": ["Clutch"],
    "phy_t6_inside_a_bike_gearbox": ["Gearbox"],
    "phy_t8_types_of_gears": ["Main_Shaft", "Gear_1", "Bearing"],
    "phy_t10_manual_transmission": ["Gearbox"],
    "phy_t12_main_shaft_vs_counter_shaft": ["Main_Shaft", "Counter_Shaft"],
    "phy_t13_bearings_inside_a_gearbox": ["Bearing"],
    "phy_t14_gear_reduction": ["Gear_1", "Gear_4"],
    "phy_t15_sequential_gearbox_mechanism": ["Gearbox"],
    "phy_t16_sequential_gearbox_animation": ["Shift_Drum"],
    "phy_t18_shift_drum_mechanism": ["Shift_Drum"],
    "phy_t19_ratchet_mechanism": ["Ratchet"],
    "phy_t22_planetary_gear_animation": ["Planetary_Gear"],
    "phy_t23_rack_pinion_worm_gears": ["Rack_Pinion", "Worm_Gear"],
    "phy_t25_differential_working": ["Differential"],
}


class TaskEngine:
    STATE_ASKING = "asking"
    STATE_WAITING = "waiting"
    STATE_MINI_TUTORIAL = "mini_tutorial"
    STATE_DONE = "done"

    def __init__(self, tasks_path, session_state):
        self.session_state = session_state
        self.load(tasks_path)

    def load(self, tasks_path):
        """Naya tasks.json load karo - subject switch karte waqt use hota hai
        (jaise Biology se Physics pe switch karna). Poora state reset ho
        jaata hai jaisa fresh start ho."""
        with open(tasks_path, "r") as f:
            config = json.load(f)
        self.segments = config["segments"]
        for segment in self.segments:
            for task in segment["tasks"]:
                targets = PRE_HARDWARE_TARGETS.get(task["task_id"])
                if targets and not task.get("expected_targets"):
                    task["expected_targets"] = targets
                    task.setdefault("selection_mode", "ordered" if len(targets) > 1 else "single")
                    task.setdefault("dwell_ms", 650)
        self.tasks_path = tasks_path

        self._seg_index = 0
        self._task_index = 0
        self.state = self.STATE_ASKING
        self.attempt_counts = {}
        self.selected_targets = {}

    def start(self):
        self._seg_index = 0
        self._task_index = 0
        self.state = self.STATE_ASKING
        self.attempt_counts = {}
        self.selected_targets = {}
        # dict: task_id -> kitni baar mini-tutorial khula (set nahi, count
        # chahiye tha - roadmap ki requirement yahi thi)
        self.session_state.mini_tutorials_played = {}
        self._sync_session_state()

    # ---- Kahan hain abhi -----------------------------------------------

    def current_segment(self):
        return self.segments[self._seg_index]

    def current_task(self):
        return self.current_segment()["tasks"][self._task_index]

    def _sync_session_state(self):
        # Confusion engine / avatar check-in / quiz isi se current context
        # padhte hain - segment_id purana naam hai isliye rakha hai
        # (quiz_page.py isko already expect karta hai).
        self.session_state.current_segment_id = self.current_segment()["id"]
        self.session_state.current_task_id = self.current_task()["task_id"]

    # ---- app_window.py in cheezon ko call karta hai --------------------

    def mark_asked(self):
        """Task ka prompt bol/dikha diya gaya - ab jawaab ka wait hai."""
        self.state = self.STATE_WAITING

    def record_result(self, correct: bool):
        """Voice answer check ho jaaye ya gesture match ho jaaye, yahan
        bata do. correct=True -> agla task. False -> mini-tutorial."""
        task = self.current_task()
        self.attempt_counts[task["task_id"]] = (
            self.attempt_counts.get(task["task_id"], 0) + 1
        )
        if correct:
            self.selected_targets.pop(task["task_id"], None)
            self._advance()
        else:
            self.state = self.STATE_MINI_TUTORIAL

    def get_mini_tutorial_for_current(self):
        task = self.current_task()
        return task["mini_tutorial_id"], task["mini_tutorial_title"]

    def get_mini_tutorial_video_for_current(self):
        """Real .mp4 file ka path - tasks.json ke 'mini_tutorial_video'
        field se aata hai."""
        return self.current_task().get("mini_tutorial_video")

    def mark_mini_tutorial_played(self):
        task_id = self.current_task()["task_id"]
        played = self.session_state.mini_tutorials_played
        played[task_id] = played.get(task_id, 0) + 1

    def retry_current_task(self):
        """Mini-tutorial dekh liya -> SAME task dobara poochna hai (loop
        back, jaisa roadmap mein bola gaya tha)."""
        self.state = self.STATE_ASKING

    def record_selected_target(self, target_id):
        """Persist correct partial progress across check-ins and task re-ASKs."""
        if not target_id:
            return []
        task_id = self.current_task()["task_id"]
        selected = self.selected_targets.setdefault(task_id, [])
        if target_id not in selected:
            selected.append(target_id)
        return list(selected)

    def selected_targets_for_current(self):
        return list(self.selected_targets.get(self.current_task()["task_id"], []))

    # ---- Aage badhna ------------------------------------------------------

    def _advance(self):
        seg = self.current_segment()
        if self._task_index < len(seg["tasks"]) - 1:
            self._task_index += 1
        elif self._seg_index < len(self.segments) - 1:
            self._seg_index += 1
            self._task_index = 0
        else:
            self.state = self.STATE_DONE
            return
        self.state = self.STATE_ASKING
        self._sync_session_state()

    # ---- Quiz / confusion engine ke liye (segment-weighted questions etc.) -

    def all_tasks_flat(self):
        flat = []
        for seg in self.segments:
            for task in seg["tasks"]:
                flat.append({**task, "segment_id": seg["id"]})
        return flat

    def current_task_position(self):
        """Return the learner-facing 1-based task number and total."""
        completed = sum(len(seg["tasks"]) for seg in self.segments[:self._seg_index])
        current = completed + self._task_index + 1
        total = sum(len(seg["tasks"]) for seg in self.segments)
        return current, total

    def progress_summary(self):
        """Kitne tasks pe kitni baar mini-tutorial khula aur kitne attempts
        lage - quiz page isse 'kis topic pe zyada questions do' decide
        karega, confusion_engine isse session-summary score banayega."""
        played = self.session_state.mini_tutorials_played
        return [
            {
                "task_id": t["task_id"],
                "segment_id": t["segment_id"],
                "prompt": t["prompt"],
                "mini_tutorial_play_count": played.get(t["task_id"], 0),
                "attempts": self.attempt_counts.get(t["task_id"], 0),
                "confusion_score": self.session_state.task_confusion_score(t["task_id"]),
            }
            for t in self.all_tasks_flat()
        ]

    def mini_tutorial_session_summary(self):
        """Session khatam hone par quiz-generation ke liye ready summary
        banata hai, keyed by mini_tutorial_title (= quiz DB ka Subtopic.name -
        xlsx quiz-bank 'Topic' column ise seedha match karta hai, isliye ID
        mapping ki zaroorat nahi, naam se hi ho jaata hai).

        Ek hi mini_tutorial_title kai task_ids pe repeat ho sakta hai (jaise
        physics mein "Types of Gears" do jagah hai) - un sabko yahan ek hi
        subtopic mein combine kiya jaata hai (play counts jode jaate hain,
        confusion scores milaake average liya jaata hai).

        Returns: {mini_tutorial_title: {"play_count": int, "confusion_score": 0..1}}
        """
        played = self.session_state.mini_tutorials_played
        summary = {}
        for t in self.all_tasks_flat():
            title = t["mini_tutorial_title"]
            task_id = t["task_id"]
            play_count = played.get(task_id, 0)
            scores = self.session_state.task_confusion_scores.get(task_id, [])

            entry = summary.setdefault(title, {"play_count": 0, "_scores": []})
            entry["play_count"] += play_count
            entry["_scores"].extend(scores)

        for title, entry in summary.items():
            scores = entry.pop("_scores")
            entry["confusion_score"] = (sum(scores) / len(scores)) if scores else 0.5

        return summary
