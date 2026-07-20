"""Start profile API, quiz API and the desktop application together."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
children = []


def wait_port(port, timeout=12):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.4):
                return True
        except OSError:
            time.sleep(.25)
    return False


def start(command, cwd, env=None):
    process = subprocess.Popen(command, cwd=cwd, env=env)
    children.append(process)
    return process


def main():
    python = sys.executable
    print("Starting local profile dashboard...")
    start([python, "app.py"], ROOT / "student_profile_module")
    print("Starting quiz API...")
    # The project historically had separate desktop/quiz venvs. When the
    # active desktop venv does not contain uvicorn, expose the already-installed
    # quiz packages to the same Python process instead of failing at startup.
    quiz_env = os.environ.copy()
    quiz_packages = ROOT / "quiz" / "backend" / "venv" / "Lib" / "site-packages"
    existing_pythonpath = quiz_env.get("PYTHONPATH", "")
    quiz_env["PYTHONPATH"] = str(quiz_packages) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    start(
        [python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        ROOT / "quiz" / "backend",
        env=quiz_env,
    )
    if not wait_port(5000) or not wait_port(8000):
        raise RuntimeError("A backend did not start. Run software_preflight.py and install the listed requirements.")
    print("Starting AI 3D Tutor...")
    desktop = start([python, "main.py"], ROOT / "integrated_app")
    return desktop.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
