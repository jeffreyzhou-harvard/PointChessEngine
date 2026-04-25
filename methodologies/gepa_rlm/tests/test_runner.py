from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from methodologies.gepa_rlm.runner import default_config, find_task_file


def test_find_task_file() -> None:
    task_file = find_task_file("C3_STATIC_EVALUATION")

    assert task_file is not None
    assert task_file.name == "C3_STATIC_EVALUATION.md"


def test_default_config_has_gepa_rlm_methodology() -> None:
    config = default_config("C3_STATIC_EVALUATION", "C3_gepa_rlm")

    assert config["methodology"] == "gepa_rlm"
    assert config["base_orchestration"] == "rlm_lite"
    assert "reflector" in config["model_assignments"]


def test_runner_audit_cli_writes_methodology_artifacts(tmp_path: Path) -> None:
    output_root = tmp_path / "gepa_rlm"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "methodologies.gepa_rlm",
            "--task",
            "C3_STATIC_EVALUATION",
            "--candidate-id",
            "C3_gepa_rlm_test",
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
    candidate_root = output_root / "C3_STATIC_EVALUATION" / "C3_gepa_rlm_test"
    assert payload["methodology"] == "gepa_rlm"
    assert payload["live_model_used"] is False
    assert (candidate_root / "trace.jsonl").exists()
    assert (candidate_root / "prompt.md").exists()
    assert (candidate_root / "response.md").exists()
    assert (candidate_root / "orchestration.json").exists()
    assert (candidate_root / "prompt_mutations.json").exists()
    assert (candidate_root / "result.json").exists()
    assert (candidate_root / "selection.md").exists()
