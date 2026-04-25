# Chess Engine UI Guide

## Overview

The chess engine includes a browser-based user interface for playing against the engine. The UI is built with vanilla HTML/CSS/JavaScript and requires no build step.

## Features

- **Interactive Chessboard**: Click-to-move interface with visual feedback
- **Side Selection**: Choose to play as White or Black
- **ELO Strength Slider**: Adjust engine strength from 400 to 2400 ELO
- **Move History**: View all moves in algebraic notation
- **Game Controls**: New game, resign, and status display
- **Pawn Promotion**: Modal dialog for selecting promotion piece
- **Legal Move Highlighting**: Visual indicators for legal moves and captures
- **Check Indication**: Visual feedback when king is in check

## Starting the Server

### Command Line

```bash
python -m ui.server
```

By default, the server starts on `http://127.0.0.1:8000/`

### Custom Port

```bash
python -m ui.server --port 8080
```

### Programmatic Usage

```python
from ui import start_server

start_server(port=8000, host='127.0.0.1')
```

## Using the UI

### Starting a Game

1. Open your browser to `http://127.0.0.1:8000/`
2. Select your color (White or Black)
3. Adjust the ELO slider to set engine strength
4. Click "New Game" to start

### Making Moves

1. Click on a piece to select it
2. Legal moves will be highlighted:
   - Small dots for empty squares
   - Red rings for captures
3. Click on a highlighted square to make the move
4. For pawn promotion, a modal will appear to select the piece

### Game Controls

- **New Game**: Start a fresh game with current settings
- **Resign**: Forfeit the current game
- **ELO Slider**: Adjust engine strength (takes effect immediately)
- **Move History**: Scrollable list of all moves played

### Game Status

The status panel shows:
- Current player to move
- Check/checkmate/stalemate notifications
- Game result when finished
- "Engine thinking..." indicator during engine moves

## API Endpoints

The server exposes a JSON API for programmatic access:

### GET /api/status

Get current game state.

**Response:**
```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "active_color": "white",
  "human_color": "white",
  "is_human_turn": true,
  "is_check": false,
  "is_checkmate": false,
  "is_stalemate": false,
  "is_draw": false,
  "result": null,
  "legal_moves": ["e2e4", "e2e3", ...],
  "move_list": [],
  "elo_rating": 1500,
  "halfmove_clock": 0,
  "fullmove_number": 1,
  "message": "",
  "board": [[...], ...]
}
```

### GET /api/legal_moves?square=e2

Get legal moves from a specific square.

**Response:**
```json
{
  "legal_moves": ["e2e3", "e2e4"]
}
```

### POST /api/new_game

Start a new game.

**Request:**
```json
{
  "human_color": "white",
  "elo_rating": 1500
}
```

**Response:** Same as GET /api/status

### POST /api/move

Make a move.

**Request:**
```json
{
  "move": "e2e4"
}
```

**Response:** Same as GET /api/status

### POST /api/engine_move

Request engine to make a move.

**Request:**
```json
{
  "time_ms": 2000
}
```

**Response:** Same as GET /api/status, plus:
```json
{
  "engine_move": "e7e5",
  ...
}
```

### POST /api/set_elo

Adjust engine strength.

**Request:**
```json
{
  "elo_rating": 1800
}
```

**Response:**
```json
{
  "elo_rating": 1800,
  "message": "Engine strength set to 1800"
}
```

### POST /api/resign

Human player resigns.

**Response:** Same as GET /api/status with result set

## Architecture

### Components

1. **ui/session.py**: Game session management
   - Wraps GameState and Engine
   - Provides clean API for UI operations
   - Manages game lifecycle

2. **ui/server.py**: HTTP server
   - ThreadingHTTPServer for concurrent requests
   - JSON API endpoints
   - Static file serving

3. **ui/static/index.html**: Browser UI
   - Single-page application
   - Vanilla JavaScript (no frameworks)
   - Responsive design

### Data Flow

```
Browser UI
    ↓ (HTTP/JSON)
Server API
    ↓ (Python calls)
GameSession
    ↓
GameState + Engine
    ↓
Core chess logic
```

## Customization

### Styling

Edit `ui/static/index.html` to customize:
- Colors and gradients
- Board size and piece symbols
- Layout and spacing
- Fonts and typography

### API Extensions

Add new endpoints in `ui/server.py`:

```python
def _handle_custom_endpoint(self) -> None:
    """Custom endpoint handler."""
    # Your logic here
    self._send_json({'result': 'success'})
```

Register in `do_POST` or `do_GET`:

```python
elif path == '/api/custom':
    self._handle_custom_endpoint()
```

### Session Management

Extend `GameSession` in `ui/session.py` for additional features:

```python
def custom_feature(self) -> Any:
    """Custom feature implementation."""
    # Your logic here
    return result
```

## Performance

- Engine moves are computed in the request thread
- Typical response time: 100ms - 3s depending on ELO
- No database or persistent storage
- Single game session per server instance

## Limitations

- Single-user application (one game at a time)
- No authentication or user management
- No game saving/loading
- No opening book or endgame tablebases
- No analysis mode or hints

## Future Enhancements

Possible improvements:
- Multi-user support with session management
- Game database and PGN export
- Analysis board with engine evaluation
- Opening book integration
- Time controls and clock display
- Undo/redo functionality
- Board themes and piece sets

## Troubleshooting

### Server won't start

- Check if port is already in use
- Try a different port: `python -m ui.server --port 8080`
- Check firewall settings

### Moves not working

- Check browser console for JavaScript errors
- Verify server is running and accessible
- Try refreshing the page

### Engine too slow/fast

- Adjust ELO slider (lower = faster, weaker)
- Modify time_ms in engine_move API call
- Check system resources

### UI not loading

- Verify `ui/static/index.html` exists
- Check server logs for errors
- Try accessing `http://127.0.0.1:8000/` directly

## Development

### Running Tests

```bash
pytest tests/test_ui_session.py -v
pytest tests/test_ui_server.py -v
```

### Adding Features

1. Implement in `GameSession` (business logic)
2. Add API endpoint in `server.py`
3. Update UI in `index.html`
4. Add tests in `tests/test_ui_*.py`
5. Document in this guide

### Debugging

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check browser console for client-side errors.

## License

Part of the chess engine project. See main README for license information.
