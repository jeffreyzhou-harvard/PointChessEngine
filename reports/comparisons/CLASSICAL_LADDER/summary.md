# Classical Milestone Ladder

| Task | Status | Duration | Test files |
| --- | --- | ---: | --- |
| `C0_ENGINE_INTERFACE` | pass | 1.142s | `tests/classical/test_c0_uci_contract.py` |
| `C1_BOARD_FEN_MOVE` | pass | 1.163s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py` |
| `C2_LEGAL_MOVE_GENERATION` | pass | 1.500s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py` |
| `C3_STATIC_EVALUATION` | pass | 1.472s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py, tests/classical/test_c3_static_evaluation.py` |
| `C4_ALPHA_BETA_SEARCH` | pass | 1.896s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py, tests/classical/test_c3_static_evaluation.py, tests/classical/test_c4_alpha_beta_search.py` |
| `C5_TACTICAL_HARDENING` | pass | 1.967s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py, tests/classical/test_c3_static_evaluation.py, tests/classical/test_c4_alpha_beta_search.py, tests/classical/test_c5_tactical_hardening.py` |
| `C6_TIME_TT_ITERATIVE` | pass | 2.444s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py, tests/classical/test_c3_static_evaluation.py, tests/classical/test_c4_alpha_beta_search.py, tests/classical/test_c5_tactical_hardening.py, tests/classical/test_c6_time_tt_iterative.py` |
| `C7_UCI_COMPATIBILITY` | pass | 2.449s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py, tests/classical/test_c3_static_evaluation.py, tests/classical/test_c4_alpha_beta_search.py, tests/classical/test_c5_tactical_hardening.py, tests/classical/test_c6_time_tt_iterative.py, tests/classical/test_c7_uci_compatibility.py` |
| `C8_ELO_SLIDER` | pass | 2.453s | `tests/classical/test_c0_uci_contract.py, tests/classical/test_c1_board_fen_move.py, tests/classical/test_c2_legal_move_generation.py, tests/classical/test_c3_static_evaluation.py, tests/classical/test_c4_alpha_beta_search.py, tests/classical/test_c5_tactical_hardening.py, tests/classical/test_c6_time_tt_iterative.py, tests/classical/test_c7_uci_compatibility.py, tests/classical/test_c8_elo_slider.py` |

- Passed: 9/9
- Estimated serial runtime: 16.486s
- Parallel wall time: 2.453s
- Speedup factor: 6.72x
- Graph data: `metrics.csv`, `metrics.jsonl`, `metrics.json`
- Scope: C0-C8 classical test gates
- Note: this validates the canonical checkout. Candidate selection still happens through per-task Champion configs and promotion review.
