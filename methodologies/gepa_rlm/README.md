# GEPA-RLM Methodology

GEPA-RLM is a methodology track for the PointChess benchmark. It is not a chess
engine and does not implement chess logic.

GEPA-RLM combines:

1. RLM-style recursive decomposition
   - a root agent decomposes the assigned task
   - focused subcalls inspect interfaces, tests, edge cases, implementation risks, and review risks
   - the root synthesizes a candidate plan or patch proposal

2. GEPA-style reflective prompt evolution
   - collect traces, test failures, review feedback, interface errors, and scores
   - diagnose what failed
   - mutate root/subagent prompts based on evidence
   - rerun improved recursive candidates
   - select the strongest evolved candidate by Champion-style scoring

The research question is:

Does failure-driven prompt evolution improve the strongest base recursive orchestration method?

## Relationship To RLM

- `methodologies/rlm` records vanilla RLM/RLM-lite orchestration.
- `methodologies/gepa_rlm` records evolved RLM orchestration with reflective prompt mutation.
- `engines/rlm` is an engine artifact; GEPA-RLM does not create an engine artifact by itself.

## Dry Run

```bash
python -m methodologies.gepa_rlm \
  --task C3_STATIC_EVALUATION \
  --candidate-id C3_gepa_rlm_claude_gpt_gemini \
  --mode audit
```

This writes:

```text
reports/gepa_rlm/<task>/<candidate>/trace.jsonl
reports/gepa_rlm/<task>/<candidate>/result.json
reports/gepa_rlm/<task>/<candidate>/report.md
reports/gepa_rlm/<task>/<candidate>/evolved_prompts/
reports/gepa_rlm/<task>/<candidate>/selection.md
```

Audit mode is deterministic and does not call model APIs. It is orchestration
evidence, not a live generated implementation.

## Live Mode

Live mode mirrors `methodologies/rlm` and uses the optional `rlms` package:

```bash
python -m methodologies.gepa_rlm \
  --task C3_STATIC_EVALUATION \
  --candidate-id C3_gepa_rlm_live \
  --mode live \
  --backend openai \
  --model gpt-5-nano
```

Live mode currently produces a GEPA-RLM planning completion plus traces and
prompt-mutation artifacts. It does not apply patches or promote candidates.

A full GEPA-RLM implementation loop should eventually:

1. run seed recursive decomposition
2. generate or coordinate candidate implementation branches
3. run Champion tests and review
4. reflect on failures
5. mutate prompts
6. rerun evolved candidates
7. select the best candidate without promoting automatically

Promotion remains owned by Champion mode and human review.
