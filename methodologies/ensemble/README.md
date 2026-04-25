# methodologies/ensemble

A **multi-model voting ensemble** that designs a chess engine. It is
the judge-free sibling of `methodologies/debate/`: every advisor
proposes, and every advisor votes. Topic winners are decided by
plurality, with no single model overriding the group. The winning
proposals are stitched into a binding design contract that the build
phase implements into `engines/ensemble/`.

This methodology is interesting because it tests whether **collective
voting** across heterogeneous model families can produce a coherent
design — without delegating the final call to one (potentially
biased) judge model.

---

## How it runs

```
[1] Ensemble vote
    For each design topic (board representation, move generation,
    search extensions, evaluation, ELO scaling, UCI/UI):
      - PROPOSAL phase: every voter writes a stance (parallel)
      - VOTE phase: every voter sees ALL proposals and casts ONE
        ballot for the strongest one (parallel; self-votes allowed)
      - TALLY: plurality decides; alphabetical tiebreak on tied votes;
        no judge

[2] Contract
    Winning proposals are glued into engines/ensemble/docs/
    design_contract.md. The full ballot record is preserved in
    ballot_transcript.md.

[3] Build
    A single builder (Claude by default) is invoked in a sandboxed
    Anthropic tool-use loop with the contract as input. It writes the
    engine into engines/ensemble/ and iterates run_pytest until green
    or the iteration cap is hit.
```

The output is a complete `engines/ensemble/` package — same shape as
the other engines in this repo, so it drops straight into `arena/`.

---

## Contrast with `methodologies/debate/`

| step           | debate                       | ensemble                          |
|----------------|------------------------------|-----------------------------------|
| proposal       | each advisor writes a stance | each voter writes a stance        |
| second pass    | each advisor critiques rivals| each voter casts ONE ballot       |
| who decides    | a single lead model (Claude) | majority vote across all voters   |
| build          | Claude implements per verdict| Claude implements per voted contract |
| Claude's role  | judge **and** builder        | peer voter **and** builder        |

The build phase is identical — what changes is who decides the design.

---

## Install

```bash
pip install -r methodologies/ensemble/requirements.txt
```

Same deps as `methodologies/debate/` (`anthropic`, `openai`,
`python-dotenv`, `pytest`).

---

## Auth

Same env vars as the debate methodology; any subset of voter keys
works. **Two voters minimum** for a vote to be meaningful.

| voter        | env var                | default model              |
|--------------|------------------------|----------------------------|
| OpenAI       | `OPENAI_API_KEY`       | `gpt-4.1`                  |
| Grok (xAI)   | `XAI_API_KEY`          | `grok-4`                   |
| Gemini       | `GEMINI_API_KEY`       | `gemini-2.5-pro`           |
| DeepSeek     | `DEEPSEEK_API_KEY`     | `deepseek-chat`            |
| Kimi         | `MOONSHOT_API_KEY`     | `kimi-k2-0905-preview`     |
| Claude       | `ANTHROPIC_API_KEY` (or `ANTHROPIC_KEY`) | `claude-opus-4-7` |

Claude is a peer voter here (no special judging role) AND the default
builder. Override the builder with `--builder-provider` /
`--builder-model`.

---

## Run

```bash
# End-to-end with every voter whose key is present.
python -m methodologies.ensemble

# Just produce the design contract; skip the build.
python -m methodologies.ensemble --skip-build

# Restrict the voter lineup explicitly.
python -m methodologies.ensemble \
    --voter openai=gpt-4.1 \
    --voter xai=grok-4 \
    --voter gemini=gemini-2.5-pro \
    --voter anthropic=claude-opus-4-7

# Larger build budget (default 60 tool-use iterations).
python -m methodologies.ensemble --max-build-iterations 120

# Inspect provider availability without spending tokens.
python -m methodologies.ensemble --list-providers
```

Output dir defaults to `./engines/ensemble`. The contract is at
`docs/design_contract.md` and the full ballot at
`docs/ballot_transcript.md`.

---

## Files

```
methodologies/ensemble/
├── __init__.py
├── __main__.py        CLI entry
├── README.md          (this file)
├── requirements.txt
├── providers.py       PROVIDERS registry + chat() across all 6 providers
├── prompts.py         master brief, topics, proposal/vote prompt builders,
                       parse_vote(), build prompt
├── ballot.py          proposal -> vote -> tally orchestration
├── tools.py           Anthropic tool-use schemas + sandboxed dispatch
├── builder.py         single-builder tool-use loop
├── runner.py          end-to-end (ballot + contract + build)
└── tests/
    ├── test_ballot.py    parse_vote + ballot orchestration with chat() patched out
    └── test_tools.py     sandbox semantics
```

---

## What this methodology measures vs. the others

| methodology   | input shape           | who decides         | who writes code     |
|---------------|-----------------------|---------------------|---------------------|
| `oneshot_*`   | one prompt            | one model           | one model           |
| `chainofthought` | many CoT steps     | one model           | one model           |
| `langgraph`   | multi-agent specialists | per-role agents   | role specialists    |
| `debate`      | multi-MODEL debate    | one lead judge      | the lead (Claude)   |
| `ensemble`    | multi-MODEL vote      | **plurality**       | a single builder    |

`ensemble` and `debate` are the natural A/B pair: same advisor pool,
same topics, same single-builder phase — the only thing that changes
is the decision rule (judge vs. vote). Comparing the resulting
engines in `arena/` is the chess-engine equivalent of an "is the
ensemble better than the best individual?" ablation.
