"""Multi-model "Council debate" methodology.

A small set of *advisor* models from different providers debate the
design of a chess engine. The lead architect (Claude) synthesises the
debate into a binding design contract, then builds the engine.
"""

from methodologies.debate.runner import run, summarize, default_brief  # noqa: F401
