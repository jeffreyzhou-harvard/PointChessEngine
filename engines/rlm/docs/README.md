# RLM Engine Notes

This directory is intentionally small like the other checked-in engine
artifacts:

- `main.py` supports engine-directory execution.
- `python -m engines.rlm --uci` supports repo-root execution.
- `engine.py` contains the deterministic chess runtime.
- `uci.py` contains the protocol adapter.
- `tests/` contains focused unit and UCI tests.

The live or audited RLM orchestration lives in `methodologies/rlm`; the engine
runtime does not call model APIs.
