"""Smoke tests for the HTTP UI."""
import json
import threading
import time
import urllib.request
import urllib.error

from ui.server import serve


def _start_server():
    srv = serve(host="127.0.0.1", port=0)  # let OS pick a port
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read()


def _post(port, path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read()


def test_ui_index_and_state():
    srv, port = _start_server()
    try:
        status, body = _get(port, "/")
        assert status == 200
        assert b"PyChess" in body
        status, body = _get(port, "/static/app.js")
        assert status == 200
        assert b"fenToGrid" in body
        status, body = _get(port, "/state")
        assert status == 200
        data = json.loads(body)
        assert "fen" in data and "legal_moves" in data
        assert data["status"] == "ongoing"
    finally:
        srv.shutdown()


def test_ui_new_game_and_move():
    srv, port = _start_server()
    try:
        # Set up a new game with low ELO and human as white.
        status, _ = _post(port, "/new", {"elo": 400, "human_color": "w"})
        assert status == 200
        # Stop any background search before making a human move.
        _post(port, "/stop", {})
        # Make a legal move.
        status, body = _post(port, "/move", {"move": "e2e4"})
        assert status == 200
        # State should now have black to move (or engine just thinking).
        status, body = _get(port, "/state")
        data = json.loads(body)
        # Either still black to move (engine queued) or already moved back.
        assert data["status"] == "ongoing"
        # Ask engine to stop so test ends fast.
        _post(port, "/stop", {})
    finally:
        srv.shutdown()
