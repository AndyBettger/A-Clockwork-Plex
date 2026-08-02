from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

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
