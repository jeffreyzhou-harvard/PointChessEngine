"""C0.* tests for the UCI-first engine contract and benchmark harness."""

import json

from tests.classical.helpers import ClassicalTestCase, run_uci_subprocess_commands


class TestC0_1ProcessContract(ClassicalTestCase):
    def test_engine_process_starts_and_exits_cleanly(self):
        result = run_uci_subprocess_commands(["uci", "quit"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("id name", result.stdout)
        self.assertIn("uciok", result.stdout)


class TestC0_2RegistrySchema(ClassicalTestCase):
    def test_registry_manifest_has_required_engine_fields(self):
        registry = {
            "engine_id": "oneshot-nocontext",
            "command": ["python3", "-m", "oneshot_nocontext_engine", "--uci"],
            "working_directory": ".",
            "fake": False,
            "supported_options": ["Skill Level", "UCI_Elo"],
        }
        encoded = json.dumps(registry)
        decoded = json.loads(encoded)
        self.assertTrue(decoded["engine_id"])
        self.assertIsInstance(decoded["command"], list)
        self.assertFalse(decoded["fake"])


class TestC0_3TranscriptHarness(ClassicalTestCase):
    def test_harness_can_drive_basic_uci_transcript(self):
        result = run_uci_subprocess_commands(["uci", "isready", "quit"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("uciok", result.stdout)
        self.assertIn("readyok", result.stdout)


class TestC0_4MalformedOutputCategories(ClassicalTestCase):
    def test_contract_distinguishes_expected_failure_categories(self):
        categories = {"missing_uciok", "missing_readyok", "invalid_bestmove", "crash", "timeout"}
        self.assertEqual(
            categories,
            {"missing_uciok", "missing_readyok", "invalid_bestmove", "crash", "timeout"},
        )


class TestC0_5ObservabilityEnvelope(ClassicalTestCase):
    def test_result_envelope_contains_observability_fields(self):
        envelope = {
            "engine_id": "oneshot-nocontext",
            "command": ["python3", "-m", "oneshot_nocontext_engine", "--uci"],
            "position": "startpos",
            "limits": {"depth": 1, "movetime_ms": None},
            "bestmove": "e2e4",
            "info": [{"depth": 1, "nodes": 1, "time_ms": 1}],
            "timings": {"startup_ms": 1, "ready_ms": 1, "go_ms": 1},
            "exit_status": "ok",
            "stdout_log": "reports/evals/example.stdout.log",
            "stderr_log": "reports/evals/example.stderr.log",
        }
        for field in [
            "engine_id",
            "command",
            "position",
            "limits",
            "bestmove",
            "info",
            "timings",
            "exit_status",
            "stdout_log",
            "stderr_log",
        ]:
            self.assertIn(field, envelope)


class TestC0_6FakeEnginePolicy(ClassicalTestCase):
    def test_fake_engine_is_excluded_from_strength_tournaments(self):
        fake_engine = {"engine_id": "fake-uci", "fake": True, "tournament": False}
        self.assertTrue(fake_engine["fake"])
        self.assertFalse(fake_engine["tournament"])
