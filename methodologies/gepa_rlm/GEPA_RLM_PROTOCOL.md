# GEPA-RLM Protocol

GEPA-RLM is a methodology track, not a chess engine and not Champion/Docker infrastructure.

It combines:

1. RLM-style recursive decomposition
   - root agent decomposes the assigned task
   - subcalls inspect interfaces, tests, edge cases, implementation risks, and review risks
   - root synthesizes an implementation plan or candidate report

2. GEPA-style reflective prompt evolution
   - collect traces, test failures, review feedback, interface errors, and score breakdowns
   - diagnose what failed
   - mutate root and subagent prompts based on evidence
   - rerun evolved recursive candidates
   - select the strongest evolved candidate

Research question:

Does reflective prompt evolution improve the strongest base recursive orchestration method?

## Loop

Phase 0: Load task and baseline.

- read task spec from `infra/tasks`
- read interface contracts
- read current repo state
- read previous reports if available
- read the Champion rubric

Phase 1: Seed RLM run.

- use seed GEPA-RLM prompts
- root decomposes task
- subagents inspect interfaces, tests, edge cases, implementation plan, and review plan
- root synthesizes candidate plan/report

Phase 2: Trace collection.

- root and subagent prompts
- subagent outputs
- implementation plan
- patch summary if available
- test/review/benchmark feedback if available
- candidate score breakdown
- cost/time/token estimates

Phase 3: Reflective diagnosis.

- what failed
- why it failed
- which prompt instruction was weak
- which edge case was underemphasized
- which interface assumption was wrong
- which subagent role underperformed

Phase 4: Prompt mutation.

- mutate root/subagent prompts only from trace evidence
- preserve task objective, tests, scoring, and interfaces
- never hardcode benchmark answers

Phase 5: Rerun evolved RLM.

- rerun using evolved prompts
- collect new traces
- compare to seed RLM

Phase 6: Selection.

- choose the best evolved candidate by test pass rate, interface compatibility, review score, benchmark impact, cost/time, and prompt evolution evidence

Phase 7: Report.

- write trace, mutation log, result JSON, and selection report
- never promote automatically
