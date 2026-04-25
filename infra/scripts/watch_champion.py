#!/usr/bin/env python3
"""Render a live terminal dashboard for Champion runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
SPINNER = "|/-\\"
COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
}


def color(text: str, name: str, enabled: bool) -> str:
    if not enabled:
        return text
    return COLORS[name] + text + COLORS["reset"]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_input_path(text: str) -> Path:
    path = Path(text)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return ROOT / path


def terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 100


def short(text: object, width: int) -> str:
    value = "" if text is None else str(text)
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def status_label(record: dict, *, phase: str) -> str:
    if not record:
        return "waiting"
    status = str(record.get("status") or "")
    if phase == "test":
        passed = record.get("tests_passed")
        total = record.get("tests_total")
        if status:
            return status
        if passed is not None and total is not None:
            return "passed" if passed == total else "failed"
    return status or "recorded"


def status_color(status: str) -> str:
    lower = status.lower()
    if lower in {"passed", "pass", "live_completed", "audit_completed", "dry_run", "recorded"}:
        return "green"
    if lower in {"waiting", "running", "not_configured"}:
        return "yellow"
    if lower in {"failed", "timeout", "missing_worktree", "patch_failed"}:
        return "red"
    return "cyan"


def phase_record(task: str, candidate_id: str, phase: str) -> dict:
    if phase == "orch":
        root = ROOT / "reports" / "orchestration" / task / candidate_id
        return load_json(root / "orchestration_command.json") or load_json(root / "orchestration.json")
    if phase == "build":
        return load_json(ROOT / "reports" / "builders" / task / candidate_id / "builder.json")
    if phase == "test":
        return load_json(ROOT / "reports" / "comparisons" / task / candidate_id / "result.json")
    return {}


def read_ladder_summary() -> dict:
    return load_json(ROOT / "reports" / "comparisons" / "CHAMPION_LADDER" / "metrics.json")


def read_task_summary(task: str) -> dict:
    return load_json(ROOT / "reports" / "comparisons" / task / "metrics.json")


def active_champion_processes() -> list[str]:
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid,etime,command"],
            text=True,
            capture_output=True,
            timeout=2,
        )
    except Exception:
        return []
    needles = (
        "run_parallel_live_champion",
        "run_champion_ladder.py",
        "run_champion_stage.py",
        "run_agent_orchestration.py",
        "run_agent_builders.py",
        "model_patch_builder.py",
    )
    lines = []
    for line in completed.stdout.splitlines():
        if any(needle in line for needle in needles) and "watch_champion.py" not in line:
            lines.append(line.strip())
    return lines


def progress_bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "[" + "." * width + "]"
    filled = int(width * done / total)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def render(args: argparse.Namespace, config: dict, tick: int, started: float) -> str:
    task = args.task or config.get("task_id", "UNKNOWN_TASK")
    candidates = config.get("candidates") or []
    width = terminal_width()
    use_color = not args.no_color
    now = datetime.now().strftime("%H:%M:%S")
    elapsed = int(time.monotonic() - started)
    spinner = SPINNER[tick % len(SPINNER)]
    active = active_champion_processes()

    rows = []
    completed_phases = 0
    phases_per_candidate = 1 if args.tests_only else 3
    total_phases = max(1, len(candidates) * phases_per_candidate)
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id", "unknown")
        orch = phase_record(task, candidate_id, "orch")
        build = phase_record(task, candidate_id, "build")
        test = phase_record(task, candidate_id, "test")
        orch_status = "skipped" if args.tests_only else status_label(orch, phase="orch")
        build_status = "skipped" if args.tests_only else status_label(build, phase="build")
        test_status = status_label(test, phase="test")
        if args.tests_only:
            completed_phases += int(bool(test))
        else:
            completed_phases += int(bool(orch)) + int(bool(build)) + int(bool(test))
        rows.append((candidate_id, candidate.get("orchestration_type", ""), orch_status, build_status, test_status, build, test))

    task_summary = read_task_summary(task)
    ladder_summary = read_ladder_summary()
    header = color("PointChess Champion Live", "bold", use_color)
    lines = [
        f"{header} {spinner}  task={task}  time={now}  elapsed={elapsed}s  jobs={args.jobs or 'config'}",
        progress_bar(completed_phases, total_phases) + f" {completed_phases}/{total_phases} phase records",
        "",
        "| Candidate | Method | Orchestration | Builder | Tests | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for candidate_id, method, orch_status, build_status, test_status, build, test in rows:
        orch_cell = orch_status
        build_cell = build_status
        test_cell = test_status
        notes = []
        if build:
            notes.append(f"build {build.get('duration_seconds', 0)}s")
            if build.get("has_changes"):
                notes.append("diff")
            if build.get("committed"):
                notes.append("commit")
        if test:
            notes.append(f"tests {test.get('tests_passed', 0)}/{test.get('tests_total', 0)}")
        line = (
            f"| {short(candidate_id, 29):29} | {short(method, 18):18} | "
            f"{short(orch_cell, 18):18} | {short(build_cell, 18):18} | "
            f"{short(test_cell, 12):12} | {short(', '.join(notes), 28):28} |"
        )
        lines.append(line)

    if task_summary:
        lines.extend(
            [
                "",
                color("Task Summary", "bold", use_color),
                f"passed={task_summary.get('passed_count', '')}/{task_summary.get('candidate_count', '')} "
                f"failed={task_summary.get('failed_count', '')} "
                f"serial_seconds={task_summary.get('estimated_serial_seconds', '')} "
                f"parallel_seconds={task_summary.get('parallel_wall_seconds', '')} "
                f"speedup={task_summary.get('speedup_factor', '')}x",
            ]
        )
    elif ladder_summary:
        lines.extend(
            [
                "",
                color("Ladder Summary", "bold", use_color),
                f"passed_stages={ladder_summary.get('passed_stage_count', '')}/{ladder_summary.get('task_count', '')} "
                f"candidate_passes={ladder_summary.get('total_candidate_passes', '')}/{ladder_summary.get('total_candidates', '')} "
                f"serial_seconds={ladder_summary.get('estimated_serial_seconds', '')}",
            ]
        )

    lines.extend(["", color("Active Processes", "bold", use_color)])
    if active:
        for line in active[:6]:
            lines.append(short(line, width))
    else:
        lines.append("No Champion process detected.")

    lines.extend(
        [
            "",
            color("Artifacts", "bold", use_color),
            f"reports/orchestration/{task}/",
            f"reports/builders/{task}/",
            f"reports/comparisons/{task}/",
            "reports/comparisons/CHAMPION_LADDER/",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="infra/configs/champion/C0_ENGINE_INTERFACE.yaml.example")
    parser.add_argument("--task")
    parser.add_argument("--jobs")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-clear", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--tests-only", action="store_true", help="Show orchestration/build as skipped and count only test records")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    started = time.monotonic()
    tick = 0
    while True:
        output = render(args, config, tick, started)
        if not args.no_clear:
            print("\033[2J\033[H", end="")
        print(output, flush=True)
        if args.once:
            return 0
        tick += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
