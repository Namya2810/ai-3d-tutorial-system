import threading

import pyttsx3


# pyttsx3's Windows/SAPI driver owns one native event loop per process.
# Task narration and avatar check-ins run on different QThreads, so without
# serialization two runAndWait() calls can overlap and terminate the app with
# "RuntimeError: run loop already started".
_speech_lock = threading.Lock()
_engine_lock = threading.Lock()
_active_engine = None


def stop_speaking():
    """Immediately stop the current narration when a lesson/page changes."""
    with _engine_lock:
        engine = _active_engine
    if engine is not None:
        try:
            engine.stop()
        except Exception:
            pass


def speak(text):
    """Speak the given text out loud.

    A fresh engine is created per call (rather than reusing one global
    engine) because pyttsx3 on Windows can silently stop working if the
    same engine instance is reused across many calls, especially across
    threads.
    """
    if not text:
        return

    global _active_engine
    with _speech_lock:
        engine = None
        try:
            engine = pyttsx3.init()
            with _engine_lock:
                _active_engine = engine
            engine.setProperty("rate", 170)
            engine.say(str(text))
            engine.runAndWait()
        except Exception as exc:
            # Voice is an enhancement; a SAPI/driver failure must never close
            # the interactive lesson. Keep the traceback concise for diagnosis.
            print(f"[TextToSpeech] Speech skipped: {exc}")
        finally:
            with _engine_lock:
                if _active_engine is engine:
                    _active_engine = None
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
