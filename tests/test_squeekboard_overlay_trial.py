"""Guarded Squeekboard trial checks; no Pi keyboard or systemd services are touched."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/try-squeekboard-overlay.py"


def load():
    spec = importlib.util.spec_from_file_location("acp_osk_trial", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KeyboardTrialTests(unittest.TestCase):
    def setUp(self):
        self.s = load()

    def test_timeout_is_bounded_and_backup_outlasts_trial(self):
        self.assertEqual(self.s.TRIAL_SECONDS, 180)
        self.assertGreater(self.s.ROLLBACK_SECONDS, self.s.TRIAL_SECONDS + 15)

    def test_plan_does_not_stage_or_start_services(self):
        with mock.patch.object(self.s, "check_baseline", return_value=(1484, {})), \
             mock.patch.object(self.s, "load_inspector") as inspector, \
             mock.patch.object(self.s, "unit_active", return_value=False), \
             mock.patch.object(self.s, "tempfile") as temporary:
            _pid, _env, state = self.s.prepare(Path("source.zip"), modify=False)
            self.assertIsNone(state)
            inspector.return_value.inspect.assert_called_once()
            temporary.mkdtemp.assert_not_called()

    def test_trial_refuses_to_stop_stock_without_armed_timer(self):
        with mock.patch.object(self.s, "read_state", return_value={"stock_pid": 1484}), \
             mock.patch.object(self.s, "unit_active", return_value=False), \
             mock.patch.object(self.s.os, "kill") as killer:
            with self.assertRaisesRegex(self.s.TrialError, "not armed"):
                self.s.worker(Path("state.json"))
            killer.assert_not_called()

    def test_user_session_is_explicit_wayland_and_dbus(self):
        with mock.patch.object(self.s.os, "getuid", return_value=1000), \
             mock.patch.object(self.s.Path, "is_socket", return_value=True):
            env = self.s.session_environment()
        self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-0")
        self.assertEqual(env["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/run/user/1000/bus")

    def test_staged_state_rejects_path_traversal(self):
        with mock.patch.object(
            self.s, "ROOT", Path("/home/andy/.cache/a-clockwork-plex/osk-overlay-trials")
        ):
            with self.assertRaises(self.s.TrialError):
                self.s.read_state(Path("/tmp/untrusted/state.json"))

    def test_recovery_does_not_require_candidate_to_still_exist(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "trial-test123"
            directory.mkdir()
            state_path = directory / "state.json"
            state_path.write_text(json.dumps({
                "schema": 1, "env": {"WAYLAND_DISPLAY": "wayland-0"},
                "candidate": str(directory / "squeekboard-overlay-arm64"),
                "stock_unit": "acp-squeekboard-stock-test123",
            }))
            with mock.patch.object(self.s, "ROOT", Path(root)), \
                 mock.patch.object(self.s, "verify_candidate", side_effect=AssertionError(
                     "Recovery must not depend on the experimental file"
                 )):
                state = self.s.read_state(state_path, require_candidate=False)
            self.assertEqual(state["stock_unit"], "acp-squeekboard-stock-test123")

    def test_start_arms_timer_before_trial_service(self):
        state_path = Path("/tmp/mock/state.json")
        commands = []

        def fake_run(*args, **kwargs):
            commands.append(args)
            return mock.Mock(returncode=0, stderr="")

        with mock.patch.object(
            self.s, "prepare", return_value=(1484, {"WAYLAND_DISPLAY": "wayland-0"}, state_path)
        ), mock.patch.object(self.s, "run", side_effect=fake_run), \
             mock.patch.object(self.s, "unit_active", return_value=True):
            self.s.start(Path("candidate.zip"))
        self.assertEqual(len(commands), 2)
        self.assertIn("--on-active=240s", commands[0])
        self.assertIn("--unit=" + self.s.TRIAL_UNIT, commands[1])

    def test_timer_failure_prevents_trial_service_start(self):
        with mock.patch.object(
            self.s, "prepare", return_value=(1484, {}, Path("/tmp/mock/state.json"))
        ), mock.patch.object(
            self.s, "run", return_value=mock.Mock(returncode=1, stderr="not available")
        ) as runner:
            with self.assertRaisesRegex(self.s.TrialError, "rollback timer"):
                self.s.start(Path("candidate.zip"))
            self.assertEqual(runner.call_count, 1)

    def test_source_never_installs_or_changes_global_keyboard(self):
        body = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("dpkg -i", "apt-get install", "sudo ", "systemctl --system", "pkill -f"):
            self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
