"""Render bar charts for the engine-vs-engine head-to-head matches.

Each match's raw cutechess-cli "Results of A vs B" line is captured
inline as a ``MatchResult``. The script renders:

  - one bar chart per matchup at
    ``figures/head_to_head/h2h_<a>_vs_<b>.png``
  - one combined overview grid at
    ``figures/head_to_head/h2h_overview.png``
  - a parallel CSV at
    ``figures/head_to_head/h2h_results.csv``

Bars are colour-coded by methodology family using the same palette
as ``plot_loc.py`` so cross-figure reading stays consistent with
the README.

Usage::

    python -m infra.scripts.plot_head_to_head           # write all figures + csv
    python -m infra.scripts.plot_head_to_head --no-csv  # skip the csv
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path.cwd() / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "figures" / "head_to_head"


# Methodology families -- mirrors plot_loc.py and the README's
# "approach spectrum" table.
ENGINE_FAMILY: dict[str, str] = {
    "oneshot_nocontext":      "single-prompt baseline",
    "oneshot_contextualized": "single-prompt baseline",
    "oneshot_react":          "single-prompt + reasoning/tools",
    "chainofthought":         "single-prompt + reasoning/tools",
    "rlm":                    "single-prompt + reasoning/tools",
    "langgraph":              "multi-agent orchestration",
    "debate":                 "multi-model collaboration",
    "ensemble":               "multi-model collaboration",
}

FAMILY_COLOR: dict[str, str] = {
    "single-prompt baseline":          "#9e9e9e",
    "single-prompt + reasoning/tools": "#1f77b4",
    "multi-agent orchestration":       "#2ca02c",
    "multi-model collaboration":       "#d62728",
}
DRAW_COLOR = "#cfcfcf"


@dataclass(frozen=True)
class MatchResult:
    a: str           # canonical engine id (matches arena REGISTRY keys)
    b: str
    a_label: str     # display name shown on the bar
    b_label: str
    a_wins: int
    b_wins: int
    draws: int
    elo: float       # may be math.inf / -math.inf for sweeps
    elo_err: float   # NaN if undefined
    points_pct: float  # A's score percentage

    @property
    def games(self) -> int:
        return self.a_wins + self.b_wins + self.draws


# Raw results pulled from cutechess-cli output. Each entry is the
# "Results of A vs B (...)" line in the user's head-to-head logs.
MATCHES: list[MatchResult] = [
    MatchResult(
        a="oneshot_nocontext",      a_label="NoContext",
        b="oneshot_contextualized", b_label="Contextualized",
        a_wins=0, b_wins=20, draws=0,
        elo=-math.inf, elo_err=math.nan, points_pct=0.00,
    ),
    MatchResult(
        a="chainofthought", a_label="ChainOfThought",
        b="oneshot_react",  b_label="OneshotReAct",
        a_wins=9, b_wins=58, draws=13,
        elo=-247.69, elo_err=91.52, points_pct=19.38,
    ),
    MatchResult(
        a="debate",   a_label="Debate",
        b="ensemble", b_label="Ensemble",
        a_wins=30, b_wins=59, draws=9,
        elo=-105.98, elo_err=72.69, points_pct=35.20,
    ),
    MatchResult(
        a="rlm",       a_label="RLM",
        b="langgraph", b_label="LangGraph",
        a_wins=73, b_wins=14, draws=13,
        elo=235.45, elo_err=95.39, points_pct=79.50,
    ),
    MatchResult(
        a="oneshot_contextualized", a_label="Contextualized",
        b="oneshot_react",          b_label="OneshotReAct",
        a_wins=100, b_wins=0, draws=0,
        elo=math.inf, elo_err=math.nan, points_pct=100.00,
    ),
    MatchResult(
        a="ensemble", a_label="Ensemble",
        b="rlm",      b_label="RLM",
        a_wins=100, b_wins=0, draws=0,
        elo=math.inf, elo_err=math.nan, points_pct=100.00,
    ),
    MatchResult(
        a="oneshot_contextualized", a_label="Contextualized",
        b="ensemble",               b_label="Ensemble",
        a_wins=18, b_wins=76, draws=6,
        elo=-230.16, elo_err=83.04, points_pct=21.00,
    ),
]


def _color_for(engine_id: str) -> str:
    return FAMILY_COLOR.get(ENGINE_FAMILY.get(engine_id, ""), "#bdbdbd")


def _format_elo(elo: float, err: float) -> str:
    if math.isinf(elo):
        return "Elo: " + ("+inf (sweep)" if elo > 0 else "-inf (sweep)")
    if math.isnan(err):
        return f"Elo: {elo:+.1f}"
    return f"Elo: {elo:+.1f} \u00b1 {err:.1f}"


def _bar(ax: plt.Axes, m: MatchResult, *, title_size: int = 13) -> None:
    """Draw the 3-bar [A wins, draws, B wins] chart for a single match."""
    labels = [f"{m.a_label}\nwins", "draws", f"{m.b_label}\nwins"]
    values = [m.a_wins, m.draws, m.b_wins]
    colors = [_color_for(m.a), DRAW_COLOR, _color_for(m.b)]
    bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.6)

    top = max(values) if max(values) > 0 else 1
    for b, v in zip(bars, values):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + top * 0.02,
            str(v),
            ha="center", va="bottom",
            fontsize=10, fontweight="bold",
        )

    ax.set_title(
        f"{m.a_label} vs {m.b_label}",
        fontsize=title_size, fontweight="bold", pad=8,
    )
    subtitle = (
        f"{m.games} games  \u00b7  "
        f"{_format_elo(m.elo, m.elo_err)}  \u00b7  "
        f"{m.a_label} scored {m.points_pct:.1f}%"
    )
    ax.set_xlabel(subtitle, fontsize=9, color="#444")
    ax.set_ylabel("games")
    ax.set_ylim(0, top * 1.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)


def _filename(m: MatchResult) -> str:
    return f"h2h_{m.a}_vs_{m.b}.png"


def render_individual(m: MatchResult, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 4.4))
    _bar(ax, m, title_size=13)
    fig.tight_layout()
    out = out_dir / _filename(m)
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return out


def render_overview(matches: list[MatchResult], out_dir: Path) -> Path:
    n = len(matches)
    cols = 4
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 4.0 * rows))
    flat = axes.flatten() if rows * cols > 1 else [axes]

    for ax, m in zip(flat, matches):
        _bar(ax, m, title_size=11)

    for ax in flat[len(matches):]:
        ax.axis("off")

    fig.suptitle(
        "Head-to-head matches  \u00b7  cutechess-cli, tc=10+0.1, "
        "openings = 8mvs_+90_+99.epd",
        fontsize=14, fontweight="bold", y=1.00,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = out_dir / "h2h_overview.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return out


def write_csv(matches: list[MatchResult], out_dir: Path) -> Path:
    out = out_dir / "h2h_results.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "engine_a", "engine_b", "games",
                "a_wins", "b_wins", "draws",
                "a_points_pct", "elo_a_perspective", "elo_err",
            ]
        )
        for m in matches:
            elo_text = (
                "+inf" if m.elo == math.inf
                else "-inf" if m.elo == -math.inf
                else f"{m.elo:.2f}"
            )
            err_text = "" if math.isnan(m.elo_err) else f"{m.elo_err:.2f}"
            w.writerow(
                [
                    m.a, m.b, m.games,
                    m.a_wins, m.b_wins, m.draws,
                    f"{m.points_pct:.2f}", elo_text, err_text,
                ]
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", default=str(OUT_DIR),
        help="output directory (default: ./figures/head_to_head)",
    )
    parser.add_argument(
        "--no-csv", action="store_true",
        help="skip writing the parallel CSV",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"writing to {out_dir}")
    print()
    print(f"  {'matchup':50s} {'wins':>10s}  {'draws':>5s}  {'elo (A)':>14s}")
    print(f"  {'-'*50} {'-'*10}  {'-'*5}  {'-'*14}")
    for m in MATCHES:
        out = render_individual(m, out_dir)
        score = f"{m.a_wins}-{m.b_wins}"
        elo = _format_elo(m.elo, m.elo_err).replace("Elo: ", "")
        name = f"{m.a_label} vs {m.b_label}"
        print(f"  {name:50s} {score:>10s}  {m.draws:>5d}  {elo:>14s}")
    print()

    overview = render_overview(MATCHES, out_dir)
    print(f"wrote overview: {overview.relative_to(REPO_ROOT)}")

    if not args.no_csv:
        csv_path = write_csv(MATCHES, out_dir)
        print(f"wrote csv:      {csv_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
