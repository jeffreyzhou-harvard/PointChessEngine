<p align="center">
  <img src="figures/ChessLogo.png" alt="Chess by Committee" width="200" />
</p>

<h1 align="center">Chess by Committee</h1>
<p align="center"><em>A methodology-driven experimental framework for AI-generated chess engines</em></p>

<p align="center">
  <a href="https://github.com/jeffreyzhou-harvard/PointChessEngine/stargazers">
    <img src="https://img.shields.io/github/stars/jeffreyzhou-harvard/PointChessEngine?style=social" alt="GitHub stars">
  </a>
  <a href="https://github.com/jeffreyzhou-harvard/PointChessEngine/network/members">
    <img src="https://img.shields.io/github/forks/jeffreyzhou-harvard/PointChessEngine?style=social" alt="GitHub forks">
  </a>
  <a href="https://github.com/jeffreyzhou-harvard/PointChessEngine/actions/workflows/tests.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/jeffreyzhou-harvard/PointChessEngine/tests.yml?branch=main&label=tests" alt="CI status">
  </a>
  <img src="https://img.shields.io/github/last-commit/jeffreyzhou-harvard/PointChessEngine" alt="last commit">
</p>

We did not build a single chess engine.
We built a structured experimental apparatus for generating and comparing chess engines under different AI methodologies, then measured the methodologies themselves.

---

## Overview

This repository investigates a core research question:

**How do different meta-prompting methods (one-shot, contextualized one-shot, chain-of-thought, ReAct, recursive-LM decomposition) and agentic development frameworks (LangGraph specialist orchestration, multi-model judge-mediated debate, multi-model peer-vote ensembles) affect the resulting chess engine's playing strength, search efficiency, build cost, and runtime behavior?**

The chess engine artifact is the *unit of measurement* — not the endpoint. The endpoint is a controlled comparison along several axes that are usually conflated:

- **meta-prompting method** — one prompt vs. [chain-of-thought](https://arxiv.org/abs/2201.11903) vs. [ReAct](https://arxiv.org/abs/2210.03629) vs. recursive decomposition
- **agentic framework** — none vs. [LangGraph](https://www.langchain.com/langgraph) specialists vs. multi-model debate vs. peer-vote ensemble
- **decision rule** — single judge vs. plurality vote vs. per-role specialist
- **model mix** — single-provider (Claude) vs. multi-provider (OpenAI / Grok / Gemini / DeepSeek / Kimi / Claude)
- **parallelization strategy** — within-process / game-level / matrix-level

Each of the eight engines holds the *task* constant (build a complete [UCI](https://www.chessprogramming.org/UCI) chess engine satisfying the same brief) and varies one or more of these axes. Every engine is then graded on the same multi-axis scorecard:

- **playing strength** — head-to-head results in `arena/`, contract-test pass rate, classical-milestone score
- **search efficiency** — depth reached, nodes searched, NPS, eval quality per move
- **runtime cost** — wall time per move, cumulative game time
- **build cost** — total $ spent, total tokens, lines of code produced, build wall time
- **robustness** — illegal-move rate, UCI-compliance failures, crash/timeout behavior

---

## Our initial hypothesis

Going in, we expected that **the more an agent is forced to plan and reason about its own design choices before writing code, the higher-quality and more thoroughly built-out the resulting engine would be** — measured both as playing strength and as raw lines of code shipped. Concretely:

- **One-shot baselines** would underperform because the model commits to a design implicitly, never surfaces tradeoffs, and runs out of attention before fleshing out the harder modules (search extensions, ELO scaling, edge cases in legality).
- **Chain-of-thought and ReAct** would do better because the model is forced to think through the design before (or during) writing it — surfacing more tradeoffs, catching more edge cases, producing more code per topic.
- **Agentic frameworks with multiple parallel roles** (LangGraph specialists, multi-model debate, peer-vote ensembles) would be the *extension* of that idea: split the planning across several focused agents, let them critique each other, and let a synthesizer compile the result. More parallel "thinking" → more design coverage → more complete engine.

The project is structured to *test* that hypothesis rather than assume it: every engine implements the same brief under the same constraints (pure Python, stdlib only, full UCI surface, ELO slider 400–2400), and the only thing that varies is the meta-prompting method or agentic framework that produced it. If the hypothesis is right, we should see playing strength and LOC scale roughly with how much pre-implementation reasoning each methodology forces. If it's wrong — if a one-shot prompt with a strong model holds its own against multi-agent orchestration — that's the more interesting finding.

---

## Sneak peek

<p align="center">
  <img src="figures/EngineHeadToHeadGIF.gif" alt="Two of the generated engines playing head-to-head inside our own tournament software" />
</p>

<p align="center"><em>Two of our final generated engines going head-to-head inside our own tournament software (the <code>arena/</code> web UI).</em></p>

<p align="center">
  <img src="figures/ChessTournament.gif" alt="Tournament mode running across all 8 final generated engines" />
</p>

<p align="center"><em>Tournament mode running for all 8 final generated engines.</em></p>

---

## Why this project matters

Most chess+LLM work reports playing strength from one methodology. That conflates model quality with system design quality.

This project separates those variables. Chess is a clean evaluation domain:

- fixed rules
- strong oracle ([Stockfish](https://stockfishchess.org/))
- well-studied search space
- measurable failure modes (illegal moves, hallucinated board state, protocol errors)

That makes it a practical benchmark for the broader engineering question:

**Given a fixed engineering task, which combination of meta-prompting method + agentic framework + model mix maximizes output quality per dollar — and is the marginal cost of more orchestration ever justified?**

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

### The eight engines and their construction methods

The whole point of the repo is the controlled A/B/C/... across these.
Every engine is a complete, UCI-speaking, pure-Python alpha-beta
chess engine. What changes is **how it was produced.**

| engine                                | construction method                                                | who decided | who wrote the code |
|---------------------------------------|--------------------------------------------------------------------|-------------|--------------------|
| `engines/oneshot_nocontext/`          | one Claude prompt, no project context                              | Claude      | Claude             |
| `engines/oneshot_contextualized/`     | one Claude prompt with curated repo context                        | Claude      | Claude             |
| `engines/oneshot_react/`              | one ReAct-style prompt with tool access                            | Claude      | Claude             |
| `engines/chainofthought/`             | incremental chain-of-thought prompting                             | Claude      | Claude             |
| `engines/langgraph/`                  | LangGraph multi-agent orchestration: per-role specialists          | per-role    | per-role           |
| `engines/debate/`                     | multi-model design *debate* (OpenAI · Grok · Gemini · DeepSeek · Kimi) → Claude judges & builds | Claude (judge) | Claude             |
| `engines/ensemble/`                   | multi-model design *vote* (same advisors, no judge) → Claude builds | plurality   | Claude             |
| `engines/rlm/`                        | Recursive Language Model-inspired decomposition                    | Claude      | Claude             |

<p align="center">
  <img src="figures/DebateArchitectureEngine.png" alt="Observability and chain-of-thought trace for the debate / ensemble architecture" width="85%" />
</p>

<p align="center"><em>Observability and chain-of-thought trace for the debate / ensemble architecture.</em></p>

Each engine is registered in `arena/engines.py::REGISTRY`, so adding
a ninth engine is a one-line addition: every cross-engine test, the
arena UI, and the contract suite pick it up automatically.

<p align="center">
  <img src="figures/EngineLOC.png" alt="Bar chart of lines of Python per generated engine, color-coded by methodology family" width="85%" />
</p>

<p align="center"><em>Lines of Python per generated engine (excludes tests, <code>__pycache__</code>, vendored deps), color-coded by methodology family. Regenerate with <code>python -m infra.scripts.plot_loc --csv</code>.</em></p>

### Methodologies (engine builders)

The build orchestrators that produce each non-trivial engine artifact:

- `methodologies/langgraph/` - LangGraph multi-agent specialists →
  `engines/langgraph/`
- `methodologies/debate/`    - multi-model debate with Claude as judge →
  `engines/debate/`
- `methodologies/ensemble/`  - multi-model voting with no judge →
  `engines/ensemble/`
- `methodologies/rlm/`       - Recursive-LM-style prompting recipe →
  `engines/rlm/`

The four `oneshot_*` and `chainofthought` engines are direct prompt
recipes; their methodology is captured in their own READMEs rather
than in a separate orchestrator module.

### Interactive arena: pit them against each other, see the numbers

`arena/` is a local web UI (`python -m arena` → `http://127.0.0.1:8765`)
that pits any two registered engines against each other in real time
and streams every metric you'd want for the comparison:

| metric                                  | source                                  |
|-----------------------------------------|-----------------------------------------|
| game result (W/D/L) and reason          | [python-chess](https://python-chess.readthedocs.io/) + arena rules |
| per-move depth, nodes, NPS, score (cp / mate) | each engine's `info` UCI line     |
| per-move wall time                      | arena timer around `go`                 |
| cumulative engine clocks                | arena scoreboard                        |
| [chess.com](https://www.chess.com/)-style move arrows + eval bar | arena UI                |
| build cost ($), tokens, model           | `arena/engine_costs.json` (per engine)  |
| lines of code                           | computed by arena from each engine tree |

The arena is the live counterpart to the batch tournament harness in
`infra/scripts/`; both feed the same comparison reports.

For arena-specific details, see `arena/README.md`.

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
- [Stockfish](https://stockfishchess.org/)-referenced decision loops in engine variants and eval scripts
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

The eight engines span the methodology axis from minimal to maximal
orchestration:

| family                          | engines                                                     |
|---------------------------------|-------------------------------------------------------------|
| **single-prompt baselines**     | `oneshot_nocontext`, `oneshot_contextualized`               |
| **single-prompt with reasoning / tools** | `chainofthought`, `oneshot_react`, `rlm`           |
| **multi-agent orchestration**   | `langgraph`                                                 |
| **multi-model collaboration**   | `debate` (judge-mediated), `ensemble` (peer vote)           |

These are evaluated comparatively through three layers:

1. **Contract layer** - `tests/contract/` runs the same UCI-surface
   checks against every engine in `arena.engines.REGISTRY` (handshake,
   legal-move guarantee, info-line semantics, lifecycle). 9 tests
   parameterized over every registered engine on every CI run.
2. **Arena layer** - live engine-vs-engine matches with streaming
   metrics (game outcome, depth, nodes, NPS, score, wall time, build
   cost).
3. **Tournament layer** - batch round-robin via
   `infra/scripts/run_local_champion.py` and the Dockerized GitHub
   Actions matrix; aggregate reports land in `reports/comparisons/`.

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
- Optional but recommended: [Stockfish](https://stockfishchess.org/) on PATH (or set `STOCKFISH_PATH`)

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

### Run interactive arena

```bash
.venv/bin/python -m arena
```

Then open: `http://127.0.0.1:8765`

### Arena environment variables

- `POINTCHESS_PYTHON` optionally overrides the Python executable used to launch registered engines.

---

## Testing

### Engine/package tests

```bash
.venv/bin/python -m pytest engines/oneshot_nocontext/tests -v
.venv/bin/python -m pytest engines/oneshot_contextualized/tests -v
```

### Arena tests

```bash
.venv/bin/python -m pytest arena/tests -q
```

### Candidate/champion workflow

See scripts:

- `infra/scripts/run_candidate_tests.py`
- `infra/scripts/run_champion_stage.py`
- `infra/scripts/aggregate_champion_artifacts.py`
- `infra/scripts/score_candidates.py`
- `infra/scripts/write_comparison_report.py`

Run the current engines in parallel:

```bash
.venv/bin/python infra/scripts/run_local_champion.py \
  --task CURRENT_ENGINES \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --jobs 7 \
  --skip-create-worktrees
```

Run the Dockerized Champion POC locally:

```bash
docker build -f infra/docker/Dockerfile.champion -t pointchess/champion:local .
docker run --rm -v "$PWD:/repo" -w /repo pointchess/champion:local \
  python infra/scripts/run_local_champion.py \
    --task CURRENT_ENGINES \
    --config infra/configs/champion/CURRENT_ENGINES.yaml \
    --jobs 7 \
    --skip-create-worktrees
```

Run a stronger tier or an orchestration audit:

```bash
.venv/bin/python infra/scripts/run_local_champion.py \
  --task CURRENT_ENGINES \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --tier contract \
  --jobs 7 \
  --skip-create-worktrees

.venv/bin/python infra/scripts/run_local_champion.py \
  --task CURRENT_ENGINES \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --candidate CURRENT_rlm \
  --milestone-task C0_ENGINE_INTERFACE \
  --run-orchestration \
  --orchestration-mode audit \
  --skip-create-worktrees
```

Run the full C0-C8 classical ladder in Docker:

```bash
docker run --rm -v "$PWD:/repo" -w /repo pointchess/champion:local \
  python infra/scripts/run_classical_ladder.py --task all --jobs 3
```

Run one configured C* candidate comparison in Docker, using host worktrees:

```bash
mkdir -p ../worktrees
docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../worktrees:/worktrees" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_champion_stage.py \
    --task C3_STATIC_EVALUATION \
    --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example \
    --run-orchestration \
    --orchestration-mode audit \
    --run-tests \
    --score \
    --write-report \
    --jobs 4 \
    --allow-missing-worktrees \
    --continue-on-failure
```

Run the full candidate ladder across all C0-C8 configs:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../worktrees:/worktrees" \
  -w /repo \
  pointchess/champion:local \
  python infra/scripts/run_champion_ladder.py \
    --tasks all \
    --run-orchestration \
    --orchestration-mode audit \
    --allow-missing-worktrees \
    --continue-on-failure \
    --jobs 4
```

This produces `reports/comparisons/CHAMPION_LADDER/summary.md`. A task is only
considered promotable when at least one real candidate worktree passes; audit
traces alone do not count as implementation wins. By default, C* candidate
evaluation also rejects non-local worktrees that have no diff from the frozen
baseline, so a branch cannot win by merely inheriting already-passing code.

GitHub Actions workflow:

- `Champion Current Engines` runs each current engine as a separate Dockerized matrix job.
- `Champion Current Engines` can also run `smoke`, `contract`, `milestone`, `perft`, or `tournament` tiers.
- `Champion Classical Ladder` runs C0-C8 milestone gates as Docker matrix jobs.
- `Champion Milestone Candidates` runs a dynamic candidate matrix from any `infra/configs/champion/C*_*.yaml.example` file.
- `Champion Candidate Ladder` runs the whole C0-C8 candidate ladder sequentially from configured experiment branches.
- Aggregate jobs write `comparison.md`, `scores.md`, `scores.json`, `metrics.csv`, `metrics.jsonl`, and `metrics.json` for graphing.

---

## Repository map (current)

```text
PointChessEngine/
├── engines/                              # 8 UCI engines (the artifacts being compared)
│   ├── oneshot_nocontext/
│   ├── oneshot_contextualized/
│   ├── oneshot_react/
│   ├── chainofthought/
│   ├── langgraph/                        # built by methodologies/langgraph
│   ├── debate/                           # built by methodologies/debate
│   ├── ensemble/                         # built by methodologies/ensemble
│   └── rlm/                              # recursive-LM-inspired decomposition (methodologies/rlm)
├── methodologies/                        # the build orchestrators
│   ├── langgraph/                        # multi-agent specialists
│   ├── debate/                           # multi-model debate, Claude judges
│   ├── ensemble/                         # multi-model vote, no judge
│   └── rlm/                              # recursive-LM prompting recipe
├── arena/                                # web UI: engine-vs-engine + live metrics
│   ├── engines.py                        # REGISTRY of all 8 launchable engines
│   └── tests/                            # 28 unit tests w/ in-tree fake UCI engine
├── infra/
│   ├── agents/                           # methodology + parallelization protocols
│   ├── orchestrators/                    # orchestration schemas, debate runtime notes
│   ├── scripts/                          # candidate / champion runners + reporters
│   ├── tasks/                            # work plans, protocol docs
│   └── configs/                          # tournament + champion YAMLs
├── reports/                              # run / eval / comparison artifacts
├── tests/
│   ├── classical/                        # 59 milestone tests (currently grades oneshot_nocontext)
│   └── contract/                         # 63 UCI-contract tests parameterized over REGISTRY
└── .github/workflows/tests.yml           # CI: every test tree on every push + PR
```

---

## Known limitations

- LLM-driven approaches are prompt-sensitive and can have wide Elo confidence intervals
- Cost/latency variance is substantial for agentic and debate-style approaches
- Cross-approach transitivity assumptions in Elo are imperfect
- Some orchestration/eval components are still evolving and documented as protocol-first

---

## Related work and inspiration

The methodologies in this repo were shaped by recent work on recursive prompting, multi-model debate, and chess as a substrate for evaluating LLM-built systems. Brief notes on how each reference shaped a specific piece of the project:

### Recursive language models
- [`alexzhang13/rlm`](https://github.com/alexzhang13/rlm) and the [Recursive Language Models paper](https://arxiv.org/abs/2512.24601) — the recursive-LM pattern, where a model calls smaller / specialized LMs to compute its next answer. Directly inspired `engines/rlm/` and `methodologies/rlm/`.

### Multi-model debate and ensembling
- [Adaptive heterogeneous multi-agent debate for enhanced educational and factual reasoning in LLMs](https://link.springer.com/article/10.1007/s44443-025-00353-3) — empirical evidence that mixing model families in a debate loop improves reasoning quality. Shaped the multi-provider advisor pool in `methodologies/debate/`.
- MIT AI Safety Fundamentals weeks [5](https://web.mit.edu/aialignment/www/aisf/week5/) and [6](https://web.mit.edu/aialignment/www/aisf/week6/) — frame the judge-vs-vote distinction we A/B-tested across `methodologies/debate/` (single judge) and `methodologies/ensemble/` (peer plurality vote).

### LLMs and chess as an evaluation domain
- [Chess as a measurement substrate for LLM-driven systems (arXiv:2502.13295)](https://arxiv.org/abs/2502.13295) — motivates using chess to *grade* LLM-built systems, not only LLMs-as-players. This is the framing our scorecard inherits.

### Chess-engine references and tooling
- [Stockfish](https://stockfishchess.org/) — the canonical reference engine; every UCI engine in this repo is conceptually compared against it.
- [python-chess](https://python-chess.readthedocs.io/) — used by `arena/` and `tests/contract/` for legality, FEN/SAN/PGN, and game-end detection.
- [FastChess](https://github.com/Disservin/fastchess) — a faster alternative to cutechess for batch tournaments; candidate replacement for the current candidate/champion runners in `infra/scripts/`.
- ["Building my own chess engine" (healeycodes)](https://healeycodes.com/building-my-own-chess-engine) — a single-author engine walkthrough that helped scope what "minimal complete" means for the master brief every methodology builds against.
- [Universal Chess Interface on the Chess Programming Wiki](https://www.chessprogramming.org/UCI) and the [UCI overview on Wikipedia](https://en.wikipedia.org/wiki/Universal_Chess_Interface) — the protocol every engine in this repo speaks.

### Evaluation and observability tooling (forward-looking)
These aren't wired in yet but inform where the eval / monitoring layer is heading.

- ["Four places where you can put LLM monitoring"](https://www.alignmentforum.org/posts/AmcEyFErJc9TQ5ySF/four-places-where-you-can-put-llm-monitoring) — taxonomy that informs where evals should attach across the build, design-debate, and play-time loops.
- [Promptfoo](https://www.promptfoo.dev/) — candidate framework for prompt-level test cases on each methodology's design-phase prompts.
- [Weights & Biases Weave](https://wandb.ai/site/weave/) — candidate framework for per-run agent observability across `methodologies/debate/`, `methodologies/ensemble/`, and `methodologies/langgraph/`.

---

## Future work

- Broader model grid runs with tighter confidence bounds
- Additional framework-isolation experiments (same model/prompt, different runtime)
- Expanded robustness suite (metamorphic + adversarial probes)
- More complete cost-Elo Pareto reporting across all approach families

---

## Related docs in this repo

- `arena/README.md` - interactive arena usage
- `infra/agents/` - methodology and operational protocols
- `infra/orchestrators/` - orchestration schemas and runtime docs
- `infra/tasks/START_HERE.md` - guided task entrypoint

If you want the README to mirror your whitepaper structure even more closely, the next step is adding dedicated top-level docs (`WHITEPAPER.md`, `RELATED_WORK.md`, `decisions/log.md`, and `/docs` figures) and linking them from here.


