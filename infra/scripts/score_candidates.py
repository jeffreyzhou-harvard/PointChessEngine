#!/usr/bin/env python3
"""Score Champion-mode candidates from result JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = {
    "correctness_tests": 35,
    "code_review_quality": 20,
    "interface_compatibility": 15,
    "performance_engine_impact": 15,
    "cost_time_efficiency": 10,
    "documentation_report_quality": 5,
}


def load_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_result(result: dict, weights: dict, *, use_builder_time: bool = False) -> dict:
    task_id = result.get("task_id", "")
    candidate_id = result.get("candidate_id")
    tests_total = result.get("tests_total") or 0
    tests_passed = result.get("tests_passed") or 0
    pass_rate = 0.0 if tests_total == 0 else clamp(tests_passed / tests_total)
    correctness = 0.0 if tests_total == 0 else clamp(tests_passed / tests_total) * weights["correctness_tests"]
    review_score = result.get("review_score")
    review = 0.0 if review_score is None else clamp(float(review_score) / 40.0) * weights["code_review_quality"]
    interface = weights["interface_compatibility"] if result.get("contract_tests_passed") else 0.0
    benchmark_score = result.get("benchmark_score")
    performance = 0.0 if benchmark_score is None else clamp(float(benchmark_score) / 15.0) * weights["performance_engine_impact"]
    cost = result.get("cost_estimate_usd")
    latency = result.get("latency_minutes")
    if cost is None and latency is None:
        efficiency = 0.0
    else:
        cost_penalty = 0.0 if cost is None else min(float(cost) / 50.0, 1.0)
        latency_penalty = 0.0 if latency is None else min(float(latency) / 180.0, 1.0)
        efficiency = (1.0 - max(cost_penalty, latency_penalty)) * weights["cost_time_efficiency"]
    doc = weights["documentation_report_quality"] if result.get("candidate_id") else 0.0
    total = correctness + review + interface + performance + efficiency + doc
    builder_record = (
        load_json_if_exists(ROOT / "reports" / "builders" / task_id / str(candidate_id) / "builder.json")
        if use_builder_time
        else {}
    )
    orchestration_record = load_json_if_exists(ROOT / "reports" / "orchestration" / task_id / str(candidate_id) / "orchestration_command.json")
    if not orchestration_record:
        orchestration_record = load_json_if_exists(ROOT / "reports" / "orchestration" / task_id / str(candidate_id) / "orchestration.json")
    test_duration = float(result.get("duration_seconds") or 0.0)
    builder_duration = builder_record.get("duration_seconds")
    orchestration_duration = orchestration_record.get("duration_seconds")
    if latency is not None:
        tie_break_seconds = float(latency) * 60.0
        tie_break_source = "latency_minutes"
    elif use_builder_time and builder_duration is not None:
        tie_break_seconds = float(builder_duration)
        tie_break_source = "builder_duration_seconds"
    else:
        tie_break_seconds = test_duration
        tie_break_source = "test_duration_seconds"
    passed = tests_total > 0 and tests_passed == tests_total and bool(result.get("contract_tests_passed"))
    return {
        "candidate_id": candidate_id,
        "total_score": round(total, 2),
        "correctness_tests": round(correctness, 2),
        "code_review_quality": round(review, 2),
        "interface_compatibility": round(interface, 2),
        "performance_engine_impact": round(performance, 2),
        "cost_time_efficiency": round(efficiency, 2),
        "documentation_report_quality": round(doc, 2),
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "pass_rate": round(pass_rate, 4),
        "passed": passed,
        "contract_tests_passed": bool(result.get("contract_tests_passed")),
        "duration_seconds": round(test_duration, 3),
        "builder_duration_seconds": round(float(builder_duration), 3) if builder_duration is not None else None,
        "orchestration_duration_seconds": round(float(orchestration_duration), 3) if orchestration_duration is not None else None,
        "tie_break_seconds": round(tie_break_seconds, 3),
        "tie_break_source": tie_break_source,
        "selection_rule": "highest_score_then_pass_rate_then_fastest_time_then_candidate_id",
        "promotion_status": result.get("promotion_status", "candidate"),
        "result_path": result.get("_result_path"),
    }


def sort_key(item: dict) -> tuple:
    return (
        -float(item.get("total_score") or 0.0),
        -float(item.get("pass_rate") or 0.0),
        0 if item.get("passed") else 1,
        float(item.get("tie_break_seconds") if item.get("tie_break_seconds") is not None else 1_000_000_000.0),
        str(item.get("candidate_id") or ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Champion config YAML")
    parser.add_argument("--results-dir", help="Override result directory")
    parser.add_argument("--use-builder-time", action="store_true", help="Use builder duration as the fastest-coder tie-break when available")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    weights = DEFAULT_WEIGHTS | (config.get("score_weights") or {})
    report_root = Path(args.results_dir) if args.results_dir else ROOT / config.get("report_root", "reports/comparisons") / task_id
    expected_ids = {candidate.get("candidate_id") for candidate in config.get("candidates") or [] if candidate.get("candidate_id")}
    result_paths = sorted(
        path for path in report_root.glob("*/result.json") if not expected_ids or path.parent.name in expected_ids
    )
    if not result_paths:
        print(f"No result JSON files found under {report_root}")
        return 1

    scored = []
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        result["_result_path"] = str(path)
        scored.append(score_result(result, weights, use_builder_time=args.use_builder_time))
    scored.sort(key=sort_key)
    for rank, item in enumerate(scored, start=1):
        item["rank"] = rank
        if rank == 1:
            item["selection_status"] = "winner"
            item["selection_reason"] = (
                "Selected by Champion score; ties break by pass rate, then fastest builder/runtime, then candidate ID."
            )
        else:
            item["selection_status"] = "rejected"

    scores_json = report_root / "scores.json"
    scores_md = report_root / "scores.md"
    scores_json.write_text(json.dumps(scored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = [
        "Selection rule: highest Champion score; ties break by pass rate, fastest builder/runtime, then candidate ID.",
        "",
        "| Rank | Candidate | Score | Tests | Tie-break time | Status |",
        "| ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for i, item in enumerate(scored, start=1):
        rows.append(
            f"| {i} | {item['candidate_id']} | {item['total_score']} | "
            f"{item['tests_passed']}/{item['tests_total']} | {item['tie_break_seconds']}s | {item['selection_status']} |"
        )
    scores_md.write_text("# Candidate Scores\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(scores_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
