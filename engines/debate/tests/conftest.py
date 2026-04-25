"""Make the debate engine package importable during pytest runs."""

from __future__ import annotations

import sys
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
path_text = str(ENGINE_ROOT)
if path_text not in sys.path:
    sys.path.insert(0, path_text)
