"""HTTP/JSON server tests for the UI.

These spin up a real :class:`UIServer` on an OS-picked port in a
background thread and hit it with ``urllib``. That's heavier than
calling handler methods directly, but it covers the wiring (status
codes, content types, JSON round-trip, threading) which is exactly
what we're worried about.

The test fixture pins the underlying engine to a fast / deterministic
ELO so engine-move endpoints don't take seconds.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from chainofthought_engine.core.types import Color
from chainofthought_engine.ui import UIServer, make_server
from chainofthought_engine.ui.session import Session


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@contextmanager
def _running_server(session: Session | None = None) -> Iterator[UIServer]:
    """Start a UIServer on an OS-picked port and tear it down cleanly."""
    if session is None:
        # 1200 ELO -> depth 3, ~2s movetime cap. Fine for tests.
        session = Session(elo=1200, seed=0)
    server = make_server(host="127.0.0.1", port=0, session=session)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _url(server: UIServer, path: str) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}{path}"


def _get(server: UIServer, path: str) -> tuple[int, str, dict[str, str]]:
    req = urllib.request.Request(_url(server, path), method="GET")
    return _do(req)


def _post(
    server: UIServer, path: str, body: dict | None = None
) -> tuple[int, str, dict[str, str]]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        _url(server, path), data=data, headers=headers, method="POST"
    )
    return _do(req)


def _do(req: urllib.request.Request) -> tuple[int, str, dict[str, str]]:
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8"),
                dict(resp.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        return exc.code, body, dict(exc.headers.items())


def _json_post(
    server: UIServer, path: str, body: dict | None = None
) -> dict[str, Any]:
    status, text, _ = _post(server, path, body)
    assert status == 200, f"{path} -> {status}: {text}"
    return json.loads(text)


def _json_get(server: UIServer, path: str) -> dict[str, Any]:
    status, text, _ = _get(server, path)
    assert status == 200, f"{path} -> {status}: {text}"
    return json.loads(text)


# ---------------------------------------------------------------------------
# 1. static surface
# ---------------------------------------------------------------------------


class TestStaticServing:
    def test_root_serves_html(self):
        with _running_server() as srv:
            status, body, headers = _get(srv, "/")
            assert status == 200
            assert headers["Content-Type"].startswith("text/html")
            assert "<html" in body.lower()
            assert "Chain-of-Thought Chess" in body

    def test_unknown_path_404(self):
        with _running_server() as srv:
            status, _, _ = _get(srv, "/no-such-endpoint")
            assert status == 404

    def test_static_path_traversal_blocked(self):
        with _running_server() as srv:
            status, _, _ = _get(srv, "/static/../session.py")
            assert status == 404


# ---------------------------------------------------------------------------
# 2. /api/state
# ---------------------------------------------------------------------------


class TestApiState:
    def test_initial_state_shape(self):
        with _running_server() as srv:
            data = _json_get(srv, "/api/state")
            for key in ("fen", "turn", "user_color", "elo",
                        "history_uci", "history_san", "legal_moves",
                        "status", "result", "game_over"):
                assert key in data
            assert data["turn"] == "white"
            assert data["history_uci"] == []
            assert data["game_over"] is False

    def test_content_type_is_json(self):
        with _running_server() as srv:
            _, _, headers = _get(srv, "/api/state")
            assert headers["Content-Type"].startswith("application/json")


# ---------------------------------------------------------------------------
# 3. /api/new
# ---------------------------------------------------------------------------


class TestApiNew:
    def test_new_game_default_color(self):
        with _running_server() as srv:
            data = _json_post(srv, "/api/new", {"color": "white", "elo": 800})
            assert data["user_color"] == "white"
            assert data["elo"] == 800
            assert data["history_uci"] == []

    def test_new_game_as_black_engine_moves_first(self):
        with _running_server() as srv:
            data = _json_post(srv, "/api/new", {"color": "black", "elo": 800})
            assert data["user_color"] == "black"
            # Engine has played one white move already.
            assert len(data["history_uci"]) == 1
            assert data["is_user_turn"] is True

    def test_new_game_invalid_color_400(self):
        with _running_server() as srv:
            status, _, _ = _post(srv, "/api/new", {"color": "purple"})
            assert status == 400


# ---------------------------------------------------------------------------
# 4. /api/move + /api/engine_move
# ---------------------------------------------------------------------------


class TestApiMove:
    def test_play_user_move_then_engine(self):
        with _running_server() as srv:
            after_user = _json_post(srv, "/api/move", {"uci": "e2e4"})
            assert after_user["history_uci"] == ["e2e4"]
            assert after_user["is_engine_turn"] is True

            after_engine = _json_post(srv, "/api/engine_move")
            assert len(after_engine["history_uci"]) == 2
            # engine_move endpoint surfaces "engine_move" with details.
            assert after_engine["engine_move"] is not None
            assert after_engine["engine_move"]["uci"]
            assert after_engine["is_user_turn"] is True

    def test_illegal_move_400(self):
        with _running_server() as srv:
            status, body, _ = _post(srv, "/api/move", {"uci": "e2e5"})
            assert status == 400
            assert "illegal" in body.lower()

    def test_missing_uci_field_400(self):
        with _running_server() as srv:
            status, _, _ = _post(srv, "/api/move", {})
            assert status == 400

    def test_bad_json_400(self):
        with _running_server() as srv:
            req = urllib.request.Request(
                _url(srv, "/api/move"),
                data=b"not json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            status, _, _ = _do(req)
            assert status == 400

    def test_engine_move_when_users_turn_400(self):
        with _running_server() as srv:
            status, _, _ = _post(srv, "/api/engine_move")
            assert status == 400


# ---------------------------------------------------------------------------
# 5. /api/elo + /api/resign + /api/pgn
# ---------------------------------------------------------------------------


class TestApiOptions:
    def test_set_elo(self):
        with _running_server() as srv:
            data = _json_post(srv, "/api/elo", {"elo": 2000})
            assert data["elo"] == 2000

    def test_elo_clamped(self):
        with _running_server() as srv:
            data = _json_post(srv, "/api/elo", {"elo": 99999})
            assert data["elo"] == data["elo_range"]["max"]

    def test_resign_marks_game_over(self):
        with _running_server() as srv:
            data = _json_post(srv, "/api/resign")
            assert data["game_over"] is True
            assert data["resigned"] is True
            assert data["result"] == "0-1"

    def test_resign_after_resign_400(self):
        with _running_server() as srv:
            _json_post(srv, "/api/resign")
            status, _, _ = _post(srv, "/api/resign")
            assert status == 400

    def test_pgn_text(self):
        with _running_server() as srv:
            _json_post(srv, "/api/move", {"uci": "e2e4"})
            _json_post(srv, "/api/engine_move")
            status, body, headers = _get(srv, "/api/pgn")
            assert status == 200
            assert headers["Content-Type"].startswith("text/plain")
            assert "[Event" in body
            assert "1. e4 " in body


# ---------------------------------------------------------------------------
# 6. threading: state polls don't deadlock with engine_move
# ---------------------------------------------------------------------------


class TestThreading:
    def test_state_poll_during_engine_move(self):
        # Use a fresh black-color session: posting /api/new with
        # color=black triggers an engine search, but since the lock
        # is released before each request returns, we should be able
        # to issue a state poll IMMEDIATELY after.
        with _running_server() as srv:
            _json_post(srv, "/api/new", {"color": "black", "elo": 800})
            data = _json_get(srv, "/api/state")
            # The engine has already moved; state is consistent.
            assert len(data["history_uci"]) == 1
            assert data["is_user_turn"] is True


# ---------------------------------------------------------------------------
# 7. full game flow over HTTP
# ---------------------------------------------------------------------------


class TestFullFlow:
    def test_new_then_alternating_moves(self):
        with _running_server() as srv:
            _json_post(srv, "/api/new", {"color": "white", "elo": 800})
            for uci in ("e2e4", "g1f3", "f1c4"):
                user_state = _json_post(srv, "/api/move", {"uci": uci})
                assert user_state["is_engine_turn"] is True
                eng_state = _json_post(srv, "/api/engine_move")
                assert eng_state["is_user_turn"] is True
            final = _json_get(srv, "/api/state")
            assert len(final["history_uci"]) == 6
