"""
main.py - AI 3D Tutorial System, integrated

Ye sabhi teammates ke modules (VR/3D+face+gesture, Voice, Quiz backend,
Student Profile backend) ko ek single PyQt6 desktop app mein jodta hai,
ek shared SessionState + confusion_engine.py ke through.

BEFORE RUNNING - do backend services alag terminals mein chalao:
    1) Quiz backend   (FastAPI):  cd quiz_backend  &&  uvicorn main:app --reload
    2) Profile backend (Flask):  cd profile_backend &&  python app.py

Phir yeh app chalao:
    python main.py

Dekho README.md poori setup instructions ke liye.
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 'voice' folder ke andar ke files (gemini_ai.py, speech_to_text.py, ...)
# ek dusre ko plain `from gemini_ai import ...` se import karte hain, isliye
# voice/ folder ko bhi sys.path mein daalna zaroori hai (sirf root add karne
# se kaam nahi chalega).
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "voice"))

from PyQt6.QtWidgets import QApplication

from session_state import SessionState
from ui.app_window import MainWindow


def main():
    app = QApplication(sys.argv)

    session_state = SessionState()
    window = MainWindow(session_state)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
