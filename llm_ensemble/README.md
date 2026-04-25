# PointChess Ensemble

A chess engine where **five large-language models vote on every move**.

Alpha-beta search generates the candidate moves; each LLM votes for the best one; votes are aggregated to pick the final move. The result is displayed in a browser UI with a live voting panel.

---

## LLMs in the panel

| Provider    | Model         | API package       |
| ----------- | ------------- | ----------------- |
| OpenAI      | gpt-4o        | `openai`          |
| Anthropic   | claude-opus-4 | `anthropic`       |
| Google      | gemini-1.5-pro| `google-generativeai` |
| xAI         | grok-2-1212   | `openai` (compat) |
| DeepSeek    | deepseek-chat | `openai` (compat) |

---

## Quick start

```bash
# Install dependencies
pip install -r llm_ensemble/requirements.txt

# Set your API keys (or edit llm_ensemble/config.py)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="..."
export GROK_API_KEY="xai-..."
export DEEPSEEK_API_KEY="..."

# Start the web UI
python -m llm_ensemble
# → Open http://127.0.0.1:8001

# Run as a UCI engine
python -m llm_ensemble --uci

# Run tests (no API keys required)
python -m pytest llm_ensemble/tests/ -v
# or
python -m unittest discover -s llm_ensemble/tests -v
```

---

## Architecture

```
llm_ensemble/
├── config.py               API keys, model names, default settings
├── __main__.py             Entry point (--uci flag or web UI)
├── llms/
│   ├── base.py             LLMClient ABC, VoteResult, build_prompt, parse_move
│   ├── openai_client.py    GPT-4o
│   ├── anthropic_client.py Claude
│   ├── gemini_client.py    Gemini 1.5 Pro
│   ├── grok_client.py      Grok-2 (OpenAI-compatible)
│   └── deepseek_client.py  DeepSeek Chat (OpenAI-compatible)
├── ensemble/
│   ├── voter.py            Parallel LLM voting (ThreadPoolExecutor)
│   ├── aggregator.py       Vote aggregation (plurality/score-weighted/consensus)
│   └── engine.py           EnsembleEngine: search + voting pipeline
├── uci/
│   └── protocol.py         UCI command handler (runs engine in worker thread)
├── ui/
│   ├── server.py           stdlib HTTP server + JSON API
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js          Single-page chess UI with LLM voting panel
└── tests/
    ├── test_voting.py      Voting layer (mock clients, no API keys)
    ├── test_aggregation.py Aggregation strategies
    └── test_uci.py         UCI protocol + ELO settings
```

**Chess rules and alpha-beta search** are imported from `oneshot_react_engine` (same repo). No chess logic is duplicated.

---

## Voting pipeline

For each engine move:

1. **Alpha-beta search** (depth + time from ELO settings) ranks all legal moves.
2. The **top-K candidates** (K determined by ELO) are formatted into a prompt.
3. All **five LLMs are queried in parallel** (ThreadPoolExecutor, configurable timeout).
4. Responses are parsed for a valid UCI move from the candidate list.
5. Votes are **aggregated** by the selected method.
6. The winning move is played. If all LLMs fail, the alpha-beta best is used.

---

## Voting methods

| Method          | Description |
| --------------- | ----------- |
| `plurality`     | Most votes wins. Ties broken by alpha-beta score rank. |
| `score_weighted`| Each vote is weighted by `1 + ab_score_fraction`. Combines engine knowledge with LLM preference. |
| `consensus`     | Requires ≥ 3/5 LLMs to agree. Falls back to plurality if no consensus. |

Configure via the UI dropdown, `setoption name VotingMethod value <method>`, or `--method` CLI flag.

---

## ELO slider (400–2400)

Lower ELO = shallower search, more candidates shown (wider, noisier choice pool), higher blunder probability.

| ELO bracket | Depth | Time   | Candidates | Eval noise | Blunder % |
| ----------- | ----- | ------ | ---------- | ---------- | --------- |
| 400–800     | 1     | 0.5 s  | 8          | ±250 cp    | 25%       |
| 800–1200    | 2     | 1.0 s  | 7          | ±120 cp    | 15%       |
| 1200–1600   | 3     | 2.0 s  | 6          | ±60 cp     | 8%        |
| 1600–2000   | 4     | 4.0 s  | 5          | ±25 cp     | 3%        |
| 2000–2400   | 6     | 8.0 s  | 3          | 0 cp       | 0.5%      |

Values are linearly interpolated between brackets. Tunable in `ensemble/engine.py`.

---

## UCI support

```
uci        → id name PointChess Ensemble
              id author PointChess Ensemble Team
              option name UCI_Elo type spin default 1500 min 400 max 2400
              option name Skill Level type spin default 10 min 0 max 20
              option name VotingMethod type combo default plurality ...
              option name Candidates type spin default 5 min 1 max 15
              option name VoteTimeout type spin default 45 min 5 max 120
              uciok
isready    → readyok
ucinewgame → resets board and engine state
position   → startpos [moves ...] | fen <fen> [moves ...]
go         → movetime / depth / wtime+btime / infinite
              emits: info depth ... score cp ... pv ...
                     info string vote <move> <count>
              emits: bestmove <uci>
stop       → interrupts search thread
setoption  → name UCI_Elo | Skill Level | VotingMethod | Candidates | VoteTimeout
quit       → exits
```

---

## Web UI features

- Click-to-move with legal move dots and capture rings
- Pawn promotion modal
- Last-move highlight, in-check highlight
- ELO slider (live, no restart needed)
- Voting method selector
- **LLM Voting Panel**: shows each LLM's vote, latency, candidate bars with vote tallies
- Fallback and blunder notices
- Alpha-beta search stats (depth, nodes, score, time)
- Move list with human/engine color coding
- New game, undo, resign

---

## Context usage summary

| Component       | Source |
| --------------- | ------ |
| Chess rules & board (`Board`, `Move`, `Square`, etc.) | Imported from `oneshot_react_engine/core/` (same repo) — built from scratch in that module |
| Alpha-beta search with TT, quiescence, iterative deepening | Imported from `oneshot_react_engine/engine/search.py` |
| ELO strength settings | Adapted from `oneshot_react_engine/engine/strength.py`; extended for candidate-count and voting params |
| LLM clients | Built from scratch; use official SDKs |
| Voting pipeline | Built from scratch |
| UCI protocol | Adapted from `oneshot_react_engine/uci/protocol.py`; extended for voting options |
| Web UI | Adapted from `oneshot_react_engine/ui/`; extended with LLM voting panel |

---

## Known limitations

- **Latency**: each engine move waits for all LLM API calls (up to `VoteTimeout` seconds). At low ELO this is noticeable. Set `VoteTimeout` to a smaller value if speed matters more than completeness.
- **Cost**: five LLM calls per move can be expensive. GPT-4o and Claude are the most costly per token.
- **LLM chess accuracy**: LLMs sometimes produce invalid or non-candidate moves (parsed as failures). The fallback to alpha-beta best ensures the engine never stalls.
- **No pondering**: the engine only thinks on its own turn.
- **Single-game web server**: not multi-user.
- **Elo not calibrated**: the ELO slider is a heuristic mapping, not a rigorously calibrated rating. Treat the numbers as relative guidance.
