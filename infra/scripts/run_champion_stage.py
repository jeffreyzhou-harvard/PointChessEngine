#!/usr/bin/env python3
"""Run a dry-run-safe Champion-mode stage for one milestone."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent


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


def validate_config(config: dict, requested_task: str) -> list[str]:
    errors = []
    if config.get("task_id") != requested_task:
        errors.append(f"config task_id {config.get('task_id')!r} does not match --task {requested_task!r}")
    for field in ["baseline_branch", "canonical_branch", "candidate_root", "report_root", "score_weights", "candidates"]:
        if field not in config:
            errors.append(f"missing config field: {field}")
    for i, candidate in enumerate(config.get("candidates") or [], start=1):
        for field in ["candidate_id", "task_id", "orchestration_type", "model_assignments", "execution_environment", "branch_name", "worktree_path", "output_report_path"]:
            if field not in candidate:
                errors.append(f"candidate {i} missing field: {field}")
    return errors


def run_script(script: str, args: list[str]) -> int:
    command = [sys.executable, str(SCRIPT_DIR / script), *args]
    print("+", " ".join(command))
    return subprocess.run(command, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--create-worktrees", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--tier", default="smoke", help="Champion tier to run")
    parser.add_argument("--milestone-task", help="Milestone task ID for milestone/perft gates")
    parser.add_argument("--run-orchestration", action="store_true", help="Run configured agent orchestration before tests")
    parser.add_argument("--orchestration-mode", default="audit", choices=["audit", "live"], help="audit is no-secrets; live may call model APIs")
    parser.add_argument("--orchestration-timeout", type=float, default=300, help="Seconds before one live orchestration command is stopped")
    parser.add_argument("--run-builders", action="store_true", help="Run configured agent builders before tests")
    parser.add_argument("--builder-provider", choices=["claude_cli", "codex_cli", "openai", "anthropic", "rlm"], help="Optional builder provider filter")
    parser.add_argument("--builder-timeout", type=float, default=1800, help="Seconds before one candidate builder is stopped")
    parser.add_argument("--commit-builds", action="store_true", help="Commit candidate builder diffs inside each worktree")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--candidate", help="Optional candidate_id filter for worktree creation/testing")
    parser.add_argument("--candidate-id", help="Candidate to promote")
    parser.add_argument("--jobs", type=int, help="Candidate test parallelism")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-missing-worktrees", action="store_true")
    parser.add_argument("--require-candidate-changes", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()

    config_path = resolve_input_path(args.config)
    config = load_config(config_path)
    errors = validate_config(config, args.task)
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1

    print(f"Champion stage: {args.task}")
    print(f"Tier: {args.tier}")
    print(f"Baseline: {config.get('baseline_branch')} -> canonical {config.get('canonical_branch')}")
    print(f"Candidates: {len(config.get('candidates') or [])}")

    if args.create_worktrees:
        script_args = ["--config", str(config_path)]
        if args.candidate:
            script_args += ["--candidate", args.candidate]
        if args.dry_run:
            script_args.append("--dry-run")
        code = run_script("create_candidate_worktrees.py", script_args)
        if code:
            return code

    if args.run_orchestration:
        script_args = ["--config", str(config_path), "--mode", args.orchestration_mode]
        if args.candidate:
            script_args += ["--candidate", args.candidate]
        if args.milestone_task:
            script_args += ["--task", args.milestone_task]
        else:
            script_args += ["--task", args.task]
        if args.jobs:
            script_args += ["--jobs", str(args.jobs)]
        script_args += ["--timeout", str(args.orchestration_timeout)]
        if args.dry_run:
            script_args.append("--dry-run")
        code = run_script("run_agent_orchestration.py", script_args)
        if code and not args.continue_on_failure:
            return code
        if code:
            print("One or more orchestration runs failed; continuing because --continue-on-failure was set.")

    if args.run_builders:
        script_args = ["--config", str(config_path)]
        if args.candidate:
            script_args += ["--candidate", args.candidate]
        if args.milestone_task:
            script_args += ["--task", args.milestone_task]
        else:
            script_args += ["--task", args.task]
        if args.jobs:
            script_args += ["--jobs", str(args.jobs)]
        if args.builder_provider:
            script_args += ["--provider", args.builder_provider]
        script_args += ["--timeout", str(args.builder_timeout)]
        if args.commit_builds:
            script_args.append("--commit")
        if args.dry_run:
            script_args.append("--dry-run")
        code = run_script("run_agent_builders.py", script_args)
        if code and not args.continue_on_failure:
            return code
        if code:
            print("One or more builders failed; continuing because --continue-on-failure was set.")

    if args.run_tests:
        script_args = ["--config", str(config_path)]
        if args.candidate:
            script_args += ["--candidate", args.candidate]
        if args.tier:
            script_args += ["--tier", args.tier]
        if args.milestone_task:
            script_args += ["--milestone-task", args.milestone_task]
        if args.dry_run:
            script_args.append("--dry-run")
        if args.allow_missing_worktrees:
            script_args.append("--allow-missing-worktrees")
        if args.require_candidate_changes:
            script_args.append("--require-candidate-changes")
        if args.jobs:
            script_args += ["--jobs", str(args.jobs)]
        code = run_script("run_candidate_tests.py", script_args)
        if code and not args.continue_on_failure:
            return code
        if code:
            print("One or more candidates failed; continuing because --continue-on-failure was set.")
    else:
        print("Tests not run. Use --run-tests when candidate worktrees/branches are ready.")

    if args.score:
        script_args = ["--config", str(config_path)]
        if args.run_builders:
            script_args.append("--use-builder-time")
        code = run_script("score_candidates.py", script_args)
        if code:
            return code

    if args.write_report:
        code = run_script("write_comparison_report.py", ["--config", str(config_path)])
        if code:
            return code
        code = run_script("aggregate_champion_artifacts.py", ["--config", str(config_path), "--summary-path", ""])
        if code:
            return code

    if args.promote:
        if not args.confirm:
            print("Refusing promotion without --confirm.")
            return 1
        if not args.candidate_id:
            print("Refusing promotion without --candidate-id.")
            return 1
        code = run_script("promote_candidate.py", ["--config", str(config_path), "--candidate-id", args.candidate_id, "--confirm"])
        if code:
            return code
    else:
        print("Promotion not attempted. Use --promote --candidate-id <id> --confirm after human review.")

    print("Next manual steps:")
    print("1. Review reports/comparisons/<task>/comparison.md.")
    print("2. Confirm the winner and promotion rationale.")
    print("3. Run promote_candidate.py with --confirm if appropriate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
