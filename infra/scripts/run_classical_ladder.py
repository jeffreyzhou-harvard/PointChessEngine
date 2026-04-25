#!/usr/bin/env python3
"""Run and summarize the C0-C8 classical milestone ladder."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = ROOT / "reports" / "comparisons" / "CLASSICAL_LADDER"
TASKS = [
    "C0_ENGINE_INTERFACE",
    "C1_BOARD_FEN_MOVE",
    "C2_LEGAL_MOVE_GENERATION",
    "C3_STATIC_EVALUATION",
    "C4_ALPHA_BETA_SEARCH",
    "C5_TACTICAL_HARDENING",
    "C6_TIME_TT_ITERATIVE",
    "C7_UCI_COMPATIBILITY",
    "C8_ELO_SLIDER",
]


def parse_observation(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def run_task(task_id: str) -> dict:
    output_dir = REPORT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "milestone.stdout.log"
    stderr_path = output_dir / "milestone.stderr.log"
    started = time.monotonic()
    command = [sys.executable, "infra/scripts/run_milestone_tests.py", "--task", task_id]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    observation = parse_observation(completed.stdout)
    result = {
        "task_id": task_id,
        "tier": "milestone",
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "duration_seconds": round(time.monotonic() - started, 3),
        "command": " ".join(command),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "observation": observation,
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def read_results() -> list[dict]:
    results = []
    for task_id in TASKS:
        path = REPORT_ROOT / task_id / "result.json"
        if path.exists():
            results.append(json.loads(path.read_text(encoding="utf-8")))
    return results


def write_summary(results: list[dict]) -> Path:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    metric_rows = []
    rows = ["| Task | Status | Duration | Test files |", "| --- | --- | ---: | --- |"]
    for result in sorted(results, key=lambda item: TASKS.index(item["task_id"])):
        observation = result.get("observation") or {}
        files = ", ".join(observation.get("test_files") or [])
        status = "pass" if result.get("passed") else "fail"
        metric_rows.append(
            {
                "task_id": result["task_id"],
                "tier": "milestone",
                "passed": bool(result.get("passed")),
                "returncode": result.get("returncode", 1),
                "duration_seconds": result.get("duration_seconds", 0),
                "test_file_count": len(observation.get("test_files") or []),
                "test_files": files,
                "stdout_log": result.get("stdout_log", ""),
                "stderr_log": result.get("stderr_log", ""),
            }
        )
        rows.append(f"| `{result['task_id']}` | {status} | {result.get('duration_seconds', 0):.3f}s | `{files}` |")
    passed = sum(1 for result in results if result.get("passed"))
    serial_seconds = round(sum(float(row["duration_seconds"] or 0) for row in metric_rows), 3)
    parallel_seconds = round(max((float(row["duration_seconds"] or 0) for row in metric_rows), default=0.0), 3)
    speedup = round(serial_seconds / parallel_seconds, 3) if parallel_seconds > 0 else 0.0
    with (REPORT_ROOT / "metrics.jsonl").open("w", encoding="utf-8") as f:
        for row in metric_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with (REPORT_ROOT / "metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "task_id",
                "tier",
                "passed",
                "returncode",
                "duration_seconds",
                "test_file_count",
                "test_files",
                "stdout_log",
                "stderr_log",
            ],
        )
        writer.writeheader()
        writer.writerows(metric_rows)
    (REPORT_ROOT / "metrics.json").write_text(
        json.dumps(
            {
                "candidate_count": len(metric_rows),
                "passed_count": passed,
                "failed_count": len(metric_rows) - passed,
                "estimated_serial_seconds": serial_seconds,
                "parallel_wall_seconds": parallel_seconds,
                "speedup_factor": speedup,
                "candidates": metric_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Classical Milestone Ladder",
        "",
        *rows,
        "",
        f"- Passed: {passed}/{len(results)}",
        f"- Estimated serial runtime: {serial_seconds:.3f}s",
        f"- Parallel wall time: {parallel_seconds:.3f}s",
        f"- Speedup factor: {speedup:.2f}x",
        "- Graph data: `metrics.csv`, `metrics.jsonl`, `metrics.json`",
        f"- Scope: C0-C8 classical test gates",
        f"- Note: this validates the canonical checkout. Candidate selection still happens through per-task Champion configs and promotion review.",
        "",
    ]
    summary_path = REPORT_ROOT / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(summary_path)
    return summary_path


def selected_tasks(task: str) -> list[str]:
    if task == "all":
        return TASKS
    if task not in TASKS:
        raise SystemExit(f"Unknown classical task {task!r}. Expected one of: {', '.join(TASKS)}")
    return [task]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="all", help="Task ID or 'all'")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()

    if args.summarize_only:
        results = read_results()
        write_summary(results)
        return 0 if results and all(result.get("passed") for result in results) else 1

    tasks = selected_tasks(args.task)
    jobs = max(1, min(args.jobs, len(tasks)))
    results: list[dict] = []
    if jobs == 1:
        for task_id in tasks:
            result = run_task(task_id)
            results.append(result)
            print(f"{task_id}: {'pass' if result['passed'] else 'fail'}")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            future_map = {executor.submit(run_task, task_id): task_id for task_id in tasks}
            for future in concurrent.futures.as_completed(future_map):
                result = future.result()
                results.append(result)
                print(f"{result['task_id']}: {'pass' if result['passed'] else 'fail'}")
    write_summary(read_results())
    return 0 if all(result.get("passed") for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
