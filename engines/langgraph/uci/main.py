"""
UCI mode entry point.

This module provides the main entry point for running the chess engine
in UCI (Universal Chess Interface) mode.

Usage:
    python -m uci.main
    
Or from the project root:
    python -m uci.main

The engine will read UCI commands from stdin and output responses to stdout.
"""

from .protocol import run_uci


def main():
    """Main entry point for UCI mode."""
    run_uci()


if __name__ == '__main__':
    main()
