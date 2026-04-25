#!/usr/bin/env python3
"""Run configured Champion candidate builders in parallel."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
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


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def default_provider(candidate: dict) -> str | None:
    orchestration = candidate.get("orchestration_type")
    if orchestration == "rlm":
        return "rlm"
    default_non_rlm = os.environ.get("POINTCHESS_DEFAULT_BUILDER_PROVIDER", "claude_cli")
    if orchestration in {"react", "debate_ensemble", "custom_langchain_parallel", "claude_cli_agent", "replit_agent"}:
        return default_non_rlm
    return None


def format_command(template: str, config_task_id: str, candidate: dict, args: argparse.Namespace) -> str:
    worktree = resolve_worktree(candidate.get("worktree_path"))
    context = SafeFormatDict(candidate.copy())
    context.update(
        {
            "task_id": config_task_id,
            "milestone_task_id": args.task or config_task_id,
            "candidate_id": candidate.get("candidate_id", ""),
            "builder_mode": args.mode,
            "python": shlex.quote(sys.executable),
            "repo_root": shlex.quote(str(ROOT)),
            "worktree_path": shlex.quote(str(worktree)),
        }
    )
    return template.format_map(context)


def build_command(config_task_id: str, candidate: dict, args: argparse.Namespace) -> str | None:
    if candidate.get("builder_command"):
        return format_command(candidate["builder_command"], config_task_id, candidate, args)
    provider = args.provider or candidate.get("builder_provider") or default_provider(candidate)
    if not provider:
        return None
    worktree = resolve_worktree(candidate.get("worktree_path"))
    command = [
        shlex.quote(sys.executable),
        "infra/scripts/model_patch_builder.py",
        "--task",
        shlex.quote(args.task or config_task_id),
        "--candidate-id",
        shlex.quote(candidate.get("candidate_id", "")),
        "--worktree",
        shlex.quote(str(worktree)),
        "--provider",
        shlex.quote(provider),
        "--style",
        shlex.quote(candidate.get("orchestration_type", "agent")),
    ]
    model = candidate.get("builder_model")
    if model:
        command.extend(["--model", shlex.quote(str(model))])
    timeout = candidate.get("builder_timeout_seconds") or args.timeout
    command.extend(["--timeout", shlex.quote(str(timeout))])
    if args.commit:
        command.append("--commit")
    if args.dry_run:
        command.append("--dry-run")
    return " ".join(command)


def run_one(config: dict, candidate: dict, args: argparse.Namespace) -> tuple[int, str, dict]:
    config_task_id = config.get("task_id", "UNKNOWN_TASK")
    task_id = args.task or config_task_id
    candidate_id = candidate.get("candidate_id", "unknown_candidate")
    output_dir = ROOT / "reports" / "builders" / task_id / candidate_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "builder.stdout.log"
    stderr_path = output_dir / "builder.stderr.log"
    worktree = resolve_worktree(candidate.get("worktree_path"))
    started = time.monotonic()

    command = build_command(config_task_id, candidate, args)
    if not command:
        record = {
            "task_id": task_id,
            "candidate_id": candidate_id,
            "orchestration_type": candidate.get("orchestration_type"),
            "status": "not_configured",
            "returncode": 0 if args.allow_unconfigured else 2,
            "worktree": str(worktree),
            "has_changes": False,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": "No builder_command or default builder provider for this candidate.",
        }
        (output_dir / "builder.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return int(record["returncode"]), f"{candidate_id}: {record['status']}", record

    if not worktree.exists():
        record = {
            "task_id": task_id,
            "candidate_id": candidate_id,
            "orchestration_type": candidate.get("orchestration_type"),
            "status": "missing_worktree",
            "returncode": 127,
            "command": command,
            "worktree": str(worktree),
            "has_changes": False,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "builder.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 127, f"{candidate_id}: missing_worktree", record

    try:
        completed = subprocess.run(command, cwd=ROOT, shell=True, text=True, capture_output=True, timeout=args.timeout)
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT after {args.timeout}s\n"
        returncode = 124
        timed_out = True
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    nested_record = {}
    nested_path = ROOT / "reports" / "builds" / task_id / candidate_id / "builder.json"
    if nested_path.exists():
        nested_record = json.loads(nested_path.read_text(encoding="utf-8"))
    record = {
        "task_id": task_id,
        "candidate_id": candidate_id,
        "orchestration_type": candidate.get("orchestration_type"),
        "status": "passed" if returncode == 0 else "failed",
        "returncode": returncode,
        "timed_out": timed_out,
        "command": command,
        "worktree": str(worktree),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "duration_seconds": round(time.monotonic() - started, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "builder_record": nested_record,
        "has_changes": bool(nested_record.get("has_changes")),
        "committed": bool(nested_record.get("committed")),
    }
    (output_dir / "builder.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return returncode, f"{candidate_id}: {record['status']} ({record['duration_seconds']}s)", record


def write_metrics(task_id: str, records: list[dict]) -> None:
    output_root = ROOT / "reports" / "builders" / task_id
    output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in sorted(records, key=lambda item: item.get("candidate_id", "")):
        rows.append(
            {
                "task_id": record.get("task_id", task_id),
                "candidate_id": record.get("candidate_id", ""),
                "orchestration_type": record.get("orchestration_type", ""),
                "status": record.get("status", ""),
                "returncode": record.get("returncode", ""),
                "duration_seconds": record.get("duration_seconds", 0),
                "has_changes": bool(record.get("has_changes")),
                "committed": bool(record.get("committed")),
                "worktree": record.get("worktree", ""),
                "timestamp": record.get("timestamp", ""),
            }
        )
    summary = {
        "task_id": task_id,
        "candidate_count": len(rows),
        "passed_count": sum(1 for row in rows if row["status"] == "passed" and row["has_changes"]),
        "failed_count": sum(1 for row in rows if not (row["status"] == "passed" and row["has_changes"])),
        "estimated_serial_seconds": round(sum(float(row["duration_seconds"] or 0) for row in rows), 3),
        "runs": rows,
    }
    (output_root / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (output_root / "metrics.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with (output_root / "metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "task_id",
                "candidate_id",
                "orchestration_type",
                "status",
                "returncode",
                "duration_seconds",
                "has_changes",
                "committed",
                "worktree",
                "timestamp",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--task")
    parser.add_argument("--provider", choices=["claude_cli", "codex_cli", "openai", "anthropic", "rlm"])
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-unconfigured", action="store_true")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    task_id = args.task or config.get("task_id", "UNKNOWN_TASK")
    candidates = config.get("candidates") or []
    if args.candidate:
        candidates = [candidate for candidate in candidates if candidate.get("candidate_id") == args.candidate]
    if not candidates:
        print("No matching candidates found.")
        return 1
    jobs = max(1, min(args.jobs or int(config.get("parallel_jobs", 1)), len(candidates)))
    records = []
    failures = 0
    if jobs == 1:
        for candidate in candidates:
            code, message, record = run_one(config, candidate, args)
            failures += 1 if code else 0
            records.append(record)
            print(message)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            future_map = {executor.submit(run_one, config, candidate, args): candidate for candidate in candidates}
            for future in concurrent.futures.as_completed(future_map):
                code, message, record = future.result()
                failures += 1 if code else 0
                records.append(record)
                print(message)
    write_metrics(task_id, records)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
