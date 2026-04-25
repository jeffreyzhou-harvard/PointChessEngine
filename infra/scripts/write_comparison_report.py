#!/usr/bin/env python3
"""Write a Champion-mode candidate comparison report."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--winner", help="Candidate ID selected for promotion")
    parser.add_argument("--reason", default="", help="Reason for promotion")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    task_id = config.get("task_id", "UNKNOWN_TASK")
    baseline = config.get("baseline_commit") or config.get("baseline_branch", "main")
    report_root = ROOT / config.get("report_root", "reports/comparisons") / task_id
    report_root.mkdir(parents=True, exist_ok=True)
    result_paths = sorted(report_root.glob("*/result.json"))
    score_path = report_root / "scores.json"
    scores = json.loads(score_path.read_text(encoding="utf-8")) if score_path.exists() else []

    lines = [
        f"# Candidate Comparison: {task_id}",
        "",
        f"Baseline commit: `{baseline}`",
        "",
        "## Candidates",
        "",
    ]
    for candidate in config.get("candidates", []):
        lines.append(f"- `{candidate.get('candidate_id')}` on `{candidate.get('branch_name')}`")

    lines.extend(["", "## Tests", ""])
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        lines.append(f"- `{result.get('candidate_id')}`: {result.get('tests_passed')}/{result.get('tests_total')} commands passed")

    lines.extend(["", "## Contract / Interface Status", ""])
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        lines.append(f"- `{result.get('candidate_id')}`: contract_tests_passed={result.get('contract_tests_passed')}")

    lines.extend(["", "## Review Scores", ""])
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        lines.append(f"- `{result.get('candidate_id')}`: {result.get('review_score')}")

    lines.extend(["", "## Benchmark Results", ""])
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        lines.append(f"- `{result.get('candidate_id')}`: benchmark_score={result.get('benchmark_score')}")

    lines.extend(["", "## Cost / Time", ""])
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        lines.append(
            f"- `{result.get('candidate_id')}`: cost=${result.get('cost_estimate_usd')}, latency={result.get('latency_minutes')} min"
        )

    lines.extend(["", "## Ranked Scores", ""])
    for i, item in enumerate(scores, start=1):
        lines.append(f"{i}. `{item.get('candidate_id')}` - {item.get('total_score')}")

    if args.winner:
        winner = args.winner
    elif scores:
        top_score = scores[0].get("total_score")
        tied = [item.get("candidate_id") for item in scores if item.get("total_score") == top_score]
        winner = scores[0]["candidate_id"] if len(tied) == 1 else "No winner selected. Top score tie: " + ", ".join(tied)
    else:
        winner = ""
    lines.extend(
        [
            "",
            "## Winner",
            "",
            winner or "No winner selected.",
            "",
            "## Reason for Promotion",
            "",
            args.reason or "Pending human review.",
            "",
            "## Rejected Candidates and Why",
            "",
            "Pending human review.",
            "",
            "## What Was Merged",
            "",
            "Pending promotion.",
            "",
            "## What Was Not Merged",
            "",
            "Pending promotion.",
            "",
        ]
    )

    report_path = report_root / "comparison.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
