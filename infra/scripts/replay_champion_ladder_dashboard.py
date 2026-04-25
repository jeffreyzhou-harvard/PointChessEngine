#!/usr/bin/env python3
"""Replay the Champion ladder dashboard stage-by-stage for demos and GIFs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
LADDER_ROOT = ROOT / "reports" / "comparisons" / "CHAMPION_LADDER"

sys.path.insert(0, str(SCRIPT_DIR))
from write_champion_ladder_html import build_html, load_json  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_dashboard(summary: dict, summary_path: Path, output_path: Path, refresh_seconds: int) -> None:
    write_json(summary_path, summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(summary, refresh_seconds), encoding="utf-8")


def open_file(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(path)], check=False)
    elif sys.platform.startswith("win"):
        subprocess.run(["cmd", "/c", "start", str(path)], check=False)


def replay_once(
    source: dict,
    summary_path: Path,
    output_path: Path,
    step_seconds: float,
    hold_seconds: float,
    refresh_seconds: int,
    force_refresh: bool,
) -> None:
    rows = list(source.get("rows") or [])
    task_order = [row.get("task_id") for row in rows if row.get("task_id")]
    requested = int(source.get("requested_task_count") or len(task_order))
    base = {
        "estimated_serial_seconds": 0.0,
        "failed_stage_count": 0,
        "force_refresh": force_refresh,
        "orchestration_enabled": source.get("orchestration_enabled", False),
        "orchestration_mode": source.get("orchestration_mode"),
        "passed_stage_count": 0,
        "requested_task_count": requested,
        "rows": [],
        "task_order": task_order,
    }
    write_dashboard(base, summary_path, output_path, refresh_seconds)
    time.sleep(step_seconds)

    completed: list[dict] = []
    for row in rows:
        running = {
            "candidate_count": row.get("candidate_count", 0),
            "duration_seconds": 0.0,
            "failed_count": 0,
            "passed_count": 0,
            "stage_status": "running",
            "task_id": row.get("task_id"),
            "tier": row.get("tier", ""),
        }
        running_summary = dict(base)
        running_summary["rows"] = completed + [running]
        running_summary["estimated_serial_seconds"] = round(
            sum(float(item.get("duration_seconds") or 0.0) for item in completed), 3
        )
        running_summary["passed_stage_count"] = sum(1 for item in completed if item.get("stage_passed"))
        running_summary["failed_stage_count"] = sum(1 for item in completed if not item.get("stage_passed"))
        write_dashboard(running_summary, summary_path, output_path, refresh_seconds)
        time.sleep(step_seconds)

        completed.append(row)
        completed_summary = dict(base)
        completed_summary["rows"] = list(completed)
        completed_summary["estimated_serial_seconds"] = round(
            sum(float(item.get("duration_seconds") or 0.0) for item in completed), 3
        )
        completed_summary["passed_stage_count"] = sum(1 for item in completed if item.get("stage_passed"))
        completed_summary["failed_stage_count"] = sum(1 for item in completed if not item.get("stage_passed"))
        write_dashboard(completed_summary, summary_path, output_path, refresh_seconds)
        time.sleep(step_seconds)

    final_summary = dict(source)
    final_summary["task_order"] = task_order
    final_summary["force_refresh"] = force_refresh
    write_dashboard(final_summary, summary_path, output_path, refresh_seconds)
    time.sleep(hold_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(LADDER_ROOT / "metrics.json"))
    parser.add_argument("--summary-output", default=str(LADDER_ROOT / "metrics_replay.json"))
    parser.add_argument("--html-output", default=str(LADDER_ROOT / "index.html"))
    parser.add_argument("--step-seconds", type=float, default=1.25)
    parser.add_argument("--hold-seconds", type=float, default=2.5)
    parser.add_argument("--refresh-seconds", type=int, default=1)
    parser.add_argument("--loop", action="store_true", help="Replay forever until interrupted.")
    parser.add_argument("--cycles", type=int, default=1, help="Number of replay cycles; ignored when --loop is set.")
    parser.add_argument("--open", action="store_true", help="Open the HTML dashboard before replaying.")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    summary_path = Path(args.summary_output)
    if not summary_path.is_absolute():
        summary_path = ROOT / summary_path
    output_path = Path(args.html_output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    source = load_json(source_path)
    if not isinstance(source, dict) or not source.get("rows"):
        raise SystemExit(f"No ladder rows found in {source_path}")

    if args.open:
        open_file(output_path)

    cycle = 0
    try:
        while args.loop or cycle < args.cycles:
            cycle += 1
            print(f"Replay cycle {cycle}: writing {output_path}")
            replay_once(
                source=source,
                summary_path=summary_path,
                output_path=output_path,
                step_seconds=args.step_seconds,
                hold_seconds=args.hold_seconds,
                refresh_seconds=args.refresh_seconds,
                force_refresh=args.loop,
            )
    except KeyboardInterrupt:
        print("Replay stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
