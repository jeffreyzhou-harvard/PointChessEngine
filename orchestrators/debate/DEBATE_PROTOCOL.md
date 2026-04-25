# Debate Protocol

Debate systems create candidate implementations or candidate reports through structured disagreement and revision.

## Rounds

Round 1: independent proposals

- Each role proposes an implementation approach independently.

Round 2: cross-critique

- Roles critique correctness, engineering risk, testing gaps, and interface compatibility.

Round 3: revised proposals

- Roles revise their proposals after critique.

Round 4: judge selects or synthesizes plan

- Judge chooses one plan or synthesizes a combined plan.

Round 5: builder implements

- Builder creates the candidate branch/patch.

Round 6: reviewer critiques patch

- Reviewer checks task scope, tests, interface safety, and benchmark integrity.

Round 7: tests/evals decide promotability

- Champion mode runs tests/evals. Debate output alone never decides promotion.

## Required Debate Artifacts

- initial proposals
- critique notes
- revised proposals
- selected/synthesized plan
- implementation summary
- review findings
- bugs caught before implementation
- tests/evals result
