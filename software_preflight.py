"""Read-only pre-hardware software audit for the ELC project."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "integrated_app"
failures: list[str] = []
warnings: list[str] = []
passes: list[str] = []


def passed(message: str):
    passes.append(message)
    print(f"PASS  {message}")


def warned(message: str):
    warnings.append(message)
    print(f"WARN  {message}")


def failed(message: str):
    failures.append(message)
    print(f"FAIL  {message}")


def check_python():
    broken = []
    for base in (APP, ROOT / "quiz" / "backend", ROOT / "student_profile_module"):
        for path in base.rglob("*.py"):
            if any(part in {"venv", "node_modules", "__pycache__"} for part in path.parts):
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except Exception as exc:
                broken.append(f"{path.relative_to(ROOT)}: {exc}")
    failed("Python syntax: " + "; ".join(broken)) if broken else passed("Python source syntax")


def check_tasks():
    videos = 0
    tasks = 0
    for subject, filename in {
        "biology": "tasks_kidney.json",
        "chemistry": "tasks_chemistry.json",
        "physics": "tasks_physics.json",
    }.items():
        path = APP / filename
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failed(f"{subject} task JSON: {exc}")
            continue
        subject_tasks = [task for seg in config.get("segments", []) for task in seg.get("tasks", [])]
        tasks += len(subject_tasks)
        bad = []
        for task in subject_tasks:
            for key in ("task_id", "type", "prompt", "mini_tutorial_title"):
                if not task.get(key):
                    bad.append(f"{task.get('task_id', '?')} missing {key}")
            video = task.get("mini_tutorial_video")
            if video:
                videos += 1
                if not (APP / "ui" / video).exists():
                    bad.append(f"missing video {video}")
        failed(f"{subject} content: " + "; ".join(bad)) if bad else passed(
            f"{subject.title()} content ({len(subject_tasks)} tasks)"
        )
    passed(f"Task library total: {tasks} tasks / {videos} tutorial references")
    try:
        sys.path.insert(0, str(APP))
        from tools.validate_task_targets import validate
        checked, target_errors = validate()
        if target_errors:
            failed("Task/scene reachability: " + "; ".join(target_errors))
        else:
            passed(f"Task/scene reachability ({checked} tasks)")
    except Exception as exc:
        failed(f"Task/scene reachability validator: {exc}")


def check_assets():
    required = [
        APP / "ui" / "tutorial_3d.html",
        APP / "ui" / "static" / "img" / "avatar_banner.png",
        APP / "ui" / "static" / "models" / "Biology_Kidney_Lab_Table.glb",
        APP / "ui" / "static" / "models" / "Realistic_Scalpel.glb",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    failed("Missing core assets: " + ", ".join(missing)) if missing else passed("Core UI, avatar and 3D assets")


def check_quiz_db():
    path = ROOT / "quiz" / "backend" / "quiz.db"
    if not path.exists():
        failed("Quiz database is missing")
        return
    try:
        with sqlite3.connect(path) as conn:
            tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
            qtable = "questions" if "questions" in tables else "question"
            count = conn.execute(f"select count(*) from {qtable}").fetchone()[0]
        passed(f"Quiz database ({count} questions)")
    except Exception as exc:
        failed(f"Quiz database: {exc}")


def check_dependencies():
    groups = {
        "desktop": ["PyQt6", "cv2", "mediapipe", "numpy"],
        "profile backend": ["flask", "werkzeug"],
        "quiz backend": ["fastapi", "uvicorn", "sqlalchemy"],
        "AI/voice optional": ["google.genai", "groq", "speech_recognition", "pyttsx3"],
    }
    def module_available(name):
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, AttributeError):
            # Dotted optional modules (for example google.genai) raise when
            # their parent package is absent; that is a normal "missing"
            # result, not a reason for preflight itself to crash.
            return False

    for label, modules in groups.items():
        missing = [name for name in modules if not module_available(name)]
        if missing:
            warned(f"{label} packages unavailable in this interpreter: {', '.join(missing)}")
        else:
            passed(f"{label} packages")
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or (APP / ".env").exists()):
        warned("No AI key detected; offline guidance remains available")
    else:
        passed("AI configuration file/key detected")


def main():
    print("ELC SOFTWARE PREFLIGHT (hardware intentionally optional)\n")
    check_python()
    check_tasks()
    check_assets()
    check_quiz_db()
    check_dependencies()
    print(f"\nSUMMARY: {len(passes)} passed, {len(warnings)} warnings, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
