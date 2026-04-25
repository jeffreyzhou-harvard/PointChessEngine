from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from methodologies.rlm.runner import audit_response, build_prompt, find_task_file


def test_find_task_file_by_exact_name() -> None:
    task_file = find_task_file(Path("infra/tasks"), "C0_ENGINE_INTERFACE")

    assert task_file is not None
    assert task_file.name == "C0_ENGINE_INTERFACE.md"


def test_build_prompt_contains_task_and_candidate() -> None:
    prompt = build_prompt("C0_ENGINE_INTERFACE", "C0_rlm_openai", "Objective: test")

    assert "C0_ENGINE_INTERFACE" in prompt
    assert "C0_rlm_openai" in prompt
    assert "Recursive Decomposition" in prompt


def test_audit_response_is_explicitly_not_live() -> None:
    response = audit_response("C0_ENGINE_INTERFACE", "C0_rlm_openai", None)

    assert "not a live model-generated patch" in response


def test_runner_audit_cli_writes_trace_files(tmp_path: Path) -> None:
    output_root = tmp_path / "orchestration"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "methodologies.rlm.runner",
            "--task",
            "C0_ENGINE_INTERFACE",
            "--candidate-id",
            "C0_rlm_openai",
            "--mode",
            "audit",
            "--output-root",
            str(output_root),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout.splitlines()[-1])
    record_path = output_root / "C0_ENGINE_INTERFACE" / "C0_rlm_openai" / "orchestration.json"
    assert payload["mode"] == "audit"
    assert payload["live_model_used"] is False
    assert record_path.exists()
