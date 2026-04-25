"""Pytest path setup for repository-level test discovery."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
root_text = str(ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)

existing_tests_module = sys.modules.get("tests")
existing_path = str(getattr(existing_tests_module, "__file__", "")) if existing_tests_module else ""
if existing_tests_module is not None and not existing_path.startswith(root_text):
    del sys.modules["tests"]
