"""PointChess ReAct Engine.

A chess engine built using the ReAct (Reasoning + Acting) prompting methodology.
The build process explicitly interleaves Thought / Action / Observation steps;
the engine itself can also emit a structured "reasoning trace" that explains
each move it makes (see engine.reasoning).
"""

__version__ = "1.0.0"
__author__ = "PointChess ReAct"
