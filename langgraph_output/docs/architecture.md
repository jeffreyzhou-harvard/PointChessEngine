# Chess Engine Architecture

**Version**: 1.0  
**Status**: FROZEN - Interface contracts are locked. Only the Integrator may modify.

---

## Table of Contents

1. [Technology Stack](#technology-stack)
2. [Module Overview](#module-overview)
3. [Core Module](#core-module)
4. [Search Module](#search-module)
5. [UCI Module](#uci-module)
6. [UI Module](#ui-module)
7. [Data Flow](#data-flow)
8. [Testing Strategy](#testing-strategy)

---

## Technology Stack

### Language
**Python 3.8+**

**Rationale**:
- Excellent for rapid development and testing
- Rich standard library (no need for external chess dependencies)
- Easy integration with web server for UI
- Performance adequate for educational chess engine (can reach 2400 ELO with good algorithms)
- Clean syntax for complex game logic

### Core Dependencies
- **Python Standard Library**: Primary dependency
- **pytest**: Testing framework
- **typing**: Type hints for interface clarity

### UI Stack
- **HTML5 + CSS3**: Board rendering
- **Vanilla JavaScript**: Client-side interactivity
- **Python http.server**: Simple web server (or Flask if needed)

### No External Chess Libraries
Per project requirements, we do NOT use:
- python-chess (except optionally in tests for validation)
- Stockfish or other engines as black boxes
- Any external move generation libraries

---

## Module Overview

```
chess-engine/
├── core/               # Chess rules and game logic
│   ├── __init__.py
│   ├── board.py        # Board representation and state
│   ├── move.py         # Move representation and validation
│   ├── pieces.py       # Piece definitions and movement
│   └── game_state.py   # Game state, check/mate/draw detection
├── search/             # Engine search and evaluation
│   ├── __init__.py
│   ├── engine.py       # Main engine interface
│   ├── search.py       # Minimax, alpha-beta, iterative deepening
│   ├── evaluation.py   # Position evaluation
│   ├── transposition.py # Transposition table
│   └── elo_config.py   # ELO strength configuration
├── uci/                # Universal Chess Interface
│   ├── __init__.py
│   ├── main.py         # UCI entry point
│   ├── protocol.py     # UCI command parser and handler
│   └── interface.py    # Bridge between UCI and engine
├── ui/                 # Browser-based interface
│   ├── __init__.py
│   ├── server.py       # Web server
│   ├── static/
│   │   ├── index.html  # Main page
│   │   ├── style.css   # Styling
│   │   └── app.js      # Client-side logic
│   └── api.py          # REST API for game actions
├── tests/              # Test suite
│   ├── __init__.py
│   ├── test_board.py
│   ├── test_moves.py
│   ├── test_game_state.py
│   ├── test_search.py
│   ├── test_uci.py
│   └── test_perft.py
├── docs/
│   ├── architecture.md (this file)
│   └── context_assessment.md
├── requirements.txt
└── README.md
```

---

## Core Module

**Responsibility**: Implement all chess rules, move generation, and game state management.

### Key Classes

#### `Board`
Represents the chess board and current position.

```python
class Board:
    """
    8x8 chess board representation.
    
    Attributes:
        squares: 8x8 array where squares[rank][file] contains Piece or None
        active_color: 'white' or 'black'
        castling_rights: dict with keys 'K', 'Q', 'k', 'q' (bool values)
        en_passant_target: Optional[Square] - target square for en passant
        halfmove_clock: int - moves since last pawn move or capture (50-move rule)
        fullmove_number: int - increments after black's move
        move_history: List[Move] - all moves played (for threefold repetition)
    """
    
    def __init__(self, fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"):
        """Initialize board from FEN string (default: starting position)."""
        pass
    
    def get_piece(self, square: Square) -> Optional[Piece]:
        """Get piece at square."""
        pass
    
    def set_piece(self, square: Square, piece: Optional[Piece]) -> None:
        """Set piece at square."""
        pass
    
    def make_move(self, move: Move) -> None:
        """Apply move to board (mutates state)."""
        pass
    
    def unmake_move(self, move: Move) -> None:
        """Undo last move (for search)."""
        pass
    
    def copy(self) -> 'Board':
        """Create deep copy of board."""
        pass
    
    def to_fen(self) -> str:
        """Export position as FEN string."""
        pass
    
    def __str__(self) -> str:
        """Human-readable board display."""
        pass
```

#### `Square`
Represents a board square.

```python
class Square:
    """
    Chess board square (0-63 or rank/file pair).
    
    Attributes:
        rank: int (0-7, where 0 is rank 1, 7 is rank 8)
        file: int (0-7, where 0 is 'a', 7 is 'h')
    """
    
    def __init__(self, rank: int, file: int):
        pass
    
    @classmethod
    def from_algebraic(cls, notation: str) -> 'Square':
        """Create from algebraic notation (e.g., 'e4')."""
        pass
    
    def to_algebraic(self) -> str:
        """Convert to algebraic notation."""
        pass
    
    def __eq__(self, other) -> bool:
        pass
    
    def __hash__(self) -> int:
        pass
```

#### `Piece`
Represents a chess piece.

```python
class Piece:
    """
    Chess piece.
    
    Attributes:
        piece_type: str - 'pawn', 'knight', 'bishop', 'rook', 'queen', 'king'
        color: str - 'white' or 'black'
    """
    
    def __init__(self, piece_type: str, color: str):
        pass
    
    def get_value(self) -> int:
        """Material value (pawn=100, knight=320, bishop=330, rook=500, queen=900, king=0)."""
        pass
    
    def __str__(self) -> str:
        """Single character representation (e.g., 'P', 'n', 'K')."""
        pass
```

#### `Move`
Represents a chess move.

```python
class Move:
    """
    Chess move with all necessary information.
    
    Attributes:
        from_square: Square
        to_square: Square
        promotion: Optional[str] - piece type if pawn promotion
        is_castling: bool
        is_en_passant: bool
        captured_piece: Optional[Piece] - for unmake_move
        previous_castling_rights: dict - for unmake_move
        previous_en_passant: Optional[Square] - for unmake_move
        previous_halfmove_clock: int - for unmake_move
    """
    
    def __init__(self, from_square: Square, to_square: Square, 
                 promotion: Optional[str] = None):
        pass
    
    def to_uci(self) -> str:
        """Convert to UCI notation (e.g., 'e2e4', 'e7e8q')."""
        pass
    
    @classmethod
    def from_uci(cls, uci_str: str) -> 'Move':
        """Parse UCI notation."""
        pass
    
    def to_algebraic(self, board: Board) -> str:
        """Convert to standard algebraic notation (e.g., 'Nf3', 'O-O')."""
        pass
    
    def __eq__(self, other) -> bool:
        pass
    
    def __hash__(self) -> int:
        pass
```

#### `GameState`
Manages game state and rule enforcement.

```python
class GameState:
    """
    Game state manager - handles move generation and game status.
    
    Attributes:
        board: Board
    """
    
    def __init__(self, board: Board):
        pass
    
    def get_legal_moves(self) -> List[Move]:
        """Generate all legal moves for active player."""
        pass
    
    def is_legal_move(self, move: Move) -> bool:
        """Check if move is legal."""
        pass
    
    def is_check(self) -> bool:
        """Check if active player is in check."""
        pass
    
    def is_checkmate(self) -> bool:
        """Check if active player is checkmated."""
        pass
    
    def is_stalemate(self) -> bool:
        """Check if position is stalemate."""
        pass
    
    def is_draw(self) -> bool:
        """Check for draw (stalemate, 50-move, repetition, insufficient material)."""
        pass
    
    def is_threefold_repetition(self) -> bool:
        """Check for threefold repetition."""
        pass
    
    def is_insufficient_material(self) -> bool:
        """Check for insufficient mating material."""
        pass
    
    def get_game_result(self) -> Optional[str]:
        """Return '1-0', '0-1', '1/2-1/2', or None if game ongoing."""
        pass
```

### Move Generation Strategy

1. **Pseudo-legal generation**: Generate all moves that follow piece movement rules
2. **Legality filtering**: Filter out moves that leave king in check
3. **Special moves**: Handle castling (king safety, empty squares), en passant, promotion

---

## Search Module

**Responsibility**: Engine search algorithms, position evaluation, and strength adjustment.

### Key Classes

#### `Engine`
Main engine interface.

```python
class Engine:
    """
    Chess engine - main interface for move selection.
    
    Attributes:
        elo_config: EloConfig - strength configuration
        transposition_table: TranspositionTable
    """
    
    def __init__(self, elo_rating: int = 1500):
        pass
    
    def set_elo(self, elo_rating: int) -> None:
        """Adjust engine strength (400-2400)."""
        pass
    
    def search(self, game_state: GameState, limits: SearchLimits) -> SearchResult:
        """
        Search for best move.
        
        Args:
            game_state: Current game state
            limits: Search limits (depth, time, nodes)
        
        Returns:
            SearchResult with best move and analysis
        """
        pass
    
    def get_best_move(self, game_state: GameState) -> Move:
        """Get best move with current ELO configuration."""
        pass
```

#### `SearchLimits`
Search constraints.

```python
class SearchLimits:
    """
    Search limits.
    
    Attributes:
        max_depth: Optional[int] - maximum search depth
        max_time_ms: Optional[int] - maximum time in milliseconds
        max_nodes: Optional[int] - maximum nodes to search
        infinite: bool - search until stopped
    """
    
    def __init__(self, max_depth: Optional[int] = None,
                 max_time_ms: Optional[int] = None,
                 max_nodes: Optional[int] = None,
                 infinite: bool = False):
        pass
```

#### `SearchResult`
Search result with analysis.

```python
class SearchResult:
    """
    Search result.
    
    Attributes:
        best_move: Move - best move found
        score: int - evaluation in centipawns
        depth: int - depth reached
        nodes: int - nodes searched
        time_ms: int - time taken
        pv: List[Move] - principal variation
    """
    
    def __init__(self, best_move: Move, score: int, depth: int,
                 nodes: int, time_ms: int, pv: List[Move]):
        pass
```

#### `EloConfig`
ELO strength configuration.

```python
class EloConfig:
    """
    ELO-based strength configuration.
    
    Maps ELO rating (400-2400) to engine parameters:
    - Search depth
    - Time allocation
    - Evaluation noise (randomness)
    - Move selection strategy (best vs probabilistic)
    
    Attributes:
        elo_rating: int (400-2400)
        base_depth: int - base search depth
        time_multiplier: float - time allocation factor
        eval_noise: int - centipawn noise to add to evaluation
        best_move_probability: float - probability of choosing best move (vs 2nd/3rd best)
    """
    
    def __init__(self, elo_rating: int):
        pass
    
    @staticmethod
    def depth_for_elo(elo: int) -> int:
        """Calculate search depth for ELO rating."""
        pass
    
    @staticmethod
    def noise_for_elo(elo: int) -> int:
        """Calculate evaluation noise for ELO rating."""
        pass
    
    @staticmethod
    def best_move_prob_for_elo(elo: int) -> float:
        """Calculate best-move probability for ELO rating."""
        pass
```

#### `Evaluator`
Position evaluation.

```python
class Evaluator:
    """
    Position evaluator.
    
    Evaluation components:
    - Material balance
    - Piece-square tables
    - King safety
    - Mobility
    - Pawn structure
    - Center control
    """
    
    def evaluate(self, board: Board) -> int:
        """
        Evaluate position from white's perspective.
        
        Returns:
            Score in centipawns (positive = white advantage)
        """
        pass
    
    def evaluate_material(self, board: Board) -> int:
        pass
    
    def evaluate_piece_square(self, board: Board) -> int:
        pass
    
    def evaluate_king_safety(self, board: Board) -> int:
        pass
    
    def evaluate_mobility(self, board: Board, game_state: GameState) -> int:
        pass
    
    def evaluate_pawn_structure(self, board: Board) -> int:
        pass
    
    def evaluate_center_control(self, board: Board) -> int:
        pass
```

#### `Searcher`
Search algorithms.

```python
class Searcher:
    """
    Search implementation (minimax, alpha-beta, iterative deepening).
    
    Attributes:
        evaluator: Evaluator
        transposition_table: TranspositionTable
    """
    
    def __init__(self, evaluator: Evaluator):
        pass
    
    def iterative_deepening(self, game_state: GameState, 
                           limits: SearchLimits) -> SearchResult:
        """Iterative deepening search."""
        pass
    
    def alpha_beta(self, game_state: GameState, depth: int,
                   alpha: int, beta: int, pv: List[Move]) -> int:
        """Alpha-beta search."""
        pass
    
    def quiescence(self, game_state: GameState, alpha: int, beta: int) -> int:
        """Quiescence search (search captures until quiet)."""
        pass
    
    def order_moves(self, moves: List[Move], board: Board) -> List[Move]:
        """Order moves for better alpha-beta pruning."""
        pass
```

#### `TranspositionTable`
Transposition table for caching positions.

```python
class TranspositionTable:
    """
    Transposition table (hash table for positions).
    
    Stores:
    - Position hash (Zobrist hashing)
    - Best move
    - Score
    - Depth
    - Node type (exact, lower bound, upper bound)
    """
    
    def __init__(self, size_mb: int = 64):
        pass
    
    def store(self, position_hash: int, depth: int, score: int,
              best_move: Move, node_type: str) -> None:
        pass
    
    def probe(self, position_hash: int) -> Optional[dict]:
        pass
    
    def clear(self) -> None:
        pass
```

---

## UCI Module

**Responsibility**: Universal Chess Interface protocol implementation.

### Key Classes

#### `UCIProtocol`
UCI command handler.

```python
class UCIProtocol:
    """
    UCI protocol handler.
    
    Implements UCI commands:
    - uci: identify engine
    - isready: synchronization
    - ucinewgame: reset game
    - position: set position
    - go: start search
    - stop: halt search
    - quit: exit
    
    Attributes:
        engine: Engine
        game_state: GameState
        searching: bool
    """
    
    def __init__(self, engine: Engine):
        pass
    
    def handle_command(self, command: str) -> Optional[str]:
        """
        Process UCI command and return response.
        
        Args:
            command: UCI command string
        
        Returns:
            Response string or None
        """
        pass
    
    def cmd_uci(self) -> str:
        """Handle 'uci' command."""
        pass
    
    def cmd_isready(self) -> str:
        """Handle 'isready' command."""
        pass
    
    def cmd_ucinewgame(self) -> None:
        """Handle 'ucinewgame' command."""
        pass
    
    def cmd_position(self, args: List[str]) -> None:
        """Handle 'position' command."""
        pass
    
    def cmd_go(self, args: List[str]) -> str:
        """Handle 'go' command."""
        pass
    
    def cmd_stop(self) -> str:
        """Handle 'stop' command."""
        pass
    
    def send_info(self, result: SearchResult) -> str:
        """Format search info for UCI output."""
        pass
```

---

## UI Module

**Responsibility**: Browser-based user interface for human play.

### Components

#### Web Server (`server.py`)
Simple HTTP server serving static files and REST API.

```python
def start_server(port: int = 8000) -> None:
    """Start web server."""
    pass
```

#### REST API (`api.py`)
JSON API for game actions.

```python
class GameAPI:
    """
    REST API for game management.
    
    Endpoints:
    - POST /api/new_game: Start new game
    - GET /api/game_state: Get current position and status
    - POST /api/move: Make player move
    - POST /api/engine_move: Request engine move
    - POST /api/set_elo: Adjust engine strength
    - GET /api/legal_moves: Get legal moves for current position
    """
    
    def __init__(self):
        self.engine = Engine()
        self.game_state = GameState(Board())
    
    def new_game(self, player_color: str, elo: int) -> dict:
        """Start new game."""
        pass
    
    def get_game_state(self) -> dict:
        """Get current game state as JSON."""
        pass
    
    def make_move(self, move_uci: str) -> dict:
        """Make player move."""
        pass
    
    def get_engine_move(self) -> dict:
        """Get engine move."""
        pass
    
    def set_elo(self, elo: int) -> dict:
        """Set engine ELO."""
        pass
    
    def get_legal_moves(self) -> dict:
        """Get legal moves."""
        pass
```

#### Frontend (`static/`)

**index.html**: Main page structure
- Chessboard display (8x8 grid)
- Move input (click squares or type algebraic notation)
- Game controls (new game, resign, side selection)
- ELO slider (400-2400)
- Move history list
- Game status display

**app.js**: Client-side logic
- Board rendering (Unicode pieces or SVG)
- Move highlighting (legal moves, last move)
- Drag-and-drop or click-to-move
- API calls to backend
- Game state updates

**style.css**: Styling
- Chessboard appearance (light/dark squares)
- Piece styling
- Responsive layout

---

## Data Flow

### Human Move Flow
1. User clicks piece in UI
2. Frontend requests legal moves from API
3. Frontend highlights legal destination squares
4. User clicks destination
5. Frontend sends move to API
6. Backend validates and applies move
7. Backend checks game status
8. Backend returns updated state
9. Frontend updates display

### Engine Move Flow
1. Frontend requests engine move from API
2. Backend calls `engine.get_best_move(game_state)`
3. Engine searches with ELO-adjusted limits
4. Engine returns best move
5. Backend applies move and checks status
6. Backend returns move and updated state
7. Frontend animates move and updates display

### UCI Flow
1. GUI sends UCI command to stdin
2. `UCIProtocol.handle_command()` parses command
3. Protocol updates game state or calls engine
4. Protocol formats response
5. Response sent to stdout
6. GUI processes response

---

## Testing Strategy

### Unit Tests
- **test_board.py**: Board representation, FEN parsing, piece placement
- **test_moves.py**: Move generation, special moves (castling, en passant, promotion)
- **test_game_state.py**: Check detection, checkmate, stalemate, draw conditions
- **test_search.py**: Search algorithms, evaluation, move ordering
- **test_uci.py**: UCI command parsing and responses

### Integration Tests
- **test_perft.py**: Perft (performance test) for move generation validation
  - Compare node counts at various depths against known positions
  - Validates move generation correctness

### Validation Tests
- Play test games against known positions
- Verify mate-in-N puzzles are solved correctly
- Test ELO scaling (weaker settings should make mistakes)

### Test Fixtures
- Standard starting position
- Tactical positions (pins, forks, skewers)
- Endgame positions (K+Q vs K, K+R vs K)
- Special move positions (castling, en passant, promotion)
- Draw positions (stalemate, insufficient material, repetition)

---

## Interface Contracts (FROZEN)

The following type names and method signatures are **FROZEN** and may only be changed by the Integrator:

### Core Module Exports
- `Board` class with methods: `__init__`, `get_piece`, `set_piece`, `make_move`, `unmake_move`, `copy`, `to_fen`
- `Square` class with methods: `__init__`, `from_algebraic`, `to_algebraic`
- `Piece` class with methods: `__init__`, `get_value`
- `Move` class with methods: `__init__`, `to_uci`, `from_uci`, `to_algebraic`
- `GameState` class with methods: `__init__`, `get_legal_moves`, `is_legal_move`, `is_check`, `is_checkmate`, `is_stalemate`, `is_draw`, `get_game_result`

### Search Module Exports
- `Engine` class with methods: `__init__`, `set_elo`, `search`, `get_best_move`
- `SearchLimits` class
- `SearchResult` class
- `EloConfig` class with static methods: `depth_for_elo`, `noise_for_elo`, `best_move_prob_for_elo`
- `Evaluator` class with method: `evaluate`
- `Searcher` class with methods: `iterative_deepening`, `alpha_beta`, `quiescence`
- `TranspositionTable` class with methods: `store`, `probe`, `clear`

### UCI Module Exports
- `UCIProtocol` class with methods: `handle_command`, `cmd_uci`, `cmd_isready`, `cmd_ucinewgame`, `cmd_position`, `cmd_go`, `cmd_stop`

### UI Module Exports
- `start_server` function
- `GameAPI` class with methods: `new_game`, `get_game_state`, `make_move`, `get_engine_move`, `set_elo`, `get_legal_moves`

---

## Design Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Testability**: All core logic is unit-testable without external dependencies
3. **Immutability Where Possible**: Board.copy() for search, avoid hidden state mutations
4. **Type Safety**: Use type hints throughout for clarity and IDE support
5. **Performance**: Optimize hot paths (move generation, evaluation) but prioritize correctness first
6. **Extensibility**: Easy to add new evaluation terms or search enhancements

---

## Implementation Order

Recommended implementation sequence:

1. **Core Module** (Rules Specialist)
   - Board, Square, Piece, Move classes
   - FEN parsing/generation
   - Basic move generation
   - Special moves (castling, en passant, promotion)
   - Check/checkmate/stalemate detection

2. **Search Module** (Engine Specialist)
   - Basic evaluation (material + piece-square tables)
   - Minimax with alpha-beta
   - Iterative deepening
   - Move ordering
   - Quiescence search
   - Transposition table
   - ELO configuration

3. **UCI Module** (UCI Specialist)
   - Command parser
   - Protocol handler
   - Integration with engine

4. **UI Module** (UI Specialist)
   - Web server
   - REST API
   - Frontend (HTML/CSS/JS)
   - Board rendering
   - Move input

5. **Testing** (Test Specialist)
   - Unit tests for all modules
   - Perft tests
   - Integration tests

6. **Integration** (Integrator)
   - Ensure all modules work together
   - Fix interface mismatches
   - Performance tuning
   - Documentation updates

---

## Success Criteria

The architecture succeeds when:

1. ✅ All chess rules are correctly implemented (validated by perft tests)
2. ✅ Engine can play legal games at various strength levels
3. ✅ UCI protocol works with standard chess GUIs
4. ✅ Browser UI allows human vs engine play
5. ✅ ELO slider produces noticeable strength differences
6. ✅ All modules are independently testable
7. ✅ Code is clean, documented, and maintainable

---

**Architecture Approved**: Ready for implementation by specialist agents.
