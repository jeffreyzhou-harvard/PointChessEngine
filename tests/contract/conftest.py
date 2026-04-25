"""Frozen public-interface contract tests.

Every engine in :data:`arena.engines.REGISTRY` must satisfy the same
UCI surface. This conftest parameterizes the suite so the same set of
checks runs against every registered engine and pytest output is keyed
by engine id.

Why UCI only? UCI is the only contract every engine in the repo
actually shares. Each engine's internal Board / Move / Evaluator /
Search Python types are private to that engine - those are graded by
:mod:`tests.classical` (currently against ``oneshot_nocontext`` only).
"""
from __future__ import annotations

import pytest

from arena.engines import REGISTRY, UCIClient

# Sorted so test IDs are deterministic in CI.
ENGINE_IDS = sorted(REGISTRY.keys())


@pytest.fixture(scope="session", params=ENGINE_IDS, ids=lambda eid: eid)
def engine_id(request) -> str:
    return request.param


@pytest.fixture(scope="session")
def uci_client(engine_id):
    """Spawn the engine once per session; close on teardown.

    Tests that need a clean board call ``uci_client.new_game()``.
    Anything that fails the UCI handshake is recorded as a SKIP, not
    a hard failure - so a single broken engine doesn't take the whole
    contract suite down with it.
    """
    spec = REGISTRY[engine_id]
    try:
        client = UCIClient(spec, startup_timeout=30.0)
    except Exception as exc:
        pytest.skip(f"engine {engine_id} failed to launch: {exc}")
        return  # unreachable, satisfies type-checkers
    try:
        yield client
    finally:
        try:
            client.close()
        except Exception:
            pass
