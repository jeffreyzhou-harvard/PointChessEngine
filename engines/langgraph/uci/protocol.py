"""
UCI protocol command handler.

Implements the Universal Chess Interface protocol for chess engine communication.
Supports: uci, isready, ucinewgame, position, go, stop, quit, setoption.
"""

import threading
import time
from typing import Optional, List

from core.board import Board
from core.game_state import GameState
from core.move import Move
from search.engine import Engine
from search.search import SearchLimits, SearchResult


class UCIProtocol:
    """
    UCI protocol handler.
    
    Manages communication between UCI interface and chess engine.
    Handles command parsing, engine control, and response formatting.
    
    Attributes:
        engine: Engine instance
        game_state: Current game state
        search_thread: Background thread for search
        stop_flag: Flag to stop ongoing search
    """
    
    def __init__(self):
        """Initialize UCI protocol handler."""
        self.engine = Engine(elo_rating=1500)
        self.board = Board()
        self.game_state = GameState(self.board)
        self.search_thread: Optional[threading.Thread] = None
        self.stop_flag = False
        self.search_result: Optional[SearchResult] = None
        self.debug_mode = False
    
    def handle_command(self, command: str) -> Optional[str]:
        """
        Handle a UCI command.
        
        Args:
            command: UCI command string
        
        Returns:
            Response string (if any), or None for quit command
        """
        command = command.strip()
        if not command:
            return ""
        
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "uci":
            return self._handle_uci()
        elif cmd == "isready":
            return self._handle_isready()
        elif cmd == "ucinewgame":
            return self._handle_ucinewgame()
        elif cmd == "position":
            return self._handle_position(parts[1:])
        elif cmd == "go":
            return self._handle_go(parts[1:])
        elif cmd == "stop":
            return self._handle_stop()
        elif cmd == "quit":
            return None  # Signal to quit
        elif cmd == "setoption":
            return self._handle_setoption(parts[1:])
        elif cmd == "debug":
            return self._handle_debug(parts[1:])
        else:
            if self.debug_mode:
                return f"info string Unknown command: {cmd}"
            return ""
    
    def _handle_uci(self) -> str:
        """
        Handle 'uci' command - identify engine.
        
        Returns:
            Engine identification string
        """
        response = []
        response.append("id name ChessEngine v1.0")
        response.append("id author Chess Engine Team")
        response.append("option name ELO type spin default 1500 min 400 max 2400")
        response.append("option name Hash type spin default 64 min 1 max 1024")
        response.append("uciok")
        return "\n".join(response)
    
    def _handle_isready(self) -> str:
        """
        Handle 'isready' command - synchronization.
        
        Returns:
            'readyok'
        """
        return "readyok"
    
    def _handle_ucinewgame(self) -> str:
        """
        Handle 'ucinewgame' command - reset for new game.
        
        Returns:
            Empty string
        """
        self.engine.new_game()
        self.board = Board()
        self.game_state = GameState(self.board)
        return ""
    
    def _handle_position(self, args: List[str]) -> str:
        """
        Handle 'position' command - set position.
        
        Formats:
        - position startpos
        - position startpos moves e2e4 e7e5
        - position fen <fen_string>
        - position fen <fen_string> moves e2e4 e7e5
        
        Args:
            args: Command arguments
        
        Returns:
            Empty string or error message
        """
        if not args:
            return "info string Error: position command requires arguments"
        
        try:
            # Parse position type
            if args[0] == "startpos":
                self.board = Board()
                self.game_state = GameState(self.board)
                move_index = 1
            elif args[0] == "fen":
                # Find where moves start (if any)
                move_index = None
                for i, arg in enumerate(args):
                    if arg == "moves":
                        move_index = i
                        break
                
                if move_index is None:
                    # No moves, entire rest is FEN
                    fen = " ".join(args[1:])
                    move_index = len(args)
                else:
                    # FEN is between 'fen' and 'moves'
                    fen = " ".join(args[1:move_index])
                
                self.board = Board(fen)
                self.game_state = GameState(self.board)
            else:
                return f"info string Error: unknown position type '{args[0]}'"
            
            # Apply moves if present
            if move_index < len(args) and args[move_index] == "moves":
                for move_str in args[move_index + 1:]:
                    try:
                        move = Move.from_uci(move_str)
                        
                        # Verify move is legal
                        legal_moves = self.game_state.get_legal_moves()
                        if move not in legal_moves:
                            return f"info string Error: illegal move '{move_str}'"
                        
                        self.board.make_move(move)
                    except ValueError as e:
                        return f"info string Error: invalid move '{move_str}': {e}"
            
            return ""
        
        except Exception as e:
            return f"info string Error in position command: {e}"
    
    def _handle_go(self, args: List[str]) -> str:
        """
        Handle 'go' command - start search.
        
        Supported parameters:
        - infinite: search until 'stop' command
        - depth <n>: search to depth n
        - movetime <ms>: search for exactly ms milliseconds
        - wtime <ms>: white time remaining
        - btime <ms>: black time remaining
        - winc <ms>: white increment per move
        - binc <ms>: black increment per move
        - movestogo <n>: moves until next time control
        
        Args:
            args: Command arguments
        
        Returns:
            Empty string (search runs in background)
        """
        # Stop any ongoing search
        if self.search_thread and self.search_thread.is_alive():
            self.stop_flag = True
            self.search_thread.join(timeout=1.0)
        
        # Parse search parameters
        limits = self._parse_go_params(args)
        
        # Start search in background thread
        self.stop_flag = False
        self.search_result = None
        self.search_thread = threading.Thread(
            target=self._search_worker,
            args=(limits,),
            daemon=True
        )
        self.search_thread.start()
        
        return ""
    
    def _parse_go_params(self, args: List[str]) -> SearchLimits:
        """
        Parse 'go' command parameters.
        
        Args:
            args: Command arguments
        
        Returns:
            SearchLimits instance
        """
        infinite = False
        max_depth = None
        max_time_ms = None
        wtime = None
        btime = None
        winc = 0
        binc = 0
        movestogo = None
        
        i = 0
        while i < len(args):
            param = args[i]
            
            if param == "infinite":
                infinite = True
                i += 1
            elif param == "depth" and i + 1 < len(args):
                max_depth = int(args[i + 1])
                i += 2
            elif param == "movetime" and i + 1 < len(args):
                max_time_ms = int(args[i + 1])
                i += 2
            elif param == "wtime" and i + 1 < len(args):
                wtime = int(args[i + 1])
                i += 2
            elif param == "btime" and i + 1 < len(args):
                btime = int(args[i + 1])
                i += 2
            elif param == "winc" and i + 1 < len(args):
                winc = int(args[i + 1])
                i += 2
            elif param == "binc" and i + 1 < len(args):
                binc = int(args[i + 1])
                i += 2
            elif param == "movestogo" and i + 1 < len(args):
                movestogo = int(args[i + 1])
                i += 2
            else:
                i += 1
        
        # Calculate time allocation if time controls given
        if max_time_ms is None and (wtime is not None or btime is not None):
            # Use time for current side
            time_remaining = wtime if self.board.active_color == 'white' else btime
            increment = winc if self.board.active_color == 'white' else binc
            
            if time_remaining is not None:
                # Simple time management: use 1/30 of remaining time + increment
                if movestogo:
                    # Time control with moves to go
                    max_time_ms = (time_remaining // movestogo) + increment
                else:
                    # Sudden death or increment
                    max_time_ms = (time_remaining // 30) + increment
                
                # Ensure minimum time
                max_time_ms = max(100, max_time_ms)
                # Cap at 1/3 of remaining time
                max_time_ms = min(max_time_ms, time_remaining // 3)
        
        return SearchLimits(
            max_depth=max_depth,
            max_time_ms=max_time_ms,
            infinite=infinite
        )
    
    def _search_worker(self, limits: SearchLimits) -> None:
        """
        Background worker for search.
        
        Args:
            limits: Search limits
        """
        try:
            # Perform search with periodic stop checks
            result = self._search_with_stop_check(limits)
            
            if not self.stop_flag and result and result.best_move:
                # Output search info
                self._output_search_info(result)
                
                # Output best move
                print(f"bestmove {result.best_move.to_uci()}", flush=True)
            elif result and result.best_move:
                # Stopped early but have a move
                print(f"bestmove {result.best_move.to_uci()}", flush=True)
            else:
                # No legal moves (shouldn't happen normally)
                print("bestmove 0000", flush=True)
        
        except Exception as e:
            if self.debug_mode:
                print(f"info string Error in search: {e}", flush=True)
            print("bestmove 0000", flush=True)
    
    def _search_with_stop_check(self, limits: SearchLimits) -> Optional[SearchResult]:
        """
        Perform search with periodic stop flag checks.
        
        Args:
            limits: Search limits
        
        Returns:
            SearchResult or None
        """
        # Monkey-patch the searcher's stop check to use our flag
        original_should_stop = self.engine.searcher._should_stop
        
        def should_stop_with_flag(lim):
            return self.stop_flag or original_should_stop(lim)
        
        self.engine.searcher._should_stop = should_stop_with_flag
        
        try:
            result = self.engine.search(self.game_state, limits)
            return result
        finally:
            # Restore original method
            self.engine.searcher._should_stop = original_should_stop
    
    def _output_search_info(self, result: SearchResult) -> None:
        """
        Output search information in UCI format.
        
        Args:
            result: Search result
        """
        # Format: info depth <d> score cp <score> nodes <n> time <ms> pv <moves>
        info_parts = ["info"]
        info_parts.append(f"depth {result.depth}")
        
        # Format score
        if abs(result.score) > 90000:
            # Mate score
            mate_in = (100000 - abs(result.score) + 1) // 2
            if result.score < 0:
                mate_in = -mate_in
            info_parts.append(f"score mate {mate_in}")
        else:
            info_parts.append(f"score cp {result.score}")
        
        info_parts.append(f"nodes {result.nodes}")
        info_parts.append(f"time {result.time_ms}")
        
        # Add PV if available
        if result.pv:
            pv_str = " ".join(m.to_uci() for m in result.pv)
            info_parts.append(f"pv {pv_str}")
        
        print(" ".join(info_parts), flush=True)
    
    def _handle_stop(self) -> str:
        """
        Handle 'stop' command - halt search.
        
        Returns:
            Empty string
        """
        self.stop_flag = True
        
        # Wait for search thread to finish (with timeout)
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.join(timeout=2.0)
        
        return ""
    
    def _handle_setoption(self, args: List[str]) -> str:
        """
        Handle 'setoption' command - set engine option.
        
        Format: setoption name <name> value <value>
        
        Args:
            args: Command arguments
        
        Returns:
            Empty string or error message
        """
        if len(args) < 4 or args[0] != "name":
            return "info string Error: setoption format: name <name> value <value>"
        
        # Find 'value' keyword
        try:
            value_index = args.index("value")
        except ValueError:
            return "info string Error: setoption requires 'value' keyword"
        
        # Extract name and value
        name = " ".join(args[1:value_index]).lower()
        value_str = " ".join(args[value_index + 1:])
        
        try:
            if name == "elo":
                elo = int(value_str)
                if 400 <= elo <= 2400:
                    self.engine.set_elo(elo)
                    if self.debug_mode:
                        return f"info string ELO set to {elo}"
                else:
                    return f"info string Error: ELO must be between 400 and 2400"
            elif name == "hash":
                # Hash table size (not fully implemented, but accept the command)
                hash_mb = int(value_str)
                if 1 <= hash_mb <= 1024:
                    # Could resize transposition table here
                    if self.debug_mode:
                        return f"info string Hash size set to {hash_mb} MB"
                else:
                    return f"info string Error: Hash must be between 1 and 1024 MB"
            else:
                return f"info string Error: unknown option '{name}'"
        
        except ValueError:
            return f"info string Error: invalid value '{value_str}'"
        
        return ""
    
    def _handle_debug(self, args: List[str]) -> str:
        """
        Handle 'debug' command - toggle debug mode.
        
        Args:
            args: Command arguments (on/off)
        
        Returns:
            Empty string
        """
        if args and args[0].lower() == "on":
            self.debug_mode = True
        elif args and args[0].lower() == "off":
            self.debug_mode = False
        
        return ""


def run_uci() -> None:
    """
    Run UCI protocol loop.
    
    Reads commands from stdin and outputs responses to stdout.
    Runs until 'quit' command is received.
    """
    protocol = UCIProtocol()
    
    while True:
        try:
            # Read command from stdin
            command = input()
            
            # Handle command
            response = protocol.handle_command(command)
            
            # Check for quit
            if response is None:
                break
            
            # Output response
            if response:
                print(response, flush=True)
        
        except EOFError:
            # End of input
            break
        except KeyboardInterrupt:
            # Ctrl+C
            break
        except Exception as e:
            if protocol.debug_mode:
                print(f"info string Error: {e}", flush=True)
