#!/usr/bin/env python3
"""Run the classical milestone gate for a task ID."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLASSICAL_ORDER = [
    ("C0", "tests/classical/test_c0_uci_contract.py"),
    ("C1", "tests/classical/test_c1_board_fen_move.py"),
    ("C2", "tests/classical/test_c2_legal_move_generation.py"),
    ("C3", "tests/classical/test_c3_static_evaluation.py"),
    ("C4", "tests/classical/test_c4_alpha_beta_search.py"),
    ("C5", "tests/classical/test_c5_tactical_hardening.py"),
    ("C6", "tests/classical/test_c6_time_tt_iterative.py"),
    ("C7", "tests/classical/test_c7_uci_compatibility.py"),
    ("C8", "tests/classical/test_c8_elo_slider.py"),
]


def task_prefix(task_id: str) -> str:
    match = re.match(r"^(C\d+)", task_id)
    if not match:
        raise SystemExit(f"Milestone tests only know classical C* tasks, got {task_id!r}")
    return match.group(1)


def selected_files(task_id: str, current_only: bool) -> list[str]:
    prefix = task_prefix(task_id)
    keys = [key for key, _ in CLASSICAL_ORDER]
    if prefix not in keys:
        raise SystemExit(f"No classical milestone mapping for {task_id!r}")
    index = keys.index(prefix)
    selected = CLASSICAL_ORDER[index : index + 1] if current_only else CLASSICAL_ORDER[: index + 1]
    return [path for _, path in selected]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="Milestone task ID such as C3_STATIC_EVALUATION")
    parser.add_argument("--current-only", action="store_true", help="Run only the exact milestone file, not prior regressions")
    args = parser.parse_args()

    files = selected_files(args.task, args.current_only)
    missing = [path for path in files if not (ROOT / path).exists()]
    if missing:
        raise SystemExit(f"Missing milestone test files: {missing}")

    started = time.monotonic()
    command = [sys.executable, "-m", "pytest", "-q", *files]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    print(
        json.dumps(
            {
                "tier": "milestone",
                "milestone_task_id": args.task,
                "test_files": files,
                "passed": completed.returncode == 0,
                "duration_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
