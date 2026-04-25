# methodologies/langgraph

A LangGraph-orchestrated **multi-agent** builder for a chess engine.
This package contains **no** chess code. Instead, it spawns specialist
Anthropic Claude agents through a `StateGraph` and lets *them* write
the engine into a sandboxed output directory.

The orchestration policy is the user's project brief verbatim
(`prompts.MASTER_BRIEF`); each specialist sees that brief plus a small
role-focused prompt enforcing a structured-JSON output contract.

## Pipeline

```text
START
  │
  ▼
context_analyst  ─▶  architect  ─▶  rules_engineer ─┐
                                                    │  Each pipeline node has
                                                    │  a *conditional* outgoing
                                                    ▼  edge: first visit goes
                                          engine_engineer    forward, a second
                                                    │      visit (after the
                                                    ▼      integrator routes
                                          strength_tuner    work back) jumps
                                                    │      straight to the
                                                    ▼      integrator instead
                                          uci_engineer       of redoing the
                                                    │      whole pipeline.
                                                    ▼
                                          ui_engineer
                                                    │
                                                    ▼
                                          qa_engineer ─────┐
                                                           │
                                                           ▼
                                                    integrator
                                                           │
        conditional: REWORK -> {rules,engine,strength,uci,ui,qa}_engineer
        else:        doc_writer
                                                           │
                                                           ▼
                                                    doc_writer
                                                           │
                                                           ▼
                                                    final_reviewer
                                                           │
                                                           ▼
                                                          END
```

The integrator's "rework" loop is bounded by
`max_revision_passes` (CLI flag `--revisions`, default `1`). Risks
flagged by *any* agent get queued as `state.errors`; the integrator
inspects them, optionally fixes small things itself, and uses keyword
heuristics in `_pick_rework_target` to pick which specialist to revisit.

## What each agent owns

| Role               | Owns (writes)                         | Reads                  |
|--------------------|----------------------------------------|------------------------|
| context_analyst    | `docs/context_assessment.md`          | external context only  |
| architect          | `README.md`, `docs/architecture.md`, `requirements.txt`, package skeleton | context_analyst output |
| rules_engineer     | `core/`, `tests/test_board.py`, `tests/test_movegen.py`, `tests/test_legal.py`, `tests/test_fen.py`, `tests/test_pgn.py`, `tests/test_draws.py` | architecture |
| engine_engineer    | `search/evaluation.py`, `search/engine.py`, `tests/test_evaluation.py`, `tests/test_search.py` | `core/`         |
| strength_tuner     | `search/elo.py`, `tests/test_elo.py`  | `search/`              |
| uci_engineer       | `uci/`, `tests/test_uci.py`           | `core/`, `search/`     |
| ui_engineer        | `ui/`, `tests/test_ui_*.py`           | `core/`, `search/`     |
| qa_engineer        | `tests/test_perft.py`, `tests/test_integration.py` | everything |
| integrator         | small targeted fixes anywhere         | everything             |
| doc_writer         | `README.md`, `docs/`                  | everything             |
| final_reviewer     | `docs/final_review.md`                | everything             |

Interfaces published in `docs/architecture.md` are *frozen* after the
architect runs — only the integrator may rename them.

## Tools every agent has

The agents talk to the project through five sandboxed tools (registered
as Anthropic tool-use):

| Tool          | Purpose                                            |
|---------------|----------------------------------------------------|
| `write_file`  | Create or overwrite a file under the sandbox      |
| `read_file`   | Read a file (truncated at 64 KiB)                 |
| `list_files`  | Recursive listing (filters `__pycache__` etc.)    |
| `delete_file` | Remove a file (refuses directories)                |
| `run_pytest`  | Run pytest in the sandbox (3-minute timeout)       |

All paths are resolved through `_resolve_inside`, which rejects `..`
traversal and absolute paths. There is no shell, network, or pip access
— the agents cannot install packages or hit external URLs.

## Layout

```text
methodologies/langgraph/
├── __init__.py            # version + public exports
├── __main__.py            # CLI: python -m methodologies.langgraph
├── state.py               # OrchestratorState / AgentLog / FileEntry TypedDicts
├── prompts.py             # MASTER_BRIEF + per-role system prompts
├── tools.py               # sandboxed file/test toolset (factory)
├── agents.py              # run_role: ReAct loop + JSON contract parser
├── graph.py               # StateGraph wiring + integrator routing
├── runner.py              # high-level run()/summarize() helpers
├── requirements.txt
├── pytest.ini
├── README.md
└── tests/
    ├── conftest.py        # FakeChatModel (no API calls)
    ├── test_tools.py
    ├── test_prompts.py
    ├── test_agents.py
    ├── test_graph.py
    └── test_runner_cli.py
```

## Setup

```bash
# from the repo root, using the existing .venv
.venv/bin/pip install -r methodologies/langgraph/requirements.txt
```

Put your Anthropic key in the repo `.env` as either:

```bash
ANTHROPIC_KEY=sk-ant-...        # short form (used by other tools in this repo)
# or
ANTHROPIC_API_KEY=sk-ant-...    # canonical form expected by the SDK
```

`runner._load_env_key` calls `dotenv.load_dotenv()` and promotes
`ANTHROPIC_KEY` → `ANTHROPIC_API_KEY` if the canonical name is unset,
so either name works.

## Run

```bash
# default: claude-sonnet-4-5, output ./engines/langgraph, 1 rework pass
python -m methodologies.langgraph

# heavier model, two rework passes, custom output
python -m methodologies.langgraph --model claude-opus-4-5 --revisions 2 --output ./out

# pass extra context for the Context Analyst to assess
python -m methodologies.langgraph \
    --context https://github.com/lichess-org/scalachess \
    --context "local notes: prefer pure-python, no Stockfish wrapper"

# verify wiring without spending tokens
python -m methodologies.langgraph --dry-run
```

The CLI streams a one-line progress summary per stage:

```text
  [context_analyst   ] stage=1. Context assessment           files=1 tests=0 risks=0
  [architect         ] stage=2. Architecture and stack       files=8 tests=0 risks=1
  [rules_engineer    ] stage=3-4. Chess rules and movegen    files=6 tests=4 risks=0
  ...
```

After the run, the engine the agents produced lives entirely under
`--output`. Try it:

```bash
cd ./engines/langgraph
python -m pytest -q                  # whatever the agents wrote
python -m <whatever_module> --uci    # if a UCI entry point was built
```

## Test the orchestrator itself

The orchestrator's tests use a `FakeChatModel` that returns the empty
JSON contract — they cover wiring, parsing, sandboxing, and CLI plumbing
without spending any tokens.

```bash
.venv/bin/python -m pytest methodologies/langgraph/tests/ -q
# 53 passed in <1s
```

The full graph end-to-end smoke test is
`tests/test_graph.py::TestSmokeRunWithFakeLLM::test_full_pipeline_runs`
— it drives all 11 nodes and asserts they execute in the correct order.

## Design choices and tradeoffs

* **LangGraph over a hand-rolled loop.** LangGraph gives us
  conditional edges, stream-mode for live progress, and a typed shared
  state with copy-on-write merges. The bounded integrator loop falls
  out naturally from `add_conditional_edges` plus a counter in state.
* **`langchain-anthropic.ChatAnthropic` instead of the raw
  `anthropic` SDK.** This lets us reuse `langgraph.prebuilt.create_react_agent`,
  which already implements the tool-use loop, message accumulation,
  and graceful tool error handling. The cost is a slightly heavier
  dependency tree. (We deliberately do *not* pull in the full
  `langchain` meta-package — only `langchain-core` and `langchain-anthropic`.)
* **Structured JSON contract per agent.** Every specialist must end
  with a fenced ```json block listing assumptions/decisions/files/tests/risks.
  The orchestrator parses *only* that JSON; free-form thinking is
  ignored. This keeps the inter-agent state machine deterministic and
  means a misbehaving model can only damage one stage's payload.
* **Recorder-based file ledger.** We trust the on-disk filesystem, not
  the agent's self-report: `tools.ToolRecorder` captures every
  successful `write_file` call and `agents.run_role` reconciles the
  agent's claimed `files_changed` against it (claims with no
  corresponding file become risks).
* **Sandbox is path-based, not OS-level.** `_resolve_inside` resolves
  symlinks and rejects anything outside `output_dir.resolve()`. This
  is a defence-in-depth check; the agents have no shell tool to begin
  with, so a path-level sandbox is sufficient for this use case.
* **Bounded rework, not free retries.** The integrator can route work
  back to upstream specialists, but only `max_revision_passes` times
  total. This is a deliberate cost control — without it, an
  argumentative model pair could loop indefinitely. If you want
  more polish, raise the budget; if you want raw speed, set it to 0.

## Known limitations

* **No Anthropic Agents SDK.** "Anthropic agents SDK" can mean either
  `claude-agent-sdk` (Claude-Code-like) or the bare `anthropic` Python
  SDK. We use the latter via `langchain-anthropic` because the user
  asked for **LangGraph** to orchestrate, and LangGraph's
  `create_react_agent` already wraps the Anthropic API with a
  tool-use loop. Swapping to `claude-agent-sdk` would require
  re-implementing the LangGraph node interface around its own loop;
  that's a meaningful refactor, not a free swap.
* **One run, one output dir.** The graph state lives in memory for a
  single invocation. We do not yet checkpoint to disk, so a crash
  mid-run loses progress (though files written under `output_dir`
  obviously persist).
* **No agent-vs-agent debate.** Specialists run sequentially and
  communicate only through the durable `OrchestratorState` (file
  ledger + agent logs). They never see each other's chat transcripts.
  This trades quality for predictability.
* **Cost is unbounded per-stage.** A single specialist can spend many
  tool-use turns inside one node. We cap recursion at 60 turns per
  invocation but do not cap total tokens. For a budget-sensitive run
  use a smaller model (`claude-haiku-4-5`) or `--revisions 0`.
* **Heuristic rework routing.** `_pick_rework_target` uses keyword
  matching on the integrator's risk strings. It is intentionally
  simple; if you need more accuracy, swap in a small classifier
  prompt or a structured-output integrator.

## Context-usage summary

* **Built from scratch.** Every line of orchestration code in this
  package; the role prompts; the sandboxed toolset; the JSON contract;
  the routing heuristics.
* **Wrapped/integrated from provided context.** The user's master
  brief is embedded verbatim in `prompts.MASTER_BRIEF`; the master
  brief drives every specialist agent.
* **Inspired by provided context.** The list of specialist roles
  (context_analyst, architect, rules_engineer, …) follows the user's
  "SUGGESTED AGENT ROLES" section; the pipeline order matches the
  "EXECUTION ORDER" section; the per-agent output contract follows the
  "Require each agent to produce" subsection of "ORCHESTRATION POLICY".
* **Adapted from provided context.** Nothing — the chess engine itself
  is built fresh by the agents into `--output`, not adapted from any
  pre-existing engine.
