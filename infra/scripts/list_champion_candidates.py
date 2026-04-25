#!/usr/bin/env python3
"""List candidate IDs from a Champion config for CI matrices."""

from __future__ import annotations

import argparse
import json
import os
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
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--github-output-name", default="")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    candidate_ids = [candidate["candidate_id"] for candidate in config.get("candidates", []) if candidate.get("candidate_id")]
    payload = json.dumps(candidate_ids)
    print(payload)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path and args.github_output_name:
        with Path(output_path).open("a", encoding="utf-8") as f:
            f.write(f"{args.github_output_name}={payload}\n")
    return 0 if candidate_ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
