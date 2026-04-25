#!/usr/bin/env python3
"""Convenience wrapper for local-first Champion mode."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_input_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate", help="Optional candidate_id filter")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--jobs", type=int, help="Candidate test parallelism")
    parser.add_argument("--skip-create-worktrees", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-score", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()
    config_path = resolve_input_path(args.config)

    command = [
        sys.executable,
        str(SCRIPT_DIR / "run_champion_stage.py"),
        "--task",
        args.task,
        "--config",
        str(config_path),
    ]
    if not args.skip_create_worktrees:
        command.append("--create-worktrees")
    if not args.skip_tests:
        command.append("--run-tests")
    if not args.skip_score:
        command.append("--score")
    if not args.skip_report:
        command.append("--write-report")
    if args.candidate:
        command.extend(["--candidate", args.candidate])
    if args.jobs:
        command.extend(["--jobs", str(args.jobs)])
    if args.dry_run:
        command.append("--dry-run")
    if args.continue_on_failure:
        command.append("--continue-on-failure")

    print("+", " ".join(command))
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
