"""Tests for arena/server.py: HTTP endpoints + SSE stream.

Spins up the real ThreadingHTTPServer on an ephemeral port. Engines
are replaced with the in-tree fake UCI so the server doesn't depend
on any of the real chess engines being importable.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from arena import server as server_mod


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_server(registered_fakes, fake_b_env):
    """Start the arena HTTP server in a background thread on a free port."""
    from http.server import ThreadingHTTPServer
    port = _free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), server_mod.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        yield base
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post_json(url: str, body: dict, timeout: float = 5.0) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _consume_sse(url: str, until_end: bool = True, timeout: float = 30.0) -> list[dict]:
    events: list[dict] = []
    deadline = time.time() + timeout
    with urllib.request.urlopen(url, timeout=timeout) as r:
        # Read line-by-line; SSE events are blank-line separated.
        for raw in r:
            if time.time() > deadline:
                break
            line = raw.decode().rstrip("\n").rstrip("\r")
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                events.append(ev)
                if until_end and ev["type"] == "end":
                    break
    return events


# --------------------------------------------------------------------------- #
# Routes                                                                      #
# --------------------------------------------------------------------------- #

class TestEnginesEndpoint:
    def test_lists_registry(self, live_server):
        data = _get_json(f"{live_server}/api/engines")
        ids = {e["id"] for e in data["engines"]}
        assert ids == {"fake", "fake_b"}
        labels = {e["label"] for e in data["engines"]}
        assert "FakeUCI" in labels


class TestStaticIndex:
    def test_serves_index(self, live_server):
        with urllib.request.urlopen(f"{live_server}/", timeout=5) as r:
            body = r.read().decode()
            assert r.status == 200
            assert "PointChess Arena" in body


class TestMatchEndpoint:
    def test_unknown_engine_returns_400(self, live_server):
        status, body = _post_json(f"{live_server}/api/match",
                                  {"white": "nope", "black": "fake"})
        assert status == 400
        assert "unknown" in body.get("error", "")

    def test_invalid_json_returns_400(self, live_server):
        req = urllib.request.Request(
            f"{live_server}/api/match",
            data=b"{not json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 400

    def test_creates_match_and_returns_id(self, live_server):
        status, body = _post_json(
            f"{live_server}/api/match",
            {"white": "fake", "black": "fake_b", "movetime_ms": 20, "max_plies": 2},
        )
        assert status == 200
        assert "match_id" in body
        assert isinstance(body["match_id"], str)


class TestMatchStream:
    def test_stream_replays_full_match(self, live_server):
        _, body = _post_json(
            f"{live_server}/api/match",
            {"white": "fake", "black": "fake_b", "movetime_ms": 20, "max_plies": 4},
        )
        mid = body["match_id"]
        # Tiny pause so the match thread starts emitting events.
        time.sleep(0.05)
        events = _consume_sse(f"{live_server}/api/match/{mid}/stream")
        types = [e["type"] for e in events]
        assert types[0] == "init"
        assert types[-1] == "end"
        moves = [e for e in events if e["type"] == "move"]
        assert len(moves) == 4

    def test_stream_404_for_unknown_match(self, live_server):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{live_server}/api/match/nope/stream", timeout=5)
        assert exc_info.value.code == 404


class TestMatchStop:
    def test_stop_unknown_match_404(self, live_server):
        status, body = _post_json(f"{live_server}/api/match/nope/stop", {})
        assert status == 404
