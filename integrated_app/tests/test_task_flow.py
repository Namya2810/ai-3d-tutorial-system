import unittest
from pathlib import Path

from session_state import SessionState
from task_engine import TaskEngine


APP_DIR = Path(__file__).resolve().parents[1]


class TaskFlowTests(unittest.TestCase):
    def make_engine(self):
        state = SessionState()
        engine = TaskEngine(APP_DIR / "tasks_kidney.json", state)
        engine.start()
        return state, engine

    def test_partial_multi_target_selection_survives_reask(self):
        _, engine = self.make_engine()
        engine.mark_asked()
        engine.record_selected_target("Kidney_Left")
        engine.state = engine.STATE_ASKING
        self.assertEqual(engine.selected_targets_for_current(), ["Kidney_Left"])
        engine.mark_asked()
        self.assertEqual(engine.selected_targets_for_current(), ["Kidney_Left"])

    def test_wrong_result_tutorial_retry_same_task(self):
        state, engine = self.make_engine()
        task_id = engine.current_task()["task_id"]
        engine.mark_asked()
        engine.record_result(False)
        self.assertEqual(engine.state, engine.STATE_MINI_TUTORIAL)
        engine.mark_mini_tutorial_played()
        engine.retry_current_task()
        self.assertEqual(engine.current_task()["task_id"], task_id)
        self.assertEqual(state.mini_tutorials_played[task_id], 1)

    def test_correct_result_advances_exactly_once(self):
        _, engine = self.make_engine()
        first = engine.current_task()["task_id"]
        engine.mark_asked()
        engine.record_result(True)
        self.assertNotEqual(engine.current_task()["task_id"], first)
        self.assertEqual(engine.current_task_position()[0], 2)

    def test_all_subject_tasks_have_runtime_targets(self):
        for filename in ("tasks_kidney.json", "tasks_chemistry.json", "tasks_physics.json"):
            engine = TaskEngine(APP_DIR / filename, SessionState())
            for task in engine.all_tasks_flat():
                if task["type"] == "gesture_task":
                    self.assertTrue(task.get("expected_targets"), task["task_id"])


if __name__ == "__main__":
    unittest.main()
