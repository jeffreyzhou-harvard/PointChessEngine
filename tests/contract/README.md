# Contract Tests

This directory is reserved for public interface contract tests.

Public interfaces are frozen unless changed through `/tasks/evals/E6_INTERFACE_CHANGE_PROTOCOL.md` if that file exists. If it does not exist, create and approve an interface-change protocol before changing shared contracts.

Agents may change internals, but candidate implementations must satisfy shared interfaces. Candidate implementations may use adapters if their internals differ.

## Promotion Gate

A candidate can only be promoted into canonical if it passes:

- interface contract tests
- current milestone tests
- previous milestone regression tests
- integration smoke tests
- code review

The canonical branch must always pass all tests up to the current milestone.

## Intended Contracts

Engine interface:

- launchable engine command
- UCI-compatible process boundary
- parseable `info` and `bestmove` output

Board interface:

- parse FEN
- serialize FEN deterministically
- expose side to move, castling, en passant, halfmove, fullmove

Move interface:

- parse UCI move strings
- serialize UCI move strings
- represent promotions

Evaluator interface:

- accept a legal position
- return deterministic numeric score
- document score perspective

Search interface:

- accept position and limits
- return legal move
- report diagnostics such as depth, nodes, time, score

UCI interface:

- support `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit`
- return `uciok`, `readyok`, and `bestmove` as required

## Candidate Promotion Checklist

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
