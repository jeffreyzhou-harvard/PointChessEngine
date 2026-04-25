#!/usr/bin/env python3
"""Create local-repo Champion ladder configs for a clean visual demo run."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
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


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default="infra/configs/champion")
    parser.add_argument("--output-root", default="reports/comparisons/CHAMPION_LADDER/demo_configs")
    parser.add_argument("--command-timeout", type=int, default=120)
    args = parser.parse_args()

    if yaml is None:
        raise SystemExit("PyYAML is required. Run inside the Champion Docker image or install requirements.txt.")

    source_root = resolve(args.source_root)
    output_root = resolve(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    for task_id in TASKS:
        source = source_root / f"{task_id}.yaml.example"
        if not source.exists():
            raise SystemExit(f"Missing source config: {source}")
        config = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        config["candidate_root"] = "."
        config["report_root"] = "reports/comparisons"
        config["command_timeout_seconds"] = args.command_timeout
        for candidate in config.get("candidates") or []:
            candidate["execution_environment"] = "local_repo"
            candidate["branch_name"] = "main"
            candidate["worktree_path"] = "."
            candidate["notes"] = (
                str(candidate.get("notes") or "")
                + " Local visual demo evaluates this candidate label against the current repo state."
            ).strip()
        target = output_root / f"{task_id}.yaml.example"
        target.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        print(target)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
