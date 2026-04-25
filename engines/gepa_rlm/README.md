# GEPA-RLM Engine Artifact

This is the uploadable GEPA-RLM engine target for Champion mode.

The current artifact reuses the deterministic `engines.rlm` runtime and exposes
it as a separate UCI engine named `PointChess GEPA-RLM`. That keeps the engine
legal and testable without inventing new chess logic inside the methodology
scaffold.

The methodology lives in `methodologies/gepa_rlm`. Its job is to run recursive
task decomposition, collect traces, reflect on failures, mutate prompts, and
eventually produce a distinct evolved implementation branch. Until live GEPA-RLM
patch generation is enabled, this engine is a bootstrap baseline for reports and
Champion comparisons.

Run:

```bash
python -m engines.gepa_rlm --uci
python infra/scripts/uci_smoke.py --engine gepa_rlm
```
