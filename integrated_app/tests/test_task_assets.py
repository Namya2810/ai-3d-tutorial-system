import unittest

from tools.validate_task_targets import validate


class TaskAssetTests(unittest.TestCase):
    def test_all_tasks_are_achievable(self):
        count, errors = validate()
        self.assertEqual(count, 55)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
