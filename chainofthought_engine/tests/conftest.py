"""Shared pytest configuration & fixtures.

Adds the ``slow`` marker so tests that take more than a few seconds
can be opted in/out without polluting the always-on suite. Run only
the always-on suite with::

    pytest chainofthought_engine/tests/

Run the slow suite too with::

    pytest chainofthought_engine/tests/ --runslow
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run tests marked @pytest.mark.slow",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "slow: deep perft / long-running correctness tests "
        "(opt in with --runslow)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="needs --runslow to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
