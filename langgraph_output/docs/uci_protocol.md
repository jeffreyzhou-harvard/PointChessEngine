# UCI Protocol Implementation

## Overview

The UCI (Universal Chess Interface) module provides a standard interface for chess GUIs to communicate with the chess engine. It implements the UCI protocol specification, allowing the engine to work with any UCI-compatible chess GUI.

## Usage

### Running the Engine in UCI Mode

```bash
python -m uci.main
```

The engine will read UCI commands from stdin and output responses to stdout.

### Supported Commands

#### Engine Identification

- **uci**: Identify the engine and list available options
  ```
  uci
  ```
  Response:
  ```
  id name ChessEngine v1.0
  id author Chess Engine Team
  option name ELO type spin default 1500 min 400 max 2400
  option name Hash type spin default 64 min 1 max 1024
  uciok
  ```

- **isready**: Synchronization command
  ```
  isready
  ```
  Response:
  ```
  readyok
  ```

#### Game Management

- **ucinewgame**: Reset engine for a new game
  ```
  ucinewgame
  ```

- **position**: Set up the board position
  ```
  position startpos
  position startpos moves e2e4 e7e5
  position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
  position fen <fen_string> moves e2e4 e7e5
  ```

#### Search Control

- **go**: Start searching for the best move
  
  Options:
  - `depth <n>`: Search to depth n
  - `movetime <ms>`: Search for exactly ms milliseconds
  - `infinite`: Search until 'stop' command
  - `wtime <ms>`: White's remaining time in milliseconds
  - `btime <ms>`: Black's remaining time in milliseconds
  - `winc <ms>`: White's increment per move
  - `binc <ms>`: Black's increment per move
  - `movestogo <n>`: Moves until next time control
  
  Examples:
  ```
  go depth 10
  go movetime 5000
  go infinite
  go wtime 60000 btime 60000 winc 1000 binc 1000
  ```
  
  Response (during search):
  ```
  info depth 5 score cp 25 nodes 12345 time 1234 pv e2e4 e7e5 g1f3
  bestmove e2e4
  ```

- **stop**: Stop the current search
  ```
  stop
  ```

#### Engine Options

- **setoption**: Set engine options
  ```
  setoption name ELO value 1500
  setoption name Hash value 128
  ```

#### Other Commands

- **debug**: Toggle debug mode
  ```
  debug on
  debug off
  ```

- **quit**: Exit the engine
  ```
  quit
  ```

## Engine Options

### ELO Rating

Adjusts the playing strength of the engine.

- **Type**: spin (integer)
- **Default**: 1500
- **Range**: 400-2400
- **Description**: Sets the engine's playing strength. Lower values make the engine play weaker, higher values make it play stronger.

Example:
```
setoption name ELO value 1200
```

### Hash Table Size

Sets the size of the transposition table.

- **Type**: spin (integer)
- **Default**: 64
- **Range**: 1-1024
- **Unit**: Megabytes
- **Description**: Size of the hash table used for position caching.

Example:
```
setoption name Hash value 256
```

## Search Information Output

During search, the engine outputs information in UCI format:

```
info depth <d> score cp <score> nodes <n> time <ms> pv <moves>
```

- **depth**: Current search depth
- **score cp**: Evaluation in centipawns (100 = 1 pawn advantage)
- **score mate**: Mate in n moves (positive = we're mating, negative = we're being mated)
- **nodes**: Number of positions searched
- **time**: Time spent searching in milliseconds
- **pv**: Principal variation (best line of play)

Example:
```
info depth 8 score cp 45 nodes 125678 time 2345 pv e2e4 e7e5 g1f3 b8c6 f1c4
```

## Integration with Chess GUIs

The engine can be used with any UCI-compatible chess GUI, such as:

- Arena Chess GUI
- ChessBase
- Cute Chess
- PyChess
- Scid

### Configuration in Arena

1. Open Arena
2. Go to Engines → Install New Engine
3. Browse to the engine executable or Python script
4. Select UCI protocol
5. Configure engine options (ELO, Hash) in the engine settings

### Configuration in Cute Chess

1. Open Cute Chess
2. Go to Tools → Settings → Engines
3. Click "Add"
4. Set command: `python -m uci.main`
5. Set working directory to project root
6. Protocol: UCI
7. Click OK

## Example UCI Session

```
> uci
id name ChessEngine v1.0
id author Chess Engine Team
option name ELO type spin default 1500 min 400 max 2400
option name Hash type spin default 64 min 1 max 1024
uciok

> isready
readyok

> setoption name ELO value 1800

> ucinewgame

> position startpos

> go depth 8
info depth 1 score cp 25 nodes 20 time 1 pv e2e4
info depth 2 score cp 10 nodes 120 time 5 pv e2e4 e7e5
info depth 3 score cp 30 nodes 850 time 25 pv e2e4 e7e5 g1f3
info depth 4 score cp 15 nodes 3200 time 95 pv e2e4 e7e5 g1f3 b8c6
info depth 5 score cp 25 nodes 12000 time 350 pv e2e4 e7e5 g1f3 b8c6 f1c4
bestmove e2e4

> position startpos moves e2e4 e7e5

> go movetime 3000
info depth 1 score cp -20 nodes 20 time 1 pv g1f3
info depth 2 score cp -15 nodes 180 time 8 pv g1f3 b8c6
info depth 3 score cp -25 nodes 1200 time 45 pv g1f3 b8c6 f1c4
bestmove g1f3

> quit
```

## Thread Safety

The UCI implementation uses background threads for search operations:

- Search runs in a separate thread to allow the 'stop' command to interrupt it
- The main thread continues to read commands while search is running
- Thread-safe stop mechanism ensures clean search termination

## Error Handling

The engine handles various error conditions gracefully:

- Invalid UCI notation: Returns error message
- Illegal moves: Returns error message
- Malformed commands: Returns error message or ignores
- Missing parameters: Returns error message

In debug mode (`debug on`), more detailed error messages are provided.

## Performance Considerations

### Time Management

When using time controls (`wtime`, `btime`), the engine uses a simple time management strategy:

- With `movestogo`: Allocates `time_remaining / movestogo + increment`
- Without `movestogo`: Allocates `time_remaining / 30 + increment`
- Minimum allocation: 100ms
- Maximum allocation: 1/3 of remaining time

### Search Depth

The engine supports iterative deepening up to depth 100. Practical search depths depend on:

- Position complexity
- Time available
- ELO setting (lower ELO = shallower search)

### Node Count

The engine can search millions of nodes per second, depending on:

- CPU speed
- Position complexity
- Transposition table hit rate

## Implementation Details

### Architecture

- **UCIProtocol**: Main protocol handler class
- **Background Search**: Search runs in separate thread
- **Stop Mechanism**: Thread-safe flag for search interruption
- **Engine Integration**: Direct integration with Engine class

### Key Features

1. **Full UCI Compliance**: Implements all essential UCI commands
2. **Background Search**: Non-blocking search with stop support
3. **ELO Adjustment**: Dynamic strength adjustment during play
4. **Time Management**: Intelligent time allocation for time controls
5. **Error Handling**: Robust error handling and reporting
6. **Thread Safety**: Safe concurrent operation

### Files

- `uci/protocol.py`: UCI protocol implementation
- `uci/__init__.py`: Module exports
- `uci/main.py`: Entry point for UCI mode
- `tests/test_uci.py`: Comprehensive test suite

## Testing

Run the UCI tests:

```bash
pytest tests/test_uci.py -v
```

The test suite covers:

- UCI handshake
- Position setup (startpos, FEN, moves)
- Search commands (go with various parameters)
- Stop functionality
- Engine options (ELO, Hash)
- Error handling
- Concurrent operations
- Complete game sessions

## Future Enhancements

Potential improvements for future versions:

1. **Additional UCI Options**:
   - Threads (multi-threaded search)
   - Ponder (thinking on opponent's time)
   - MultiPV (show multiple best lines)

2. **Enhanced Time Management**:
   - More sophisticated time allocation
   - Time management based on position complexity

3. **Search Features**:
   - Pondering support
   - Multi-PV output
   - Selective depth reporting

4. **Performance**:
   - Parallel search
   - Optimized move generation
   - Larger transposition tables
