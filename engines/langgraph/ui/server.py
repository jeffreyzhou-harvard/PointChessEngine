"""
Web server for browser-based UI.

Implements HTTP server with JSON API for game management.
Uses stdlib http.server (no external dependencies).
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

from .session import GameSession


# Global game session (single-user application)
game_session = GameSession()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server with threading support."""
    daemon_threads = True


class ChessHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for chess UI.
    
    Serves static files and handles JSON API endpoints.
    """
    
    def log_message(self, format: str, *args) -> None:
        """Override to customize logging."""
        # Print to stdout with custom format
        print(f"[{self.log_date_time_string()}] {format % args}")
    
    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """
        Send JSON response.
        
        Args:
            data: Dictionary to serialize as JSON
            status: HTTP status code
        """
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _send_error_json(self, message: str, status: int = 400) -> None:
        """
        Send JSON error response.
        
        Args:
            message: Error message
            status: HTTP status code
        """
        self._send_json({'error': message}, status)
    
    def _read_json_body(self) -> Dict[str, Any]:
        """
        Read and parse JSON request body.
        
        Returns:
            Parsed JSON data
        
        Raises:
            ValueError: If body is not valid JSON
        """
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # API endpoints
        if path == '/api/status':
            self._handle_get_status()
        elif path == '/api/legal_moves':
            self._handle_get_legal_moves(parsed_path.query)
        elif path.startswith('/api/'):
            self._send_error_json('Unknown API endpoint', 404)
        else:
            # Serve static files
            self._serve_static_file(path)
    
    def do_POST(self) -> None:
        """Handle POST requests."""
        path = urlparse(self.path).path
        
        # API endpoints
        if path == '/api/new_game':
            self._handle_new_game()
        elif path == '/api/move':
            self._handle_move()
        elif path == '/api/engine_move':
            self._handle_engine_move()
        elif path == '/api/set_elo':
            self._handle_set_elo()
        elif path == '/api/resign':
            self._handle_resign()
        else:
            self._send_error_json('Unknown API endpoint', 404)
    
    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests (CORS preflight)."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _serve_static_file(self, path: str) -> None:
        """
        Serve static files from ui/static directory.
        
        Args:
            path: Request path
        """
        # Default to index.html
        if path == '/':
            path = '/index.html'
        
        # Security: prevent directory traversal
        if '..' in path:
            self.send_error(403, 'Forbidden')
            return
        
        # Build file path
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        file_path = os.path.join(static_dir, path.lstrip('/'))
        
        # Check if file exists
        if not os.path.isfile(file_path):
            self.send_error(404, 'File not found')
            return
        
        # Determine content type
        content_type = 'text/html'
        if path.endswith('.css'):
            content_type = 'text/css'
        elif path.endswith('.js'):
            content_type = 'application/javascript'
        elif path.endswith('.json'):
            content_type = 'application/json'
        elif path.endswith('.png'):
            content_type = 'image/png'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif path.endswith('.svg'):
            content_type = 'image/svg+xml'
        
        # Send file
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f'Internal server error: {str(e)}')
    
    # API endpoint handlers
    
    def _handle_get_status(self) -> None:
        """GET /api/status - Get current game status."""
        status = game_session.get_game_status()
        status['board'] = game_session.get_board_array()
        self._send_json(status)
    
    def _handle_get_legal_moves(self, query: str) -> None:
        """GET /api/legal_moves?square=e2 - Get legal moves from square."""
        params = parse_qs(query)
        square = params.get('square', [None])[0]
        
        if square:
            moves = game_session.get_legal_moves_from_square(square)
        else:
            moves = game_session.get_legal_moves()
        
        self._send_json({'legal_moves': moves})
    
    def _handle_new_game(self) -> None:
        """POST /api/new_game - Start new game."""
        try:
            data = self._read_json_body()
            human_color = data.get('human_color', 'white')
            elo_rating = data.get('elo_rating', None)
            
            if human_color not in ['white', 'black']:
                self._send_error_json('Invalid human_color (must be white or black)')
                return
            
            if elo_rating is not None:
                if not isinstance(elo_rating, int) or elo_rating < 400 or elo_rating > 2400:
                    self._send_error_json('Invalid elo_rating (must be 400-2400)')
                    return
            
            game_session.new_game(human_color, elo_rating)
            
            status = game_session.get_game_status()
            status['board'] = game_session.get_board_array()
            self._send_json(status)
        
        except json.JSONDecodeError:
            self._send_error_json('Invalid JSON')
        except Exception as e:
            self._send_error_json(f'Error: {str(e)}', 500)
    
    def _handle_move(self) -> None:
        """POST /api/move - Make a move."""
        try:
            data = self._read_json_body()
            move = data.get('move')
            
            if not move:
                self._send_error_json('Missing move parameter')
                return
            
            success = game_session.make_move(move)
            
            if not success:
                self._send_error_json('Illegal move')
                return
            
            status = game_session.get_game_status()
            status['board'] = game_session.get_board_array()
            self._send_json(status)
        
        except json.JSONDecodeError:
            self._send_error_json('Invalid JSON')
        except Exception as e:
            self._send_error_json(f'Error: {str(e)}', 500)
    
    def _handle_engine_move(self) -> None:
        """POST /api/engine_move - Request engine move."""
        try:
            data = self._read_json_body()
            time_ms = data.get('time_ms', 2000)
            
            if not isinstance(time_ms, int) or time_ms < 100 or time_ms > 60000:
                self._send_error_json('Invalid time_ms (must be 100-60000)')
                return
            
            move = game_session.get_engine_move(time_ms)
            
            if not move:
                self._send_error_json('No legal moves available')
                return
            
            # Make the engine move
            game_session.make_move(move)
            
            status = game_session.get_game_status()
            status['board'] = game_session.get_board_array()
            status['engine_move'] = move
            self._send_json(status)
        
        except json.JSONDecodeError:
            self._send_error_json('Invalid JSON')
        except Exception as e:
            self._send_error_json(f'Error: {str(e)}', 500)
    
    def _handle_set_elo(self) -> None:
        """POST /api/set_elo - Adjust engine strength."""
        try:
            data = self._read_json_body()
            elo_rating = data.get('elo_rating')
            
            if not isinstance(elo_rating, int) or elo_rating < 400 or elo_rating > 2400:
                self._send_error_json('Invalid elo_rating (must be 400-2400)')
                return
            
            game_session.set_elo(elo_rating)
            
            self._send_json({
                'elo_rating': elo_rating,
                'message': f'Engine strength set to {elo_rating}'
            })
        
        except json.JSONDecodeError:
            self._send_error_json('Invalid JSON')
        except Exception as e:
            self._send_error_json(f'Error: {str(e)}', 500)
    
    def _handle_resign(self) -> None:
        """POST /api/resign - Human player resigns."""
        try:
            result = game_session.resign()
            
            status = game_session.get_game_status()
            status['board'] = game_session.get_board_array()
            status['result'] = result
            status['message'] = 'You resigned!'
            
            self._send_json(status)
        
        except Exception as e:
            self._send_error_json(f'Error: {str(e)}', 500)


def start_server(port: int = 8000, host: str = '127.0.0.1') -> None:
    """
    Start web server.
    
    Args:
        port: Port to listen on
        host: Host to bind to
    """
    server = ThreadingHTTPServer((host, port), ChessHTTPHandler)
    print(f"Chess UI server starting on http://{host}:{port}/")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == '__main__':
    start_server()
