"""
Search algorithms.

Implements:
- Searcher class
- Minimax with alpha-beta pruning
- Iterative deepening
- Quiescence search
- Move ordering
"""

from typing import List, Optional, Tuple
import time

from core.board import Board
from core.game_state import GameState
from core.move import Move
from .evaluation import Evaluator
from .transposition import TranspositionTable


# Constants
MATE_SCORE = 100000
MAX_DEPTH = 100


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
        """
        Initialize search limits.
        
        Args:
            max_depth: Maximum search depth
            max_time_ms: Maximum time in milliseconds
            max_nodes: Maximum nodes to search
            infinite: Search until stopped
        """
        self.max_depth = max_depth
        self.max_time_ms = max_time_ms
        self.max_nodes = max_nodes
        self.infinite = infinite


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
        """
        Initialize search result.
        
        Args:
            best_move: Best move found
            score: Evaluation in centipawns
            depth: Depth reached
            nodes: Nodes searched
            time_ms: Time taken in milliseconds
            pv: Principal variation (list of moves)
        """
        self.best_move = best_move
        self.score = score
        self.depth = depth
        self.nodes = nodes
        self.time_ms = time_ms
        self.pv = pv
    
    def __str__(self) -> str:
        """String representation."""
        pv_str = ' '.join(m.to_uci() for m in self.pv[:5])
        return (f"SearchResult(move={self.best_move.to_uci()}, score={self.score}, "
                f"depth={self.depth}, nodes={self.nodes}, time={self.time_ms}ms, pv={pv_str})")


class Searcher:
    """
    Search implementation (minimax, alpha-beta, iterative deepening).
    
    Attributes:
        evaluator: Evaluator
        transposition_table: TranspositionTable
    """
    
    def __init__(self, evaluator: Evaluator, transposition_table: TranspositionTable = None):
        """
        Initialize searcher.
        
        Args:
            evaluator: Position evaluator
            transposition_table: Optional transposition table
        """
        self.evaluator = evaluator
        self.transposition_table = transposition_table or TranspositionTable()
        self.nodes_searched = 0
        self.start_time = 0
        self.stop_search = False
    
    def iterative_deepening(self, game_state: GameState, 
                           limits: SearchLimits) -> SearchResult:
        """
        Iterative deepening search.
        
        Args:
            game_state: Current game state
            limits: Search limits
        
        Returns:
            SearchResult with best move and analysis
        """
        self.nodes_searched = 0
        self.start_time = time.time()
        self.stop_search = False
        
        best_move = None
        best_score = 0
        best_pv = []
        max_depth_reached = 0
        
        # Get legal moves
        legal_moves = game_state.get_legal_moves()
        if not legal_moves:
            # No legal moves (checkmate or stalemate)
            return SearchResult(None, 0, 0, 0, 0, [])
        
        # If only one legal move, return it immediately
        if len(legal_moves) == 1:
            return SearchResult(legal_moves[0], 0, 1, 1, 1, [legal_moves[0]])
        
        # Determine max depth
        if limits.max_depth:
            max_depth = min(limits.max_depth, MAX_DEPTH)
        else:
            max_depth = MAX_DEPTH
        
        # Iterative deepening
        for depth in range(1, max_depth + 1):
            if self._should_stop(limits):
                break
            
            pv = []
            score = self.alpha_beta_root(game_state, depth, pv)
            
            if self.stop_search:
                break
            
            # Update best move
            if pv:
                best_move = pv[0]
                best_score = score
                best_pv = pv
                max_depth_reached = depth
        
        elapsed_ms = int((time.time() - self.start_time) * 1000)
        
        return SearchResult(
            best_move=best_move,
            score=best_score,
            depth=max_depth_reached,
            nodes=self.nodes_searched,
            time_ms=elapsed_ms,
            pv=best_pv
        )
    
    def alpha_beta_root(self, game_state: GameState, depth: int, pv: List[Move]) -> int:
        """
        Alpha-beta search at root (returns PV).
        
        Args:
            game_state: Current game state
            depth: Search depth
            pv: Principal variation (output)
        
        Returns:
            Best score
        """
        alpha = -MATE_SCORE
        beta = MATE_SCORE
        best_score = -MATE_SCORE
        best_move = None
        
        legal_moves = game_state.get_legal_moves()
        ordered_moves = self.order_moves(legal_moves, game_state.board, None)
        
        for move in ordered_moves:
            if self._should_stop(None):
                break
            
            game_state.board.make_move(move)
            child_pv = []
            score = -self.alpha_beta(game_state, depth - 1, -beta, -alpha, child_pv)
            game_state.board.unmake_move(move)
            
            if score > best_score:
                best_score = score
                best_move = move
                pv.clear()
                pv.append(move)
                pv.extend(child_pv)
            
            alpha = max(alpha, score)
        
        return best_score
    
    def alpha_beta(self, game_state: GameState, depth: int,
                   alpha: int, beta: int, pv: List[Move]) -> int:
        """
        Alpha-beta search.
        
        Args:
            game_state: Current game state
            depth: Remaining search depth
            alpha: Alpha value (lower bound)
            beta: Beta value (upper bound)
            pv: Principal variation (output)
        
        Returns:
            Position score
        """
        self.nodes_searched += 1
        
        # Check time limit periodically
        if self.nodes_searched % 1000 == 0:
            if self._should_stop(None):
                self.stop_search = True
                return 0
        
        # Check for simple draws (skip threefold repetition check during search for performance)
        if game_state.is_stalemate() or game_state._is_fifty_move_draw() or game_state.is_insufficient_material():
            return 0
        
        # Terminal node (depth 0 or checkmate)
        if depth <= 0:
            return self.quiescence(game_state, alpha, beta)
        
        # Check transposition table
        position_hash = self.transposition_table.hash_position(game_state.board)
        tt_entry = self.transposition_table.probe(position_hash)
        
        if tt_entry and tt_entry['depth'] >= depth:
            if tt_entry['node_type'] == TranspositionTable.EXACT:
                return tt_entry['score']
            elif tt_entry['node_type'] == TranspositionTable.LOWER_BOUND:
                alpha = max(alpha, tt_entry['score'])
            elif tt_entry['node_type'] == TranspositionTable.UPPER_BOUND:
                beta = min(beta, tt_entry['score'])
            
            if alpha >= beta:
                return tt_entry['score']
        
        # Get legal moves
        legal_moves = game_state.get_legal_moves()
        
        # Checkmate or stalemate
        if not legal_moves:
            if game_state.is_check():
                return -MATE_SCORE + (MAX_DEPTH - depth)  # Prefer faster mates
            else:
                return 0  # Stalemate
        
        # Order moves
        tt_move = tt_entry['best_move'] if tt_entry else None
        ordered_moves = self.order_moves(legal_moves, game_state.board, tt_move)
        
        best_score = -MATE_SCORE
        best_move = None
        node_type = TranspositionTable.UPPER_BOUND
        
        for move in ordered_moves:
            game_state.board.make_move(move)
            child_pv = []
            score = -self.alpha_beta(game_state, depth - 1, -beta, -alpha, child_pv)
            game_state.board.unmake_move(move)
            
            if score > best_score:
                best_score = score
                best_move = move
                
                if score > alpha:
                    alpha = score
                    node_type = TranspositionTable.EXACT
                    pv.clear()
                    pv.append(move)
                    pv.extend(child_pv)
            
            if alpha >= beta:
                node_type = TranspositionTable.LOWER_BOUND
                break
        
        # Store in transposition table
        if best_move:
            self.transposition_table.store(position_hash, depth, best_score, best_move, node_type)
        
        return best_score
    
    def quiescence(self, game_state: GameState, alpha: int, beta: int) -> int:
        """
        Quiescence search (search captures until quiet).
        
        Args:
            game_state: Current game state
            alpha: Alpha value
            beta: Beta value
        
        Returns:
            Position score
        """
        self.nodes_searched += 1
        
        # Stand-pat score
        stand_pat = self.evaluator.evaluate(game_state.board, game_state)
        
        # Adjust score based on side to move
        if game_state.board.active_color == 'black':
            stand_pat = -stand_pat
        
        if stand_pat >= beta:
            return beta
        
        if stand_pat > alpha:
            alpha = stand_pat
        
        # Only search captures
        legal_moves = game_state.get_legal_moves()
        capture_moves = [m for m in legal_moves if self._is_capture(m, game_state.board)]
        
        for move in capture_moves:
            game_state.board.make_move(move)
            score = -self.quiescence(game_state, -beta, -alpha)
            game_state.board.unmake_move(move)
            
            if score >= beta:
                return beta
            
            if score > alpha:
                alpha = score
        
        return alpha
    
    def _is_capture(self, move: Move, board: Board) -> bool:
        """Check if move is a capture."""
        return (board.get_piece(move.to_square) is not None or 
                move.is_en_passant)
    
    def order_moves(self, moves: List[Move], board: Board, tt_move: Move = None) -> List[Move]:
        """
        Order moves for better alpha-beta pruning.
        
        Move ordering:
        1. Transposition table move (if available)
        2. Captures (MVV-LVA: Most Valuable Victim - Least Valuable Attacker)
        3. Other moves
        
        Args:
            moves: List of moves to order
            board: Current board
            tt_move: Move from transposition table
        
        Returns:
            Ordered list of moves
        """
        def move_score(move: Move) -> int:
            score = 0
            
            # TT move gets highest priority
            if tt_move and move == tt_move:
                return 10000
            
            # Captures
            captured = board.get_piece(move.to_square)
            if captured or move.is_en_passant:
                if captured:
                    victim_value = captured.get_value()
                else:
                    victim_value = 100  # En passant captures pawn
                
                attacker = board.get_piece(move.from_square)
                attacker_value = attacker.get_value() if attacker else 0
                
                # MVV-LVA: prioritize capturing valuable pieces with less valuable pieces
                score = 1000 + victim_value - attacker_value // 10
            
            # Promotions
            if move.promotion:
                if move.promotion == 'queen':
                    score += 900
                elif move.promotion == 'rook':
                    score += 500
                elif move.promotion == 'bishop':
                    score += 330
                elif move.promotion == 'knight':
                    score += 320
            
            return score
        
        return sorted(moves, key=move_score, reverse=True)
    
    def _should_stop(self, limits: Optional[SearchLimits]) -> bool:
        """Check if search should stop."""
        if self.stop_search:
            return True
        
        if limits is None:
            return False
        
        # Check time limit
        if limits.max_time_ms:
            elapsed_ms = (time.time() - self.start_time) * 1000
            if elapsed_ms >= limits.max_time_ms:
                return True
        
        # Check node limit
        if limits.max_nodes:
            if self.nodes_searched >= limits.max_nodes:
                return True
        
        return False
