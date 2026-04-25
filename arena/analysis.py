"""Position-analysis endpoint backend.

Spawns a UCIClient per requested engine in parallel, feeds them a FEN
position (or startpos), and returns the per-engine bestmove + metrics.
Synchronous - the caller waits for every engine to finish.
"""
from __future__ import annotations

import concurrent.futures as _cf
import time
from dataclasses import asdict, dataclass

import chess

from arena.engines import REGISTRY, UCIClient


STARTING_FEN = chess.STARTING_FEN


@dataclass
class AnalysisResult:
    engine_id: str
    label: str
    bestmove: str
    san: str | None
    score_cp: int | None
    mate: int | None
    depth: int | None
    nodes: int | None
    nps: int | None
    pv: str | None
    wall_ms: int
    error: str | None = None


def _run_one(engine_id: str, fen: str, movetime_ms: int) -> AnalysisResult:
    spec = REGISTRY[engine_id]
    t0 = time.time()
    try:
        client = UCIClient(spec, startup_timeout=30.0)
    except Exception as exc:
        return AnalysisResult(
            engine_id=engine_id, label=spec.label, bestmove="", san=None,
            score_cp=None, mate=None, depth=None, nodes=None, nps=None, pv=None,
            wall_ms=int((time.time() - t0) * 1000),
            error=f"launch failed: {exc}",
        )
    try:
        client.new_game()
        bm, infos = client.go(moves_uci=[], movetime_ms=movetime_ms, fen=fen)
        wall_ms = int((time.time() - t0) * 1000)
        last = infos[-1] if infos else {}
        # SAN if move is legal in the supplied position.
        san: str | None = None
        try:
            board = chess.Board(fen)
            move = chess.Move.from_uci(bm)
            if move in board.legal_moves:
                san = board.san(move)
        except Exception:
            san = None
        score_cp = last.get("score_val") if last.get("score_kind") == "cp" else None
        mate     = last.get("score_val") if last.get("score_kind") == "mate" else None
        return AnalysisResult(
            engine_id=engine_id, label=spec.label,
            bestmove=bm, san=san,
            score_cp=score_cp, mate=mate,
            depth=last.get("depth"), nodes=last.get("nodes"), nps=last.get("nps"),
            pv=last.get("pv"),
            wall_ms=wall_ms,
        )
    except Exception as exc:
        return AnalysisResult(
            engine_id=engine_id, label=spec.label, bestmove="", san=None,
            score_cp=None, mate=None, depth=None, nodes=None, nps=None, pv=None,
            wall_ms=int((time.time() - t0) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


def analyze(fen: str, engine_ids: list[str], movetime_ms: int = 500) -> dict:
    """Run every requested engine on the same position in parallel."""
    fen = (fen or "").strip() or STARTING_FEN
    # Validate FEN early so an obvious typo isn't surfaced as a UCI error.
    try:
        chess.Board(fen)
    except Exception as exc:
        return {"fen": fen, "error": f"invalid FEN: {exc}", "results": []}

    movetime_ms = max(50, min(int(movetime_ms), 30000))
    valid_ids = [eid for eid in engine_ids if eid in REGISTRY]
    if not valid_ids:
        return {"fen": fen, "error": "no valid engine_ids", "results": []}

    results: list[AnalysisResult] = []
    with _cf.ThreadPoolExecutor(max_workers=min(len(valid_ids), 8)) as ex:
        futures = {ex.submit(_run_one, eid, fen, movetime_ms): eid for eid in valid_ids}
        for fut in _cf.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                eid = futures[fut]
                results.append(AnalysisResult(
                    engine_id=eid, label=REGISTRY[eid].label,
                    bestmove="", san=None, score_cp=None, mate=None,
                    depth=None, nodes=None, nps=None, pv=None,
                    wall_ms=0, error=str(exc),
                ))
    # Stable order: input order, with errors at the end.
    by_id = {r.engine_id: r for r in results}
    ordered = [by_id[eid] for eid in valid_ids]
    return {
        "fen": fen,
        "movetime_ms": movetime_ms,
        "results": [asdict(r) for r in ordered],
    }
