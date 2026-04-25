#!/usr/bin/env python3
"""Write a self-contained HTML visualization for the C0-C8 Champion ladder."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LADDER_ROOT = ROOT / "reports" / "comparisons" / "CHAMPION_LADDER"


def load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_scores(row: dict) -> list[dict]:
    path_text = row.get("scores_path")
    if not path_text:
        return []
    path = ROOT / path_text
    data = load_json(path)
    return data if isinstance(data, list) else []


def pct(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return max(0.0, min(100.0, value * 100.0 / max_value))


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def candidate_rows(row: dict, scores: list[dict]) -> str:
    if not scores:
        return "<p class='muted'>No candidate scores recorded yet.</p>"
    max_score = max(float(item.get("total_score") or 0.0) for item in scores) or 1.0
    lines = []
    for item in scores:
        status = "winner" if item.get("selection_status") == "winner" else "candidate"
        lines.append(
            f"""
            <div class="candidate-row {status}">
              <div class="candidate-main">
                <strong>{esc(item.get("candidate_id"))}</strong>
                <span>{esc(item.get("tests_passed"))}/{esc(item.get("tests_total"))} tests</span>
                <span>{esc(item.get("tie_break_seconds"))}s tie</span>
              </div>
              <div class="score-bar">
                <span style="width: {pct(float(item.get("total_score") or 0.0), max_score):.1f}%"></span>
              </div>
              <div class="score-number">{esc(item.get("total_score"))}</div>
            </div>
            """
        )
    return "\n".join(lines)


def stage_card(row: dict) -> str:
    task_id = row.get("task_id", "")
    passed = bool(row.get("stage_passed"))
    scores = read_scores(row)
    winner = row.get("top_candidate_id") or "pending"
    score = row.get("top_score") if row.get("top_score") != "" else "pending"
    passed_count = row.get("passed_count", 0)
    candidate_count = row.get("candidate_count", 0)
    status_class = "pass" if passed else "fail"
    status_label = "champion selected" if passed else "no passing champion"
    return f"""
    <section class="stage-card {status_class}">
      <div class="stage-head">
        <div>
          <p class="eyebrow">{esc(task_id).split("_", 1)[0]}</p>
          <h2>{esc(task_id)}</h2>
        </div>
        <span class="pill {status_class}">{status_label}</span>
      </div>
      <div class="stage-stats">
        <div><span>{esc(passed_count)}/{esc(candidate_count)}</span><label>passed</label></div>
        <div><span>{esc(winner)}</span><label>winner</label></div>
        <div><span>{esc(score)}</span><label>score</label></div>
        <div><span>{float(row.get("duration_seconds") or 0.0):.1f}s</span><label>stage time</label></div>
      </div>
      <div class="candidate-list">
        {candidate_rows(row, scores[:6])}
      </div>
    </section>
    """


def build_html(summary: dict, refresh_seconds: int) -> str:
    rows = summary.get("rows") or []
    requested = int(summary.get("requested_task_count") or len(rows) or 0)
    complete = len(rows) >= requested and requested > 0
    refresh = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds > 0 and not complete else ""
    cards = "\n".join(stage_card(row) for row in rows)
    selected = [row for row in rows if row.get("stage_passed")]
    failed = [row for row in rows if not row.get("stage_passed")]
    serial = float(summary.get("estimated_serial_seconds") or 0.0)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {refresh}
  <title>PointChess Champion Ladder</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #101316;
      --panel: #171c20;
      --panel-2: #20272d;
      --text: #eef3f7;
      --muted: #93a1ad;
      --line: #2d3740;
      --green: #37d67a;
      --red: #ff6575;
      --cyan: #49c6e5;
      --gold: #f2c14e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{ width: min(1280px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 48px; }}
    header {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 18px;
      align-items: end;
      border-bottom: 1px solid var(--line);
      padding-bottom: 22px;
      margin-bottom: 22px;
    }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 54px); line-height: 1; letter-spacing: 0; }}
    .sub {{ color: var(--muted); margin: 12px 0 0; max-width: 780px; }}
    .scoreboard {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); padding: 14px; border-radius: 8px; }}
    .metric span {{ display: block; font-size: 26px; font-weight: 750; }}
    .metric label {{ display: block; color: var(--muted); margin-top: 3px; font-size: 13px; }}
    .rule {{
      background: #12181c;
      border: 1px solid var(--line);
      padding: 12px 14px;
      border-radius: 8px;
      margin-bottom: 18px;
      color: var(--muted);
    }}
    .rule strong {{ color: var(--text); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .stage-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-top: 4px solid var(--red);
      border-radius: 8px;
      padding: 14px;
      min-height: 310px;
    }}
    .stage-card.pass {{ border-top-color: var(--green); }}
    .stage-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 14px; }}
    .eyebrow {{ margin: 0 0 4px; color: var(--cyan); font-weight: 700; font-size: 12px; letter-spacing: .08em; }}
    h2 {{ margin: 0; font-size: 17px; letter-spacing: 0; }}
    .pill {{ white-space: nowrap; padding: 5px 8px; border-radius: 999px; font-size: 12px; background: var(--panel-2); }}
    .pill.pass {{ color: #0b2918; background: var(--green); }}
    .pill.fail {{ color: #2e070c; background: var(--red); }}
    .stage-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }}
    .stage-stats div {{ background: var(--panel-2); border-radius: 8px; padding: 9px; min-width: 0; }}
    .stage-stats span {{ display: block; font-weight: 750; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .stage-stats label {{ display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }}
    .candidate-list {{ display: grid; gap: 8px; }}
    .candidate-row {{ display: grid; grid-template-columns: 1fr 58px; gap: 8px; align-items: center; }}
    .candidate-main {{ display: flex; gap: 8px; align-items: baseline; min-width: 0; }}
    .candidate-main strong {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }}
    .candidate-main span {{ color: var(--muted); font-size: 12px; white-space: nowrap; }}
    .score-bar {{ grid-column: 1 / -1; height: 7px; background: #0d1114; border-radius: 999px; overflow: hidden; }}
    .score-bar span {{ display: block; height: 100%; background: var(--cyan); }}
    .candidate-row.winner .score-bar span {{ background: var(--gold); }}
    .score-number {{ font-weight: 750; text-align: right; }}
    .muted {{ color: var(--muted); }}
    footer {{ color: var(--muted); margin-top: 20px; font-size: 13px; }}
    @media (max-width: 980px) {{
      header {{ grid-template-columns: 1fr; }}
      .scoreboard {{ grid-template-columns: repeat(2, 1fr); }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>PointChess Champion Ladder</h1>
        <p class="sub">Local Docker evaluation across the classical C0-C8 task ladder. Open this file during a run; it refreshes until the requested ladder is complete.</p>
      </div>
      <div class="scoreboard">
        <div class="metric"><span>{len(rows)}/{requested}</span><label>stages recorded</label></div>
        <div class="metric"><span>{len(selected)}</span><label>champions selected</label></div>
        <div class="metric"><span>{len(failed)}</span><label>failed stages</label></div>
        <div class="metric"><span>{serial:.1f}s</span><label>runtime</label></div>
      </div>
    </header>
    <div class="rule"><strong>Champion rule:</strong> highest score wins. Ties break by pass rate, then fastest builder/runtime, then candidate ID. Promotion still requires human review.</div>
    <div class="grid">
      {cards}
    </div>
    <footer>
      Data: reports/comparisons/CHAMPION_LADDER/metrics.json. Generated by write_champion_ladder_html.py.
    </footer>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default=str(LADDER_ROOT / "metrics.json"))
    parser.add_argument("--output", default=str(LADDER_ROOT / "index.html"))
    parser.add_argument("--refresh-seconds", type=int, default=0)
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.is_absolute():
        summary_path = ROOT / summary_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    summary = load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        summary = {"rows": [], "requested_task_count": 0, "estimated_serial_seconds": 0}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(summary, args.refresh_seconds), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
