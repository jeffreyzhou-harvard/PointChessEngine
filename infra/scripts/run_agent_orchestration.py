#!/usr/bin/env python3
"""Run or audit configured agent orchestration before Champion evaluation."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import signal
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


def find_task_file(task_id: str) -> Path | None:
    task_root = ROOT / "infra" / "tasks"
    exact_name = f"{task_id}.md"
    for path in task_root.rglob("*.md"):
        if path.name == exact_name:
            return path
    prefix = task_id.split("_", 1)[0]
    for path in task_root.rglob("*.md"):
        if path.name.startswith(prefix + "_"):
            return path
    return None


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def format_command(template: str, config_task_id: str, candidate: dict, args: argparse.Namespace) -> str:
    context = SafeFormatDict(candidate.copy())
    context.update(
        {
            "task_id": config_task_id,
            "milestone_task_id": args.task or config_task_id,
            "candidate_id": candidate.get("candidate_id", ""),
            "orchestration_mode": args.mode,
            "python": shlex.quote(sys.executable),
            "repo_root": shlex.quote(str(ROOT)),
        }
    )
    return template.format_map(context)


def run_shell_command(command: str, timeout: float | None) -> tuple[int, str, str, bool]:
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout or "", stderr or "", False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except Exception:
                pass
            stdout, stderr = process.communicate()
        timeout_message = f"\nTIMEOUT after {timeout} seconds\n" if timeout else "\nTIMEOUT\n"
        return 124, stdout or "", (stderr or "") + timeout_message, True


def write_unconfigured_record(config_task_id: str, candidate: dict, args: argparse.Namespace, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    task_id = args.task or config_task_id
    task_file = find_task_file(task_id)
    if args.mode == "audit":
        prompt_path = output_dir / "prompt.md"
        response_path = output_dir / "response.md"
        task_text = task_file.read_text(encoding="utf-8") if task_file else f"No task file found for {task_id}."
        prompt_path.write_text(
            "\n\n".join(
                [
                    "# Champion Methodology Audit Prompt",
                    f"Candidate: `{candidate.get('candidate_id')}`",
                    f"Task: `{task_id}`",
                    f"Orchestration type: `{candidate.get('orchestration_type')}`",
                    "## Task Spec",
                    task_text,
                    "## Required Orchestration Evidence",
                    "- implementation plan",
                    "- files allowed to change",
                    "- tests/evals to run",
                    "- interface risks",
                    "- expected report fields",
                    "- cost/time logging plan",
                ]
            ),
            encoding="utf-8",
        )
        response_path.write_text(
            "\n".join(
                [
                    "# Methodology Audit Response",
                    "",
                    f"Candidate: `{candidate.get('candidate_id')}`",
                    f"Task: `{task_id}`",
                    f"Orchestration type: `{candidate.get('orchestration_type')}`",
                    "",
                    "Audit mode recorded the task prompt and candidate metadata without invoking a live model.",
                    "This is valid orchestration observability, but it is not a live generated patch.",
                    "",
                    "Live execution requires either an `orchestration_command` in the Champion config or an external branch from the named agent framework.",
                ]
            ),
            encoding="utf-8",
        )
        status = "audit_completed"
        notes = "Audit trace written. No live orchestration command is configured for this candidate."
    else:
        prompt_path = None
        response_path = None
        status = "not_configured"
        notes = "No orchestration_command is configured for this candidate; Champion can only evaluate its existing artifact/branch."
    record = {
        "task_id": task_id,
        "candidate_id": candidate.get("candidate_id"),
        "orchestration_type": candidate.get("orchestration_type"),
        "mode": args.mode,
        "status": status,
        "live_model_used": False,
        "prompt_path": display_path(prompt_path) if prompt_path else None,
        "response_path": display_path(response_path) if response_path else None,
        "task_file": display_path(task_file) if task_file else None,
        "notes": notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "orchestration.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def run_one(config: dict, candidate: dict, args: argparse.Namespace) -> tuple[int, str, dict]:
    config_task_id = config.get("task_id", "UNKNOWN_TASK")
    candidate_id = candidate.get("candidate_id", "unknown_candidate")
    output_dir = ROOT / "reports" / "orchestration" / (args.task or config_task_id) / candidate_id
    command_template = candidate.get("orchestration_command")
    if not command_template:
        record = write_unconfigured_record(config_task_id, candidate, args, output_dir)
        return 0, f"{candidate_id}: {record['status']}", record

    output_dir.mkdir(parents=True, exist_ok=True)
    command = format_command(command_template, config_task_id, candidate, args)
    stdout_path = output_dir / "orchestration.stdout.log"
    stderr_path = output_dir / "orchestration.stderr.log"
    started = time.monotonic()
    timeout = candidate.get("orchestration_timeout_seconds") or config.get("orchestration_timeout_seconds") or args.timeout
    timeout = float(timeout) if timeout else None
    if args.dry_run:
        stdout_path.write_text(f"DRY RUN: {command}\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        record = {
            "task_id": args.task or config_task_id,
            "candidate_id": candidate_id,
            "orchestration_type": candidate.get("orchestration_type"),
            "mode": args.mode,
            "command": command,
            "returncode": 0,
            "status": "dry_run",
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "duration_seconds": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "orchestration_command.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0, f"{candidate_id}: dry-run orchestration command recorded", record

    returncode, stdout, stderr, timed_out = run_shell_command(command, timeout)
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    record = {
        "task_id": args.task or config_task_id,
        "candidate_id": candidate_id,
        "orchestration_type": candidate.get("orchestration_type"),
        "mode": args.mode,
        "command": command,
        "returncode": returncode,
        "status": "timeout" if timed_out else ("passed" if returncode == 0 else "failed"),
        "timed_out": timed_out,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "duration_seconds": round(time.monotonic() - started, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "orchestration_command.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return returncode, f"{candidate_id}: orchestration {record['status']} ({record['duration_seconds']}s)", record


def write_orchestration_metrics(task_id: str, records: list[dict]) -> None:
    if not records:
        return
    output_root = ROOT / "reports" / "orchestration" / task_id
    output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in sorted(records, key=lambda item: item.get("candidate_id", "")):
        rows.append(
            {
                "task_id": record.get("task_id", task_id),
                "candidate_id": record.get("candidate_id", ""),
                "orchestration_type": record.get("orchestration_type", ""),
                "mode": record.get("mode", ""),
                "status": record.get("status", ""),
                "returncode": record.get("returncode", ""),
                "duration_seconds": record.get("duration_seconds", 0),
                "live_model_used": bool(record.get("live_model_used", False)),
                "timestamp": record.get("timestamp", ""),
            }
        )
    summary = {
        "task_id": task_id,
        "candidate_count": len(rows),
        "passed_count": sum(1 for row in rows if row["status"] in {"passed", "audit_completed", "live_completed", "not_configured", "dry_run"}),
        "failed_count": sum(1 for row in rows if row["status"] in {"failed", "timeout"}),
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
                "mode",
                "status",
                "returncode",
                "duration_seconds",
                "live_model_used",
                "timestamp",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--task", help="Milestone task to feed to the orchestrator")
    parser.add_argument("--mode", default="audit", choices=["audit", "live"])
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--timeout", type=float, default=300, help="Seconds before one live orchestration command is stopped")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    candidates = config.get("candidates") or []
    if args.candidate:
        candidates = [candidate for candidate in candidates if candidate.get("candidate_id") == args.candidate]
    if not candidates:
        print("No matching candidates found.")
        return 1

    jobs = max(1, min(args.jobs or int(config.get("parallel_jobs", 1)), len(candidates)))
    failures = 0
    records: list[dict] = []
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
    write_orchestration_metrics(args.task or config.get("task_id", "UNKNOWN_TASK"), records)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
