"""HTTP + SSE server for the engine arena."""
from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from arena.analysis import analyze
from arena.engines import REGISTRY, populate_static_metadata
from arena.match import Match, _engine_dict
from arena.tournament import Tournament

STATIC_DIR = Path(__file__).parent / "static"
MATCHES: dict[str, Match] = {}
MATCHES_LOCK = threading.Lock()
TOURNAMENTS: dict[str, Tournament] = {}
TOURNAMENTS_LOCK = threading.Lock()


def _engines_payload() -> list[dict]:
    return [_engine_dict(spec) for spec in REGISTRY.values()]


class Handler(BaseHTTPRequestHandler):
    server_version = "ChessArena/0.1"

    def log_message(self, format: str, *args) -> None:  # quieter logs
        return

    # ----- helpers ------------------------------------------------------------
    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "not found")
            return
        ctype, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ----- GET ----------------------------------------------------------------
    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path
        if path == "/":
            self._file(STATIC_DIR / "index.html")
            return
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            target = (STATIC_DIR / rel).resolve()
            if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
                self.send_error(403, "forbidden")
                return
            self._file(target)
            return
        if path == "/api/engines":
            self._json(200, {"engines": _engines_payload()})
            return
        if path.startswith("/api/match/") and path.endswith("/stream"):
            mid = path.split("/")[3]
            self._stream_match(mid)
            return
        if path.startswith("/api/tournament/") and path.endswith("/stream"):
            tid = path.split("/")[3]
            self._stream_tournament(tid)
            return
        self.send_error(404, "not found")

    # ----- POST ---------------------------------------------------------------
    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path == "/api/match":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            white = body.get("white")
            black = body.get("black")
            movetime_ms = int(body.get("movetime_ms", 500))
            max_plies = int(body.get("max_plies", 200))
            if white not in REGISTRY or black not in REGISTRY:
                self._json(400, {"error": "unknown engine id"})
                return
            movetime_ms = max(50, min(movetime_ms, 30000))
            max_plies = max(2, min(max_plies, 600))
            match = Match(white, black, movetime_ms, max_plies)
            with MATCHES_LOCK:
                MATCHES[match.id] = match
            threading.Thread(target=match.run, daemon=True).start()
            self._json(200, {"match_id": match.id})
            return
        if url.path.startswith("/api/match/") and url.path.endswith("/stop"):
            mid = url.path.split("/")[3]
            with MATCHES_LOCK:
                m = MATCHES.get(mid)
            if not m:
                self._json(404, {"error": "no such match"})
                return
            m.stop()
            self._json(200, {"ok": True})
            return

        # ----- Tournament ----------------------------------------------------
        if url.path == "/api/tournament":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            engine_ids = body.get("engines") or []
            unknown = [e for e in engine_ids if e not in REGISTRY]
            if unknown:
                self._json(400, {"error": f"unknown engine ids: {unknown}"})
                return
            if len(engine_ids) < 2:
                self._json(400, {"error": "need at least 2 engines"})
                return
            try:
                t = Tournament(
                    engine_ids=engine_ids,
                    movetime_ms=int(body.get("movetime_ms", 200)),
                    max_plies=int(body.get("max_plies", 60)),
                    games_per_pair=int(body.get("games_per_pair", 1)),
                )
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            with TOURNAMENTS_LOCK:
                TOURNAMENTS[t.id] = t
            threading.Thread(target=t.run, daemon=True).start()
            self._json(200, {"tournament_id": t.id, "total_games": len(t.games)})
            return
        if url.path.startswith("/api/tournament/") and url.path.endswith("/stop"):
            tid = url.path.split("/")[3]
            with TOURNAMENTS_LOCK:
                t = TOURNAMENTS.get(tid)
            if not t:
                self._json(404, {"error": "no such tournament"})
                return
            t.stop()
            self._json(200, {"ok": True})
            return

        # ----- Analyze (sync) ------------------------------------------------
        if url.path == "/api/analyze":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            payload = analyze(
                fen=str(body.get("fen", "")).strip(),
                engine_ids=list(body.get("engines") or []),
                movetime_ms=int(body.get("movetime_ms", 500)),
            )
            self._json(200, payload)
            return

        self.send_error(404, "not found")

    # ----- SSE ----------------------------------------------------------------
    def _stream_match(self, mid: str) -> None:
        with MATCHES_LOCK:
            match = MATCHES.get(mid)
        if not match:
            self.send_error(404, "no such match")
            return
        self._stream(match)

    def _stream_tournament(self, tid: str) -> None:
        with TOURNAMENTS_LOCK:
            t = TOURNAMENTS.get(tid)
        if not t:
            self.send_error(404, "no such tournament")
            return
        self._stream(t)

    def _stream(self, source) -> None:
        """Generic SSE pump shared by Match and Tournament (both expose
        subscribe()/unsubscribe()/done)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = source.subscribe()
        try:
            while True:
                try:
                    chunk = q.get(timeout=15)
                except Exception:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(chunk.encode())
                self.wfile.flush()
                if source.done and q.empty():
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            source.unsubscribe(q)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    populate_static_metadata()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Engine arena listening on http://{host}:{port}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
