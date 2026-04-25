# Chess by Committee
## A methodology-driven experimental framework for AI-generated chess engines

We did not build a single chess engine.
We built a structured experimental apparatus for generating and comparing chess engines under different AI methodologies, then measured the methodologies themselves.

---

## Overview

This repository investigates a core question:

**When an AI system builds a chess engine, which AI-usage methodology yields the strongest result for the lowest cost?**

The engine artifact is the output, not the endpoint. The endpoint is controlled comparison across:

- prompting patterns
- multi-agent topologies
- orchestration runtimes
- model choices
- parallelization strategies

Every approach is implemented end-to-end, evaluated in a unified harness, and reported on a multi-axis scorecard (quality, cost, latency, robustness, and engineering process).

---

## Why this project matters

Most chess+LLM work reports playing strength from one methodology. That conflates model quality with system design quality.

This project separates those variables. Chess is a clean evaluation domain:

- fixed rules
- strong oracle (`stockfish`)
- well-studied search space
- measurable failure modes (illegal moves, hallucinated board state, protocol errors)

That makes it a practical benchmark for the broader engineering question:

**How should AI teams structure their LLM workflows to maximize output quality per dollar?**

---

## Current repository scope

This repo currently contains multiple concrete engine implementations plus orchestration/testing infrastructure.

### Top-level layout

```
engines/         the chess-engine artifacts being compared (each speaks UCI)
methodologies/   the builders that produce engines (orchestration runtimes)
arena/           web UI for engine-vs-engine matches with live metrics
infra/           configs, scripts, agent/task/orchestrator protocol docs
reports/         run, eval, and comparison artifacts
tests/           cross-engine classical / contract tests
```

### Engine implementations

- `engines/oneshot_nocontext/`
- `engines/oneshot_contextualized/`
- `engines/oneshot_react/`
- `engines/chainofthought/`
- `engines/langgraph/` (artifact produced by `methodologies/langgraph/`)

Each engine supports UCI mode so it can be tournament-evaluated in a common pipeline.

### Methodologies (engine builders)

- `methodologies/langgraph/` - LangGraph multi-agent orchestrator that builds an engine into `engines/langgraph/`

### Interactive dashboard (new)

- `dashboard/backend/` - FastAPI backend + WebSocket streaming + local persistence
- `dashboard/frontend/` - React + Vite UI for live matches and result exploration
- `dashboard/results/` - persisted match artifacts

Dashboard supports:

- engine-vs-engine (fixed four LLM engines)
- engine-vs-stockfish
- live boards/charts/cross-table
- replay/export from saved history

For dashboard-specific details, see `dashboard/README.md`.

### Evaluation and orchestration assets

- `infra/agents/` - methodology/process protocols and parallelization plans
- `infra/orchestrators/` - orchestration schemas and debate runtime notes
- `infra/scripts/` - candidate scoring, champion tests, report generation
- `infra/tasks/` - work plans and protocol docs
- `reports/` - run/eval/comparison outputs
- `tests/` - classical/contract/dashboard tests

---

## Judging criteria alignment

### Creativity

- Heterogeneous debate personas and orchestration exploration in `infra/orchestrators/debate/`
- Stockfish-referenced decision loops in engine variants and eval scripts
- Persona/rating-aware behavior explored across approach families
- Geometric and format robustness treated as a separate eval concern from raw Elo

### Rigor

- Reproducible protocol docs in `infra/agents/` and `infra/tasks/`
- Tournament and candidate-stage automation in `infra/scripts/`
- Structured comparisons and reporting in `reports/comparisons/`
- Contract and integration-level tests under `tests/`

### Ingenuity

- Three-layer parallelization strategy (within-process, game-level, matrix-level)
- Multiple methodology families under one repo contract (one-shot, CoT, ReAct, graph/debate)
- Cost-aware experimentation and model/routing flexibility

### Engineering

- Modular engine packages with UCI adapters
- Shared orchestration protocols and stage gates
- Automated candidate/champion evaluation scripts
- Interactive local dashboard for live experiments

---

## System architecture (repository-aligned)

The framework has five replaceable layers:

1. **Engine implementations**  
   Engine packages listed above expose UCI-compatible behavior.

2. **Harness/orchestration glue**  
   Protocol and orchestration definitions in `infra/orchestrators/`, `infra/agents/`, `infra/tasks/`, and `infra/scripts/`.

3. **Tournament/evaluation**  
   Candidate/champion evaluation workflow in `infra/scripts/`, with artifacts in `reports/`.

4. **Parallel execution**  
   Strategy docs in `infra/agents/PARALLELIZATION_PLAN.md` plus branch-specific parallel demos.

5. **UI surface**  
   - Engine-specific web UIs inside each engine package  
   - Unified experiment dashboard in `dashboard/`

---

## AI methodology used in this project

This project treats AI as three separate roles:

1. **AI as builder**: helps produce harness/eval/UI code
2. **AI as player**: powers LLM-driven chess engines
3. **AI as judge/critic**: evaluates reasoning quality and process outputs where applicable

A central principle is human-reviewed iteration:

- proposed changes are tested and compared, not blindly accepted
- orchestration decisions are documented as protocols and stage gates
- performance/cost tradeoffs are measured, not assumed

---

## Experimental framework (approach spectrum)

Core families represented in this repo:

- One-shot baseline (`engines/oneshot_nocontext/`)
- One-shot contextualized (`engines/oneshot_contextualized/`)
- Structured reasoning / chain-of-thought (`engines/chainofthought/`)
- Tool-using ReAct (`engines/oneshot_react/`)
- Graph/orchestration-focused variants (`methodologies/langgraph/`, orchestrator docs)

These are evaluated comparatively through shared run scripts and reporting outputs.

---

## Parallelization strategy

Three distinct bottlenecks are handled separately:

1. **LLM calls inside one game** (network bound)  
   Async concurrency and rate-limited orchestration

2. **Many games at once** (CPU/process bound)  
   Multi-game runners and engine process pools

3. **Full experiment matrix** (orchestration bound)  
   Batch workflows, staged candidate pipelines, and scheduled comparisons

See `infra/agents/PARALLELIZATION_PLAN.md` and `infra/scripts/` for concrete process flow.

---

## Setup and run

### Prerequisites

- Python 3.11+
- Node 20+ (for dashboard/frontend)
- Optional but recommended: `stockfish` on PATH or set `STOCKFISH_PATH`

### Install core Python deps

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Run an engine directly

```bash
# Example: no-context engine UI
.venv/bin/python -m engines.oneshot_nocontext

# Example: UCI mode
.venv/bin/python -m engines.oneshot_nocontext --uci
```

### Run interactive dashboard (recommended)

```bash
make dashboard-install
make dashboard
```

Then open: `http://127.0.0.1:5173`

### Dashboard environment variables

- `STOCKFISH_PATH` (required for engine-vs-stockfish tab)
- model provider keys required by selected engine(s)

---

## Testing

### Engine/package tests

```bash
.venv/bin/python -m pytest engines/oneshot_nocontext/tests -v
.venv/bin/python -m pytest engines/oneshot_contextualized/tests -v
```

### Dashboard backend test

```bash
.venv/bin/python -m pytest tests/dashboard/test_backend_ws.py -q
```

### Candidate/champion workflow

See scripts:

- `scripts/run_candidate_tests.py`
- `scripts/run_champion_stage.py`
- `scripts/score_candidates.py`
- `scripts/write_comparison_report.py`

---

## Repository map (current)

```text
PointChessEngine/
├── engines/chainofthought/
├── engines/oneshot_contextualized/
├── engines/oneshot_nocontext/
├── engines/oneshot_react/
├── methodologies/langgraph/
├── dashboard/
│   ├── backend/
│   ├── frontend/
│   └── results/
├── agents/
├── orchestrators/
├── scripts/
├── reports/
├── tasks/
├── tests/
├── Makefile
└── README.md
```

---

## Known limitations

- LLM-driven approaches are prompt-sensitive and can have wide Elo confidence intervals
- Cost/latency variance is substantial for agentic and debate-style approaches
- Cross-approach transitivity assumptions in Elo are imperfect
- Some orchestration/eval components are still evolving and documented as protocol-first

---

## Future work

- Broader model grid runs with tighter confidence bounds
- Additional framework-isolation experiments (same model/prompt, different runtime)
- Expanded robustness suite (metamorphic + adversarial probes)
- More complete cost-Elo Pareto reporting across all approach families

---

## Related docs in this repo

- `dashboard/README.md` - interactive dashboard usage
- `infra/agents/` - methodology and operational protocols
- `infra/orchestrators/` - orchestration schemas and runtime docs
- `tasks/START_HERE.md` - guided task entrypoint

If you want the README to mirror your whitepaper structure even more closely, the next step is adding dedicated top-level docs (`WHITEPAPER.md`, `RELATED_WORK.md`, `decisions/log.md`, and `/docs` figures) and linking them from here.
