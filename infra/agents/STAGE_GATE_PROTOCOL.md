# Stage Gate Protocol

Champion mode runs one milestone at a time. A milestone usually maps to one task spec from `/tasks`, such as `C3_STATIC_EVALUATION`.

## Stage Gate Loop

For each milestone:

1. Freeze task spec.
2. Freeze canonical baseline commit.
3. Spawn candidate branches/worktrees from baseline.
4. Run or audit the configured agent orchestration.
5. Run frameworks/configurations in parallel.
6. Run tiered Champion gates.
7. Run code review.
8. Score candidates.
9. Promote winner into canonical baseline.
10. Archive loser branches/reports.
11. Write comparison report.
12. Begin next milestone.

## Champion Tiers

Champion mode has five evaluation tiers:

| Tier | Purpose | Typical cadence |
|---|---|---|
| `smoke` | Fast Docker matrix. Launch each engine and require a legal UCI bestmove. | every PR |
| `contract` | Run `tests/contract` against each registered engine. | PRs touching UCI/registry/engines |
| `milestone` | Run relevant `tests/classical/test_c*.py` selected by milestone task, including prior C* regressions. | candidate promotion |
| `perft` | Run current perft legality gate; deeper per-engine perft needs a future debug/perft interface. | candidate promotion / scheduled |
| `tournament` | FastChess round robin and Stockfish calibration when tooling is installed. | manual or scheduled |

The ground truth remains task specs and tests. A promoted candidate becomes the
canonical baseline; it is not ground truth.

## Orchestration vs Artifact Testing

Testing `engines/<id>` only evaluates an existing artifact. It does not prove the
agent framework can generate that artifact.

For orchestration evidence, run:

```bash
python infra/scripts/run_agent_orchestration.py \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --candidate CURRENT_rlm \
  --task C0_ENGINE_INTERFACE \
  --mode audit
```

Use `--mode live` only when provider keys and dependencies are available. Audit
mode is useful for reproducible CI evidence, but it must be reported separately
from a live model-generated candidate run.

## Local Manual Mode

Candidates are created primarily by Claude/Anthropic-backed builders, with
Replit Agent, Cursor, RLM, and other tools available as comparison arms in local
git worktrees. The local Champion scripts evaluate existing branches/worktrees,
write reports, score candidates, and optionally print promotion commands.

Local manual mode is the recommended MVP.

See `infra/agents/LOCAL_CHAMPION_SETUP.md`.

## VM Manual Mode

The Ubuntu VM version is the same workflow on a clean remote machine. Use it later for reproducibility, hardware isolation, or long tournament runs.

## Automated Mode

The local runner, GitHub workflow, or VM orchestrator may call model APIs
directly. In GitHub/Docker, use the `anthropic` builder provider by default. On
a local machine or self-hosted runner with Claude Code installed, use
`claude_cli`. Automated mode still must use the same candidate branch naming,
tests, scoring, and promotion gates.

## Recommended MVP

Use manual candidate creation plus local evaluation/scoring/promotion:

1. Human freezes task and baseline.
2. Agents create candidate branches.
3. Local runner creates worktrees for candidate branches.
4. Local runner runs `infra/scripts/run_champion_stage.py`.
5. Human reviews comparison report.
6. Human confirms promotion.

## Stage Gate Outputs

Each stage should produce:

- candidate result JSON per candidate
- orchestration JSON per candidate when orchestration is enabled
- test logs per candidate
- code review summary per candidate
- AI usage records
- comparison report
- promotion decision
- graph-ready metric files: `metrics.csv`, `metrics.jsonl`, and `metrics.json`

## Stop Conditions

Stop before promotion if:

- task spec changed during candidate work
- baseline commit was not frozen
- candidate branch cannot be reproduced
- contract tests fail
- milestone tests fail
- previous milestone regressions fail
- public interface changes were not approved
- review score is missing
- AI usage/cost is missing
