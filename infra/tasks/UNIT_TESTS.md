# Unit Test Command Index

Use this file when an agent is working through classical `C*.*` work packages. Each listed command should be run before committing that work package.

All commands assume the repo root as the working directory and use the standard library test runner:

```text
python3 -m unittest <test-target> -v
```

## C0 - UCI Engine Contract

- C0.1: `python3 -m unittest tests.classical.test_c0_uci_contract.TestC0_1ProcessContract -v`
- C0.2: `python3 -m unittest tests.classical.test_c0_uci_contract.TestC0_2RegistrySchema -v`
- C0.3: `python3 -m unittest tests.classical.test_c0_uci_contract.TestC0_3TranscriptHarness -v`
- C0.4: `python3 -m unittest tests.classical.test_c0_uci_contract.TestC0_4MalformedOutputCategories -v`
- C0.5: `python3 -m unittest tests.classical.test_c0_uci_contract.TestC0_5ObservabilityEnvelope -v`
- C0.6: `python3 -m unittest tests.classical.test_c0_uci_contract.TestC0_6FakeEnginePolicy -v`

## C1 - Board, FEN, and Move Representation

- C1.1: `python3 -m unittest tests.classical.test_c1_board_fen_move.TestC1_1Representation -v`
- C1.2: `python3 -m unittest tests.classical.test_c1_board_fen_move.TestC1_2FenParsing -v`
- C1.3: `python3 -m unittest tests.classical.test_c1_board_fen_move.TestC1_3FenSerialization -v`
- C1.4: `python3 -m unittest tests.classical.test_c1_board_fen_move.TestC1_4UciMoveRepresentation -v`
- C1.5: `python3 -m unittest tests.classical.test_c1_board_fen_move.TestC1_5StateFields -v`
- C1.6: `python3 -m unittest tests.classical.test_c1_board_fen_move.TestC1_6FullC1Gate -v`

## C2 - Legal Move Generation

- C2.1: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_1AttackDetection -v`
- C2.2: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_2PseudoLegalGeneration -v`
- C2.3: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_3SpecialRules -v`
- C2.4: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_4StateRestoration -v`
- C2.5: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_5LegalFiltering -v`
- C2.6: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_6TerminalDetection -v`
- C2.7: `python3 -m unittest tests.classical.test_c2_legal_move_generation.TestC2_7PerftHooks -v`

## C3 - Static Evaluation

- C3.1: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_1ScoreConvention -v`
- C3.2: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_2MaterialAndPst -v`
- C3.3: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_3MobilityCenterControl -v`
- C3.4: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_4PawnStructure -v`
- C3.5: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_5KingSafety -v`
- C3.6: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_6WeightDeterminism -v`
- C3.7: `python3 -m unittest tests.classical.test_c3_static_evaluation.TestC3_7DiagnosticsGate -v`

## C4 - Alpha-Beta Search

- C4.1: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_1SearchApi -v`
- C4.2: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_2FixedDepthTerminalHandling -v`
- C4.3: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_3AlphaBetaDeterminism -v`
- C4.4: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_4BoardStateSafety -v`
- C4.5: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_5Diagnostics -v`
- C4.6: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_6TacticalSmoke -v`
- C4.7: `python3 -m unittest tests.classical.test_c4_alpha_beta_search.TestC4_7RandomBaselineSmoke -v`

## C5 - Tactical Hardening

- C5.1: `python3 -m unittest tests.classical.test_c5_tactical_hardening.TestC5_1BaselineTacticalSuite -v`
- C5.2: `python3 -m unittest tests.classical.test_c5_tactical_hardening.TestC5_2MoveOrdering -v`
- C5.3: `python3 -m unittest tests.classical.test_c5_tactical_hardening.TestC5_3QuiescenceBounds -v`
- C5.4: `python3 -m unittest tests.classical.test_c5_tactical_hardening.TestC5_4MateDistanceScoring -v`
- C5.5: `python3 -m unittest tests.classical.test_c5_tactical_hardening.TestC5_5OptionalHeuristics -v`
- C5.6: `python3 -m unittest tests.classical.test_c5_tactical_hardening.TestC5_6ImprovementGate -v`

## C6 - Time, TT, and Iterative Deepening

- C6.1: `python3 -m unittest tests.classical.test_c6_time_tt_iterative.TestC6_1TimeControlModel -v`
- C6.2: `python3 -m unittest tests.classical.test_c6_time_tt_iterative.TestC6_2IterativeDeepening -v`
- C6.3: `python3 -m unittest tests.classical.test_c6_time_tt_iterative.TestC6_3SearchInterruption -v`
- C6.4: `python3 -m unittest tests.classical.test_c6_time_tt_iterative.TestC6_4TranspositionTable -v`
- C6.5: `python3 -m unittest tests.classical.test_c6_time_tt_iterative.TestC6_5TimedDiagnostics -v`
- C6.6: `python3 -m unittest tests.classical.test_c6_time_tt_iterative.TestC6_6TimedComparisonGate -v`

## C7 - UCI Compatibility

- C7.1: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_1Entrypoint -v`
- C7.2: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_2CommandParser -v`
- C7.3: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_3PositionLoading -v`
- C7.4: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_4GoDepth -v`
- C7.5: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_5GoMovetimeAndStop -v`
- C7.6: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_6OutputFormat -v`
- C7.7: `python3 -m unittest tests.classical.test_c7_uci_compatibility.TestC7_7ComplianceGate -v`

## C8 - Strength Slider

- C8.1: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_1StrengthConfig -v`
- C8.2: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_2DepthTimeScaling -v`
- C8.3: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_3ControlledNoise -v`
- C8.4: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_4TopKLegalSampling -v`
- C8.5: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_5UciExposure -v`
- C8.6: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_6CalibrationSmoke -v`
- C8.7: `python3 -m unittest tests.classical.test_c8_elo_slider.TestC8_7BehaviorReportGate -v`

## Aggregate Commands

Run all classical benchmark tests:

```text
python3 -m unittest discover -s tests/classical -v
```

Run the existing engine package tests:

```text
python3 -m unittest discover -s engines/oneshot_nocontext/tests -v
```
