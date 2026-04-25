"""Smoke test for the HTTP UI server."""

import json
import threading
import time
import urllib.request

from engine.core import EngineCore
from ui.server import UIServer


def _wait(predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _http_get(url):
    with urllib.request.urlopen(url, timeout=5.0) as r:
        return r.status, r.read()


def _http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5.0) as r:
        return r.status, r.read()


def test_ui_smoke_endpoints():
    core = EngineCore()
    worker = threading.Thread(target=core.run_forever, daemon=True)
    worker.start()
    server = UIServer(core, host="127.0.0.1", port=0)
    # bind to port 0: ThreadingHTTPServer assigns one
    server.start()
    try:
        port = server.httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"

        # index.html
        s, body = _http_get(base + "/")
        assert s == 200
        assert b"<html" in body.lower() or b"<!DOCTYPE" in body

        # static assets
        s, body = _http_get(base + "/static/board.js")
        assert s == 200
        s, body = _http_get(base + "/static/board.css")
        assert s == 200

        # state
        s, body = _http_get(base + "/api/state")
        assert s == 200
        snap = json.loads(body)
        assert snap["turn"] == "white"
        assert len(snap["legal_moves"]) == 20

        # newgame + move
        _http_post_json(base + "/api/newgame", {})
        _http_post_json(base + "/api/move", {"uci": "e2e4"})
        assert _wait(lambda: json.loads(_http_get(base + "/api/state")[1])["turn"] == "black")

        # set elo
        _http_post_json(base + "/api/elo", {"elo": 1200, "limit": True})
        assert _wait(lambda: json.loads(_http_get(base + "/api/state")[1])["elo"] == 1200)

        # go (engine think)
        _http_post_json(base + "/api/go", {"movetime": 200})
        assert _wait(
            lambda: json.loads(_http_get(base + "/api/state")[1])["last_bestmove"] is not None,
            timeout=10.0,
        )
    finally:
        server.stop()
        from engine.core import CmdQuit
        core.submit(CmdQuit())
        worker.join(timeout=3.0)
