from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.shairport_name import ShairportNameManager, validate_receiver_name


HELPER_PATH = Path("scripts/a-clockwork-plex-shairport-name.py")
SPEC = importlib.util.spec_from_file_location("acp_shairport_name_helper", HELPER_PATH)
HELPER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(HELPER)


class ShairportNameTests(unittest.TestCase):
    def test_receiver_name_validation_preserves_human_readable_names(self):
        self.assertEqual(validate_receiver_name("  Mostly Harmless Bedroom  "), "Mostly Harmless Bedroom")
        with self.assertRaisesRegex(ValueError, "cannot be blank"):
            validate_receiver_name("   ")
        with self.assertRaisesRegex(ValueError, "50 characters"):
            validate_receiver_name("x" * 51)
        with self.assertRaisesRegex(ValueError, "control characters"):
            validate_receiver_name("Bedroom\nReceiver")

    def test_helper_updates_only_general_name_and_preserves_other_blocks(self):
        original = '''general =\n{\n    name = "Old Receiver";\n    interpolation = "soxr";\n};\n\nsessioncontrol =\n{\n    active_state_timeout = 10;\n};\n'''
        updated = HELPER.update_receiver_name(original, "Mostly Harmless Bedroom")

        self.assertEqual(HELPER.receiver_name_from_config(updated), "Mostly Harmless Bedroom")
        self.assertIn('interpolation = "soxr";', updated)
        self.assertIn("active_state_timeout = 10;", updated)
        self.assertEqual(updated.count("name ="), 1)

    def test_helper_adds_general_block_when_missing(self):
        original = 'sessioncontrol =\n{\n    active_state_timeout = 10;\n};\n'
        updated = HELPER.update_receiver_name(original, 'Bedroom "Plexamp"')

        self.assertEqual(HELPER.receiver_name_from_config(updated), 'Bedroom "Plexamp"')
        self.assertTrue(updated.startswith("general ="))
        self.assertIn('name = "Bedroom \\"Plexamp\\"";', updated)
        self.assertIn("sessioncontrol", updated)

    def test_candidate_validation_uses_an_isolated_temporary_identity_and_port(self):
        candidate = Path("/tmp/shairport-sync-candidate.conf")
        command = HELPER.validation_command(candidate)

        self.assertEqual(command[0], str(HELPER.SHAIRPORT_BINARY))
        self.assertIn("--displayConfig", command)
        self.assertEqual(command[command.index("--configfile") + 1], str(candidate))
        self.assertEqual(command[command.index("--port") + 1], "0")
        self.assertTrue(command[command.index("--name") + 1].startswith("ACP-config-check-"))
        self.assertNotIn("systemctl", " ".join(command))

    def test_candidate_validation_stops_after_parser_completion_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "fake-shairport-sync"
            binary.write_text(
                "#!/usr/bin/env python3\n"
                "import time\n"
                "print('>> Display Config Start.', flush=True)\n"
                "print('>> Display Config End.', flush=True)\n"
                "time.sleep(10)\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            candidate = root / "candidate.conf"
            candidate.write_text('general = { name = "Bedroom"; };\n', encoding="utf-8")

            started = time.monotonic()
            with patch.object(HELPER, "SHAIRPORT_BINARY", binary):
                valid, error = HELPER.validate_config(candidate)
            elapsed = time.monotonic() - started

        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertLess(elapsed, 2.0, "validator should stop as soon as parsing completes")

    def test_candidate_validation_rejects_output_without_completion_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "fake-shairport-sync"
            binary.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print('line 7: syntax error near receiver name', flush=True)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            candidate = root / "candidate.conf"
            candidate.write_text("invalid", encoding="utf-8")

            with patch.object(HELPER, "SHAIRPORT_BINARY", binary):
                valid, error = HELPER.validate_config(candidate)

        self.assertFalse(valid)
        self.assertIn("syntax error", error or "")

    def test_manager_uses_restricted_status_and_set_commands(self):
        commands = []
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper"
            helper.write_text("#!/bin/sh\n", encoding="utf-8")
            helper.chmod(0o755)

            def runner(command, **_kwargs):
                commands.append(command)
                payload = {
                    "ok": True,
                    "available": True,
                    "receiver_name": "New Receiver" if command[-2] == "set" else "Old Receiver",
                    "service_active": True,
                }
                return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

            manager = ShairportNameManager(helper, runner=runner)
            status = manager.status()
            applied = manager.apply("New Receiver")

        self.assertEqual(commands[0], ["sudo", "-n", str(helper), "status"])
        self.assertEqual(commands[1], ["sudo", "-n", str(helper), "set", "New Receiver"])
        self.assertEqual(status["receiver_name"], "Old Receiver")
        self.assertEqual(applied["receiver_name"], "New Receiver")

    def test_manager_reports_missing_helper_without_sudo_attempt(self):
        manager = ShairportNameManager("/definitely/not/installed")
        status = manager.status()

        self.assertFalse(status["available"])
        self.assertFalse(status["installed"])
        self.assertIn("not installed", status["error"])
        with self.assertRaisesRegex(RuntimeError, "not installed"):
            manager.apply("Bedroom Plexamp")


if __name__ == "__main__":
    unittest.main()
