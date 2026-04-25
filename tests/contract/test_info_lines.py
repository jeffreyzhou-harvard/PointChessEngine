"""C-3: every search emits at least one parseable ``info`` line.

We don't pin which fields each engine reports - search styles vary -
but at minimum every engine must emit one ``info`` line containing at
least one of: depth, nodes, score, time. Otherwise the arena UI's
metrics panel would have nothing to show.
"""
from __future__ import annotations


_REQUIRED_AT_LEAST_ONE = {"depth", "nodes", "score_kind", "time"}


def test_search_emits_at_least_one_useful_info(uci_client, engine_id):
    uci_client.new_game()
    _, infos = uci_client.go(moves_uci=[], movetime_ms=300)
    assert infos, f"{engine_id} emitted no info lines"
    assert any(_REQUIRED_AT_LEAST_ONE & set(info.keys()) for info in infos), (
        f"{engine_id} info lines lack any of {sorted(_REQUIRED_AT_LEAST_ONE)}; "
        f"got: {infos[-1] if infos else None}"
    )


def test_score_is_numeric_when_present(uci_client, engine_id):
    """If an engine reports a `score`, it must be either cp or mate
    with an integer value (not a string like 'unknown')."""
    uci_client.new_game()
    _, infos = uci_client.go(moves_uci=[], movetime_ms=200)
    scored = [i for i in infos if "score_kind" in i]
    if not scored:
        return  # no score reported is acceptable
    for info in scored:
        kind = info["score_kind"]
        val = info.get("score_val")
        assert kind in ("cp", "mate"), f"{engine_id}: unknown score kind {kind!r}"
        assert isinstance(val, int), f"{engine_id}: non-int score val {val!r}"
