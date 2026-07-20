import speech_recognition as sr


class SpeechRecognizer:
    """Wraps the microphone + Google Web Speech API for quick STT."""

    def __init__(self, timeout=5, phrase_time_limit=10):
        self.recognizer = sr.Recognizer()
        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit

    def listen(self):
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(
                    source, timeout=self.timeout, phrase_time_limit=self.phrase_time_limit
                )
            except sr.WaitTimeoutError:
                return ""

        try:
            # Indian English improves yes/no and common Hindi-English words
            # for the project's primary classroom environment.
            text = self.recognizer.recognize_google(audio, language="en-IN")
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"Speech recognition error: {e}")
            return ""
