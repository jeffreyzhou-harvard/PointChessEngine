"""RLM orchestration runner for PointChess tasks.

Audit mode is deterministic and does not call model APIs. Live mode uses the
optional `rlms` package and requires provider credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from methodologies.rlm.prompts import SYSTEM_PROMPT, TASK_DECOMPOSITION_PROMPT


ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


@dataclass
class RLMRunRecord:
    task_id: str
    candidate_id: str
    mode: str
    orchestration_type: str
    task_file: str | None
    prompt_path: str
    response_path: str | None
    trajectory_log_dir: str | None
    status: str
    live_model_used: bool
    duration_seconds: float
    notes: str


def find_task_file(task_root: Path, task_id: str) -> Path | None:
    exact_name = f"{task_id}.md"
    for path in task_root.rglob("*.md"):
        if path.name == exact_name:
            return path
    prefix = task_id.split("_", 1)[0]
    for path in task_root.rglob("*.md"):
        if path.name.startswith(prefix + "_"):
            return path
    return None


def build_prompt(task_id: str, candidate_id: str, task_text: str) -> str:
    return "\n\n".join(
        [
            "# RLM PointChess Orchestration Prompt",
            f"Candidate: `{candidate_id}`",
            f"Task: `{task_id}`",
            "## System",
            SYSTEM_PROMPT,
            "## Recursive Decomposition Directive",
            TASK_DECOMPOSITION_PROMPT,
            "## Task Spec",
            task_text,
            "## Required Output",
            "- recursively decompose the implementation plan",
            "- identify files allowed to change",
            "- identify tests to add or run",
            "- identify interface risks",
            "- produce a patch plan or patch instructions",
            "- write candidate-report content with AI usage and limitations",
        ]
    )


def audit_response(task_id: str, candidate_id: str, task_file: Path | None) -> str:
    task_ref = display_path(task_file) if task_file else "task file not found"
    return "\n".join(
        [
            "# RLM Audit Response",
            "",
            f"Candidate: `{candidate_id}`",
            f"Task: `{task_id}`",
            f"Task file: `{task_ref}`",
            "",
            "This is a deterministic orchestration audit, not a live model-generated patch.",
            "",
            "## Recursive Work Units",
            "",
            "1. Interface read: inspect task spec, dependency specs, registry, and current tests.",
            "2. Rules read: identify legality, FEN, move, perft, and UCI constraints.",
            "3. Build plan: assign bounded file ownership and expected tests.",
            "4. Critique pass: check interface drift, hardcoded benchmark risk, and missing reports.",
            "5. Eval pass: run smoke, contract, milestone, perft, and tournament tiers as applicable.",
            "",
            "## Live Mode",
            "",
            "Run with `--mode live` and install/configure the `rlms` package plus provider keys to execute the actual RLM loop.",
        ]
    )


def live_response(prompt: str, backend: str, model_name: str, verbose: bool, trajectory_log_dir: Path) -> str:
    try:
        from rlm import RLM
    except ImportError as exc:  # pragma: no cover - optional external package
        raise SystemExit(
            "Live RLM mode requires the optional package from https://github.com/alexzhang13/rlm. "
            "Install with `pip install rlms`."
        ) from exc

    logger = None
    try:  # pragma: no cover - depends on optional external package internals
        from rlm.logger import RLMLogger

        trajectory_log_dir.mkdir(parents=True, exist_ok=True)
        logger = RLMLogger(log_dir=str(trajectory_log_dir))
    except Exception:
        logger = None

    kwargs = {
        "backend": backend,
        "backend_kwargs": {"model_name": model_name},
        "verbose": verbose,
    }
    if logger is not None:
        kwargs["logger"] = logger
    rlm = RLM(**kwargs)
    completion = rlm.completion(prompt)
    return getattr(completion, "response", str(completion))


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--mode", default="audit", choices=["audit", "live"])
    parser.add_argument("--task-root", default="infra/tasks")
    parser.add_argument("--output-root", default="reports/orchestration")
    parser.add_argument("--backend", default=os.environ.get("RLM_BACKEND", "openai"))
    parser.add_argument("--model", default=os.environ.get("RLM_MODEL", "gpt-5-nano"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    task_root = (ROOT / args.task_root).resolve()
    output_dir = ROOT / args.output_root / args.task / args.candidate_id
    output_dir.mkdir(parents=True, exist_ok=True)
    task_file = find_task_file(task_root, args.task)
    task_text = task_file.read_text(encoding="utf-8") if task_file else f"No task file found for {args.task}."

    prompt = build_prompt(args.task, args.candidate_id, task_text)
    prompt_path = output_dir / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    response_path = output_dir / "response.md"
    trajectory_log_dir = output_dir / "trajectory"
    if args.mode == "live":
        response = live_response(prompt, args.backend, args.model, args.verbose, trajectory_log_dir)
        status = "live_completed"
        live_model_used = True
        notes = "Live RLM completion ran. Review response/patch and trajectory logs before applying or promoting."
    else:
        response = audit_response(args.task, args.candidate_id, task_file)
        status = "audit_completed"
        live_model_used = False
        notes = "Audit mode produced orchestration evidence without model calls or repo edits."
    response_path.write_text(response, encoding="utf-8")

    record = RLMRunRecord(
        task_id=args.task,
        candidate_id=args.candidate_id,
        mode=args.mode,
        orchestration_type="rlm",
        task_file=display_path(task_file) if task_file else None,
        prompt_path=display_path(prompt_path),
        response_path=display_path(response_path),
        trajectory_log_dir=display_path(trajectory_log_dir) if args.mode == "live" and trajectory_log_dir.exists() else None,
        status=status,
        live_model_used=live_model_used,
        duration_seconds=round(time.monotonic() - started, 3),
        notes=notes,
    )
    record_path = output_dir / "orchestration.json"
    record_path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(asdict(record), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
