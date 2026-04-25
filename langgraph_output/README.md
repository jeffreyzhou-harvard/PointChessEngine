# Chess Engine with ELO Slider

A modular chess engine implementation with UCI support and adjustable playing strength.

## Features

- **Complete Chess Rules**: All legal moves including castling, en passant, promotion, check, checkmate, stalemate, threefold repetition, fifty-move rule, and insufficient material
- **Engine Search**: Minimax with alpha-beta pruning, iterative deepening, move ordering, quiescence search, and transposition tables
- **Smart Evaluation**: Material, piece-square tables, king safety, mobility, pawn structure, and center control
- **Adjustable Strength**: ELO slider (400-2400) controlling search depth, time, evaluation noise, and move selection
- **UCI Protocol**: Full Universal Chess Interface support for compatibility with chess GUIs
- **Browser Interface**: Play against the engine with side selection, move input, game controls, and move history

## Architecture

This project is organized into clean, testable modules:

- `core/` - Chess rules, board representation, move generation, and game state
- `search/` - Engine search algorithms and evaluation functions
- `uci/` - Universal Chess Interface protocol implementation
- `ui/` - Browser-based user interface
- `tests/` - Comprehensive test suite

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## Requirements

- Python 3.8 or higher
- Modern web browser (for UI)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd chess-engine

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Play in Browser

```bash
python -m ui.server
# Open http://localhost:8000 in your browser
```

### UCI Mode (for chess GUIs)

```bash
python -m uci.main
```

### Run Tests

```bash
pytest
```

## Project Status

This project is under active development. See the architecture documentation for implementation details and module contracts.

## License

MIT License - see LICENSE file for details.

## Development

This is an educational chess engine built from scratch to demonstrate:
- Chess programming fundamentals
- Search algorithms (minimax, alpha-beta)
- Evaluation function design
- UCI protocol implementation
- Strength adjustment techniques

All core logic is original implementation. No external chess libraries (python-chess, Stockfish, etc.) are used for move generation or evaluation.
