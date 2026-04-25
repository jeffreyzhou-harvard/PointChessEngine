# PointChess Arena

A web UI for pitting the repo's UCI engines against each other and watching their
metrics live (depth, nodes, NPS, score, wall time per move, plus build-cost
metadata for each engine).

## Run

```bash
pip install python-chess          # only runtime dependency
python -m arena                   # http://127.0.0.1:8765
python -m arena --port 9000       # custom port
```

## Engines

The registry in `arena/engines.py` knows how to launch each engine in UCI mode:

| id                       | launch                                    |
|--------------------------|-------------------------------------------|
| `oneshot_nocontext`      | `python -m oneshot_nocontext_engine --uci`|
| `oneshot_contextualized` | `python run_uci.py` (cwd = engine dir)    |
| `oneshot_react`          | `python -m oneshot_react_engine --uci`    |
| `chainofthought`         | `python -m chainofthought_engine --uci`   |
| `langgraph`              | `python -m uci.main` (cwd = `langgraph_output`) |

To add another engine, append an `EngineSpec(...)` to `REGISTRY`.

## Build-cost metadata

`arena/engine_costs.json` is merged into the static engine metadata at server
start. Any field on `EngineSpec` is overridable; e.g.:

```json
{
  "chainofthought": {
    "build_cost_usd": 4.20,
    "build_tokens": 380000,
    "build_model": "claude-sonnet-4-5"
  }
}
```

LOC counts are computed from each engine's source tree on startup.

## API

- `GET  /api/engines` — engine registry + metadata
- `POST /api/match` — body `{white, black, movetime_ms, max_plies}`, returns `{match_id}`
- `GET  /api/match/{id}/stream` — Server-Sent Events: `init` → `move`* → `end`
- `POST /api/match/{id}/stop` — request the running game to halt
