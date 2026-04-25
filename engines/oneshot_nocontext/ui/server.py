"""Simple HTTP server for the browser-based chess UI.

Uses only Python stdlib (http.server + json). Serves static files
and provides a JSON API for the chess engine.
"""

import json
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from engines.oneshot_nocontext.core.board import Board
from engines.oneshot_nocontext.core.types import Color, PieceType, Move, Square
from engines.oneshot_nocontext.search.engine import Engine


class GameState:
    """Shared game state for the web server."""
    def __init__(self):
        self.board = Board()
        self.engine = Engine(elo=1500)
        self.player_color = Color.WHITE
        self.move_list: list = []  # SAN notation moves

    def reset(self, player_color: Color = Color.WHITE, elo: int = 1500):
        self.board = Board()
        self.engine = Engine(elo=elo)
        self.engine.clear()
        self.player_color = player_color
        self.move_list = []

    def to_dict(self) -> dict:
        legal_moves = []
        if not self.board.is_game_over()[0]:
            for m in self.board.legal_moves():
                legal_moves.append({
                    'from': m.from_sq.algebraic(),
                    'to': m.to_sq.algebraic(),
                    'uci': m.uci(),
                    'promotion': m.promotion.name.lower() if m.promotion else None,
                })

        over, reason = self.board.is_game_over()
        in_check = self.board.is_in_check(self.board.turn)

        # Build board array
        board_array = []
        for r in range(8):
            row = []
            for c in range(8):
                p = self.board.squares[r][c]
                if p:
                    row.append(p.symbol())
                else:
                    row.append(None)
            board_array.append(row)

        return {
            'board': board_array,
            'turn': 'white' if self.board.turn == Color.WHITE else 'black',
            'playerColor': 'white' if self.player_color == Color.WHITE else 'black',
            'legalMoves': legal_moves,
            'moveList': self.move_list,
            'inCheck': in_check,
            'gameOver': over,
            'gameResult': reason,
            'fen': self.board.to_fen(),
            'elo': self.engine.settings.elo,
        }


# Global game state
game = GameState()


class ChessHandler(SimpleHTTPRequestHandler):
    """HTTP handler for chess API and static files."""

    def __init__(self, *args, **kwargs):
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        super().__init__(*args, directory=static_dir, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/state':
            self._json_response(game.to_dict())
        elif parsed.path == '/api/pgn':
            pgn = game.board.to_pgn()
            self._json_response({'pgn': pgn})
        elif parsed.path == '/' or parsed.path == '':
            self.path = '/index.html'
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if parsed.path == '/api/new':
            color = Color.WHITE if data.get('color', 'white') == 'white' else Color.BLACK
            elo = int(data.get('elo', 1500))
            game.reset(player_color=color, elo=elo)

            result = game.to_dict()

            # If engine plays first (player is black), make engine move
            if game.player_color == Color.BLACK:
                self._engine_move()
                result = game.to_dict()

            self._json_response(result)

        elif parsed.path == '/api/move':
            uci_str = data.get('move', '')
            if not uci_str:
                self._json_response({'error': 'No move provided'}, 400)
                return

            move = Move.from_uci(uci_str)

            # Find matching legal move
            legal = game.board.legal_moves()
            matched = None
            for m in legal:
                if m.from_sq == move.from_sq and m.to_sq == move.to_sq:
                    if move.promotion is None or m.promotion == move.promotion:
                        matched = m
                        break

            if matched is None:
                self._json_response({'error': 'Illegal move'}, 400)
                return

            san = game.board.move_to_san(matched)
            game.board.make_move(matched)
            game.move_list.append(san)

            # Check if game is over after player move
            over, _ = game.board.is_game_over()
            if not over:
                # Engine responds
                self._engine_move()

            self._json_response(game.to_dict())

        elif parsed.path == '/api/undo':
            # Undo two moves (player + engine)
            if len(game.move_list) >= 2:
                game.board.unmake_move()
                game.move_list.pop()
                game.board.unmake_move()
                game.move_list.pop()
            elif len(game.move_list) == 1:
                game.board.unmake_move()
                game.move_list.pop()
            self._json_response(game.to_dict())

        elif parsed.path == '/api/resign':
            winner = "Black" if game.player_color == Color.WHITE else "White"
            self._json_response({
                **game.to_dict(),
                'gameOver': True,
                'gameResult': f'{winner} wins by resignation',
            })

        elif parsed.path == '/api/elo':
            elo = int(data.get('elo', 1500))
            game.engine.set_elo(elo)
            self._json_response(game.to_dict())

        else:
            self._json_response({'error': 'Not found'}, 404)

    def _engine_move(self):
        """Have the engine make a move."""
        move, score = game.engine.search(game.board)
        if move:
            san = game.board.move_to_san(move)
            game.board.make_move(move)
            game.move_list.append(san)

    def _json_response(self, data: dict, status: int = 200):
        response = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


def start_server(port: int = 8000):
    """Start the chess web server."""
    server = HTTPServer(('0.0.0.0', port), ChessHandler)
    print(f"PointChess Engine running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
