#!/usr/bin/env python3
"""Run a local Dockerized Champion smoke demo with a live two-stage dashboard."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "infra/configs/champion/CURRENT_ENGINES.yaml"
DEFAULT_IMAGE = "pointchess/champion:local"
SPINNER = "|/-\\"
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
}


@dataclass
class Candidate:
    candidate_id: str
    engine_id: str = ""
    orchestration_type: str = ""


@dataclass
class CandidateRun:
    candidate: Candidate
    status: str = "queued"
    started_at: float | None = None
    ended_at: float | None = None
    returncode: int | None = None
    process: subprocess.Popen | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    bestmove: str = ""
    legal: str = ""
    tests: str = ""
    duration_seconds: float = 0.0

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return end - self.started_at


@dataclass
class AggregateStep:
    label: str
    command: list[str]
    status: str = "queued"
    duration_seconds: float = 0.0
    returncode: int | None = None


@dataclass
class DemoState:
    task_id: str
    tier: str
    candidates: list[CandidateRun]
    aggregate_steps: list[AggregateStep]
    stage: str = "candidate"
    started_at: float = field(default_factory=time.monotonic)
    final_returncode: int = 0


def color(text: str, name: str, enabled: bool) -> str:
    if not enabled:
        return text
    return COLORS[name] + text + COLORS["reset"]


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def parse_config(path: Path) -> tuple[str, str, list[Candidate]]:
    """Parse the small fields this visual demo needs without requiring PyYAML on the host."""
    task_id = "CURRENT_ENGINES"
    report_root = "reports/comparisons"
    candidates: list[Candidate] = []
    current: dict[str, str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.startswith("task_id:"):
            task_id = stripped.split(":", 1)[1].strip()
        elif not line.startswith(" ") and stripped.startswith("report_root:"):
            report_root = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- candidate_id:"):
            if current and current.get("candidate_id"):
                candidates.append(
                    Candidate(
                        candidate_id=current.get("candidate_id", ""),
                        engine_id=current.get("engine_id", ""),
                        orchestration_type=current.get("orchestration_type", ""),
                    )
                )
            current = {"candidate_id": stripped.split(":", 1)[1].strip()}
        elif current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key in {"engine_id", "orchestration_type"}:
                current[key] = value.strip()

    if current and current.get("candidate_id"):
        candidates.append(
            Candidate(
                candidate_id=current.get("candidate_id", ""),
                engine_id=current.get("engine_id", ""),
                orchestration_type=current.get("orchestration_type", ""),
            )
        )
    return task_id, report_root, candidates


def terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 110


def short(text: object, width: int) -> str:
    value = "" if text is None else str(text)
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "[" + "." * width + "]"
    filled = int(width * done / total)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def status_color(status: str) -> str:
    return {
        "queued": "dim",
        "running": "yellow",
        "passed": "green",
        "failed": "red",
        "skipped": "dim",
    }.get(status, "cyan")


def clean_reports(report_root: Path, candidates: list[Candidate]) -> None:
    for candidate in candidates:
        shutil.rmtree(report_root / candidate.candidate_id, ignore_errors=True)
    for name in (
        "comparison.md",
        "parallel_summary.md",
        "scores.md",
        "scores.json",
        "metrics.csv",
        "metrics.json",
        "metrics.jsonl",
        "local_docker_visual.md",
        "local_docker_visual.json",
    ):
        try:
            (report_root / name).unlink()
        except FileNotFoundError:
            pass


def docker_base(image: str) -> list[str]:
    return ["docker", "run", "--rm", "-v", f"{ROOT}:/repo", "-w", "/repo", image]


def start_candidate(run: CandidateRun, image: str, config: str, tier: str, visual_root: Path) -> None:
    visual_root.mkdir(parents=True, exist_ok=True)
    stdout_path = visual_root / f"{run.candidate.candidate_id}.stdout.log"
    stderr_path = visual_root / f"{run.candidate.candidate_id}.stderr.log"
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    command = docker_base(image) + [
        "python",
        "infra/scripts/run_candidate_tests.py",
        "--config",
        config,
        "--candidate",
        run.candidate.candidate_id,
        "--tier",
        tier,
    ]
    run.process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, text=True)
    run.stdout_path = stdout_path
    run.stderr_path = stderr_path
    run.started_at = time.monotonic()
    run.status = "running"


def refresh_candidate(run: CandidateRun, report_root: Path) -> None:
    if run.process is None or run.status not in {"running"}:
        return
    code = run.process.poll()
    if code is None:
        return
    run.ended_at = time.monotonic()
    run.returncode = code
    result_path = report_root / run.candidate.candidate_id / "result.json"
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result = {}
        run.bestmove = str(result.get("bestmove") or "")
        legal = result.get("legal_from_startpos")
        run.legal = "" if legal is None else str(legal)
        run.tests = f"{result.get('tests_passed', 0)}/{result.get('tests_total', 0)}"
        run.duration_seconds = float(result.get("duration_seconds") or run.elapsed)
        passed = result.get("tests_passed") == result.get("tests_total") and bool(result.get("contract_tests_passed"))
        run.status = "passed" if code == 0 and passed else "failed"
    else:
        run.duration_seconds = run.elapsed
        run.status = "passed" if code == 0 else "failed"


def render(state: DemoState, *, no_color: bool, tick: int) -> str:
    elapsed = int(time.monotonic() - state.started_at)
    spin = SPINNER[tick % len(SPINNER)]
    done = sum(1 for item in state.candidates if item.status in {"passed", "failed"})
    total = len(state.candidates)
    passed = sum(1 for item in state.candidates if item.status == "passed")
    failed = sum(1 for item in state.candidates if item.status == "failed")
    agg_done = sum(1 for item in state.aggregate_steps if item.status in {"passed", "failed"})
    agg_total = len(state.aggregate_steps)

    title = color("PointChess Local Docker Champion", "bold", not no_color)
    lines = [
        f"{title} {spin}  task={state.task_id}  tier={state.tier}  elapsed={elapsed}s",
        "",
        color("Stage 1/2: parallel candidate containers", "bold", not no_color),
        f"{bar(done, total)} {done}/{total} complete   passed={passed} failed={failed}",
        "",
        "| Candidate | Method | Engine | Status | Bestmove | Legal | Tests | Time |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for item in state.candidates:
        status = color(item.status, status_color(item.status), not no_color)
        display_time = item.duration_seconds if item.status in {"passed", "failed"} else item.elapsed
        lines.append(
            "| {candidate} | {method} | {engine} | {status} | {bestmove} | {legal} | {tests} | {seconds:.2f}s |".format(
                candidate=short(item.candidate.candidate_id, 28),
                method=short(item.candidate.orchestration_type, 19),
                engine=short(item.candidate.engine_id, 16),
                status=status,
                bestmove=item.bestmove,
                legal=item.legal,
                tests=item.tests,
                seconds=display_time,
            )
        )

    lines.extend(
        [
            "",
            color("Stage 2/2: aggregate, score, report", "bold", not no_color),
            f"{bar(agg_done, agg_total)} {agg_done}/{agg_total} complete",
            "",
            "| Step | Status | Time |",
            "| --- | --- | ---: |",
        ]
    )
    for step in state.aggregate_steps:
        lines.append(
            f"| {step.label} | {color(step.status, status_color(step.status), not no_color)} | {step.duration_seconds:.2f}s |"
        )
    lines.extend(
        [
            "",
            "Artifacts:",
            f"- reports/comparisons/{state.task_id}/parallel_summary.md",
            f"- reports/comparisons/{state.task_id}/metrics.json",
            f"- reports/comparisons/{state.task_id}/local_docker_visual.md",
        ]
    )
    return "\n".join(lines)


def print_dashboard(state: DemoState, args: argparse.Namespace, tick: int) -> None:
    if not args.no_clear:
        print("\033[2J\033[H", end="")
    print(render(state, no_color=args.no_color, tick=tick), flush=True)


def run_aggregate_step(step: AggregateStep, state: DemoState, args: argparse.Namespace, tick: int) -> int:
    step.status = "running"
    started = time.monotonic()
    print_dashboard(state, args, tick)
    completed = subprocess.run(step.command, cwd=ROOT, text=True, capture_output=True)
    step.duration_seconds = round(time.monotonic() - started, 3)
    step.returncode = completed.returncode
    step.status = "passed" if completed.returncode == 0 else "failed"
    log_root = ROOT / "reports" / "comparisons" / state.task_id / "_local_docker_visual"
    log_root.mkdir(parents=True, exist_ok=True)
    safe_label = step.label.lower().replace(" ", "_").replace("/", "_")
    (log_root / f"{safe_label}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (log_root / f"{safe_label}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    return completed.returncode


def write_visual_artifacts(state: DemoState, report_root: Path) -> None:
    rows = []
    for item in state.candidates:
        rows.append(
            {
                "candidate_id": item.candidate.candidate_id,
                "engine_id": item.candidate.engine_id,
                "orchestration_type": item.candidate.orchestration_type,
                "status": item.status,
                "bestmove": item.bestmove,
                "legal_from_startpos": item.legal,
                "tests": item.tests,
                "duration_seconds": round(item.duration_seconds or item.elapsed, 3),
            }
        )
    aggregate = [
        {
            "label": step.label,
            "status": step.status,
            "duration_seconds": step.duration_seconds,
            "returncode": step.returncode,
        }
        for step in state.aggregate_steps
    ]
    payload = {
        "task_id": state.task_id,
        "tier": state.tier,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(state.candidates),
        "passed_count": sum(1 for item in state.candidates if item.status == "passed"),
        "failed_count": sum(1 for item in state.candidates if item.status == "failed"),
        "candidates": rows,
        "aggregate_steps": aggregate,
    }
    (report_root / "local_docker_visual.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Local Docker Champion Visual",
        "",
        f"- Task: `{state.task_id}`",
        f"- Tier: `{state.tier}`",
        f"- Candidates: {payload['candidate_count']}",
        f"- Passed: {payload['passed_count']}",
        f"- Failed: {payload['failed_count']}",
        "",
        "## Stage 1: Parallel Candidate Containers",
        "",
        "| Candidate | Method | Engine | Status | Bestmove | Legal | Tests | Time |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['candidate_id']}` | {row['orchestration_type']} | {row['engine_id']} | {row['status']} | {row['bestmove']} | {row['legal_from_startpos']} | {row['tests']} | {row['duration_seconds']:.3f}s |"
        )
    lines.extend(
        [
            "",
            "## Stage 2: Aggregate, Score, Report",
            "",
            "| Step | Status | Time |",
            "| --- | --- | ---: |",
        ]
    )
    for step in aggregate:
        lines.append(f"| {step['label']} | {step['status']} | {step['duration_seconds']:.3f}s |")
    lines.append("")
    (report_root / "local_docker_visual.md").write_text("\n".join(lines), encoding="utf-8")


def build_image_if_needed(args: argparse.Namespace) -> None:
    if not args.build_image:
        return
    subprocess.run(
        ["docker", "build", "-f", "infra/docker/Dockerfile.champion", "-t", args.image, "."],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--tier", default="smoke")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--build-image", action="store_true")
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--no-clear", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()

    config_path = resolve(args.config)
    task_id, report_root_text, candidates = parse_config(config_path)
    if not candidates:
        raise SystemExit(f"No candidates found in {config_path}")
    jobs = max(1, min(args.jobs, len(candidates)))
    report_root = ROOT / report_root_text / task_id
    visual_root = report_root / "_local_docker_visual"
    report_root.mkdir(parents=True, exist_ok=True)
    if not args.no_clean:
        clean_reports(report_root, candidates)

    build_image_if_needed(args)

    runs = [CandidateRun(candidate=candidate) for candidate in candidates]
    aggregate_steps = [
        AggregateStep("score candidates", docker_base(args.image) + ["python", "infra/scripts/score_candidates.py", "--config", args.config]),
        AggregateStep("write comparison", docker_base(args.image) + ["python", "infra/scripts/write_comparison_report.py", "--config", args.config]),
        AggregateStep(
            "write parallel summary",
            docker_base(args.image)
            + ["python", "infra/scripts/aggregate_champion_artifacts.py", "--config", args.config, "--summary-path", ""],
        ),
    ]
    state = DemoState(task_id=task_id, tier=args.tier, candidates=runs, aggregate_steps=aggregate_steps)

    pending = list(runs)
    running: list[CandidateRun] = []
    tick = 0
    try:
        while pending or running:
            while pending and len(running) < jobs:
                item = pending.pop(0)
                start_candidate(item, args.image, args.config, args.tier, visual_root)
                running.append(item)
            for item in list(running):
                refresh_candidate(item, report_root)
                if item.status in {"passed", "failed"}:
                    running.remove(item)
            print_dashboard(state, args, tick)
            tick += 1
            if pending or running:
                time.sleep(args.interval)

        state.stage = "aggregate"
        for step in aggregate_steps:
            code = run_aggregate_step(step, state, args, tick)
            tick += 1
            if code != 0:
                state.final_returncode = code
                break

        write_visual_artifacts(state, report_root)
        print_dashboard(state, args, tick)
    except KeyboardInterrupt:
        for item in running:
            if item.process and item.process.poll() is None:
                item.process.terminate()
        raise

    failed_candidates = any(item.status != "passed" for item in runs)
    failed_steps = any(step.status == "failed" for step in aggregate_steps)
    return state.final_returncode or (1 if failed_candidates or failed_steps else 0)


if __name__ == "__main__":
    sys.exit(main())
