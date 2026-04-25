"""UCI (Universal Chess Interface) protocol implementation.

Supports the core UCI commands needed for GUI compatibility:
- uci: identify engine
- isready: synchronization
- ucinewgame: reset engine state
- position: set up position (startpos or FEN, with optional moves)
- go: start searching (depth, movetime, wtime/btime)
- stop: stop searching
- quit: exit
- setoption: set engine options (Skill Level / ELO)
"""

import sys
import threading
from typing import Optional
from engines.oneshot_nocontext.core.board import Board
from engines.oneshot_nocontext.core.types import Move, PieceType
from engines.oneshot_nocontext.search.engine import Engine


ENGINE_NAME = "PointChess"
ENGINE_AUTHOR = "PointChess Team"


class UCIProtocol:
    def __init__(self, input_stream=None, output_stream=None):
        self.board = Board()
        self.engine = Engine(elo=1500)
        self.input_stream = input_stream or sys.stdin
        self.output_stream = output_stream or sys.stdout
        self.search_thread: Optional[threading.Thread] = None
        self.running = True

    def send(self, msg: str):
        self.output_stream.write(msg + '\n')
        self.output_stream.flush()

    def run(self):
        """Main UCI loop - read commands from stdin."""
        while self.running:
            try:
                line = self.input_stream.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    self._handle_command(line)
            except EOFError:
                break

    def _handle_command(self, line: str):
        parts = line.split()
        cmd = parts[0] if parts else ''

        if cmd == 'uci':
            self._cmd_uci()
        elif cmd == 'isready':
            self.send('readyok')
        elif cmd == 'ucinewgame':
            self.engine.clear()
            self.board = Board()
        elif cmd == 'position':
            self._cmd_position(parts[1:])
        elif cmd == 'go':
            self._cmd_go(parts[1:])
        elif cmd == 'stop':
            self.engine.stop_search = True
        elif cmd == 'quit':
            self.engine.stop_search = True
            self.running = False
        elif cmd == 'setoption':
            self._cmd_setoption(parts[1:])
        elif cmd == 'd':
            # Debug: display board
            self.send(str(self.board))
            self.send(f'FEN: {self.board.to_fen()}')

    def _cmd_uci(self):
        self.send(f'id name {ENGINE_NAME}')
        self.send(f'id author {ENGINE_AUTHOR}')
        self.send('option name Skill Level type spin default 1500 min 400 max 2400')
        self.send('option name UCI_Elo type spin default 1500 min 400 max 2400')
        self.send('uciok')

    def _cmd_position(self, args: list):
        if not args:
            return

        move_idx = None
        if args[0] == 'startpos':
            self.board = Board()
            if len(args) > 1 and args[1] == 'moves':
                move_idx = 2
        elif args[0] == 'fen':
            # Find where 'moves' keyword is, or take all remaining as FEN
            fen_parts = []
            for i, arg in enumerate(args[1:], 1):
                if arg == 'moves':
                    move_idx = i + 1
                    break
                fen_parts.append(arg)
            fen = ' '.join(fen_parts)
            self.board = Board(fen)

        # Apply moves
        if move_idx is not None:
            for uci_move in args[move_idx:]:
                move = Move.from_uci(uci_move)
                # Find matching legal move (to handle promotions correctly)
                legal = self.board.legal_moves()
                matched = None
                for m in legal:
                    if m.from_sq == move.from_sq and m.to_sq == move.to_sq:
                        if move.promotion is None or m.promotion == move.promotion:
                            matched = m
                            break
                if matched:
                    self.board.make_move(matched)

    def _cmd_go(self, args: list):
        """Handle go command with various time control options."""
        max_depth = None
        move_time = None
        wtime = None
        btime = None

        i = 0
        while i < len(args):
            if args[i] == 'depth' and i + 1 < len(args):
                max_depth = int(args[i + 1])
                i += 2
            elif args[i] == 'movetime' and i + 1 < len(args):
                move_time = int(args[i + 1]) / 1000.0  # ms to seconds
                i += 2
            elif args[i] == 'wtime' and i + 1 < len(args):
                wtime = int(args[i + 1])
                i += 2
            elif args[i] == 'btime' and i + 1 < len(args):
                btime = int(args[i + 1])
                i += 2
            elif args[i] == 'infinite':
                max_depth = 99
                move_time = 3600
                i += 1
            else:
                i += 1

        # Calculate time limit
        time_limit = move_time
        if time_limit is None and (wtime or btime):
            # Use ~2% of remaining time
            from engines.oneshot_nocontext.core.types import Color
            remaining = wtime if self.board.turn == Color.WHITE else btime
            if remaining:
                time_limit = remaining / 1000.0 / 40  # assume 40 moves left
                time_limit = min(time_limit, 10.0)

        def do_search():
            move, score = self.engine.search(
                self.board,
                max_depth=max_depth,
                time_limit=time_limit
            )
            if move:
                info = self.engine.get_info()
                self.send(f"info depth {max_depth or self.engine.settings.max_depth} "
                         f"nodes {info['nodes']} "
                         f"time {info['time_ms']} "
                         f"nps {info['nps']} "
                         f"score cp {score}")
                self.send(f"bestmove {move.uci()}")
            else:
                self.send("bestmove 0000")

        self.search_thread = threading.Thread(target=do_search, daemon=True)
        self.search_thread.start()

    def _cmd_setoption(self, args: list):
        """Handle setoption name <name> value <value>."""
        # Parse: name <words> value <val>
        name_parts = []
        value = None
        i = 0
        reading_name = False
        reading_value = False

        for arg in args:
            if arg == 'name':
                reading_name = True
                reading_value = False
                continue
            elif arg == 'value':
                reading_name = False
                reading_value = True
                continue

            if reading_name:
                name_parts.append(arg)
            elif reading_value:
                value = arg

        name = ' '.join(name_parts).lower()

        if name in ('skill level', 'uci_elo') and value is not None:
            try:
                elo = int(value)
                self.engine.set_elo(elo)
            except ValueError:
                pass


def main():
    """Entry point for UCI mode."""
    protocol = UCIProtocol()
    protocol.run()


if __name__ == '__main__':
    main()
