# AI-Assisted Chess Engine Benchmark Tasks

This directory is the agent-executable benchmark plan for the chess engine project.

The goal is not just to build a chess engine. The goal is to run a rigorous study of AI-assisted software engineering workflows: how different agents and teams design, test, review, benchmark, and improve a complex software artifact.

Agents should not free-form build features. Each agent must select a task file, read its dependencies, implement only that task, add tests, run the required evals, self-review the result, write a task report, and commit on a task-specific branch.

For multi-agent or long-running execution, use `tasks/ORCHESTRATION.md`. It defines the task state machine, run artifacts, observability fields, and final showcase gate.

Core workflow:

1. Pick one task from `tasks/classical`, `tasks/neural`, or `tasks/evals`.
2. Read `tasks/START_HERE.md`.
3. Read `tasks/AGENT_PROTOCOL.md`.
4. Read `tasks/ORCHESTRATION.md`.
5. Read `tasks/UNIT_TESTS.md`.
6. Read the assigned task file and dependency task files.
7. Inspect the repo before editing.
8. Complete the task's `Work Packages` in order.
9. Run each work package's required pre-commit unit tests.
10. Commit after each work package using the work package ID.
11. Implement only the assigned task.
12. Add or update tests and evals required by the task.
13. Run the relevant checks.
14. Self-review with `tasks/evals/E4_CODE_REVIEW_RUBRIC.md`.
15. Write `reports/tasks/<TASK_ID>.md`.
16. Update any run-level observability artifacts if this is part of an orchestrated run.
17. Open a recognizable GitHub PR using the required task PR template.

The priority order is defined in `tasks/PRIORITY_PLAN.md`. Evaluation scaffolding comes before engine features so that all generated engines can be compared under the same rules. `C0_ENGINE_INTERFACE` is UCI-first: it defines the external benchmark contract and fake UCI harness behavior, not a mandatory in-process engine API.

Do not implement engine code from this directory. These files define the benchmark task suite, acceptance criteria, review protocol, and evaluation methodology.
