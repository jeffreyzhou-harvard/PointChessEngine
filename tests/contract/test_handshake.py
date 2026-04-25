"""C-1: launch + UCI handshake.

Every engine must launch as a subprocess, return a non-empty
``id name`` line, complete the ``uci`` -> ``uciok`` handshake, and
respond to ``isready`` with ``readyok``. The session-scoped
``uci_client`` fixture already drives all four steps before yielding,
so a successful fixture build IS the test.
"""
from __future__ import annotations


def test_engine_handshakes(uci_client, engine_id):
    """If we got here, the engine launched + handshook successfully."""
    assert uci_client is not None
    assert uci_client.id_name, f"engine {engine_id} returned empty id name"


def test_id_name_is_human_readable(uci_client, engine_id):
    name = uci_client.id_name.strip()
    # Reject obviously-broken values: punctuation-only, single char, etc.
    assert len(name) >= 2, f"engine {engine_id} id name too short: {name!r}"
    assert any(ch.isalpha() for ch in name), \
        f"engine {engine_id} id name has no letters: {name!r}"
