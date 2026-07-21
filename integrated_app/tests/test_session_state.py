import threading
import unittest

from session_state import SessionState


class SessionStateTests(unittest.TestCase):
    def test_concurrent_counter_updates_are_not_lost(self):
        state = SessionState()

        def update():
            for _ in range(500):
                state.register_help_request()

        workers = [threading.Thread(target=update) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(state.help_requests, 2000)

    def test_numeric_chemistry_task_is_well_formed(self):
        import json
        from pathlib import Path

        data = json.loads(
            (Path(__file__).parents[1] / "tasks_chemistry.json").read_text(encoding="utf-8")
        )
        numeric = [
            task for segment in data["segments"] for task in segment["tasks"]
            if task.get("type") == "numeric_question"
        ]
        self.assertTrue(numeric)
        self.assertTrue(all("expected_numeric_answer" in task for task in numeric))


if __name__ == "__main__":
    unittest.main()
