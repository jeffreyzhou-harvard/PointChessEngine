# Orchestrators

This folder documents orchestration patterns for generating candidate implementations and candidate reports.

It does not contain chess engine logic.

Orchestrators may:

- generate candidate branches
- produce patches
- produce candidate reports
- run local tests
- coordinate subagents
- run debate or review loops

Candidate implementations are evaluated by Champion mode. Champion mode owns test execution, scoring, comparison reports, and promotion decisions.

For the MVP, run orchestrators locally by pointing each framework at a separate git worktree. See `infra/agents/LOCAL_CHAMPION_SETUP.md`.

Supported orchestration patterns include:

- `one_shot_no_context`
- `one_shot_with_context`
- `react`
- `chain_of_thought_decomposition`
- `gstack`
- `cursor_agents`
- `codex_agent`
- `replit_agent`
- `debate_ensemble`
- `debate_non_ensemble`
- `rlm`
- `custom_langchain_parallel`
- `custom_openai_agents_sdk`

Orchestration pattern is separate from model provider and execution environment.
