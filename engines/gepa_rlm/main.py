"""Entry point mirroring the other engine directories.

Usage:
    python -m engines.gepa_rlm --uci
    python engines/gepa_rlm/main.py --uci
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
path_text = str(REPO_ROOT)
if path_text not in sys.path:
    sys.path.insert(0, path_text)

from engines.gepa_rlm.uci import run_uci


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pointchess-gepa-rlm")
    parser.add_argument("--uci", action="store_true", help="Run UCI mode; this is also the default")
    parser.parse_args(argv)
    run_uci()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
