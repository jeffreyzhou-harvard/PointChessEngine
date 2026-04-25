# Priority Plan

## Priority 0: Evaluation Scaffolding

These must happen first.

0. START_HERE and ORCHESTRATION read-through
1. C0_ENGINE_INTERFACE
2. E1_PERFT_SUITE
3. E2_UCI_COMPLIANCE
4. E3_TOURNAMENT_RUNNER
5. E4_CODE_REVIEW_RUBRIC

`C0_ENGINE_INTERFACE` is a UCI-first benchmark contract. It should define how a generated engine process is launched, driven, observed, and validated. It should not force a specific internal engine API.

## Priority 1: Classical Engine Core

These produce the first real legal chess engine.

1. C1_BOARD_FEN_MOVE
2. C2_LEGAL_MOVE_GENERATION
3. C3_STATIC_EVALUATION
4. C4_ALPHA_BETA_SEARCH

Classical core tasks are segmented internally into work packages. Orchestrators should treat each top-level task as one PR by default, but may split work packages into smaller branches if review volume becomes too large.

## Priority 2: Tournament Readiness

These make the engine usable for final judging.

1. C7_UCI_COMPATIBILITY
2. C5_TACTICAL_HARDENING
3. C6_TIME_TT_ITERATIVE
4. C8_ELO_SLIDER

`C7_UCI_COMPATIBILITY` is where the real engine is connected to the C0 UCI harness. C0 defines the contract; C7 implements production UCI behavior for the actual engine.

## Priority 3: Neural-Assisted Extensions

Only begin after C0-C4 and basic evals exist.

1. N1_DATASET_LABELING
2. N2_ENCODER_LEGAL_MASK
3. N4_NEURAL_POLICY_ORDERING
4. N5_HYBRID_ENGINE

## Priority 4: Stretch Neural/Demo Work

1. N3_NEURAL_VALUE_EVAL
2. N6_NEURAL_STRENGTH_CALIBRATION

## Final Evaluation

Final evaluation must include:

1. legality/perft report
2. UCI compliance report
3. generated-engine round robin
4. Stockfish calibration
5. code review summary
6. AI usage/cost table
7. final whitepaper/report

## Orchestrated Run Output

An orchestration run is complete only when these files or equivalent artifacts exist:

1. `reports/runs/<RUN_ID>/manifest.md`
2. `reports/runs/<RUN_ID>/task_status.md`
3. `reports/runs/<RUN_ID>/ai_usage.md`
4. `reports/runs/<RUN_ID>/eval_index.md`
5. `reports/runs/<RUN_ID>/showcase.md`

The run should end by executing the final showcase gate in `tasks/ORCHESTRATION.md`.
