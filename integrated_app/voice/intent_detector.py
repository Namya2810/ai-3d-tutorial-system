import re


class IntentDetector:
    """Simple keyword-based intent classifier for voice commands."""

    def __init__(self):
        self.keywords = {
            "STOP": ["stop", "quit", "exit", "goodbye", "bye"],
            "YES": ["yes", "yeah", "yep", "sure", "okay", "continue", "next lesson", "next"],
            "NO": ["no", "nope", "not now", "wait"],
            "REPEAT": ["repeat", "again", "say that again", "one more time"],
            "HELP": ["help", "i don't understand", "i dont understand", "confused", "stuck"],
            "EXPLAIN": ["explain", "what is", "what's", "how does", "why", "define", "meaning of"],
        }

    def detect(self, text):
        if not text:
            return None

        text = text.lower().strip()

        # Check in priority order so short commands (stop/yes/no) aren't
        # accidentally overridden by a partial keyword match elsewhere.
        for intent in ("STOP", "YES", "NO", "REPEAT", "HELP", "EXPLAIN"):
            for phrase in self.keywords[intent]:
                if phrase in text:
                    return intent

        # Fallback: treat unmatched questions as a request for help
        if "?" in text:
            return "HELP"

        return "EXPLAIN"

    @staticmethod
    def detect_yes_no(text):
        """Return YES/NO only for an unambiguous, whole-word response.

        Generic intent matching uses substring checks, which is useful for
        commands but unsafe for a consent-style assistance prompt.  For
        example, "not sure" used to match "sure" and become YES.  This
        dedicated classifier intentionally returns None when both sides or
        neither side are present, so the UI can ask again instead of guessing.
        """
        if not text:
            return None
        words = set(re.findall(r"[a-zA-Z']+", text.lower()))
        yes_words = {"yes", "yeah", "yep", "yup", "haan", "han", "help", "explain"}
        no_words = {"no", "nope", "nah", "nahi", "continue", "skip"}
        has_yes = bool(words & yes_words)
        has_no = bool(words & no_words)
        if has_yes == has_no:
            return None
        return "YES" if has_yes else "NO"
