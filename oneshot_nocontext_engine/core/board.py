"""Chess board representation with full legal move generation."""

from typing import List, Optional, Tuple, Dict
from .types import Color, PieceType, Piece, Move, Square
import copy


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class Board:
    def __init__(self, fen: str = STARTING_FEN):
        self.squares: List[List[Optional[Piece]]] = [[None]*8 for _ in range(8)]
        self.turn: Color = Color.WHITE
        self.castling_rights: Dict[str, bool] = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.en_passant: Optional[Square] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.move_history: List[Tuple[Move, dict]] = []  # (move, undo_info)
        self.position_history: List[str] = []  # for threefold repetition
        self._load_fen(fen)
        self.position_history.append(self._position_key())

    def _load_fen(self, fen: str):
        parts = fen.strip().split()
        rows = parts[0].split('/')
        piece_map = {
            'P': (Color.WHITE, PieceType.PAWN), 'N': (Color.WHITE, PieceType.KNIGHT),
            'B': (Color.WHITE, PieceType.BISHOP), 'R': (Color.WHITE, PieceType.ROOK),
            'Q': (Color.WHITE, PieceType.QUEEN), 'K': (Color.WHITE, PieceType.KING),
            'p': (Color.BLACK, PieceType.PAWN), 'n': (Color.BLACK, PieceType.KNIGHT),
            'b': (Color.BLACK, PieceType.BISHOP), 'r': (Color.BLACK, PieceType.ROOK),
            'q': (Color.BLACK, PieceType.QUEEN), 'k': (Color.BLACK, PieceType.KING),
        }
        for r, row_str in enumerate(rows):
            c = 0
            for ch in row_str:
                if ch.isdigit():
                    c += int(ch)
                else:
                    color, pt = piece_map[ch]
                    self.squares[r][c] = Piece(color, pt)
                    c += 1

        self.turn = Color.WHITE if parts[1] == 'w' else Color.BLACK

        self.castling_rights = {'K': False, 'Q': False, 'k': False, 'q': False}
        if parts[2] != '-':
            for ch in parts[2]:
                self.castling_rights[ch] = True

        if parts[3] != '-':
            self.en_passant = Square.from_algebraic(parts[3])
        else:
            self.en_passant = None

        self.halfmove_clock = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove_number = int(parts[5]) if len(parts) > 5 else 1

    def to_fen(self) -> str:
        rows = []
        for r in range(8):
            row_str = ''
            empty = 0
            for c in range(8):
                piece = self.squares[r][c]
                if piece is None:
                    empty += 1
                else:
                    if empty > 0:
                        row_str += str(empty)
                        empty = 0
                    row_str += piece.fen_char()
            if empty > 0:
                row_str += str(empty)
            rows.append(row_str)

        fen = '/'.join(rows)
        fen += ' w ' if self.turn == Color.WHITE else ' b '

        castling = ''
        for ch in 'KQkq':
            if self.castling_rights[ch]:
                castling += ch
        fen += castling if castling else '-'

        fen += ' '
        fen += self.en_passant.algebraic() if self.en_passant else '-'
        fen += f' {self.halfmove_clock} {self.fullmove_number}'
        return fen

    def _position_key(self) -> str:
        """Key for threefold repetition (board + turn + castling + en passant)."""
        rows = []
        for r in range(8):
            row_str = ''
            empty = 0
            for c in range(8):
                piece = self.squares[r][c]
                if piece is None:
                    empty += 1
                else:
                    if empty > 0:
                        row_str += str(empty)
                        empty = 0
                    row_str += piece.fen_char()
            if empty > 0:
                row_str += str(empty)
            rows.append(row_str)
        key = '/'.join(rows)
        key += ' w' if self.turn == Color.WHITE else ' b'
        castling = ''.join(ch for ch in 'KQkq' if self.castling_rights[ch])
        key += ' ' + (castling if castling else '-')
        # Only include en passant if there's actually a pawn that can capture
        if self.en_passant and self._ep_is_capturable():
            key += ' ' + self.en_passant.algebraic()
        else:
            key += ' -'
        return key

    def _ep_is_capturable(self) -> bool:
        """Check if any pawn can actually capture en passant."""
        if not self.en_passant:
            return False
        ep = self.en_passant
        direction = 1 if self.turn == Color.WHITE else -1
        pawn_row = ep.row + direction  # row where capturing pawn sits
        for dc in [-1, 1]:
            pc = ep.col + dc
            if 0 <= pc < 8 and 0 <= pawn_row < 8:
                piece = self.squares[pawn_row][pc]
                if piece and piece.color == self.turn and piece.piece_type == PieceType.PAWN:
                    return True
        return False

    def piece_at(self, sq: Square) -> Optional[Piece]:
        return self.squares[sq.row][sq.col]

    def find_king(self, color: Color) -> Square:
        for r in range(8):
            for c in range(8):
                p = self.squares[r][c]
                if p and p.color == color and p.piece_type == PieceType.KING:
                    return Square(r, c)
        raise ValueError(f"No {color.name} king found")

    def is_square_attacked(self, sq: Square, by_color: Color) -> bool:
        """Check if a square is attacked by any piece of the given color."""
        r, c = sq

        # Pawn attacks
        pawn_dir = 1 if by_color == Color.WHITE else -1
        for dc in [-1, 1]:
            pr, pc = r + pawn_dir, c + dc
            if 0 <= pr < 8 and 0 <= pc < 8:
                p = self.squares[pr][pc]
                if p and p.color == by_color and p.piece_type == PieceType.PAWN:
                    return True

        # Knight attacks
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = self.squares[nr][nc]
                if p and p.color == by_color and p.piece_type == PieceType.KNIGHT:
                    return True

        # King attacks
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    p = self.squares[nr][nc]
                    if p and p.color == by_color and p.piece_type == PieceType.KING:
                        return True

        # Sliding pieces: bishop/queen diagonals, rook/queen straight
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                p = self.squares[nr][nc]
                if p:
                    if p.color == by_color and p.piece_type in (PieceType.BISHOP, PieceType.QUEEN):
                        return True
                    break
                nr += dr
                nc += dc

        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                p = self.squares[nr][nc]
                if p:
                    if p.color == by_color and p.piece_type in (PieceType.ROOK, PieceType.QUEEN):
                        return True
                    break
                nr += dr
                nc += dc

        return False

    def is_in_check(self, color: Color) -> bool:
        king_sq = self.find_king(color)
        return self.is_square_attacked(king_sq, color.opposite())

    def _pseudo_legal_moves(self) -> List[Move]:
        """Generate all pseudo-legal moves (may leave king in check)."""
        moves = []
        color = self.turn

        for r in range(8):
            for c in range(8):
                piece = self.squares[r][c]
                if piece is None or piece.color != color:
                    continue
                sq = Square(r, c)
                pt = piece.piece_type

                if pt == PieceType.PAWN:
                    moves.extend(self._pawn_moves(sq, color))
                elif pt == PieceType.KNIGHT:
                    moves.extend(self._knight_moves(sq, color))
                elif pt == PieceType.BISHOP:
                    moves.extend(self._sliding_moves(sq, color, [(-1,-1),(-1,1),(1,-1),(1,1)]))
                elif pt == PieceType.ROOK:
                    moves.extend(self._sliding_moves(sq, color, [(-1,0),(1,0),(0,-1),(0,1)]))
                elif pt == PieceType.QUEEN:
                    moves.extend(self._sliding_moves(sq, color,
                        [(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)]))
                elif pt == PieceType.KING:
                    moves.extend(self._king_moves(sq, color))

        return moves

    def _pawn_moves(self, sq: Square, color: Color) -> List[Move]:
        moves = []
        r, c = sq
        direction = -1 if color == Color.WHITE else 1
        start_row = 6 if color == Color.WHITE else 1
        promo_row = 0 if color == Color.WHITE else 7

        # Single push
        nr = r + direction
        if 0 <= nr < 8 and self.squares[nr][c] is None:
            if nr == promo_row:
                for pt in [PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT]:
                    moves.append(Move(sq, Square(nr, c), pt))
            else:
                moves.append(Move(sq, Square(nr, c)))
                # Double push
                if r == start_row:
                    nr2 = r + 2 * direction
                    if self.squares[nr2][c] is None:
                        moves.append(Move(sq, Square(nr2, c)))

        # Captures
        for dc in [-1, 1]:
            nc = c + dc
            if 0 <= nc < 8:
                nr = r + direction
                if 0 <= nr < 8:
                    target = self.squares[nr][nc]
                    if target and target.color != color:
                        if nr == promo_row:
                            for pt in [PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT]:
                                moves.append(Move(sq, Square(nr, nc), pt))
                        else:
                            moves.append(Move(sq, Square(nr, nc)))
                    # En passant
                    if self.en_passant and Square(nr, nc) == self.en_passant:
                        moves.append(Move(sq, self.en_passant))

        return moves

    def _knight_moves(self, sq: Square, color: Color) -> List[Move]:
        moves = []
        r, c = sq
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                target = self.squares[nr][nc]
                if target is None or target.color != color:
                    moves.append(Move(sq, Square(nr, nc)))
        return moves

    def _sliding_moves(self, sq: Square, color: Color, directions: list) -> List[Move]:
        moves = []
        r, c = sq
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                target = self.squares[nr][nc]
                if target is None:
                    moves.append(Move(sq, Square(nr, nc)))
                elif target.color != color:
                    moves.append(Move(sq, Square(nr, nc)))
                    break
                else:
                    break
                nr += dr
                nc += dc
        return moves

    def _king_moves(self, sq: Square, color: Color) -> List[Move]:
        moves = []
        r, c = sq
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.squares[nr][nc]
                    if target is None or target.color != color:
                        moves.append(Move(sq, Square(nr, nc)))

        # Castling
        enemy = color.opposite()
        king_row = 7 if color == Color.WHITE else 0

        if r == king_row and c == 4:
            # Kingside
            rights_k = 'K' if color == Color.WHITE else 'k'
            if self.castling_rights[rights_k]:
                if (self.squares[king_row][5] is None and
                    self.squares[king_row][6] is None and
                    not self.is_square_attacked(Square(king_row, 4), enemy) and
                    not self.is_square_attacked(Square(king_row, 5), enemy) and
                    not self.is_square_attacked(Square(king_row, 6), enemy)):
                    moves.append(Move(sq, Square(king_row, 6)))

            # Queenside
            rights_q = 'Q' if color == Color.WHITE else 'q'
            if self.castling_rights[rights_q]:
                if (self.squares[king_row][3] is None and
                    self.squares[king_row][2] is None and
                    self.squares[king_row][1] is None and
                    not self.is_square_attacked(Square(king_row, 4), enemy) and
                    not self.is_square_attacked(Square(king_row, 3), enemy) and
                    not self.is_square_attacked(Square(king_row, 2), enemy)):
                    moves.append(Move(sq, Square(king_row, 2)))

        return moves

    def legal_moves(self) -> List[Move]:
        """Generate all legal moves for the current position."""
        legal = []
        for move in self._pseudo_legal_moves():
            if self._is_legal(move):
                legal.append(move)
        return legal

    def _is_legal(self, move: Move) -> bool:
        """Check if a pseudo-legal move is actually legal (doesn't leave king in check)."""
        undo = self._make_move_internal(move)
        in_check = self.is_in_check(self.turn.opposite())
        self._unmake_move_internal(move, undo)
        return not in_check

    def make_move(self, move: Move) -> bool:
        """Make a move on the board. Returns True if legal."""
        if not self._is_legal(move):
            return False
        undo = self._make_move_internal(move)
        self.move_history.append((move, undo))
        self.position_history.append(self._position_key())
        return True

    def unmake_move(self) -> Optional[Move]:
        """Undo the last move. Returns the undone move or None."""
        if not self.move_history:
            return None
        move, undo = self.move_history.pop()
        self.position_history.pop()
        self._unmake_move_internal(move, undo)
        return move

    def _make_move_internal(self, move: Move) -> dict:
        """Execute a move and return undo information."""
        fr, fc = move.from_sq
        tr, tc = move.to_sq
        piece = self.squares[fr][fc]
        captured = self.squares[tr][tc]

        undo = {
            'captured': captured,
            'castling': dict(self.castling_rights),
            'en_passant': self.en_passant,
            'halfmove_clock': self.halfmove_clock,
            'ep_captured_sq': None,
            'ep_captured_piece': None,
            'castled_rook': None,
        }

        # En passant capture
        if piece.piece_type == PieceType.PAWN and move.to_sq == self.en_passant:
            ep_pawn_row = fr  # captured pawn is on the same row as the capturing pawn
            undo['ep_captured_sq'] = Square(ep_pawn_row, tc)
            undo['ep_captured_piece'] = self.squares[ep_pawn_row][tc]
            self.squares[ep_pawn_row][tc] = None

        # Move piece
        self.squares[tr][tc] = piece
        self.squares[fr][fc] = None

        # Promotion
        if move.promotion:
            self.squares[tr][tc] = Piece(piece.color, move.promotion)

        # Castling - move the rook
        king_row = 7 if piece.color == Color.WHITE else 0
        if piece.piece_type == PieceType.KING and abs(fc - tc) == 2:
            if tc == 6:  # kingside
                rook = self.squares[king_row][7]
                self.squares[king_row][5] = rook
                self.squares[king_row][7] = None
                undo['castled_rook'] = ('K', king_row)
            elif tc == 2:  # queenside
                rook = self.squares[king_row][0]
                self.squares[king_row][3] = rook
                self.squares[king_row][0] = None
                undo['castled_rook'] = ('Q', king_row)

        # Update en passant square
        self.en_passant = None
        if piece.piece_type == PieceType.PAWN and abs(fr - tr) == 2:
            self.en_passant = Square((fr + tr) // 2, fc)

        # Update castling rights
        if piece.piece_type == PieceType.KING:
            if piece.color == Color.WHITE:
                self.castling_rights['K'] = False
                self.castling_rights['Q'] = False
            else:
                self.castling_rights['k'] = False
                self.castling_rights['q'] = False

        if piece.piece_type == PieceType.ROOK:
            if piece.color == Color.WHITE:
                if move.from_sq == Square(7, 7):
                    self.castling_rights['K'] = False
                elif move.from_sq == Square(7, 0):
                    self.castling_rights['Q'] = False
            else:
                if move.from_sq == Square(0, 7):
                    self.castling_rights['k'] = False
                elif move.from_sq == Square(0, 0):
                    self.castling_rights['q'] = False

        # If a rook is captured, remove its castling rights
        if captured and captured.piece_type == PieceType.ROOK:
            if move.to_sq == Square(7, 7):
                self.castling_rights['K'] = False
            elif move.to_sq == Square(7, 0):
                self.castling_rights['Q'] = False
            elif move.to_sq == Square(0, 7):
                self.castling_rights['k'] = False
            elif move.to_sq == Square(0, 0):
                self.castling_rights['q'] = False

        # Update halfmove clock
        if piece.piece_type == PieceType.PAWN or captured is not None:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Update fullmove number
        if self.turn == Color.BLACK:
            self.fullmove_number += 1

        # Switch turn
        self.turn = self.turn.opposite()

        return undo

    def _unmake_move_internal(self, move: Move, undo: dict):
        """Reverse a move using undo information."""
        # Switch turn back
        self.turn = self.turn.opposite()

        fr, fc = move.from_sq
        tr, tc = move.to_sq

        # Get the piece that was moved (may have been promoted)
        moved_piece = self.squares[tr][tc]

        # If it was a promotion, restore to pawn
        if move.promotion:
            moved_piece = Piece(moved_piece.color, PieceType.PAWN)

        # Move piece back
        self.squares[fr][fc] = moved_piece
        self.squares[tr][tc] = undo['captured']

        # Undo en passant capture
        if undo['ep_captured_sq']:
            ep_sq = undo['ep_captured_sq']
            self.squares[ep_sq.row][ep_sq.col] = undo['ep_captured_piece']

        # Undo castling rook move
        if undo['castled_rook']:
            side, row = undo['castled_rook']
            if side == 'K':
                self.squares[row][7] = self.squares[row][5]
                self.squares[row][5] = None
            else:
                self.squares[row][0] = self.squares[row][3]
                self.squares[row][3] = None

        # Restore state
        self.castling_rights = undo['castling']
        self.en_passant = undo['en_passant']
        self.halfmove_clock = undo['halfmove_clock']

        if self.turn == Color.BLACK:
            self.fullmove_number -= 1

    # --- Game state queries ---

    def is_checkmate(self) -> bool:
        return self.is_in_check(self.turn) and len(self.legal_moves()) == 0

    def is_stalemate(self) -> bool:
        return not self.is_in_check(self.turn) and len(self.legal_moves()) == 0

    def is_insufficient_material(self) -> bool:
        pieces = []
        for r in range(8):
            for c in range(8):
                p = self.squares[r][c]
                if p and p.piece_type != PieceType.KING:
                    pieces.append(p)

        if len(pieces) == 0:
            return True  # K vs K
        if len(pieces) == 1:
            return pieces[0].piece_type in (PieceType.BISHOP, PieceType.KNIGHT)
        if len(pieces) == 2:
            # K+B vs K+B same color bishops
            if all(p.piece_type == PieceType.BISHOP for p in pieces):
                # Find bishop squares
                bishop_squares = []
                for r in range(8):
                    for c in range(8):
                        p = self.squares[r][c]
                        if p and p.piece_type == PieceType.BISHOP:
                            bishop_squares.append((r + c) % 2)
                if len(bishop_squares) == 2 and bishop_squares[0] == bishop_squares[1]:
                    return True
        return False

    def is_threefold_repetition(self) -> bool:
        if len(self.position_history) < 5:
            return False
        current = self.position_history[-1]
        return self.position_history.count(current) >= 3

    def is_fifty_move_rule(self) -> bool:
        return self.halfmove_clock >= 100

    def is_draw(self) -> bool:
        return (self.is_stalemate() or self.is_insufficient_material() or
                self.is_threefold_repetition() or self.is_fifty_move_rule())

    def is_game_over(self) -> Tuple[bool, str]:
        """Returns (is_over, reason)."""
        if self.is_checkmate():
            winner = "White" if self.turn == Color.BLACK else "Black"
            return True, f"Checkmate - {winner} wins"
        if self.is_stalemate():
            return True, "Draw by stalemate"
        if self.is_insufficient_material():
            return True, "Draw by insufficient material"
        if self.is_threefold_repetition():
            return True, "Draw by threefold repetition"
        if self.is_fifty_move_rule():
            return True, "Draw by fifty-move rule"
        return False, ""

    def move_to_san(self, move: Move) -> str:
        """Convert a move to Standard Algebraic Notation."""
        piece = self.piece_at(move.from_sq)
        if piece is None:
            return move.uci()

        # Castling
        if piece.piece_type == PieceType.KING and abs(move.from_sq.col - move.to_sq.col) == 2:
            return "O-O" if move.to_sq.col == 6 else "O-O-O"

        san = ''
        is_capture = (self.piece_at(move.to_sq) is not None or
                      (piece.piece_type == PieceType.PAWN and move.to_sq == self.en_passant))

        if piece.piece_type == PieceType.PAWN:
            if is_capture:
                san += chr(ord('a') + move.from_sq.col)
        else:
            san += {PieceType.KNIGHT: 'N', PieceType.BISHOP: 'B', PieceType.ROOK: 'R',
                    PieceType.QUEEN: 'Q', PieceType.KING: 'K'}[piece.piece_type]

            # Disambiguation
            ambiguous = []
            for m in self.legal_moves():
                if (m.to_sq == move.to_sq and m.from_sq != move.from_sq and
                    self.piece_at(m.from_sq) == piece):
                    ambiguous.append(m)
            if ambiguous:
                same_col = any(m.from_sq.col == move.from_sq.col for m in ambiguous)
                same_row = any(m.from_sq.row == move.from_sq.row for m in ambiguous)
                if not same_col:
                    san += chr(ord('a') + move.from_sq.col)
                elif not same_row:
                    san += str(8 - move.from_sq.row)
                else:
                    san += chr(ord('a') + move.from_sq.col) + str(8 - move.from_sq.row)

        if is_capture:
            san += 'x'

        san += move.to_sq.algebraic()

        if move.promotion:
            promo_chars = {PieceType.QUEEN: 'Q', PieceType.ROOK: 'R',
                          PieceType.BISHOP: 'B', PieceType.KNIGHT: 'N'}
            san += '=' + promo_chars[move.promotion]

        # Check / checkmate markers
        undo = self._make_move_internal(move)
        if self.is_in_check(self.turn):
            if len(self.legal_moves()) == 0:
                san += '#'
            else:
                san += '+'
        self._unmake_move_internal(move, undo)

        return san

    def to_pgn(self, headers: Optional[Dict[str, str]] = None) -> str:
        """Export the game as PGN."""
        if headers is None:
            headers = {}
        default_headers = {
            'Event': 'PointChess Game',
            'Site': 'Local',
            'Date': '????.??.??',
            'Round': '-',
            'White': 'Human',
            'Black': 'PointChess Engine',
            'Result': '*'
        }
        default_headers.update(headers)

        pgn = ''
        for key, value in default_headers.items():
            pgn += f'[{key} "{value}"]\n'
        pgn += '\n'

        # Replay all moves to generate SAN
        board = Board(STARTING_FEN)
        moves_text = []
        for i, (move, _) in enumerate(self.move_history):
            if i % 2 == 0:
                moves_text.append(f'{i // 2 + 1}.')
            san = board.move_to_san(move)
            moves_text.append(san)
            board.make_move(move)

        # Add result
        over, reason = self.is_game_over()
        if over:
            if 'White wins' in reason:
                result = '1-0'
            elif 'Black wins' in reason:
                result = '0-1'
            else:
                result = '1/2-1/2'
            default_headers['Result'] = result
            moves_text.append(result)

        pgn_lines = []
        for key, value in default_headers.items():
            pgn_lines.append(f'[{key} "{value}"]')
        pgn_lines.append('')

        # Word wrap at 80 chars
        line = ''
        for token in moves_text:
            if len(line) + len(token) + 1 > 80:
                pgn_lines.append(line)
                line = token
            else:
                line = (line + ' ' + token).strip()
        if line:
            pgn_lines.append(line)

        return '\n'.join(pgn_lines) + '\n'

    def perft(self, depth: int) -> int:
        """Count leaf nodes at given depth for move generation testing."""
        if depth == 0:
            return 1
        count = 0
        for move in self.legal_moves():
            self.make_move(move)
            count += self.perft(depth - 1)
            self.unmake_move()
        return count

    def copy(self) -> 'Board':
        """Deep copy the board."""
        return copy.deepcopy(self)

    def __str__(self) -> str:
        s = ''
        for r in range(8):
            s += f'{8 - r} '
            for c in range(8):
                p = self.squares[r][c]
                s += (p.symbol() if p else '.') + ' '
            s += '\n'
        s += '  a b c d e f g h\n'
        return s
