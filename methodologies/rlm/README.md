# RLM Methodology

This folder records how the RLM candidate should be generated and audited.

Reference implementation:

https://github.com/alexzhang13/rlm

RLMs replace a single completion call with a recursive language-model loop that
can inspect files, execute small REPL snippets, decompose subtasks, and call
child model invocations. For PointChess, the intended RLM workflow is:

1. Read the assigned task and current engine registry.
2. Recursively decompose the target into interface, rules, evaluation, search,
   UCI, tests, and Champion observability.
3. Let child calls critique legality, time control behavior, and integration.
4. Build one bounded patch.
5. Run tests and Champion smoke.
6. Write an implementation report that records recursion depth, child prompts,
   model provider, latency, cost, and bugs caught before implementation.

Important distinction:

- `engines/rlm` is the generated engine artifact.
- `methodologies.rlm.runner` is the orchestration runner/audit trail.

The checked-in `engines/rlm` runtime does not import `rlms` or call model APIs.
That keeps normal engine execution reproducible without secrets. To run the
actual RLM orchestration loop, use live mode:

```bash
python -m methodologies.rlm.runner \
  --task C0_ENGINE_INTERFACE \
  --candidate-id C0_rlm_openai \
  --mode live
```

Live mode requires the optional `rlms` package and provider credentials. Audit
mode is no-secrets and writes the prompt bundle plus recursive work plan, but it
must not be claimed as a live model-generated candidate.

When the installed `rlms` package exposes `RLMLogger`, live mode also writes
trajectory logs under:

```text
reports/orchestration/<task>/<candidate>/trajectory/
```

Those JSONL traces are intended for later graphing of recursive calls, latency,
and critique/fix cycles.
