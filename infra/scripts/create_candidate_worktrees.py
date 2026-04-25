#!/usr/bin/env python3
"""Create git worktrees for Champion-mode candidates."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without dependency installed
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


def run(cmd: list[str], *, dry_run: bool) -> None:
    print("+", " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, cwd=ROOT, check=True)


def git_success(args: list[str]) -> bool:
    return subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def branch_exists(branch: str) -> bool:
    return git_success(["rev-parse", "--verify", "--quiet", branch])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Champion config YAML")
    parser.add_argument("--candidate", help="Optional candidate_id filter")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
    args = parser.parse_args()

    config = load_config(resolve_input_path(args.config))
    baseline = config.get("baseline_branch", "main")
    candidates = config.get("candidates", [])
    if args.candidate:
        candidates = [candidate for candidate in candidates if candidate.get("candidate_id") == args.candidate]
    if not candidates:
        print("No candidates found in config; nothing to create.")
        return 0

    for candidate in candidates:
        branch = candidate.get("branch_name")
        worktree = candidate.get("worktree_path")
        candidate_id = candidate.get("candidate_id", "<unknown>")
        if candidate.get("execution_environment") == "local_repo":
            print(f"Skipping {candidate_id}: existing local repo candidate does not need a worktree")
            continue
        if not branch or not worktree:
            print(f"Skipping {candidate_id}: missing branch_name or worktree_path")
            continue

        worktree_path = (ROOT / worktree).resolve() if not Path(worktree).is_absolute() else Path(worktree)
        if worktree_path.exists():
            print(f"Skipping {candidate_id}: worktree already exists at {worktree_path}")
            continue

        if not args.dry_run:
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
        if branch_exists(branch):
            run(["git", "worktree", "add", str(worktree_path), branch], dry_run=args.dry_run)
        else:
            run(["git", "worktree", "add", str(worktree_path), "-b", branch, baseline], dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
