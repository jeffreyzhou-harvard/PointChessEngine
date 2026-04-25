"""
Transposition table for caching positions.

Implements:
- TranspositionTable class
- Zobrist hashing for position identification
- Entry storage with depth, score, and best move
"""

from typing import Optional, Dict
import random


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
    
    # Node types
    EXACT = 0      # Exact score
    LOWER_BOUND = 1  # Alpha cutoff (score >= stored value)
    UPPER_BOUND = 2  # Beta cutoff (score <= stored value)
    
    def __init__(self, size_mb: int = 64):
        """
        Initialize transposition table.
        
        Args:
            size_mb: Size in megabytes (approximate)
        """
        # Estimate entries: each entry ~50 bytes, so 1MB ~= 20000 entries
        self.max_entries = size_mb * 20000
        self.table: Dict[int, dict] = {}
        
        # Initialize Zobrist keys for hashing
        self._init_zobrist_keys()
    
    def _init_zobrist_keys(self):
        """Initialize Zobrist random keys for position hashing."""
        random.seed(42)  # Fixed seed for reproducibility
        
        # Keys for each piece type, color, and square
        self.zobrist_pieces = {}
        piece_types = ['pawn', 'knight', 'bishop', 'rook', 'queen', 'king']
        colors = ['white', 'black']
        
        for piece_type in piece_types:
            for color in colors:
                self.zobrist_pieces[(piece_type, color)] = [
                    random.getrandbits(64) for _ in range(64)
                ]
        
        # Keys for castling rights
        self.zobrist_castling = {
            'K': random.getrandbits(64),
            'Q': random.getrandbits(64),
            'k': random.getrandbits(64),
            'q': random.getrandbits(64)
        }
        
        # Keys for en passant file
        self.zobrist_en_passant = [random.getrandbits(64) for _ in range(8)]
        
        # Key for side to move
        self.zobrist_side = random.getrandbits(64)
    
    def hash_position(self, board) -> int:
        """
        Compute Zobrist hash for a board position.
        
        Args:
            board: Board to hash
        
        Returns:
            64-bit hash value
        """
        hash_value = 0
        
        # Hash pieces
        for rank in range(8):
            for file in range(8):
                piece = board.squares[rank][file]
                if piece:
                    square_index = rank * 8 + file
                    key = self.zobrist_pieces[(piece.piece_type, piece.color)][square_index]
                    hash_value ^= key
        
        # Hash castling rights
        for right, has_right in board.castling_rights.items():
            if has_right:
                hash_value ^= self.zobrist_castling[right]
        
        # Hash en passant
        if board.en_passant_target:
            hash_value ^= self.zobrist_en_passant[board.en_passant_target.file]
        
        # Hash side to move
        if board.active_color == 'black':
            hash_value ^= self.zobrist_side
        
        return hash_value
    
    def store(self, position_hash: int, depth: int, score: int,
              best_move, node_type: int) -> None:
        """
        Store position in transposition table.
        
        Args:
            position_hash: Zobrist hash of position
            depth: Search depth
            score: Position score
            best_move: Best move found
            node_type: EXACT, LOWER_BOUND, or UPPER_BOUND
        """
        # Replace if:
        # 1. Entry doesn't exist
        # 2. New search is deeper
        # 3. Same depth but exact score (more valuable than bounds)
        
        if position_hash in self.table:
            old_entry = self.table[position_hash]
            if old_entry['depth'] > depth and old_entry['node_type'] == self.EXACT:
                return  # Keep deeper exact score
        
        self.table[position_hash] = {
            'depth': depth,
            'score': score,
            'best_move': best_move,
            'node_type': node_type
        }
        
        # Limit table size (simple eviction: remove random entry)
        if len(self.table) > self.max_entries:
            # Remove oldest/random entry (simplified)
            key_to_remove = next(iter(self.table))
            del self.table[key_to_remove]
    
    def probe(self, position_hash: int) -> Optional[dict]:
        """
        Probe transposition table for position.
        
        Args:
            position_hash: Zobrist hash of position
        
        Returns:
            Entry dict with keys: depth, score, best_move, node_type
            or None if not found
        """
        return self.table.get(position_hash)
    
    def clear(self) -> None:
        """Clear transposition table."""
        self.table.clear()
    
    def size(self) -> int:
        """Get number of entries in table."""
        return len(self.table)
