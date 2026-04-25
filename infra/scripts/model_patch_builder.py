#!/usr/bin/env python3
"""Run one model-backed agent builder for a Champion candidate worktree.

The builder is intentionally patch-oriented: it reads the task spec, asks an
agent/model to edit only the candidate worktree, records the prompt/response,
and optionally commits any produced changes. Providers that cannot run without
credentials fail loudly instead of writing fake implementation artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def resolve_path(path_text: str, *, base: Path = ROOT) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else (base / path).resolve()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def find_task_file(task_id: str) -> Path | None:
    task_root = ROOT / "infra" / "tasks"
    exact_name = f"{task_id}.md"
    for path in task_root.rglob("*.md"):
        if path.name == exact_name:
            return path
    prefix = task_id.split("_", 1)[0]
    for path in task_root.rglob("*.md"):
        if path.name.startswith(prefix + "_"):
            return path
    return None


def read_dependencies(task_id: str) -> str:
    docs = []
    for name in ["START_HERE.md", "AGENT_PROTOCOL.md", "PRIORITY_PLAN.md"]:
        path = ROOT / "infra" / "tasks" / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            docs.append(f"# {display_path(path)}\n\n{text[:5000]}")
    unit_tests = ROOT / "infra" / "tasks" / "UNIT_TESTS.md"
    prefix = task_id.split("_", 1)[0]
    if unit_tests.exists() and prefix.startswith("C"):
        text = unit_tests.read_text(encoding="utf-8")
        pattern = re.compile(rf"(?ms)^## {re.escape(prefix)}\b.*?(?=^## C\d+|\Z)")
        match = pattern.search(text)
        if match:
            docs.append(f"# {display_path(unit_tests)} relevant section\n\n{match.group(0)}")
    if prefix.startswith("C"):
        current = int(prefix[1:])
        for i in range(max(0, current - 2), current):
            for path in (ROOT / "infra" / "tasks" / "classical").glob(f"C{i}_*.md"):
                docs.append(f"# {display_path(path)}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(docs)


def build_prompt(args: argparse.Namespace, worktree: Path) -> str:
    task_file = find_task_file(args.task)
    task_text = task_file.read_text(encoding="utf-8") if task_file else f"No task file found for {args.task}."
    dependencies = read_dependencies(args.task)
    return "\n\n".join(
        [
            "# PointChess Candidate Builder Prompt",
            f"Task ID: `{args.task}`",
            f"Candidate ID: `{args.candidate_id}`",
            f"Methodology style: `{args.style}`",
            f"Provider: `{args.provider}`",
            f"Worktree: `{worktree}`",
            "## Non-Negotiable Rules",
            "- Implement only the assigned task.",
            "- Do not edit unrelated modules.",
            "- Do not remove or weaken tests.",
            "- Do not hardcode benchmark answers.",
            "- Preserve public interfaces unless the task explicitly requires an interface change.",
            "- Add or update task-relevant tests.",
            "- Write a task report under `reports/tasks/`.",
            "- Run the relevant tests if possible.",
            "- Leave a clear git diff in this worktree.",
            "## Task Spec",
            task_text,
            "## Dependency Context",
            dependencies,
            "## Expected Final State",
            "The repository worktree should contain a real implementation diff for this task, plus tests/report updates. "
            "If using a patch-only provider, return a single unified diff that applies cleanly with `git apply`.",
        ]
    )


def run_subprocess(command: list[str], cwd: Path, timeout: float | None, *, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, text=True, input=input_text, capture_output=True, timeout=timeout)


def git_has_changes(worktree: Path) -> bool:
    status = run_subprocess(["git", "status", "--porcelain"], worktree, None)
    return bool(status.stdout.strip())


def commit_changes(worktree: Path, task_id: str, candidate_id: str) -> bool:
    if not git_has_changes(worktree):
        return False
    subprocess.run(["git", "config", "user.name", "PointChess Champion Bot"], cwd=worktree, check=False)
    subprocess.run(["git", "config", "user.email", "champion-bot@pointchess.local"], cwd=worktree, check=False)
    subprocess.run(["git", "add", "-A"], cwd=worktree, check=True)
    message = f"{task_id}: {candidate_id} candidate build"
    completed = subprocess.run(["git", "commit", "-m", message], cwd=worktree, text=True, capture_output=True)
    return completed.returncode == 0


def extract_diff(text: str) -> str:
    fenced = re.search(r"```(?:diff|patch)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start_match = re.search(r"(?m)^(diff --git |--- |\*\*\* Begin Patch)", candidate)
    if not start_match:
        return ""
    diff = candidate[start_match.start() :].strip()
    if diff.startswith("*** Begin Patch"):
        return ""
    return diff + "\n"


def apply_unified_diff(worktree: Path, response: str) -> tuple[bool, str]:
    diff = extract_diff(response)
    if not diff:
        return False, "response did not contain a unified diff"
    check = run_subprocess(["git", "apply", "--check", "-"], worktree, None, input_text=diff)
    if check.returncode != 0:
        return False, check.stderr or check.stdout or "git apply --check failed"
    apply = run_subprocess(["git", "apply", "-"], worktree, None, input_text=diff)
    if apply.returncode != 0:
        return False, apply.stderr or apply.stdout or "git apply failed"
    return True, "diff applied"


def run_codex_cli(prompt: str, worktree: Path, output_dir: Path, timeout: float | None, model: str | None) -> dict:
    codex = os.environ.get("CODEX_CLI") or shutil.which("codex")
    if not codex:
        return {"returncode": 127, "status": "missing_tool", "error": "codex CLI not found"}
    last_message = output_dir / "codex_last_message.md"
    command = [
        codex,
        "-a",
        "never",
        "exec",
        "--cd",
        str(worktree),
        "--sandbox",
        "workspace-write",
        "--output-last-message",
        str(last_message),
    ]
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    completed = run_subprocess(command, worktree, timeout)
    return {
        "returncode": completed.returncode,
        "status": "completed" if completed.returncode == 0 else "failed",
        "command": command[:1] + ["exec", "..."],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "response_path": display_path(last_message) if last_message.exists() else None,
        "response": last_message.read_text(encoding="utf-8") if last_message.exists() else completed.stdout,
    }


def run_claude_cli(prompt: str, worktree: Path, output_dir: Path, timeout: float | None, model: str | None) -> dict:
    claude = os.environ.get("CLAUDE_CLI") or shutil.which("claude")
    if not claude:
        return {"returncode": 127, "status": "missing_tool", "error": "claude CLI not found"}
    response_path = output_dir / "claude_response.md"
    command = [
        claude,
        "-p",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "text",
    ]
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    completed = run_subprocess(command, worktree, timeout)
    response_path.write_text(completed.stdout, encoding="utf-8")
    return {
        "returncode": completed.returncode,
        "status": "completed" if completed.returncode == 0 else "failed",
        "command": command[:1] + ["-p", "..."],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "response_path": display_path(response_path),
        "response": completed.stdout,
    }


def run_openai_patch(prompt: str, model: str | None) -> dict:
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPEN_AI_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_KEY"]
    if not os.environ.get("OPENAI_API_KEY"):
        return {"returncode": 2, "status": "missing_credentials", "error": "OPENAI_API_KEY is not set"}
    try:
        from openai import OpenAI
    except ImportError as exc:
        return {"returncode": 127, "status": "missing_dependency", "error": str(exc)}
    client = OpenAI()
    response = client.responses.create(
        model=model or os.environ.get("POINTCHESS_OPENAI_MODEL", "gpt-5.4"),
        input=[
            {
                "role": "system",
                "content": "You are a senior software engineering agent. Return only a unified git diff unless impossible.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return {"returncode": 0, "status": "completed", "response": response.output_text}


def run_anthropic_patch(prompt: str, model: str | None) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_KEY")
    if not key:
        return {"returncode": 2, "status": "missing_credentials", "error": "ANTHROPIC_API_KEY/ANTHROPIC_KEY is not set"}
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        return {"returncode": 127, "status": "missing_dependency", "error": str(exc)}
    client = Anthropic(api_key=key)
    response = client.messages.create(
        model=model or os.environ.get("POINTCHESS_ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt + "\n\nReturn only a unified git diff."}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    return {"returncode": 0, "status": "completed", "response": text}


def run_rlm_patch(prompt: str, model: str | None) -> dict:
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPEN_AI_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_KEY"]
    if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_KEY"]
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_KEY"):
        return {"returncode": 2, "status": "missing_credentials", "error": "RLM live mode requires provider credentials"}
    try:
        from rlm import RLM
    except ImportError as exc:
        return {"returncode": 127, "status": "missing_dependency", "error": str(exc)}
    backend = os.environ.get("RLM_BACKEND", "openai")
    rlm = RLM(backend=backend, backend_kwargs={"model_name": model or os.environ.get("RLM_MODEL", "gpt-5-mini")})
    completion = rlm.completion(prompt + "\n\nReturn only a unified git diff.")
    return {"returncode": 0, "status": "completed", "response": getattr(completion, "response", str(completion))}


def provider_run(args: argparse.Namespace, prompt: str, worktree: Path, output_dir: Path) -> dict:
    if args.provider == "claude_cli":
        return run_claude_cli(prompt, worktree, output_dir, args.timeout, args.model)
    if args.provider == "codex_cli":
        return run_codex_cli(prompt, worktree, output_dir, args.timeout, args.model)
    if args.provider == "openai":
        return run_openai_patch(prompt, args.model)
    if args.provider == "anthropic":
        return run_anthropic_patch(prompt, args.model)
    if args.provider == "rlm":
        return run_rlm_patch(prompt, args.model)
    raise SystemExit(f"Unknown builder provider: {args.provider}")


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--provider", required=True, choices=["claude_cli", "codex_cli", "openai", "anthropic", "rlm"])
    parser.add_argument("--style", default="agent")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--output-root", default="reports/builds")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    worktree = resolve_path(args.worktree)
    output_dir = ROOT / args.output_root / args.task / args.candidate_id
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(args, worktree)
    prompt_path = output_dir / "prompt.md"
    response_path = output_dir / "response.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    if not worktree.exists():
        result = {"returncode": 127, "status": "missing_worktree", "error": f"worktree does not exist: {worktree}"}
    elif args.dry_run:
        result = {"returncode": 0, "status": "dry_run", "response": "Dry run: builder prompt written; no model invoked."}
    else:
        result = provider_run(args, prompt, worktree, output_dir)

    response = result.get("response") or result.get("error") or ""
    response_path.write_text(response, encoding="utf-8")
    applied = False
    apply_message = ""
    if result.get("returncode") == 0 and args.provider not in {"codex_cli", "claude_cli"} and not args.dry_run:
        applied, apply_message = apply_unified_diff(worktree, response)
        if not applied:
            result["returncode"] = 1
            result["status"] = "patch_failed"
            result["error"] = apply_message
    has_changes = worktree.exists() and git_has_changes(worktree)
    committed = False
    if args.commit and has_changes and result.get("returncode") == 0:
        committed = commit_changes(worktree, args.task, args.candidate_id)
        has_changes = worktree.exists() and git_has_changes(worktree)

    record = {
        "task_id": args.task,
        "candidate_id": args.candidate_id,
        "provider": args.provider,
        "style": args.style,
        "model": args.model,
        "worktree": str(worktree),
        "prompt_path": display_path(prompt_path),
        "response_path": display_path(response_path),
        "status": result.get("status"),
        "returncode": result.get("returncode"),
        "error": result.get("error"),
        "applied_patch": applied,
        "apply_message": apply_message,
        "has_changes": has_changes,
        "committed": committed,
        "duration_seconds": round(time.monotonic() - started, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "builder.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stdout_log = output_dir / "stdout.log"
    stderr_log = output_dir / "stderr.log"
    stdout_log.write_text(result.get("stdout", ""), encoding="utf-8")
    stderr_log.write_text(result.get("stderr", "") + ("\n" + result.get("error", "") if result.get("error") else ""), encoding="utf-8")
    print(json.dumps(record, sort_keys=True))
    return int(result.get("returncode") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
