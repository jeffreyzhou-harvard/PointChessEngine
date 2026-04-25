# PointChess RLM Engine

This engine is the repo-local artifact for the RLM orchestration track. It is
inspired by the Recursive Language Models project:

https://github.com/alexzhang13/rlm

The checked-in runtime is intentionally API-free. RLM is used as the generation
methodology: recursively decompose the chess task, keep evaluator signals
inspectable, and then build a deterministic UCI engine from the resulting plan.

## Run

```bash
python -m engines.rlm --uci
cd engines/rlm && python main.py --uci
```

## Design

- `engine.py` contains legal move selection using python-chess, bounded negamax,
  alpha-beta pruning, move ordering, and a recursive evaluation trace.
- `uci.py` adapts the engine to the UCI commands used by Champion mode.
- Tests cover legality, deterministic search, evaluation sanity, and UCI smoke.

This is a current-engine benchmark artifact, not the canonical C0/C1
implementation path.
