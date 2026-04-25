# RLM Audit Response

Candidate: `C7_rlm_openai`
Task: `C7_UCI_COMPATIBILITY`
Task file: `infra/tasks/classical/C7_UCI_COMPATIBILITY.md`

This is a deterministic orchestration audit, not a live model-generated patch.

## Recursive Work Units

1. Interface read: inspect task spec, dependency specs, registry, and current tests.
2. Rules read: identify legality, FEN, move, perft, and UCI constraints.
3. Build plan: assign bounded file ownership and expected tests.
4. Critique pass: check interface drift, hardcoded benchmark risk, and missing reports.
5. Eval pass: run smoke, contract, milestone, perft, and tournament tiers as applicable.

## Live Mode

Run with `--mode live` and install/configure the `rlms` package plus provider keys to execute the actual RLM loop.