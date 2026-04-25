"""Strength config tests."""

from engine.strength import configure, StrengthConfig


def test_low_elo_endpoints():
    c = configure(400)
    assert c.max_depth == 1
    assert c.soft_time_ms == 100
    assert c.hard_time_ms == 300
    assert c.eval_noise_cp == 75
    assert c.top_k == 4
    # softmax_temp at t=0 = 80
    assert abs(c.softmax_temp_cp - 80.0) < 0.01
    # blunder margin = 700
    assert c.blunder_margin_cp == 700


def test_high_elo_endpoints():
    c = configure(2400)
    assert c.max_depth == 10
    assert c.soft_time_ms == 3000
    assert c.hard_time_ms == 5000
    assert c.eval_noise_cp == 0
    assert c.top_k == 1
    assert abs(c.softmax_temp_cp - 1.0) < 0.01
    assert c.blunder_margin_cp == 300


def test_clamping():
    c1 = configure(100)
    c2 = configure(5000)
    assert c1.elo == 400
    assert c2.elo == 2400


def test_limit_strength_false_returns_full_strength():
    c = configure(800, limit_strength=False)
    assert c.max_depth == 10
    assert c.top_k == 1
    assert c.eval_noise_cp == 0
    assert not c.limit_strength


def test_monotonic_depth():
    last = 0
    for elo in range(400, 2401, 200):
        c = configure(elo)
        assert c.max_depth >= last
        last = c.max_depth
