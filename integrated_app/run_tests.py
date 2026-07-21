"""Run the complete test suite reliably from either repo root or app folder."""

import os
import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))

suite = unittest.defaultTestLoader.discover(str(APP_DIR / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
