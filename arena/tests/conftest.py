"""Shared fixtures for arena tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `import arena.*` resolve when pytest runs from anywhere.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arena import engines as engines_mod
from arena.engines import EngineSpec

FAKE_UCI = Path(__file__).resolve().parent / "fake_uci.py"


def _make_fake_spec(eid: str, label: str, moves: list[str]) -> EngineSpec:
    return EngineSpec(
        id=eid,
        label=label,
        blurb="In-tree scripted UCI engine for tests.",
        cmd=[sys.executable, str(FAKE_UCI), "--moves", ",".join(moves), "--name", label],
        cwd=str(FAKE_UCI.parent),
    )


# A pair of move scripts that form a real opening when alternated:
# Italian game out to ply 8.
WHITE_LINE = ["e2e4", "g1f3", "f1c4", "b1c3"]
BLACK_LINE = ["e7e5", "b8c6", "g8f6", "f8c5"]


@pytest.fixture
def fake_engine_spec() -> EngineSpec:
    """White-side fake engine spec."""
    return _make_fake_spec("fake", "FakeUCI", WHITE_LINE)


@pytest.fixture
def fake_b_spec() -> EngineSpec:
    """Black-side fake engine spec (different script, different label)."""
    return _make_fake_spec("fake_b", "FakeUCI-B", BLACK_LINE)


@pytest.fixture
def registered_fakes(fake_engine_spec, fake_b_spec):
    """Replace REGISTRY contents with two fake engines for the test.

    Mutates the dict IN PLACE so consumers that did
    ``from arena.engines import REGISTRY`` see the swap (rebinding the
    module attribute would leave stale references in arena.server and
    arena.match).
    """
    saved = dict(engines_mod.REGISTRY)
    engines_mod.REGISTRY.clear()
    for spec in (fake_engine_spec, fake_b_spec):
        engines_mod.REGISTRY[spec.id] = spec
    try:
        yield engines_mod.REGISTRY
    finally:
        engines_mod.REGISTRY.clear()
        engines_mod.REGISTRY.update(saved)


@pytest.fixture
def fake_b_env():
    """Compatibility no-op kept so existing test signatures still work."""
    return None
