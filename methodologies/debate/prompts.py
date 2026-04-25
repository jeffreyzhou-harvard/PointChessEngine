"""All prompts: master brief, debate topics, advisor prompts, lead prompts.

The methodology is: for each design TOPIC, every available advisor
writes a PROPOSAL. Then each advisor sees the others' proposals and
writes a CRITIQUE that tries to convince the lead architect why their
own approach should win. The lead architect (Claude) reads the whole
transcript and issues a binding VERDICT per topic. The verdicts get
glued into a design contract that the build phase implements.
"""
from __future__ import annotations


# --------------------------------------------------------------------------- #
# Master brief - identical across advisors and lead.                          #
# --------------------------------------------------------------------------- #

MASTER_BRIEF = """\
You are an advisor on a multi-model design council. The council's job
is to design and ultimately build a complete chess engine that:

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

You are NOT writing the engine yet - you are influencing the binding
design contract that the lead architect (Claude) will follow when it
writes the code. Your job is to convince the lead that YOUR
recommendation is the right one.

Be opinionated. Be concise. Cite tradeoffs explicitly.
"""


# --------------------------------------------------------------------------- #
# Topics. Each is one binding design decision the lead must make.             #
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
            "should they be weighted? Include / exclude with reasons: "
            "material, piece-square tables, mobility, king safety, pawn "
            "structure, bishop pair, passed pawns, center control, "
            "tempo. Be specific about coefficients or relative ordering."
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
# Per-phase prompt builders.                                                  #
# --------------------------------------------------------------------------- #

def proposal_prompt(topic: dict, advisor_label: str) -> tuple[str, str]:
    """Return (system, user) messages for an advisor's first round."""
    system = (
        MASTER_BRIEF
        + f"\nYou are speaking as {advisor_label}. This is the PROPOSAL "
          f"phase. You will write your stance on ONE design topic."
    )
    user = (
        f"TOPIC: {topic['title']}\n\n"
        f"{topic['question']}\n\n"
        "Write a focused proposal of 150-300 words. Structure it as:\n"
        "  1. Your recommendation (one sentence).\n"
        "  2. Why this is the right choice for a pure-Python engine.\n"
        "  3. Tradeoffs you accept.\n"
        "  4. What other approaches you reject and why.\n"
        "Do NOT write code. This is a design brief, not an implementation."
    )
    return system, user


def critique_prompt(
    topic: dict,
    advisor_label: str,
    own_proposal: str,
    others: list[tuple[str, str]],
) -> tuple[str, str]:
    """others is a list of (other_advisor_label, their_proposal_text)."""
    others_block = "\n\n".join(
        f"--- Proposal from {label} ---\n{text}" for label, text in others
    ) or "(no other proposals)"
    system = (
        MASTER_BRIEF
        + f"\nYou are speaking as {advisor_label}. This is the CRITIQUE "
          f"phase. Your goal: convince the lead architect that YOUR "
          f"approach should win."
    )
    user = (
        f"TOPIC: {topic['title']}\n\n"
        f"Your own proposal (verbatim):\n---\n{own_proposal}\n---\n\n"
        f"The other advisors' proposals:\n\n{others_block}\n\n"
        "Now write a 150-250 word critique. Cover:\n"
        "  1. The strongest weakness in EACH rival proposal (one sentence each).\n"
        "  2. The single strongest reason your approach beats theirs.\n"
        "  3. One concession - where a rival's idea is genuinely better, if any.\n"
        "Be sharp but technical. The lead architect rewards specificity."
    )
    return system, user


def verdict_prompt(topic: dict, transcript: str) -> tuple[str, str]:
    """Lead-architect prompt to issue a binding verdict on one topic."""
    system = (
        MASTER_BRIEF
        + "\nYou are the LEAD ARCHITECT. You will issue a binding verdict "
          "for one design topic after reading the full debate. Your verdict "
          "becomes part of the design contract the build phase implements."
    )
    user = (
        f"TOPIC: {topic['title']}\n\n{topic['question']}\n\n"
        f"=== Council debate transcript ===\n{transcript}\n=== end ===\n\n"
        "Write your verdict in this exact shape (markdown):\n\n"
        "## Decision\n"
        "<one or two sentences naming the chosen approach>\n\n"
        "## Reasoning\n"
        "<2-4 short paragraphs. Cite which advisor(s) influenced you and "
        "where; note where you overrode the majority and why.>\n\n"
        "## Implementation directive\n"
        "<concrete, unambiguous instructions for the build phase. Names "
        "of modules, functions, parameters, ranges - whatever the builder "
        "needs to obey without further interpretation.>\n"
    )
    return system, user


# --------------------------------------------------------------------------- #
# Build phase prompts (lead architect uses tool-use to write the engine).     #
# --------------------------------------------------------------------------- #

BUILD_SYSTEM = """\
You are the lead architect implementing a chess engine that the design
council just signed off on. The design contract below is BINDING - do
not relitigate it. Build the engine end-to-end.

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
        "DESIGN CONTRACT (binding)\n"
        "=========================\n"
        f"{design_contract}\n"
        "=========================\n\n"
        "Begin. Use list_files to confirm the workspace is empty, then "
        "write the package skeleton and proceed."
    )
