# methodologies/debate

A **multi-model design council** that builds a chess engine through
debate. A handful of advisor models from different providers
(OpenAI, Grok, Gemini, DeepSeek, Kimi) propose and critique design
choices for a fixed set of topics; Claude (the lead architect) reads
the debate, issues a binding verdict per topic, then writes the engine
into `engines/debate/` using sandboxed tool-use.

The methodology is interesting because it tests whether smaller /
cheaper models from different families can produce arguments
persuasive enough to shape a stronger model's design choices.

---

## How it runs

```
[1] Council
    For each design topic (board representation, move generation,
    search extensions, evaluation, ELO scaling, UCI/UI):
      - PROPOSAL phase: every advisor writes a stance (parallel)
      - CRITIQUE phase: each advisor sees the others' proposals and
        writes a rebuttal trying to convince the lead (parallel)
      - VERDICT phase: the lead reads the whole debate and issues a
        binding decision + implementation directive

[2] Contract
    All verdicts are glued into engines/debate/docs/design_contract.md.
    The full transcript is preserved alongside it.

[3] Build
    The lead architect (Claude) is invoked in a tool-use loop with the
    contract as input and a sandboxed write_file / read_file / list_files
    / delete_file / run_pytest toolkit. It writes the engine, runs tests,
    and iterates until pytest is green or the iteration cap is hit.
```

The output is a complete `engines/debate/` package — same shape as the
other engines in this repo, so it drops straight into `arena/` and
`tests/classical/`.

---

## Install

```bash
pip install -r methodologies/debate/requirements.txt
```

Requires only `anthropic`, `openai`, `python-dotenv`, `pytest`. All
five non-Anthropic advisors hit OpenAI-compatible HTTP endpoints, so
the same `openai` SDK serves them all with custom base URLs.

---

## Auth

Set the env vars for whichever advisors you want to participate. Any
that aren't present are simply skipped.

| advisor      | env var              | default model              |
|--------------|----------------------|----------------------------|
| OpenAI       | `OPENAI_API_KEY`     | `gpt-4.1`                  |
| Grok (xAI)   | `XAI_API_KEY`        | `grok-4`                   |
| Gemini       | `GEMINI_API_KEY`     | `gemini-2.5-pro`           |
| DeepSeek     | `DEEPSEEK_API_KEY`   | `deepseek-chat`            |
| Kimi (Moonshot) | `MOONSHOT_API_KEY`| `kimi-k2-0905-preview`     |
| **lead** Claude | `ANTHROPIC_API_KEY` (or `ANTHROPIC_KEY`) | `claude-opus-4-7` |

Defaults can be overridden per-advisor on the command line.

---

## Run

```bash
# End-to-end with everyone whose key is present.
python -m methodologies.debate

# Just produce the design contract; skip the build phase.
python -m methodologies.debate --skip-build

# Override the lead model.
python -m methodologies.debate --lead-model claude-sonnet-4-6

# Restrict the advisor lineup explicitly.
python -m methodologies.debate \
    --advisor openai=gpt-4.1 \
    --advisor xai=grok-4 \
    --advisor gemini=gemini-2.5-pro

# Bigger build budget (default 60 tool-use iterations).
python -m methodologies.debate --max-build-iterations 120

# Inspect provider availability without spending tokens.
python -m methodologies.debate --list-providers
```

Output dir defaults to `./engines/debate`. The contract is at
`docs/design_contract.md` and the full debate at
`docs/council_transcript.md`.

---

## Files

```
methodologies/debate/
├── __init__.py
├── __main__.py        CLI entry
├── README.md          (this file)
├── requirements.txt
├── providers.py       PROVIDERS registry + chat() across all 6 providers
├── prompts.py         master brief, topics, per-phase prompt builders, build prompt
├── council.py         proposal -> critique -> verdict orchestration
├── tools.py           Anthropic tool-use schemas + sandboxed dispatch
├── builder.py         lead-architect tool-use loop
├── runner.py          end-to-end (council + contract + build)
└── tests/
    ├── test_council.py   council orchestration with chat() patched out
    └── test_tools.py     sandbox semantics
```

---

## What this methodology measures vs. the others

| methodology   | input shape           | who decides | who writes code      |
|---------------|-----------------------|-------------|----------------------|
| `oneshot_*`   | one prompt            | one model   | one model            |
| `chainofthought` | many CoT steps     | one model   | one model            |
| `langgraph`   | multi-agent specialists | per-role  | role specialists     |
| `debate`      | multi-MODEL debate    | one lead    | the lead (after debate) |

The debate methodology is the only one in the repo that introduces
**heterogeneity across model families** as a design-time signal. The
final code is still single-author (Claude), so any quality difference
vs. `langgraph` or `oneshot_react` is attributable to the design
contract, not to the implementation pass.
