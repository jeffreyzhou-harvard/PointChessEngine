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
- `claude_cli_agent`
- `codex_agent` as an optional comparison adapter only
- `replit_agent`
- `debate_ensemble`
- `debate_non_ensemble`
- `rlm`
- `custom_langchain_parallel`
- `custom_openai_agents_sdk`

Orchestration pattern is separate from model provider and execution environment.

For the current benchmark, the default builder is Claude:

- use `claude_cli` locally or on a self-hosted runner with Claude Code installed
- use `anthropic` in Docker/GitHub Actions where API credentials are available
- use OpenAI/Gemini/Grok/Kimi/DeepSeek mainly as critics, advisors, or comparison arms
