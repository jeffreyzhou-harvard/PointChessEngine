#!/usr/bin/env python3
"""Run configured test commands for Champion-mode candidates."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_input_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return ROOT / path


def resolve_worktree(path_text: str | None) -> Path:
    if not path_text:
        return ROOT
    path = Path(path_text)
    return path if path.is_absolute() else (ROOT / path).resolve()


def format_command(command: str, task_id: str, candidate: dict, args: argparse.Namespace) -> str:
    context = SafeFormatDict(candidate.copy())
    context.update(
        {
            "task_id": task_id,
            "candidate_id": candidate.get("candidate_id", ""),
            "tier": args.tier or "smoke",
            "milestone_task_id": args.milestone_task or task_id,
            "python": shlex.quote(sys.executable),
            "repo_root": shlex.quote(str(ROOT)),
        }
    )
    return command.format_map(context)


def commands_for_tier(config: dict, tier: str | None, fallback_commands: list[str]) -> list[str]:
    if not tier:
        return fallback_commands
    tiers = config.get("tiers") or {}
    if not tiers and tier == "smoke":
        return fallback_commands
    tier_config = tiers.get(tier)
    if not tier_config:
        raise SystemExit(f"Unknown Champion tier {tier!r}. Available tiers: {', '.join(sorted(tiers)) or 'none'}")
    return tier_config.get("test_commands") or fallback_commands


def run_command(command: str, cwd: Path, output_dir: Path, index: int, dry_run: bool, timeout: float | None) -> dict:
    stdout_path = output_dir / f"command_{index}.stdout.log"
    stderr_path = output_dir / f"command_{index}.stderr.log"
    started = time.monotonic()
    if dry_run:
        stdout_path.write_text(f"DRY RUN: {command}\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": command,
            "returncode": 0,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "dry_run": True,
            "duration_seconds": round(time.monotonic() - started, 3),
        }

    try:
        completed = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True, timeout=timeout)
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT after {timeout} seconds\n"
        timed_out = True
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return {
        "command": command,
        "returncode": returncode,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "dry_run": False,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def candidate_has_changes(cwd: Path, baseline: str) -> bool:
    if not (cwd / ".git").exists():
        return False
    status = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, text=True, capture_output=True)
    if status.stdout.strip():
        return True
    merge_base = subprocess.run(["git", "merge-base", baseline, "HEAD"], cwd=cwd, text=True, capture_output=True)
    if merge_base.returncode != 0:
        return False
    diff = subprocess.run(["git", "diff", "--quiet", merge_base.stdout.strip(), "HEAD"], cwd=cwd)
    return diff.returncode == 1


def parse_command_observation(command_result: dict) -> dict:
    stdout_log = command_result.get("stdout_log")
    if not stdout_log:
        return {}
    path = Path(stdout_log)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return {}
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def evaluate_candidate(config: dict, task_id: str, report_root: Path, config_commands: list[str], candidate: dict, args: argparse.Namespace) -> tuple[int, str]:
    candidate_id = candidate.get("candidate_id", "unknown_candidate")
    output_dir = ROOT / report_root / task_id / candidate_id
    output_dir.mkdir(parents=True, exist_ok=True)
    cwd = resolve_worktree(candidate.get("worktree_path"))
    commands = candidate.get("test_commands") or config_commands
    timeout = candidate.get("command_timeout_seconds", config.get("command_timeout_seconds"))
    timeout = float(timeout) if timeout else None
    missing_worktree = not cwd.exists()
    dry_run = args.dry_run or not commands
    baseline = config.get("baseline_branch", "main")
    require_changes = args.require_candidate_changes and candidate.get("execution_environment") != "local_repo"
    if not cwd.exists():
        print(f"{candidate_id}: worktree missing at {cwd}")

    if not commands:
        print(f"{candidate_id}: no test_commands configured; defaulting to dry-run result record.")

    if missing_worktree:
        command_results = [
            {
                "command": "<worktree missing>",
                "returncode": 127,
                "stdout_log": "",
                "stderr_log": "",
                "dry_run": bool(args.allow_missing_worktrees),
                "error": f"worktree missing at {cwd}",
                "duration_seconds": 0.0,
            }
        ]
    elif require_changes and not candidate_has_changes(cwd, baseline):
        command_results = [
            {
                "command": "<candidate has no changes from baseline>",
                "returncode": 126,
                "stdout_log": "",
                "stderr_log": "",
                "dry_run": False,
                "error": f"candidate worktree has no committed or uncommitted changes from {baseline}",
                "duration_seconds": 0.0,
            }
        ]
    else:
        command_results = []
        for i, command_template in enumerate(commands or ["<no test_commands configured>"], start=1):
            command = format_command(command_template, task_id, candidate, args)
            command_results.append(run_command(command, cwd if cwd.exists() else ROOT, output_dir, i, dry_run, timeout))

    passed = sum(1 for item in command_results if item["returncode"] == 0)
    total = len(command_results)
    failed = total - passed
    observations = [parse_command_observation(item) for item in command_results]
    merged_observation: dict = {}
    for observation in observations:
        merged_observation.update(observation)
    duration_seconds = round(sum(float(item.get("duration_seconds") or 0.0) for item in command_results), 3)
    result = {
        "task_id": task_id,
        "tier": args.tier or "smoke",
        "milestone_task_id": args.milestone_task or task_id,
        "candidate_id": candidate_id,
        "orchestration_type": candidate.get("orchestration_type"),
        "model_assignments": candidate.get("model_assignments", {}),
        "execution_environment": candidate.get("execution_environment"),
        "engine_id": candidate.get("engine_id"),
        "branch": candidate.get("branch_name"),
        "baseline_commit": config.get("baseline_commit", ""),
        "bestmove": merged_observation.get("bestmove"),
        "legal_from_startpos": merged_observation.get("legal_from_startpos"),
        "duration_seconds": duration_seconds,
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
        "observations": observations,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    message = f"{candidate_id}: {passed}/{total} commands passed; result={result_path}"
    return failed, message


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Champion config YAML")
    parser.add_argument("--candidate", help="Optional candidate_id filter")
    parser.add_argument("--tier", default="smoke", help="Champion tier to run: smoke, contract, milestone, perft, tournament")
    parser.add_argument("--milestone-task", help="Milestone task used by tier commands, e.g. C3_STATIC_EVALUATION")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute commands")
    parser.add_argument("--jobs", type=int, help="Number of candidates to test in parallel")
    parser.add_argument("--require-candidate-changes", action="store_true", help="Fail non-local candidates whose worktree has no diff from baseline")
    parser.add_argument(
        "--allow-missing-worktrees",
        action="store_true",
        help="Write dry-run records for missing worktrees instead of failing",
    )
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    report_root = Path(config.get("report_root", "reports/comparisons"))
    commands = commands_for_tier(config, args.tier, config.get("test_commands") or [])
    candidates = config.get("candidates") or []

    if args.candidate:
        candidates = [c for c in candidates if c.get("candidate_id") == args.candidate]
    if not candidates:
        print("No matching candidates found.")
        return 1
    jobs = args.jobs or int(config.get("parallel_jobs", 1))
    jobs = max(1, min(jobs, len(candidates)))

    failures = 0
    if jobs == 1:
        for candidate in candidates:
            failed, message = evaluate_candidate(config, task_id, report_root, commands, candidate, args)
            failures += failed
            print(message)
    else:
        print(f"Testing {len(candidates)} candidates with {jobs} parallel workers.")
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            future_map = {
                executor.submit(evaluate_candidate, config, task_id, report_root, commands, candidate, args): candidate
                for candidate in candidates
            }
            for future in concurrent.futures.as_completed(future_map):
                failed, message = future.result()
                failures += failed
                print(message)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
