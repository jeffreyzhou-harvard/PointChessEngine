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

The checked-in `engines/rlm` runtime does not import `rlms` or call model APIs.
That keeps CI, Docker, and Champion mode reproducible without secrets.
