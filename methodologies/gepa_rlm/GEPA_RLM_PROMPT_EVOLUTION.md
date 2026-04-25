# GEPA-RLM Prompt Evolution

Mutation rules:

- mutate prompts only based on trace evidence
- preserve task objective
- preserve interface contracts
- add missing constraints
- add missing edge cases
- improve test-first behavior
- improve code review behavior
- make prompts more specific and less vague
- avoid overfitting to one test name
- do not hardcode expected benchmark outputs

Good mutation example:

Failure:

`C2` failed an en passant discovered-check test.

Bad mutation:

> Make the en passant test pass.

Good mutation:

> When validating en passant, remember that removing the captured pawn can reveal an attack line against the moving side's king. Do not treat en passant as legal until the resulting board state has been checked for king safety.

Bad mutation:

> Skip en passant if complicated.

Good mutation:

> Generate pseudo-legal moves first, then apply each candidate move on a reversible board state and reject it if own king remains or becomes attacked.
