"""Smoke tests for stage 1.

These tests do not exercise any chess logic (none has been implemented
yet). They only verify that the package is importable and that the test
harness itself is wired up correctly. They will be superseded by real
tests in later stages but should remain green throughout the project.
"""

import importlib


def test_package_is_importable():
    pkg = importlib.import_module("engines.chainofthought")
    assert pkg is not None


def test_package_exposes_version():
    pkg = importlib.import_module("engines.chainofthought")
    assert isinstance(pkg.__version__, str)
    assert pkg.__version__  # non-empty
