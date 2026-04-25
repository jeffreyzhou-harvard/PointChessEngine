# Stage Gate Protocol

Champion mode runs one milestone at a time. A milestone usually maps to one task spec from `/tasks`, such as `C3_STATIC_EVALUATION`.

## Stage Gate Loop

For each milestone:

1. Freeze task spec.
2. Freeze canonical baseline commit.
3. Spawn candidate branches/worktrees from baseline.
4. Run frameworks/configurations in parallel.
5. Run unit tests/evals.
6. Run contract/interface tests.
7. Run code review.
8. Score candidates.
9. Promote winner into canonical baseline.
10. Archive loser branches/reports.
11. Write comparison report.
12. Begin next milestone.

## Local Manual Mode

Candidates are created by Codex, Claude, Replit Agent, Cursor, or other tools in local git worktrees. The local Champion scripts evaluate existing branches/worktrees, write reports, score candidates, and optionally print promotion commands.

Local manual mode is the recommended MVP.

See `agents/LOCAL_CHAMPION_SETUP.md`.

## VM Manual Mode

The Ubuntu VM version is the same workflow on a clean remote machine. Use it later for reproducibility, hardware isolation, or long tournament runs.

## Automated Mode

The local runner or VM orchestrator may later call model APIs directly. Automated mode still must use the same candidate branch naming, tests, scoring, and promotion gates.

## Recommended MVP

Use manual candidate creation plus local evaluation/scoring/promotion:

1. Human freezes task and baseline.
2. Agents create candidate branches.
3. Local runner creates worktrees for candidate branches.
4. Local runner runs `scripts/run_champion_stage.py`.
5. Human reviews comparison report.
6. Human confirms promotion.

## Stage Gate Outputs

Each stage should produce:

- candidate result JSON per candidate
- test logs per candidate
- code review summary per candidate
- AI usage records
- comparison report
- promotion decision

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
