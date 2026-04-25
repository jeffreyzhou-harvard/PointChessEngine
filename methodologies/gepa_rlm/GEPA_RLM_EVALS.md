# GEPA-RLM Evals

GEPA-RLM uses the same base Champion score as other methodology candidates.

Base score:

- correctness tests: 35
- code review quality: 20
- interface compatibility: 15
- performance / engine impact: 15
- cost/time efficiency: 10
- documentation/report quality: 5

GEPA-specific metrics:

- improvement over seed RLM
- number of reflection rounds
- number of prompt mutations
- number of bugs caught before implementation
- number of critique issues resolved
- cost per score-point improvement
- latency per score-point improvement
- whether evolved prompt generalized to another task
- whether mutation caused overfitting or interface breakage

Comparison table:

| Candidate | Round | Champion Score | Tests | Review | Interface | Cost | Latency | Delta vs RLM seed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
