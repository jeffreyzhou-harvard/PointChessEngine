# Workstreams

The `/tasks` suite defines the milestones. This document groups those milestones into workstreams for parallel planning and Champion-mode candidate execution.

| Workstream | Primary tasks | Dependencies | Can run in parallel with | Merge risks |
| --- | --- | --- | --- | --- |
| Core rules | C1, C2 | C0, E1 | Evaluation harness, research/reporting | Incorrect board or move APIs can break every later task |
| Evaluation harness | C0, E1, E2, E3, E4 if present in `/tasks` | None for C0/E4; C1/C2 for deep legality checks | Core rules, review/integration | Harness drift can make candidates incomparable |
| Search/eval | C3, C4, C5, C6 | C1, C2, E1 | UCI/tournament after interfaces stabilize | Search may mutate board state or bypass legal moves |
| UCI/tournament | C7, tournament scripts | C0, C4, E2, E3; preferably C6 | Search/eval, reporting | Protocol regressions can block all tournaments |
| Strength/UI | C8; UI deferred | C4, C7; preferably C6 | Reporting and calibration | Strength claims can overstate Elo or introduce illegal moves |
| Neural | N1, N2, N4, N5 | C1, C2, C4 | Reporting, non-overlapping data work | Illegal policy outputs or model artifacts can make runs non-reproducible |
| Review/integration | Code review, interface checks, merge decisions | Active candidate branches | All workstreams | Premature promotion can destabilize canonical baseline |
| Research/reporting | Final report, prior art, prompt/cost logs | Evals and task reports | All workstreams | Missing logs make workflow comparisons unauditable |

## Workstream Rules

- Every workstream must identify its public interface touchpoints before editing.
- Workstream branches must not silently change shared contracts.
- Candidate work must preserve task reports and AI usage records.
- Review/integration owns promotion into canonical main.
- Reporting owns the audit trail but must not retroactively change eval results.
