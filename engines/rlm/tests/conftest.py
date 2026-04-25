"""Make the RLM engine package importable during pytest runs."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
path_text = str(REPO_ROOT)
if path_text not in sys.path:
    sys.path.insert(0, path_text)
