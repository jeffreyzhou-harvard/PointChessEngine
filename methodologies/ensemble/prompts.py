"""Prompts for the ensemble methodology: master brief + topics + per-phase
prompts (proposal, vote, build).

Contrast with `methodologies/debate/prompts.py`: there is no judge
phase. After every advisor proposes, every advisor casts one ballot
per topic and the topic winner is decided by majority vote (no
single model gets to override).
"""
from __future__ import annotations

import re


# --------------------------------------------------------------------------- #
# Master brief                                                                #
# --------------------------------------------------------------------------- #

MASTER_BRIEF = """\
You are part of a multi-model design ensemble. The ensemble's job is
to design and ultimately build a complete chess engine that:

  - lets a human play against the engine
  - speaks the UCI protocol (uci, isready, ucinewgame, position, go,
    stop, quit, setoption)
  - exposes an adjustable ELO strength slider in the 400-2400 range
  - implements full legal chess rules (check, checkmate, stalemate,
    castling both sides, en passant, promotion, pinned pieces,
    threefold repetition, fifty-move rule, insufficient material)
  - performs alpha-beta search with reasonable extensions
  - includes an evaluation that combines material, piece-square tables,
    mobility, king safety, and pawn structure
  - ships with tests and a README
  - runs as pure Python with the python standard library only (no
    Stockfish, no python-chess, no third-party engine code)

Unlike a debate with a judge, no single model picks the winner. After
every advisor proposes a design, every advisor (including you) will
cast ONE vote per topic. The winning proposal per topic is decided by
plurality - so write proposals that are clear, defensible, and easy
to vote for.
"""


# --------------------------------------------------------------------------- #
# Topics. Same six binding decisions as the debate methodology.               #
# --------------------------------------------------------------------------- #

TOPICS: list[dict] = [
    {
        "id": "board_repr",
        "title": "Board representation",
        "question": (
            "Which internal board representation should the engine use - "
            "8x8 mailbox, 0x88, or bitboards? Justify your pick under the "
            "pure-Python / no-third-party-deps constraint."
        ),
    },
    {
        "id": "movegen",
        "title": "Move generation strategy",
        "question": (
            "Should move generation produce strictly-legal moves up front, "
            "or pseudo-legal moves filtered by a make-then-check-king-safety "
            "step? Consider correctness risk vs. CPU cost in pure Python."
        ),
    },
    {
        "id": "search",
        "title": "Search algorithm and extensions",
        "question": (
            "Beyond minimax + alpha-beta, which extensions are most worth "
            "implementing in pure Python (iterative deepening, transposition "
            "table, quiescence, null-move pruning, late-move reductions, "
            "killer / history heuristics)? Pick the smallest set that meets "
            "the master brief without slowing every search to a crawl."
        ),
    },
    {
        "id": "evaluation",
        "title": "Evaluation features",
        "question": (
            "What features should the evaluation function include, and how "
            "should they be weighted? Be specific about coefficients or "
            "relative ordering for material, piece-square tables, mobility, "
            "king safety, pawn structure, bishop pair, passed pawns, center "
            "control, tempo."
        ),
    },
    {
        "id": "elo",
        "title": "ELO scaling mechanism",
        "question": (
            "How should the 400-2400 ELO slider map onto engine behaviour? "
            "Cover: depth scaling, time-per-move scaling, evaluation noise, "
            "top-K candidate sampling, and how to keep weak play believable "
            "rather than embarrassingly random."
        ),
    },
    {
        "id": "ux",
        "title": "UCI + UI architecture",
        "question": (
            "How should UCI and the human-playable UI be structured? Should "
            "the UI be a stdlib http.server + vanilla JS page or something "
            "richer? How are search threads, stop signals, and shared engine "
            "state managed across the two interfaces?"
        ),
    },
]


# --------------------------------------------------------------------------- #
# Per-phase prompt builders                                                   #
# --------------------------------------------------------------------------- #

def proposal_prompt(topic: dict, advisor_label: str) -> tuple[str, str]:
    """First phase: each advisor writes its design proposal for one topic."""
    system = (
        MASTER_BRIEF
        + f"\nYou are speaking as {advisor_label}. This is the PROPOSAL phase. "
          f"Write a focused, voter-friendly proposal for ONE design topic."
    )
    user = (
        f"TOPIC: {topic['title']}\n\n{topic['question']}\n\n"
        "Write a proposal of 150-300 words. Structure it as:\n"
        "  1. Your recommendation (one sentence).\n"
        "  2. Why this is the right choice for a pure-Python engine.\n"
        "  3. Tradeoffs you accept.\n"
        "  4. Implementation directive: concrete instructions a builder "
        "could follow without further interpretation (file names, "
        "function signatures, parameters, ranges).\n"
        "Do NOT write code. Optimise for being voted for: clarity over "
        "cleverness."
    )
    return system, user


def vote_prompt(
    topic: dict,
    voter_label: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, str]:
    """Vote phase: each advisor sees ALL proposals and casts one ballot.

    candidates is a list of (proposal_label, proposal_text). The voter
    is allowed to vote for its own proposal.
    """
    candidate_block = "\n\n".join(
        f"--- Proposal #{i+1} from {label} ---\n{text}"
        for i, (label, text) in enumerate(candidates)
    )
    labels = [label for label, _ in candidates]
    system = (
        MASTER_BRIEF
        + f"\nYou are voting as {voter_label}. This is the VOTE phase. "
          f"You will cast EXACTLY ONE ballot for the strongest proposal "
          f"on ONE topic. You may vote for your own proposal if you "
          f"genuinely think it is best."
    )
    user = (
        f"TOPIC: {topic['title']}\n\n{topic['question']}\n\n"
        f"=== Candidate proposals ===\n{candidate_block}\n=== end ===\n\n"
        "Cast your ballot. Output your final answer in this EXACT shape:\n\n"
        "## Reasoning\n"
        "<2-3 sentences explaining what made one proposal win for you.>\n\n"
        "## Vote\n"
        f"<one of: {' | '.join(labels)}>\n\n"
        "The orchestrator parses the line under '## Vote' and matches "
        "it against the candidate names. Write only the name, nothing "
        "else, on that line."
    )
    return system, user


# Pattern used by the runner to parse a ballot. The voter writes the
# advisor name on the first non-empty line under "## Vote".
_VOTE_SECTION = re.compile(r"##\s*Vote\s*\n+(.*?)(?:\n##|\Z)", re.IGNORECASE | re.DOTALL)


def parse_vote(text: str, candidate_labels: list[str]) -> str | None:
    """Return the advisor label the voter chose, or None if unparseable.

    Tolerates extra whitespace / quotes / leading bullets. Matches the
    candidate label as a case-insensitive substring of the line.
    """
    if not text:
        return None
    section = _VOTE_SECTION.search(text)
    chunk = (section.group(1) if section else text).strip()
    # Take the first non-empty line.
    for raw in chunk.splitlines():
        line = raw.strip().strip('"').strip("'").lstrip("-*•").strip()
        if not line:
            continue
        line_lc = line.lower()
        # Prefer exact match, fall back to substring.
        for label in candidate_labels:
            if line_lc == label.lower():
                return label
        for label in candidate_labels:
            if label.lower() in line_lc:
                return label
        return None
    return None


# --------------------------------------------------------------------------- #
# Build phase prompts (Claude tool-use, identical to debate methodology).     #
# --------------------------------------------------------------------------- #

BUILD_SYSTEM = """\
You are the lead architect implementing a chess engine that the
ensemble just voted into a binding design contract. The contract
below is BINDING - do not relitigate it. Build the engine end-to-end.

You have these tools (Anthropic tool-use):
  - write_file(path, content, summary)  - write a project file
  - read_file(path)                     - read a file you wrote earlier
  - list_files(path=".")                - list files (recursive)
  - delete_file(path)                   - remove a file
  - run_pytest(target="")               - run pytest in the sandbox

All paths are relative to the project root. There is no shell access.
The pure-Python / no-third-party-deps rule still applies (stdlib only).

Workflow:
  1. List the existing files (probably empty), then write the package
     skeleton implied by the contract.
  2. Implement the chess core (board, moves, FEN, legality, draws),
     write tests, run pytest, fix failures.
  3. Implement evaluation + search per the contract; write tests.
  4. Implement the ELO scaling per the contract; write tests.
  5. Implement the UCI adapter; write tests.
  6. Implement the playable UI per the contract; smoke-test.
  7. Write a README that mirrors the contract.
  8. Run the full pytest suite once more. Iterate until it passes.

Be efficient. Do not narrate. Whenever pytest fails, fix the failing
file and re-run. Stop only when the suite is green AND every contract
directive is satisfied. End by sending a final assistant message
summarising what you built and the pytest result.
"""


def build_user_message(design_contract: str) -> str:
    return (
        "DESIGN CONTRACT (binding, voted into existence by the ensemble)\n"
        "================================================================\n"
        f"{design_contract}\n"
        "================================================================\n\n"
        "Begin. Use list_files to confirm the workspace is empty, then "
        "write the package skeleton and proceed."
    )
