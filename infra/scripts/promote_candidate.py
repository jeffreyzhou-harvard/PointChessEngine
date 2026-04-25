#!/usr/bin/env python3
"""Promote a Champion-mode candidate after explicit confirmation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Perform safe git merge instead of printing instructions")
    args = parser.parse_args()

    if not args.confirm:
        print("Refusing promotion without --confirm.")
        return 1

    config = load_config(Path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    candidate = next((c for c in config.get("candidates", []) if c.get("candidate_id") == args.candidate_id), None)
    if not candidate:
        print(f"Candidate not found in config: {args.candidate_id}")
        return 1

    report_root = ROOT / config.get("report_root", "reports/comparisons") / task_id
    result_path = report_root / args.candidate_id / "result.json"
    if not result_path.exists():
        print(f"Refusing promotion: missing result JSON at {result_path}")
        return 1
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("tests_passed") != result.get("tests_total") or not result.get("contract_tests_passed"):
        print("Refusing promotion: tests or contract checks did not pass.")
        return 1

    comparison = report_root / "comparison.md"
    if not comparison.exists():
        print(f"Refusing promotion: missing comparison report at {comparison}")
        return 1

    branch = candidate.get("branch_name")
    canonical = config.get("canonical_branch", "main")
    if not branch:
        print("Refusing promotion: candidate has no branch_name.")
        return 1

    commands = [
        ["git", "checkout", canonical],
        ["git", "merge", "--no-ff", branch, "-m", f"Promote {args.candidate_id} for {task_id}"],
    ]
    print("Promotion commands:")
    for command in commands:
        print("+", " ".join(command))
    print("Loser branches will not be deleted.")

    if args.execute:
        for command in commands:
            subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
