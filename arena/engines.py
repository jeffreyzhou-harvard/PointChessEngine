"""Registry of UCI engines and a thin subprocess client to drive them."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = os.environ.get("POINTCHESS_PYTHON", sys.executable)


@dataclass
class EngineSpec:
    id: str
    label: str
    blurb: str
    cmd: list[str]
    cwd: str
    # Static metadata shown in the UI. Edit engine_costs.json to override.
    build_pattern: str = ""
    build_cost_usd: float | None = None
    build_tokens: int | None = None
    build_model: str = ""
    loc: int | None = None


REGISTRY: dict[str, EngineSpec] = {
    "oneshot_nocontext": EngineSpec(
        id="oneshot_nocontext",
        label="One-shot (no context)",
        blurb="Single Claude prompt, no project context.",
        cmd=[PYTHON, "-m", "engines.oneshot_nocontext", "--uci"],
        cwd=str(REPO_ROOT),
        build_pattern="one-shot · no context",
    ),
    "oneshot_contextualized": EngineSpec(
        id="oneshot_contextualized",
        label="One-shot (contextualized)",
        blurb="Single prompt with curated project context.",
        cmd=[PYTHON, "run_uci.py"],
        cwd=str(REPO_ROOT / "engines" / "oneshot_contextualized"),
        build_pattern="one-shot · contextualized",
    ),
    "oneshot_react": EngineSpec(
        id="oneshot_react",
        label="One-shot ReAct",
        blurb="Single ReAct-style prompt with tool access.",
        cmd=[PYTHON, "-m", "engines.oneshot_react", "--uci"],
        cwd=str(REPO_ROOT),
        build_pattern="one-shot · ReAct",
    ),
    "chainofthought": EngineSpec(
        id="chainofthought",
        label="Chain-of-thought",
        blurb="Built incrementally via chain-of-thought prompting.",
        cmd=[PYTHON, "-m", "engines.chainofthought", "--uci"],
        cwd=str(REPO_ROOT),
        build_pattern="incremental · CoT",
    ),
    "langgraph": EngineSpec(
        id="langgraph",
        label="LangGraph multi-agent",
        blurb="LangGraph-supervised multi-agent Claude system.",
        cmd=[PYTHON, "-m", "uci.main"],
        cwd=str(REPO_ROOT / "engines" / "langgraph"),
        build_pattern="multi-agent · LangGraph",
    ),
    "debate": EngineSpec(
        id="debate",
        label="Council debate",
        blurb="Multi-model debate (OpenAI, Grok, Gemini, DeepSeek, Kimi) → Claude builds.",
        cmd=[PYTHON, "main.py", "--uci"],
        cwd=str(REPO_ROOT / "engines" / "debate"),
        build_pattern="multi-model · debate",
    ),
    "ensemble": EngineSpec(
        id="ensemble",
        label="Ensemble vote",
        blurb="Same advisors as debate but plurality-vote on the design (no judge), then Claude builds.",
        cmd=[PYTHON, "main.py", "--uci"],
        cwd=str(REPO_ROOT / "engines" / "ensemble"),
        build_pattern="multi-model · vote",
    ),
    "rlm": EngineSpec(
        id="rlm",
        label="RLM recursive",
        blurb="Recursive Language Model-inspired decomposition with local deterministic UCI runtime.",
        cmd=[PYTHON, "-m", "engines.rlm", "--uci"],
        cwd=str(REPO_ROOT),
        build_pattern="recursive LM · RLM",
    ),
}


_SKIP_PARTS = {"__pycache__", "tests", ".venv", "venv", "site-packages", "node_modules", ".git"}


def _count_loc(root: Path) -> int:
    total = 0
    for p in root.rglob("*.py"):
        if any(part in _SKIP_PARTS for part in p.parts):
            continue
        try:
            total += sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return total


_ENGINE_DIRS = {
    "oneshot_nocontext":      REPO_ROOT / "engines" / "oneshot_nocontext",
    "oneshot_contextualized": REPO_ROOT / "engines" / "oneshot_contextualized",
    "oneshot_react":          REPO_ROOT / "engines" / "oneshot_react",
    "chainofthought":         REPO_ROOT / "engines" / "chainofthought",
    "langgraph":              REPO_ROOT / "engines" / "langgraph",
    "debate":                 REPO_ROOT / "engines" / "debate",
    "ensemble":               REPO_ROOT / "engines" / "ensemble",
    "rlm":                    REPO_ROOT / "engines" / "rlm",
}


def populate_static_metadata() -> None:
    """Compute LOC and merge user-supplied costs from engine_costs.json."""
    for eid, spec in REGISTRY.items():
        d = _ENGINE_DIRS.get(eid)
        if d and d.exists():
            spec.loc = _count_loc(d)
    cost_file = Path(__file__).parent / "engine_costs.json"
    if cost_file.exists():
        import json

        try:
            data = json.loads(cost_file.read_text())
        except json.JSONDecodeError:
            return
        for eid, overrides in data.items():
            spec = REGISTRY.get(eid)
            if not spec:
                continue
            for k, v in overrides.items():
                if hasattr(spec, k):
                    setattr(spec, k, v)


def parse_info(line: str) -> dict:
    """Parse a UCI `info ...` line into a flat dict."""
    parts = line.split()
    out: dict = {}
    i = 1  # skip 'info'
    while i < len(parts):
        tok = parts[i]
        if tok in ("depth", "seldepth", "multipv", "nodes", "time", "nps", "hashfull"):
            try:
                out[tok] = int(parts[i + 1])
            except (ValueError, IndexError):
                pass
            i += 2
        elif tok == "score" and i + 2 < len(parts):
            kind = parts[i + 1]
            val = parts[i + 2]
            try:
                out["score_kind"] = kind
                out["score_val"] = int(val)
            except ValueError:
                pass
            i += 3
        elif tok == "pv":
            out["pv"] = " ".join(parts[i + 1:])
            break
        elif tok == "string":
            break
        else:
            i += 1
    return out


class UCIClient:
    """Tiny UCI subprocess wrapper. One thread reads stdout into a queue."""

    def __init__(self, spec: EngineSpec, startup_timeout: float = 20.0):
        self.spec = spec
        env = os.environ.copy()
        # Make sure `python` finds repo packages.
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        self.proc = subprocess.Popen(
            spec.cmd,
            cwd=spec.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()

        self.id_name = spec.label
        self._send("uci")
        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            line = self._read(timeout=startup_timeout)
            if line is None:
                raise RuntimeError(f"engine {spec.id} died during handshake")
            if line.startswith("id name "):
                self.id_name = line[len("id name "):].strip()
            if line == "uciok":
                break
        else:
            raise TimeoutError(f"engine {spec.id} never sent uciok")
        self._send("isready")
        self._wait_for("readyok", timeout=startup_timeout)

    # --- subprocess plumbing --------------------------------------------------
    def _reader(self) -> None:
        try:
            for line in self.proc.stdout:  # type: ignore[union-attr]
                self._lines.put(line.rstrip())
        except Exception:
            pass
        finally:
            self._lines.put("__EOF__")

    def _send(self, s: str) -> None:
        if self.proc.stdin is None or self.proc.poll() is not None:
            raise RuntimeError("engine stdin closed")
        self.proc.stdin.write(s + "\n")
        self.proc.stdin.flush()

    def _read(self, timeout: float) -> str | None:
        try:
            line = self._lines.get(timeout=timeout)
        except queue.Empty:
            return None
        if line == "__EOF__":
            return None
        return line

    def _wait_for(self, prefix: str, timeout: float) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self._read(timeout=deadline - time.time())
            if line is None:
                raise RuntimeError(f"engine died waiting for {prefix}")
            if line.startswith(prefix):
                return line
        raise TimeoutError(f"timeout waiting for {prefix}")

    # --- public API -----------------------------------------------------------
    def new_game(self) -> None:
        self._send("ucinewgame")
        self._send("isready")
        self._wait_for("readyok", timeout=10)

    def go(self, moves_uci: list[str], movetime_ms: int) -> tuple[str, list[dict]]:
        """Send the position + go, return (bestmove_uci, list_of_info_dicts)."""
        cmd = "position startpos"
        if moves_uci:
            cmd += " moves " + " ".join(moves_uci)
        self._send(cmd)
        self._send(f"go movetime {movetime_ms}")
        infos: list[dict] = []
        # Generous slack — some engines emit bestmove well past movetime.
        deadline = time.time() + max(movetime_ms / 1000.0 * 4 + 30, 60)
        while time.time() < deadline:
            line = self._read(timeout=deadline - time.time())
            if line is None:
                raise RuntimeError("engine died mid-search")
            if line.startswith("info "):
                infos.append(parse_info(line))
            elif line.startswith("bestmove"):
                parts = line.split()
                bm = parts[1] if len(parts) > 1 else "0000"
                return bm, infos
        raise TimeoutError("engine never returned bestmove")

    def close(self) -> None:
        try:
            self._send("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
