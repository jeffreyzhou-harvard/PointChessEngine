# RLM Audit Response

Candidate: `C1_rlm_openai`
Task: `C1_BOARD_FEN_MOVE`
Task file: `infra/tasks/classical/C1_BOARD_FEN_MOVE.md`

This is a deterministic orchestration audit, not a live model-generated patch.

## Recursive Work Units

1. Interface read: inspect task spec, dependency specs, registry, and current tests.
2. Rules read: identify legality, FEN, move, perft, and UCI constraints.
3. Build plan: assign bounded file ownership and expected tests.
4. Critique pass: check interface drift, hardcoded benchmark risk, and missing reports.
5. Eval pass: run smoke, contract, milestone, perft, and tournament tiers as applicable.

## Live Mode

Run with `--mode live` and install/configure the `rlms` package plus provider keys to execute the actual RLM loop.