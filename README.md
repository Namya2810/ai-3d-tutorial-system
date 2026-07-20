# AI 3D Tutorial System

Desktop learning application combining interactive Three.js labs, camera or
ESP32 glove gestures, an AI teacher, adaptive mini-tutorials, quizzes, live
confusion scoring, and a student dashboard for Biology, Chemistry and Physics.

## Quick start

On Windows PowerShell, from this folder:

```powershell
python -m venv integrated_app\venv
.\integrated_app\venv\Scripts\python.exe -m pip install -r integrated_app\requirements.txt
.\integrated_app\venv\Scripts\python.exe software_preflight.py
.\integrated_app\venv\Scripts\python.exe run_all.py
```

The launcher starts the profile service on port 5000, quiz API on port 8000,
and then the desktop app. Hardware is optional; camera gestures are the
fallback when `GestureGlove` is not connected.

## Verification

```powershell
cd integrated_app
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe tools\validate_task_targets.py
```

See [integrated_app/README.md](integrated_app/README.md) and
[integrated_app/hardware/GLOVE_INTEGRATION_GUIDE.md](integrated_app/hardware/GLOVE_INTEGRATION_GUIDE.md)
for architecture, firmware and hardware integration details.

## Private data

API keys (`.env`), virtual environments, raw glove CSV sessions, caches,
generated comparison folders and frontend dependencies are intentionally
excluded from Git. Do not commit student-identifiable exports.
