import unittest

from voice.intent_detector import IntentDetector


class YesNoIntentTests(unittest.TestCase):
    def test_clear_yes_variants(self):
        for phrase in ("yes", "Yeah please", "haan", "please explain", "help"):
            self.assertEqual(IntentDetector.detect_yes_no(phrase), "YES", phrase)

    def test_clear_no_variants(self):
        for phrase in ("no", "nope", "nahi", "continue", "skip"):
            self.assertEqual(IntentDetector.detect_yes_no(phrase), "NO", phrase)

    def test_ambiguous_response_is_never_guessed(self):
        for phrase in ("not sure", "yes no", "maybe", "noise", ""):
            self.assertIsNone(IntentDetector.detect_yes_no(phrase), phrase)


if __name__ == "__main__":
    unittest.main()
