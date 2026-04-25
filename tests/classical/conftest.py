"""Pytest path setup for classical benchmark tests."""

from __future__ import annotations

import sys
from pathlib import Path


CLASSICAL_TEST_DIR = Path(__file__).resolve().parent
path_text = str(CLASSICAL_TEST_DIR)
if path_text not in sys.path:
    sys.path.insert(0, path_text)
