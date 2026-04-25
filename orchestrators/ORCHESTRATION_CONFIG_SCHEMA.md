# Orchestration Config Schema

Champion mode config files live under `configs/champion/`.

Required fields:

- `candidate_id`
- `task_id`
- `orchestration_type`
- `model_assignments`
- `execution_environment`
- `allowed_tools`
- `budget`
- `branch_name`
- `worktree_path`
- `output_report_path`
- `notes`

## Example YAML Candidate

```yaml
candidate_id: C3_debate_heterogeneous_claude_gpt_gemini
task_id: C3_STATIC_EVALUATION
orchestration_type: debate_ensemble
model_assignments:
  architect: claude
  skeptic: gemini
  builder: gpt
  reviewer: claude
execution_environment: external_branch_or_vm
branch_name: experiments/C3/debate_heterogeneous
worktree_path: ../worktrees/C3-debate-heterogeneous
allowed_tools:
  - repo_edit
  - pytest
  - git_diff
budget:
  max_minutes: 45
  max_cost_usd: 15
output_report_path: reports/tasks/C3_debate_heterogeneous.md
notes: "Heterogeneous debate candidate for C3."
```

## Candidate ID Format

```text
<task_id>_<orchestration>_<model_setup>
```

Examples:

- `C3_react_claude`
- `C3_debate_heterogeneous_claude_gpt_gemini`
- `C4_codex_agent`
- `C8_replit_agent`
