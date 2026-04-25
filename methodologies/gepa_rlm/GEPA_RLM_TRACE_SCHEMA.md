# GEPA-RLM Trace Schema

`methodologies.gepa_rlm.runner` writes JSONL trace events.

Each event contains:

- `run_id`
- `task_id`
- `candidate_id`
- `round`
- `event_type`
- `agent_role`
- `model`
- `prompt_path`
- `input_summary`
- `output_summary`
- `file_refs`
- `timestamp`
- `latency_ms`
- `token_estimate`
- `cost_estimate_usd`
- `notes`

Event types:

- `root_decomposition`
- `subcall_interface_inspection`
- `subcall_test_design`
- `subcall_edge_case_analysis`
- `subcall_implementation_planning`
- `subcall_review`
- `synthesized_plan`
- `reflection`
- `prompt_mutation`
- `candidate_selection`

Candidate result fields:

- `candidate_id`
- `task_id`
- `methodology`
- `base_orchestration`
- `round`
- `tests_passed`
- `tests_total`
- `contract_tests_passed`
- `review_score`
- `benchmark_score`
- `champion_score`
- `cost_estimate_usd`
- `latency_minutes`
- `prompt_mutations`
- `bugs_caught_before_implementation`
- `promotion_recommendation`
