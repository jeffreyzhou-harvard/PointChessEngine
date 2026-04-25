"""Tests for UCI protocol handling."""

import io
import unittest
from oneshot_nocontext_engine.uci.protocol import UCIProtocol


class TestUCI(unittest.TestCase):
    def _run_commands(self, commands: list) -> str:
        """Run UCI commands and capture output."""
        input_stream = io.StringIO('\n'.join(commands) + '\n')
        output_stream = io.StringIO()
        protocol = UCIProtocol(input_stream=input_stream, output_stream=output_stream)
        protocol.run()
        return output_stream.getvalue()

    def test_uci_command(self):
        output = self._run_commands(['uci', 'quit'])
        self.assertIn('id name PointChess', output)
        self.assertIn('uciok', output)

    def test_isready(self):
        output = self._run_commands(['isready', 'quit'])
        self.assertIn('readyok', output)

    def test_position_startpos(self):
        output = self._run_commands([
            'position startpos',
            'quit'
        ])
        # No error should occur

    def test_position_startpos_with_moves(self):
        output = self._run_commands([
            'position startpos moves e2e4 e7e5',
            'quit'
        ])
        # No error

    def test_position_fen(self):
        output = self._run_commands([
            'position fen rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
            'quit'
        ])
        # No error

    def test_go_depth(self):
        output = self._run_commands([
            'position startpos',
            'go depth 1',
            'quit'
        ])
        # Should find bestmove (might need a small delay for thread)
        # The quit command should stop the search
        self.assertIn('bestmove', output)

    def test_setoption_skill(self):
        output = self._run_commands([
            'uci',
            'setoption name Skill Level value 800',
            'isready',
            'quit'
        ])
        self.assertIn('readyok', output)

    def test_ucinewgame(self):
        output = self._run_commands([
            'ucinewgame',
            'isready',
            'quit'
        ])
        self.assertIn('readyok', output)


if __name__ == '__main__':
    unittest.main()
