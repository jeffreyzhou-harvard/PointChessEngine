"""Multi-model "Ensemble vote" methodology.

Each advisor proposes a stance on every design topic. Then every
advisor casts ONE vote per topic, picking the proposal it thinks is
strongest. Ballots are tallied by simple majority - there is no judge
model. The winning proposal per topic becomes the binding design
contract that the build phase implements.
"""

from methodologies.ensemble.runner import default_brief, run, summarize  # noqa: F401
