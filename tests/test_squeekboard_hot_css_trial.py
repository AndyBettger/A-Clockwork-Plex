"""Safety gates for isolated C3 keyboard handover and independent stock recovery."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-squeekboard-hot-css.py"
C2 = ROOT / "scripts/try-squeekboard-overlay.py"

spec = importlib.util.spec_from_file_location("acp_c3_keyboard_trial", SRC)
assert spec and spec.loader
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


class C3TimedTrialTests(unittest.TestCase):
    def test_exact_c3_hash_and_distinct_service_identifiers(self):
        self.assertEqual(trial.EXPECTED_CANDIDATE_SHA256,
                         "fdd1da08861bbc45331e66a70996953ed6ebfb52915a0a5abeb21c585f40bfd5")
        self.assertEqual(trial.EXPECTED_VENDOR_SHA256,
                         "2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338")
        self.assertEqual((trial.TRIAL_SECONDS, trial.ROLLBACK_SECONDS), (180, 240))
        self.assertNotEqual(trial.TRIAL_UNIT, "acp-squeekboard-overlay-trial")
        self.assertNotEqual(trial.ROLLBACK_UNIT, "acp-squeekboard-overlay-restore")
        self.assertEqual(trial.CANDIDATE_FILENAME, "squeekboard-c3-hot-css-arm64")

    def test_readonly_plan_verifies_exact_artifact_and_c3_css(self):
        checked = []
        probe = mock.Mock(inspect=lambda p: checked.append(p))
        with mock.patch.object(trial, "check_baseline",
                               return_value=(1432, {"WAYLAND_DISPLAY": "wayland-0"})), \
             mock.patch.object(trial, "load_inspector", return_value=probe), \
             mock.patch.object(trial, "unit_active", return_value=False), \
             mock.patch.object(trial, "candidate_style_environment",
                               return_value={"ACP_SQUEEKBOARD_CSS_DIR": "/private"}), \
             mock.patch.object(Path, "mkdir") as create:
            pid, env, state = trial.prepare(Path("/my/private.zip"), modify=False)
        self.assertEqual(pid, 1432)
        self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-0")
        self.assertIsNone(state)
        self.assertEqual(checked, [Path("/my/private.zip")])
        create.assert_not_called()

    def test_c2_and_c3_active_trials_refuse_any_handover(self):
        units = (
            trial.TRIAL_UNIT + ".service", trial.ROLLBACK_UNIT + ".timer",
            trial.C2_TRIAL_UNIT + ".service", trial.C2_ROLLBACK_UNIT + ".timer",
        )
        for unit in units:
            with self.subTest(unit=unit), \
                 mock.patch.object(trial, "check_baseline", return_value=(1, {})), \
                 mock.patch.object(trial, "load_inspector", return_value=mock.Mock()), \
                 mock.patch.object(trial, "unit_active", side_effect=lambda u: u == unit), \
                 mock.patch.object(trial, "candidate_style_environment") as style:
                with self.assertRaisesRegex(trial.TrialError, "active"):
                    trial.prepare(Path("/fake.zip"), modify=False)
                style.assert_not_called()

    def test_orphan_experimental_keyboard_refuses_handover(self):
        with mock.patch.object(trial, "check_baseline", return_value=(1, {})), \
             mock.patch.object(trial, "load_inspector", return_value=mock.Mock()), \
             mock.patch.object(trial, "unit_active", return_value=False), \
             mock.patch.object(trial, "orphan_trial_keyboard_pids", return_value=[4321]), \
             mock.patch.object(trial, "candidate_style_environment") as style:
            with self.assertRaisesRegex(trial.TrialError, "Orphan C2/C3"):
                trial.prepare(Path("/test.zip"), modify=False)
            style.assert_not_called()

    def test_private_c3_environment_contains_only_four_candidate_overrides(self):
        layout = mock.Mock(ROOT=Path("/accepted/c2-compact"))
        layout.expected_layouts.return_value = ({}, 1, 1)
        layout.input_layouts.return_value = {}
        layout.verify.return_value = None
        generator = mock.Mock(DEST=Path("/accepted/c2"))
        gen = mock.Mock(generator=lambda: generator, validate=mock.Mock(), CheckError=ValueError)
        stage = mock.Mock(ROOT=Path("/candidate/c3"), RESOURCE_PREFIX="/sm/puri/squeekboard",
                          DEFAULT_PALETTE="classic_dark", CSSStageError=ValueError,
                          palettes=lambda: {"classic_dark": b"css"},
                          inspect=lambda css: "classic_dark")
        stage.resource_environment.return_value = {
            "G_RESOURCE_OVERLAYS": "/sm/puri/squeekboard=/candidate/c3",
            "ACP_SQUEEKBOARD_CSS_DIR": "/candidate/c3",
        }
        with mock.patch.object(trial, "load_theme_validator", return_value=gen), \
             mock.patch.object(trial, "load_compact_number_stage", return_value=layout), \
             mock.patch.object(trial, "load_c3_stage", return_value=stage), \
             mock.patch.object(Path, "is_dir", return_value=True):
            got = trial.candidate_style_environment()
        self.assertEqual(got, {
            "G_RESOURCE_OVERLAYS": "/sm/puri/squeekboard=/candidate/c3",
            "ACP_SQUEEKBOARD_CSS_DIR": "/candidate/c3",
            "SQUEEKBOARD_KEYBOARDSDIR": "/accepted/c2-compact/keyboards",
            "XDG_CONFIG_HOME": "/accepted/c2/themes/classic_dark",
        })

    def test_c3_requires_classic_dark_initially(self):
        generator = mock.Mock(DEST=Path("/accepted/c2"))
        gen = mock.Mock(generator=lambda: generator, validate=mock.Mock(), CheckError=ValueError)
        stage = mock.Mock(ROOT=Path("/candidate/c3"), RESOURCE_PREFIX="/sm/puri/squeekboard",
                          DEFAULT_PALETTE="classic_dark", CSSStageError=ValueError)
        stage.palettes.return_value = {"classic_dark": b"a", "midnight_blue": b"b"}
        stage.inspect.return_value = "midnight_blue"
        with mock.patch.object(trial, "load_theme_validator", return_value=gen), \
             mock.patch.object(trial, "verified_compact_keyboard_dir", return_value="/private/layout"), \
             mock.patch.object(trial, "load_c3_stage", return_value=stage), \
             mock.patch.object(Path, "is_dir", return_value=True):
            with self.assertRaisesRegex(trial.TrialError, "Classic Dark"):
                trial.candidate_style_environment()

    def test_candidate_hash_refuses_wrong_bytes_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / trial.CANDIDATE_FILENAME
            file.write_bytes(b"wrong keyboard")
            with self.assertRaisesRegex(trial.TrialError, "hash mismatch"):
                trial.verify_candidate(file)
            self.assertEqual(file.read_bytes(), b"wrong keyboard")

    def fake_trial_state(self, dir: Path):
        root = dir / "c3-private-root"
        session = root / "trial-abcd"
        session.mkdir(parents=True)
        path = session / "state.json"
        runtime = Path("/run/user") / str(trial.os.getuid())
        env = {
            "XDG_RUNTIME_DIR": str(runtime),
            "WAYLAND_DISPLAY": "wayland-0",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "bus"),
            "XDG_SESSION_TYPE": "wayland",
            "HOME": str(Path.home()),
        }
        path.write_text(json.dumps({
            "schema": 3,
            "stock_pid": 1212,
            "candidate": str(session / trial.CANDIDATE_FILENAME),
            "env": env,
            "trial_env": {
                "SQUEEKBOARD_KEYBOARDSDIR": str(dir / "compact/keyboards"),
                "XDG_CONFIG_HOME": str(dir / "accepted/themes/classic_dark"),
                "G_RESOURCE_OVERLAYS": "/sm/puri/squeekboard=" + str(dir / "c3-live"),
                "ACP_SQUEEKBOARD_CSS_DIR": str(dir / "c3-live"),
            },
            "stock_unit": "acp-squeekboard-c3-stock-abcd",
        }))
        path.chmod(0o600)
        return root, path

    def read_fake_state(self, root: Path, path: Path):
        stage = mock.Mock(ROOT=root.parent / "c3-live", RESOURCE_PREFIX="/sm/puri/squeekboard")
        layout = mock.Mock(ROOT=root.parent / "compact")
        gen = mock.Mock(DEST=root.parent / "accepted")
        checker = mock.Mock(generator=lambda: gen)
        return (
            mock.patch.object(trial, "ROOT", root),
            mock.patch.object(trial, "load_c3_stage", return_value=stage),
            mock.patch.object(trial, "load_compact_number_stage", return_value=layout),
            mock.patch.object(trial, "load_theme_validator", return_value=checker),
        )

    def test_stock_rescue_validates_state_without_css_or_wayland_socket(self):
        with tempfile.TemporaryDirectory() as temp:
            root, path = self.fake_trial_state(Path(temp))
            patches = self.read_fake_state(root, path)
            with patches[0], patches[1], patches[2], patches[3], \
                 mock.patch.object(trial, "session_environment",
                                   side_effect=AssertionError("No live socket check allowed")), \
                 mock.patch.object(trial, "verify_candidate") as candidate:
                saved = trial.read_state(path, require_candidate=False)
            self.assertEqual(saved["stock_pid"], 1212)
            candidate.assert_not_called()

    def test_rejects_tampered_trial_env_on_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root, path = self.fake_trial_state(Path(temp))
            data = json.loads(path.read_text())
            data["trial_env"]["G_RESOURCE_OVERLAYS"] = "/tmp/untrusted"
            path.write_text(json.dumps(data))
            patches = self.read_fake_state(root, path)
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(trial.TrialError, "trial-only environment"):
                    trial.read_state(path, require_candidate=False)

    def test_c3_rescue_refuses_overlapping_candidate_before_stock_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root, path = self.fake_trial_state(Path(temp))
            with mock.patch.object(trial, "read_state",
                                   return_value={"candidate": str(path.parent / trial.CANDIDATE_FILENAME)}), \
                 mock.patch.object(trial, "candidate_pids", return_value=[4444]), \
                 mock.patch.object(trial, "vendor_pids") as stock, \
                 mock.patch.object(trial, "run") as command, \
                 mock.patch.object(trial.time, "sleep"):
                with self.assertRaisesRegex(trial.TrialError, "still running"):
                    trial.restore_stock(path, stop_trial=False)
                stock.assert_not_called()
                command.assert_not_called()

    def test_restore_never_sets_candidate_css_on_stock_service(self):
        with tempfile.TemporaryDirectory() as temp:
            root, path = self.fake_trial_state(Path(temp))
            runtime = Path("/run/user") / str(trial.os.getuid())
            env = {
                "XDG_RUNTIME_DIR": str(runtime), "WAYLAND_DISPLAY": "wayland-0",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "bus"),
                "XDG_SESSION_TYPE": "wayland", "HOME": str(Path.home()),
            }
            commands = []
            def fake_run(*args, **kwargs):
                commands.append(args)
                return mock.Mock(returncode=0, stderr="")
            with mock.patch.object(trial, "read_state", return_value={
                "env": env, "stock_unit": "acp-squeekboard-c3-stock-abcd",
                "candidate": str(path.parent / trial.CANDIDATE_FILENAME),
            }), mock.patch.object(trial, "run", side_effect=fake_run), \
                 mock.patch.object(trial, "candidate_pids", return_value=[]), \
                 mock.patch.object(trial, "vendor_pids", side_effect=[[], [9876]]), \
                 mock.patch.object(trial.time, "sleep"):
                trial.restore_stock(path, stop_trial=False)
            command = commands[-1]
            self.assertIn("/usr/bin/sbtest", command)
            self.assertFalse(any("ACP_SQUEEKBOARD_CSS_DIR" in x for x in command))
            self.assertFalse(any("G_RESOURCE_OVERLAYS" in x for x in command))
            self.assertIn("--unit=acp-squeekboard-c3-stock-abcd", command)

    def test_rescue_timer_armed_before_candidate_worker(self):
        commands = []
        def fake_run(*args, **kwargs):
            commands.append(args)
            return mock.Mock(returncode=0, stderr="")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trial-a" / "state.json"
            with mock.patch.object(trial, "prepare",
                                   return_value=(42, {"WAYLAND_DISPLAY": "wayland-0"}, path)), \
                 mock.patch.object(trial, "run", side_effect=fake_run), \
                 mock.patch.object(trial, "unit_active", return_value=True):
                trial.start(Path("/fake.zip"))
        self.assertEqual(len(commands), 2)
        self.assertIn("--on-active=240s", commands[0])
        self.assertIn("--unit=" + trial.ROLLBACK_UNIT, commands[0])
        self.assertIn("--unit=" + trial.TRIAL_UNIT, commands[1])
        self.assertIn("--property=KillMode=control-group", commands[1])
        self.assertIn("--property=TimeoutStopSec=5s", commands[1])
        self.assertTrue(all("ACP_SQUEEKBOARD_CSS_DIR" not in str(x) for x in commands))

    def test_worker_refuses_to_stop_stock_without_independent_timer(self):
        with mock.patch.object(trial, "read_state",
                               return_value={"stock_pid": 1001}), \
             mock.patch.object(trial, "unit_active", return_value=False), \
             mock.patch.object(trial.os, "kill") as kill:
            with self.assertRaisesRegex(trial.TrialError, "timer not armed"):
                trial.worker(Path("/nonexistent/state.json"))
            kill.assert_not_called()

    def test_c2_trial_and_old_inspector_completely_unchanged(self):
        source = SRC.read_text()
        self.assertNotIn("--uk-theme", source)
        self.assertNotIn("--resource-overlay", source)
        self.assertNotIn("--compact-number", source)
        self.assertNotIn("dpkg -i", source)
        self.assertNotIn("apt-get", source)
        self.assertNotIn("gsettings set", source)
        self.assertNotIn("systemctl --system", source)
        self.assertNotIn("pkill -f", source)
        self.assertIn('"--property=KillMode=control-group"', source)
        self.assertIn('"--unit=" + ROLLBACK_UNIT', source)
        self.assertNotIn("acp-squeekboard-overlay-restore", trial.ROLLBACK_UNIT)
        self.assertNotIn("try-squeekboard-hot-css.py", C2.read_text())


if __name__ == "__main__":
    unittest.main()
