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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = {
    "correctness_tests": 35,
    "code_review_quality": 20,
    "interface_compatibility": 15,
    "performance_engine_impact": 15,
    "cost_time_efficiency": 10,
    "documentation_report_quality": 5,
}


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Run: pip install -r requirements.txt")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_result(result: dict, weights: dict) -> dict:
    tests_total = result.get("tests_total") or 0
    tests_passed = result.get("tests_passed") or 0
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
    return {
        "candidate_id": result.get("candidate_id"),
        "total_score": round(total, 2),
        "correctness_tests": round(correctness, 2),
        "code_review_quality": round(review, 2),
        "interface_compatibility": round(interface, 2),
        "performance_engine_impact": round(performance, 2),
        "cost_time_efficiency": round(efficiency, 2),
        "documentation_report_quality": round(doc, 2),
        "promotion_status": result.get("promotion_status", "candidate"),
        "result_path": result.get("_result_path"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Champion config YAML")
    parser.add_argument("--results-dir", help="Override result directory")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    weights = DEFAULT_WEIGHTS | (config.get("score_weights") or {})
    report_root = Path(args.results_dir) if args.results_dir else ROOT / config.get("report_root", "reports/comparisons") / task_id
    result_paths = sorted(report_root.glob("*/result.json"))
    if not result_paths:
        print(f"No result JSON files found under {report_root}")
        return 1

    scored = []
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        result["_result_path"] = str(path)
        scored.append(score_result(result, weights))
    scored.sort(key=lambda item: item["total_score"], reverse=True)

    scores_json = report_root / "scores.json"
    scores_md = report_root / "scores.md"
    scores_json.write_text(json.dumps(scored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = ["| Rank | Candidate | Score |", "| ---: | --- | ---: |"]
    for i, item in enumerate(scored, start=1):
        rows.append(f"| {i} | {item['candidate_id']} | {item['total_score']} |")
    scores_md.write_text("# Candidate Scores\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(scores_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
