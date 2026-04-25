#!/usr/bin/env python3
"""Append AI usage records for Champion-mode task runs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "ai_usage" / "task_runs.jsonl"


def parse_json_object(text: str | None) -> dict:
    if not text:
        return {}
    return json.loads(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--orchestration-type", required=True)
    parser.add_argument("--model-assignments", default="{}", help="JSON object")
    parser.add_argument("--execution-environment", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--start-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--prompts-used", type=int, default=0)
    parser.add_argument("--tokens-estimate", type=int, default=0)
    parser.add_argument("--cost-estimate", type=float, default=0.0)
    parser.add_argument("--tests-passed", type=int, default=0)
    parser.add_argument("--tests-total", type=int, default=0)
    parser.add_argument("--review-score", type=float)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "task_id": args.task_id,
        "candidate_id": args.candidate_id,
        "orchestration_type": args.orchestration_type,
        "model_assignments": parse_json_object(args.model_assignments),
        "execution_environment": args.execution_environment,
        "branch": args.branch,
        "start_time": args.start_time or now,
        "end_time": args.end_time or now,
        "prompts_used": args.prompts_used,
        "tokens_estimate": args.tokens_estimate,
        "cost_estimate": args.cost_estimate,
        "tests_passed": args.tests_passed,
        "tests_total": args.tests_total,
        "review_score": args.review_score,
        "notes": args.notes,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
