# Multi-Model Policy

Champion mode treats orchestration pattern, model provider, and execution environment as separate experimental variables.

## Separation of Variables

- Orchestration pattern is separate from model provider.
- Execution environment is separate from both.
- Model diversity is an experimental variable.

Examples:

- A debate ensemble can use Claude + GPT + Gemini.
- A homogeneous debate can use one model with different role prompts.
- A Codex agent can run inside a local repo execution environment.
- A Replit agent may produce a branch externally.
- A custom LangChain runner may call multiple model providers.

## Debate Definitions

Homogeneous debate:

- Same base model.
- Different role prompts.
- Example: `C3_debate_homogeneous_claude_roles`.

Heterogeneous debate:

- Different model families.
- Example: `C3_debate_heterogeneous_claude_gpt_gemini`.

## Reporting Requirements

Every candidate report must record:

- orchestration pattern
- model assignments
- execution environment
- number of prompts or major agent steps
- cost estimate
- latency
- bugs caught before implementation, when using debate systems

No model output is trusted without tests and code review.

## Examples

- `C3_react_claude`
- `C3_debate_homogeneous_claude_roles`
- `C3_debate_heterogeneous_claude_gpt_gemini`
- `C4_codex_agent`
- `C4_replit_agent`
- `C5_custom_langchain_parallel`
