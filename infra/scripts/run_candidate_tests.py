#!/usr/bin/env python3
"""Run configured test commands for Champion-mode candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
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


def resolve_worktree(path_text: str | None) -> Path:
    if not path_text:
        return ROOT
    path = Path(path_text)
    return path if path.is_absolute() else (ROOT / path).resolve()


def run_command(command: str, cwd: Path, output_dir: Path, index: int, dry_run: bool) -> dict:
    stdout_path = output_dir / f"command_{index}.stdout.log"
    stderr_path = output_dir / f"command_{index}.stderr.log"
    if dry_run:
        stdout_path.write_text(f"DRY RUN: {command}\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": command,
            "returncode": 0,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "dry_run": True,
        }

    completed = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "dry_run": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Champion config YAML")
    parser.add_argument("--candidate", help="Optional candidate_id filter")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute commands")
    parser.add_argument(
        "--allow-missing-worktrees",
        action="store_true",
        help="Write dry-run records for missing worktrees instead of failing",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    report_root = Path(config.get("report_root", "reports/comparisons"))
    commands = config.get("test_commands") or []
    candidates = config.get("candidates") or []

    if args.candidate:
        candidates = [c for c in candidates if c.get("candidate_id") == args.candidate]
    if not candidates:
        print("No matching candidates found.")
        return 1

    if not commands:
        print("No test_commands configured; defaulting to dry-run result records.")

    failures = 0
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id", "unknown_candidate")
        output_dir = ROOT / report_root / task_id / candidate_id
        output_dir.mkdir(parents=True, exist_ok=True)
        cwd = resolve_worktree(candidate.get("worktree_path"))
        missing_worktree = not cwd.exists()
        dry_run = args.dry_run or not commands or (missing_worktree and args.allow_missing_worktrees)
        if not cwd.exists():
            print(f"{candidate_id}: worktree missing at {cwd}")

        if missing_worktree and not dry_run:
            command_results = [
                {
                    "command": "<worktree missing>",
                    "returncode": 127,
                    "stdout_log": "",
                    "stderr_log": "",
                    "dry_run": False,
                    "error": f"worktree missing at {cwd}",
                }
            ]
        else:
            command_results = [
                run_command(command, cwd if cwd.exists() else ROOT, output_dir, i, dry_run)
                for i, command in enumerate(commands or ["<no test_commands configured>"], start=1)
            ]
        passed = sum(1 for item in command_results if item["returncode"] == 0)
        total = len(command_results)
        failed = total - passed
        failures += failed
        result = {
            "task_id": task_id,
            "candidate_id": candidate_id,
            "orchestration_type": candidate.get("orchestration_type"),
            "model_assignments": candidate.get("model_assignments", {}),
            "execution_environment": candidate.get("execution_environment"),
            "branch": candidate.get("branch_name"),
            "baseline_commit": config.get("baseline_commit", ""),
            "tests_passed": passed,
            "tests_total": total,
            "contract_tests_passed": failed == 0,
            "review_score": candidate.get("review_score"),
            "benchmark_score": candidate.get("benchmark_score"),
            "cost_estimate_usd": candidate.get("cost_estimate_usd"),
            "latency_minutes": candidate.get("latency_minutes"),
            "promotion_status": "candidate",
            "dry_run": dry_run,
            "commands": command_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result_path = output_dir / "result.json"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{candidate_id}: {passed}/{total} commands passed; result={result_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
