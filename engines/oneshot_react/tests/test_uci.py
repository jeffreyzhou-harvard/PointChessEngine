"""UCI protocol handler tests."""

from engines.oneshot_react.uci.protocol import UCIProtocol


def collect():
    out = []
    proto = UCIProtocol(out=out.append)
    return out, proto


def test_uci_identification():
    out, proto = collect()
    proto.handle("uci")
    text = "\n".join(out)
    assert "id name" in text
    assert "uciok" in text
    assert "UCI_Elo" in text


def test_isready():
    out, proto = collect()
    proto.handle("isready")
    assert out == ["readyok"]


def test_position_startpos_with_moves():
    _, proto = collect()
    proto.handle("position startpos moves e2e4 e7e5 g1f3")
    assert proto.board.to_fen() == (
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
    )


def test_position_fen():
    _, proto = collect()
    proto.handle("position fen 8/P7/8/8/8/8/8/k6K w - - 0 1")
    assert proto.board.to_fen() == "8/P7/8/8/8/8/8/k6K w - - 0 1"


def test_setoption_uci_elo():
    _, proto = collect()
    proto.handle("setoption name UCI_Elo value 1200")
    assert proto.engine.strength.elo == 1200


def test_setoption_skill_level():
    _, proto = collect()
    proto.handle("setoption name Skill Level value 0")
    assert proto.engine.strength.elo == 400
    proto.handle("setoption name Skill Level value 20")
    assert proto.engine.strength.elo == 2400


def test_go_movetime_emits_bestmove():
    out, proto = collect()
    proto.handle("position startpos")
    proto.handle("go movetime 200")
    # Wait for the search thread to finish
    proto._search_thread.join(timeout=10.0)
    # Should have at least one bestmove line
    assert any(line.startswith("bestmove ") for line in out)


def test_go_depth_emits_bestmove():
    out, proto = collect()
    proto.handle("position startpos")
    proto.handle("go depth 2")
    proto._search_thread.join(timeout=10.0)
    assert any(line.startswith("bestmove ") for line in out)


def test_quit_returns_false():
    _, proto = collect()
    assert proto.handle("quit") is False


def test_ucinewgame_resets_state():
    _, proto = collect()
    proto.handle("position startpos moves e2e4")
    proto.handle("ucinewgame")
    assert proto.board.to_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
