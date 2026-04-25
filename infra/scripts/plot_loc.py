"""Render a bar chart of lines of code per engine.

We use the *canonical* LOC counter from ``arena.engines._count_loc`` so
the numbers in this chart always match what the arena UI reports.
Bars are colour-coded by methodology family (matching the
"Experimental framework / approach spectrum" table in the root README)
so the chart is readable at a glance.

Usage::

    python -m infra.scripts.plot_loc                     # writes figures/EngineLOC.png
    python -m infra.scripts.plot_loc --out /tmp/loc.png  # custom path
    python -m infra.scripts.plot_loc --csv               # also write figures/EngineLOC.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

# Use a writable matplotlib cache to silence the home-dir warning on
# locked-down environments (CI, sandboxes).
os.environ.setdefault("MPLCONFIGDIR", str(Path.cwd() / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from arena.engines import _ENGINE_DIRS, _count_loc  # noqa: E402


# Methodology families -- mirrors the "approach spectrum" table in
# README.md. Engine id -> (display label, family).
ENGINE_META: dict[str, tuple[str, str]] = {
    "oneshot_nocontext":      ("oneshot\nnocontext",      "single-prompt baseline"),
    "oneshot_contextualized": ("oneshot\ncontextualized", "single-prompt baseline"),
    "oneshot_react":          ("oneshot\nReAct",          "single-prompt + reasoning/tools"),
    "chainofthought":         ("chain-of-\nthought",      "single-prompt + reasoning/tools"),
    "rlm":                    ("RLM",                     "single-prompt + reasoning/tools"),
    "langgraph":              ("LangGraph",               "multi-agent orchestration"),
    "debate":                 ("debate\n(judge)",         "multi-model collaboration"),
    "ensemble":               ("ensemble\n(vote)",        "multi-model collaboration"),
}

# One colour per family. Matplotlib "tab10" picks four well-separated hues.
FAMILY_COLOR: dict[str, str] = {
    "single-prompt baseline":          "#9e9e9e",  # grey -- the baselines
    "single-prompt + reasoning/tools": "#1f77b4",  # blue  -- single-LM with thinking
    "multi-agent orchestration":       "#2ca02c",  # green -- LangGraph
    "multi-model collaboration":       "#d62728",  # red   -- debate / ensemble
}


def collect_loc() -> list[tuple[str, str, str, int]]:
    """Return ``[(engine_id, label, family, loc), ...]`` sorted desc by LOC."""
    rows: list[tuple[str, str, str, int]] = []
    for eid, d in _ENGINE_DIRS.items():
        if eid not in ENGINE_META:
            # Be defensive: any engine added to the registry should at
            # least appear, even if we don't have a family label yet.
            label, family = eid, "uncategorised"
        else:
            label, family = ENGINE_META[eid]
        rows.append((eid, label, family, _count_loc(d)))
    rows.sort(key=lambda r: r[3], reverse=True)
    return rows


def render(rows: list[tuple[str, str, str, int]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 5.6))

    labels = [r[1] for r in rows]
    families = [r[2] for r in rows]
    locs = [r[3] for r in rows]
    colors = [FAMILY_COLOR.get(f, "#bdbdbd") for f in families]

    bars = ax.bar(labels, locs, color=colors, edgecolor="black", linewidth=0.6)

    # Value labels on top of each bar.
    for b, v in zip(bars, locs):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + max(locs) * 0.012,
            f"{v:,}",
            ha="center", va="bottom",
            fontsize=10, fontweight="bold",
        )

    ax.set_title(
        "Lines of code per generated engine",
        fontsize=14, fontweight="bold", pad=12,
    )
    ax.set_ylabel("Lines of Python (excludes tests, __pycache__, vendored deps)")
    ax.set_ylim(0, max(locs) * 1.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    # Family legend -- one entry per family in the order they appear in
    # FAMILY_COLOR (which matches the README's spectrum table).
    seen: set[str] = set()
    handles = []
    for fam in FAMILY_COLOR:
        if fam in families and fam not in seen:
            seen.add(fam)
            handles.append(
                plt.Rectangle((0, 0), 1, 1, color=FAMILY_COLOR[fam], label=fam)
            )
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_csv(rows: list[tuple[str, str, str, int]], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["engine", "family", "lines_of_code"])
        for eid, _label, family, loc in rows:
            w.writerow([eid, family, loc])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "figures" / "EngineLOC.png"),
        help="output PNG path (default: ./figures/EngineLOC.png)",
    )
    parser.add_argument(
        "--csv", action="store_true",
        help="also write a parallel .csv next to the PNG",
    )
    args = parser.parse_args(argv)

    rows = collect_loc()
    out_png = Path(args.out)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    render(rows, out_png)

    print(f"wrote {out_png}  ({out_png.stat().st_size:,} bytes)")
    print()
    print(f"  {'engine':24s} {'family':36s} {'LOC':>7s}")
    print(f"  {'-'*24} {'-'*36} {'-'*7}")
    for eid, _lbl, fam, loc in rows:
        print(f"  {eid:24s} {fam:36s} {loc:>7,}")

    if args.csv:
        out_csv = out_png.with_suffix(".csv")
        write_csv(rows, out_csv)
        print(f"\nwrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
