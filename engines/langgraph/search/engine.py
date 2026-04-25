"""
Main chess engine interface.

Implements:
- Engine class (main interface for move selection)
- Integration of search, evaluation, and ELO configuration
- Best move selection with strength adjustment
"""

from typing import Optional

from core.game_state import GameState
from core.move import Move
from .evaluation import Evaluator
from .search import Searcher, SearchLimits, SearchResult
from .transposition import TranspositionTable
from .elo import EloConfig, config_from_elo


class Engine:
    """
    Chess engine - main interface for move selection.
    
    Attributes:
        elo_config: EloConfig - strength configuration
        transposition_table: TranspositionTable
        evaluator: Evaluator
        searcher: Searcher
    """
    
    def __init__(self, elo_rating: int = 1500):
        """
        Initialize engine.
        
        Args:
            elo_rating: ELO rating for strength (400-2400)
        """
        self.elo_config = config_from_elo(elo_rating)
        self.transposition_table = TranspositionTable(size_mb=64)
        self.evaluator = Evaluator()
        self.searcher = Searcher(self.evaluator, self.transposition_table)
    
    def set_elo(self, elo_rating: int) -> None:
        """
        Adjust engine strength.
        
        Args:
            elo_rating: ELO rating (400-2400)
        """
        self.elo_config = config_from_elo(elo_rating)
    
    def search(self, game_state: GameState, limits: SearchLimits) -> SearchResult:
        """
        Search for best move.
        
        Backward-compatible signature. Applies ELO-based adjustments internally.
        
        Args:
            game_state: Current game state
            limits: Search limits (depth, time, nodes)
        
        Returns:
            SearchResult with best move and analysis
        """
        # Perform search
        result = self.searcher.iterative_deepening(game_state, limits)
        
        # Apply ELO-based adjustments
        if result.best_move:
            # Add noise to evaluation
            result.score = self.elo_config.add_noise_to_score(result.score)
        
        return result
    
    def _apply_elo_move_selection(self, game_state: GameState, 
                                  result: SearchResult, limits: SearchLimits) -> SearchResult:
        """
        Apply ELO-based move selection (may choose suboptimal move).
        
        Args:
            game_state: Current game state
            result: Original search result
            limits: Search limits
        
        Returns:
            Modified search result with potentially different move
        """
        # Get all legal moves
        legal_moves = game_state.get_legal_moves()
        
        if len(legal_moves) <= 1:
            return result
        
        # Check if this is a forced mate - never blunder those
        is_forced_mate = abs(result.score) > 90000  # Near MATE_SCORE
        if is_forced_mate and not self.elo_config.should_blunder_mate(True):
            return result
        
        # Evaluate top moves quickly (shallow search)
        moves_with_scores = []
        shallow_depth = max(1, self.elo_config.base_depth - 2)
        
        for move in legal_moves[:10]:  # Limit to top 10 for performance
            game_state.board.make_move(move)
            
            # Quick evaluation
            if shallow_depth > 0:
                pv = []
                score = -self.searcher.alpha_beta(game_state, shallow_depth, -100000, 100000, pv)
            else:
                score = -self.evaluator.evaluate(game_state.board, game_state)
            
            game_state.board.unmake_move(move)
            
            # Add noise
            score = self.elo_config.add_noise_to_score(score)
            moves_with_scores.append((move, score))
        
        # Sort by score (best first)
        moves_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Select move based on ELO configuration
        selected_move = self.elo_config.select_move(moves_with_scores)
        
        if selected_move and selected_move != result.best_move:
            # Update result with selected move
            result.best_move = selected_move
            # Keep original score/depth/nodes (just changed the move)
        
        return result
    
    def get_best_move(self, game_state: GameState, time_ms: Optional[int] = None) -> Move:
        """
        Get best move with current ELO configuration.
        
        Args:
            game_state: Current game state
            time_ms: Optional time limit in milliseconds
        
        Returns:
            Best move
        """
        # Create search limits based on ELO configuration
        if time_ms is None:
            # Use depth-based search
            limits = SearchLimits(max_depth=self.elo_config.base_depth)
        else:
            # Use time-based search with ELO multiplier
            adjusted_time = int(time_ms * self.elo_config.time_multiplier)
            limits = SearchLimits(
                max_depth=self.elo_config.base_depth,
                max_time_ms=adjusted_time
            )
        
        result = self.search(game_state, limits)
        return result.best_move
    
    def new_game(self) -> None:
        """Reset engine for new game."""
        self.transposition_table.clear()
    
    def get_evaluation(self, game_state: GameState) -> int:
        """
        Get static evaluation of current position.
        
        Args:
            game_state: Current game state
        
        Returns:
            Evaluation in centipawns (positive = white advantage)
        """
        return self.evaluator.evaluate(game_state.board, game_state)
    
    def __str__(self) -> str:
        """String representation."""
        return f"Engine(ELO={self.elo_config.elo_rating}, depth={self.elo_config.base_depth})"
