# Candidate Comparison Protocol

This protocol scores candidate implementations for the same milestone. It is used by Champion mode after tests, contract checks, review, and benchmarks are complete.

## Scoring

Total: 100 points.

| Category | Points |
| --- | ---: |
| Correctness tests | 35 |
| Code review quality | 20 |
| Interface compatibility / integration cleanliness | 15 |
| Performance / engine impact | 15 |
| Cost/time efficiency | 10 |
| Documentation/report quality | 5 |

Correctness and contract failures should normally block promotion even if the weighted score is high.

## Candidate Result Schema

```json
{
  "task_id": "C3_STATIC_EVALUATION",
  "candidate_id": "C3_debate_heterogeneous_claude_gpt_gemini",
  "orchestration_type": "debate_ensemble",
  "model_assignments": {
    "architect": "claude",
    "skeptic": "gemini",
    "builder": "gpt",
    "reviewer": "claude"
  },
  "execution_environment": "external_branch_or_vm",
  "branch": "experiments/C3/debate_heterogeneous",
  "baseline_commit": "...",
  "tests_passed": 42,
  "tests_total": 45,
  "contract_tests_passed": true,
  "review_score": 36,
  "benchmark_score": 14,
  "cost_estimate_usd": 5.25,
  "latency_minutes": 28,
  "promotion_status": "candidate"
}
```

## Comparison Report Format

Each comparison report must include:

- task
- baseline commit
- candidates
- tests
- contract/interface status
- review scores
- benchmark results
- cost/time
- winner
- reason for promotion
- rejected candidates and why
- what was merged
- what was not merged

## Candidate ID Format

```text
<task_id>_<orchestration>_<model_setup>
```

Examples:

- `C3_react_claude`
- `C3_debate_heterogeneous_claude_gpt_gemini`
- `C4_codex_agent`
- `C8_replit_agent`

## Reporting Location

Use:

```text
reports/comparisons/<task_id>/<candidate_id>/
reports/comparisons/<task_id>/comparison.md
reports/comparisons/<task_id>/scores.json
```
