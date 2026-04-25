#!/usr/bin/env python3
"""Merge matrix candidate artifacts and write a GitHub summary."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]


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
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merge_artifacts(artifact_root: Path, report_root: Path) -> list[Path]:
    result_paths: list[Path] = []
    if artifact_root.exists():
        for source_result in sorted(artifact_root.rglob("result.json")):
            result = json.loads(source_result.read_text(encoding="utf-8"))
            candidate_id = result.get("candidate_id")
            if not candidate_id:
                continue
            destination = report_root / candidate_id
            destination.mkdir(parents=True, exist_ok=True)
            if source_result.parent.resolve() != destination.resolve():
                for item in source_result.parent.iterdir():
                    target = destination / item.name
                    if item.is_file() and item.resolve() != target.resolve():
                        shutil.copy2(item, target)
            result_paths.append(destination / "result.json")
    if not result_paths:
        result_paths = sorted(report_root.glob("*/result.json"))
    return result_paths


def read_results(result_paths: list[Path]) -> list[dict]:
    results = []
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        result["_result_path"] = str(path)
        results.append(result)
    return sorted(results, key=lambda item: item.get("candidate_id", ""))


def ensure_expected_results(config: dict, report_root: Path, results: list[dict]) -> list[dict]:
    expected_ids = {candidate.get("candidate_id") for candidate in config.get("candidates", []) if candidate.get("candidate_id")}
    by_candidate = {
        result.get("candidate_id"): result
        for result in results
        if not expected_ids or result.get("candidate_id") in expected_ids
    }
    for candidate in config.get("candidates", []):
        candidate_id = candidate.get("candidate_id")
        if not candidate_id or candidate_id in by_candidate:
            continue
        missing_dir = report_root / candidate_id
        missing_dir.mkdir(parents=True, exist_ok=True)
        missing = {
            "task_id": config.get("task_id", "UNKNOWN_TASK"),
            "candidate_id": candidate_id,
            "orchestration_type": candidate.get("orchestration_type"),
            "model_assignments": candidate.get("model_assignments", {}),
            "execution_environment": candidate.get("execution_environment"),
            "engine_id": candidate.get("engine_id"),
            "branch": candidate.get("branch_name"),
            "tests_passed": 0,
            "tests_total": 1,
            "contract_tests_passed": False,
            "promotion_status": "candidate",
            "dry_run": False,
            "duration_seconds": 0.0,
            "commands": [
                {
                    "command": "<missing artifact>",
                    "returncode": 127,
                    "stdout_log": "",
                    "stderr_log": "",
                    "dry_run": False,
                    "error": "candidate artifact missing",
                }
            ],
        }
        (missing_dir / "result.json").write_text(json.dumps(missing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        by_candidate[candidate_id] = missing
    return sorted(by_candidate.values(), key=lambda item: item.get("candidate_id", ""))


def result_observation(result: dict) -> dict:
    if result.get("bestmove") is not None or result.get("legal_from_startpos") is not None:
        return {
            "engine": result.get("engine_id"),
            "bestmove": result.get("bestmove"),
            "legal_from_startpos": result.get("legal_from_startpos"),
            "duration_seconds": result.get("duration_seconds"),
        }
    for command in result.get("commands", []):
        stdout_log = command.get("stdout_log")
        if not stdout_log:
            continue
        path = Path(stdout_log)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            continue
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


def metric_row(result: dict) -> dict:
    observation = result_observation(result)
    commands = result.get("commands") or []
    duration = float(result.get("duration_seconds") or observation.get("duration_seconds") or 0.0)
    commands_failed = sum(1 for command in commands if command.get("returncode") not in (0, None))
    tests_passed = int(result.get("tests_passed") or 0)
    tests_total = int(result.get("tests_total") or 0)
    passed = tests_total > 0 and tests_passed == tests_total and bool(result.get("contract_tests_passed"))
    return {
        "task_id": result.get("task_id", ""),
        "tier": result.get("tier", "smoke"),
        "milestone_task_id": result.get("milestone_task_id", ""),
        "candidate_id": result.get("candidate_id", ""),
        "engine_id": result.get("engine_id") or observation.get("engine", ""),
        "orchestration_type": result.get("orchestration_type", ""),
        "execution_environment": result.get("execution_environment", ""),
        "branch": result.get("branch", ""),
        "passed": passed,
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "contract_tests_passed": bool(result.get("contract_tests_passed")),
        "commands_total": len(commands),
        "commands_failed": commands_failed,
        "duration_seconds": round(duration, 3),
        "bestmove": observation.get("bestmove", ""),
        "legal_from_startpos": observation.get("legal_from_startpos", ""),
        "cost_estimate_usd": result.get("cost_estimate_usd", ""),
        "latency_minutes": result.get("latency_minutes", ""),
        "result_path": result.get("_result_path", ""),
    }


def write_metric_files(report_root: Path, results: list[dict]) -> dict:
    rows = [metric_row(result) for result in results]
    serial_seconds = round(sum(float(row["duration_seconds"] or 0.0) for row in rows), 3)
    parallel_seconds = round(max((float(row["duration_seconds"] or 0.0) for row in rows), default=0.0), 3)
    speedup = round(serial_seconds / parallel_seconds, 3) if parallel_seconds > 0 else 0.0
    summary = {
        "task_id": rows[0]["task_id"] if rows else "",
        "tier": rows[0]["tier"] if rows else "",
        "candidate_count": len(rows),
        "passed_count": sum(1 for row in rows if row["passed"]),
        "failed_count": sum(1 for row in rows if not row["passed"]),
        "estimated_serial_seconds": serial_seconds,
        "parallel_wall_seconds": parallel_seconds,
        "speedup_factor": speedup,
        "metric_files": {
            "json": "metrics.json",
            "jsonl": "metrics.jsonl",
            "csv": "metrics.csv",
        },
        "candidates": rows,
    }

    (report_root / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (report_root / "metrics.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    fieldnames = [
        "task_id",
        "tier",
        "milestone_task_id",
        "candidate_id",
        "engine_id",
        "orchestration_type",
        "execution_environment",
        "branch",
        "passed",
        "tests_passed",
        "tests_total",
        "contract_tests_passed",
        "commands_total",
        "commands_failed",
        "duration_seconds",
        "bestmove",
        "legal_from_startpos",
        "cost_estimate_usd",
        "latency_minutes",
        "result_path",
    ]
    with (report_root / "metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return summary


def write_parallel_summary(report_root: Path, results: list[dict], summary_path: Path | None) -> None:
    metrics = write_metric_files(report_root, results)
    rows = []
    failures = 0
    for result in results:
        observation = result_observation(result)
        duration = float(result.get("duration_seconds") or observation.get("duration_seconds") or 0.0)
        passed = result.get("tests_passed") == result.get("tests_total") and result.get("contract_tests_passed")
        failures += 0 if passed else 1
        rows.append(
            "| {candidate} | {status} | {engine} | {bestmove} | {legal} | {duration:.3f}s |".format(
                candidate=result.get("candidate_id", ""),
                status="pass" if passed else "fail",
                engine=result.get("engine_id") or observation.get("engine", ""),
                bestmove=observation.get("bestmove", ""),
                legal=observation.get("legal_from_startpos", ""),
                duration=duration,
            )
        )

    report_path = report_root / "comparison.md"
    try:
        report_display = report_path.relative_to(ROOT)
    except ValueError:
        report_display = report_path
    lines = [
        "# Champion Current Engines",
        "",
        "| Candidate | Status | Engine | Bestmove | Legal | Duration |",
        "| --- | --- | --- | --- | --- | ---: |",
        *rows,
        "",
        f"- Candidates: {len(results)}",
        f"- Failures: {failures}",
        f"- Estimated serial runtime: {metrics['estimated_serial_seconds']:.3f}s",
        f"- Parallel wall time: {metrics['parallel_wall_seconds']:.3f}s",
        f"- Speedup factor: {metrics['speedup_factor']:.2f}x",
        f"- Report: `{report_display}`",
        f"- Graph data: `metrics.csv`, `metrics.jsonl`, `metrics.json`",
        "",
    ]
    summary = "\n".join(lines)
    summary_file = report_root / "parallel_summary.md"
    summary_file.write_text(summary, encoding="utf-8")
    if summary_path:
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(summary)
            f.write("\n")
    print(summary_file)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--artifact-root", default="", help="Directory containing downloaded matrix artifacts")
    parser.add_argument("--summary-path", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    parser.add_argument("--fail-on-failures", action="store_true")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    report_root = ROOT / config.get("report_root", "reports/comparisons") / task_id
    report_root.mkdir(parents=True, exist_ok=True)

    artifact_root = resolve_input_path(args.artifact_root) if args.artifact_root else report_root
    result_paths = merge_artifacts(artifact_root, report_root)
    results = ensure_expected_results(config, report_root, read_results(result_paths))
    summary_path = Path(args.summary_path) if args.summary_path else None
    write_parallel_summary(report_root, results, summary_path)
    if not results:
        print("No candidate result JSON files found.")
        return 1
    failed = any(r.get("tests_passed") != r.get("tests_total") or not r.get("contract_tests_passed") for r in results)
    return 1 if failed and args.fail_on_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
