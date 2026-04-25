# Engine Interfaces

This directory documents stable interfaces for generated engine candidates. It does not contain engine logic.

Public interfaces are frozen unless changed through `/infra/tasks/evals/E6_INTERFACE_CHANGE_PROTOCOL.md` if that file exists. If it does not exist, create and approve such a protocol before changing shared contracts.

Agents may change internals but must satisfy shared interfaces. Candidate implementations may use adapters if their internals differ.

## Interface Contracts

Engine interface:

- candidate can be launched by command from the Champion config
- candidate exposes UCI for external evaluation
- candidate produces parseable diagnostics where available

Board interface:

- supports FEN parse/serialize
- preserves side-to-move, castling, en passant, halfmove, and fullmove state

Move interface:

- supports UCI notation
- supports promotion notation
- supports deterministic equality/serialization

Evaluator interface:

- returns numeric position score
- documents sign convention
- handles terminal states consistently

Search interface:

- returns only legal moves
- respects depth/time limits when supported
- reports score, nodes, depth, and time when supported

UCI interface:

- supports core UCI commands
- exits cleanly
- does not hang on invalid input

## Promotion Checklist

- candidate branch exists
- candidate report exists
- tests run
- contract tests pass
- milestone tests pass
- previous tests pass
- no public interface changes unless approved
- code review score exists
- benchmark results exist if applicable
- AI usage/cost logged
- winner comparison report generated
