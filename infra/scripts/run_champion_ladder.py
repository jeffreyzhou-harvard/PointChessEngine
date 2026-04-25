#!/usr/bin/env python3
"""Run Champion-mode candidate stages across the C0-C8 milestone ladder."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = ROOT / "reports" / "comparisons" / "CHAMPION_LADDER"
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


def config_for_task(config_root: Path, task_id: str) -> Path:
    path = config_root / f"{task_id}.yaml.example"
    if not path.exists():
        raise SystemExit(f"Missing Champion config for {task_id}: {path}")
    return path


def selected_tasks(task_text: str) -> list[str]:
    if task_text == "all":
        return TASKS
    requested = [item.strip() for item in task_text.split(",") if item.strip()]
    unknown = [task for task in requested if task not in TASKS]
    if unknown:
        raise SystemExit(f"Unknown task(s): {', '.join(unknown)}")
    return requested


def run_stage(task_id: str, config_path: Path, args: argparse.Namespace) -> dict:
    output_dir = REPORT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "stage.stdout.log"
    stderr_path = output_dir / "stage.stderr.log"
    command = [
        sys.executable,
        "infra/scripts/run_champion_stage.py",
        "--task",
        task_id,
        "--config",
        str(config_path),
        "--tier",
        args.tier,
        "--milestone-task",
        task_id,
        "--run-tests",
        "--score",
        "--write-report",
        "--jobs",
        str(args.jobs),
    ]
    if args.create_worktrees:
        command.append("--create-worktrees")
    if args.run_orchestration:
        command.extend(["--run-orchestration", "--orchestration-mode", args.orchestration_mode])
    if args.allow_missing_worktrees:
        command.append("--allow-missing-worktrees")
    if args.require_candidate_changes:
        command.append("--require-candidate-changes")
    if args.continue_on_failure:
        command.append("--continue-on-failure")
    if args.dry_run:
        command.append("--dry-run")

    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    stage_result = {
        "task_id": task_id,
        "config_path": str(config_path.relative_to(ROOT)),
        "returncode": completed.returncode,
        "stage_completed": completed.returncode == 0,
        "passed": completed.returncode == 0,
        "duration_seconds": round(time.monotonic() - started, 3),
        "command": command,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }
    comparison_root = ROOT / "reports" / "comparisons" / task_id
    metrics_path = comparison_root / "metrics.json"
    scores_path = comparison_root / "scores.json"
    if metrics_path.exists():
        stage_result["metrics_path"] = str(metrics_path.relative_to(ROOT))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        stage_result["metrics"] = metrics
        stage_result["passed"] = bool(stage_result["stage_completed"]) and int(metrics.get("passed_count") or 0) > 0
    if scores_path.exists():
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
        stage_result["scores_path"] = str(scores_path.relative_to(ROOT))
        stage_result["scores"] = scores
        if scores:
            stage_result["top_candidate_id"] = scores[0].get("candidate_id")
            stage_result["top_score"] = scores[0].get("total_score")
    orchestration_metrics = ROOT / "reports" / "orchestration" / task_id / "metrics.json"
    if orchestration_metrics.exists():
        stage_result["orchestration_metrics_path"] = str(orchestration_metrics.relative_to(ROOT))
        stage_result["orchestration_metrics"] = json.loads(orchestration_metrics.read_text(encoding="utf-8"))
    (output_dir / "result.json").write_text(json.dumps(stage_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return stage_result


def write_ladder_reports(results: list[dict], args: argparse.Namespace) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    serial_seconds = 0.0
    for result in results:
        metrics = result.get("metrics") or {}
        orchestration_metrics = result.get("orchestration_metrics") or {}
        serial_seconds += float(result.get("duration_seconds") or 0.0)
        candidate_count = metrics.get("candidate_count", 0)
        passed_count = metrics.get("passed_count", 0)
        failed_count = metrics.get("failed_count", candidate_count - passed_count)
        stage_passed = bool(result.get("passed")) and int(passed_count or 0) > 0
        rows.append(
            {
                "task_id": result.get("task_id"),
                "tier": args.tier,
                "orchestration_mode": args.orchestration_mode if args.run_orchestration else "",
                "stage_passed": stage_passed,
                "returncode": result.get("returncode"),
                "duration_seconds": result.get("duration_seconds", 0),
                "candidate_count": candidate_count,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "top_candidate_id": result.get("top_candidate_id", "") if stage_passed else "",
                "top_score": result.get("top_score", "") if stage_passed else "",
                "orchestration_runs": orchestration_metrics.get("candidate_count", 0),
                "orchestration_failed": orchestration_metrics.get("failed_count", 0),
                "metrics_path": result.get("metrics_path", ""),
                "scores_path": result.get("scores_path", ""),
                "orchestration_metrics_path": result.get("orchestration_metrics_path", ""),
            }
        )

    with (REPORT_ROOT / "metrics.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with (REPORT_ROOT / "metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "task_id",
                "tier",
                "orchestration_mode",
                "stage_passed",
                "returncode",
                "duration_seconds",
                "candidate_count",
                "passed_count",
                "failed_count",
                "top_candidate_id",
                "top_score",
                "orchestration_runs",
                "orchestration_failed",
                "metrics_path",
                "scores_path",
                "orchestration_metrics_path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "task_count": len(rows),
        "passed_stage_count": sum(1 for row in rows if row["stage_passed"]),
        "failed_stage_count": sum(1 for row in rows if not row["stage_passed"]),
        "total_candidates": sum(int(row["candidate_count"] or 0) for row in rows),
        "total_candidate_passes": sum(int(row["passed_count"] or 0) for row in rows),
        "total_candidate_failures": sum(int(row["failed_count"] or 0) for row in rows),
        "estimated_serial_seconds": round(serial_seconds, 3),
        "tier": args.tier,
        "orchestration_enabled": bool(args.run_orchestration),
        "orchestration_mode": args.orchestration_mode if args.run_orchestration else None,
        "rows": rows,
    }
    (REPORT_ROOT / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    table = ["| Task | Stage | Candidates Passed | Top Candidate | Score | Duration |", "| --- | --- | ---: | --- | ---: | ---: |"]
    for row in rows:
        status = "pass" if row["stage_passed"] else "fail"
        table.append(
            f"| `{row['task_id']}` | {status} | {row['passed_count']}/{row['candidate_count']} | "
            f"`{row['top_candidate_id']}` | {row['top_score']} | {float(row['duration_seconds']):.3f}s |"
        )
    lines = [
        "# Champion C0-C8 Candidate Ladder",
        "",
        *table,
        "",
        f"- Tier: `{args.tier}`",
        f"- Orchestration: `{args.orchestration_mode if args.run_orchestration else 'disabled'}`",
        f"- Passed stages: {summary['passed_stage_count']}/{summary['task_count']}",
        f"- Candidate passes: {summary['total_candidate_passes']}/{summary['total_candidates']}",
        f"- Estimated serial runtime: {summary['estimated_serial_seconds']:.3f}s",
        "- Promotion: not automatic; each task winner still requires human review and `promote_candidate.py --confirm`.",
        "- Graph data: `metrics.csv`, `metrics.jsonl`, `metrics.json`.",
        "",
    ]
    (REPORT_ROOT / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default="all", help="'all' or comma-separated task IDs")
    parser.add_argument("--config-root", default="infra/configs/champion")
    parser.add_argument("--tier", default="smoke")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--create-worktrees", action="store_true")
    parser.add_argument("--run-orchestration", action="store_true")
    parser.add_argument("--orchestration-mode", default="audit", choices=["audit", "live"])
    parser.add_argument("--allow-missing-worktrees", action="store_true")
    parser.add_argument("--require-candidate-changes", action="store_true", default=True)
    parser.add_argument("--no-require-candidate-changes", action="store_false", dest="require_candidate_changes")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_root = (ROOT / args.config_root).resolve()
    results = []
    failures = 0
    for task_id in selected_tasks(args.tasks):
        config_path = config_for_task(config_root, task_id)
        print(f"== {task_id} ==")
        result = run_stage(task_id, config_path, args)
        results.append(result)
        failures += 0 if result.get("passed") else 1
        print(f"{task_id}: {'pass' if result.get('passed') else 'fail'} ({result.get('duration_seconds')}s)")
        if result.get("returncode") and not args.continue_on_failure:
            break
    write_ladder_reports(results, args)
    print(REPORT_ROOT / "summary.md")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
