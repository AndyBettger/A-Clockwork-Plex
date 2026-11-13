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

    def test_resource_css_is_verified_only_for_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "squeekboard-c2-uk-theme-v1"
            root.mkdir()
            theme = "midnight_blue"
            gen = mock.Mock(DEST=root, styles=lambda: {theme: "CSS"})
            checker = mock.Mock(generator=lambda: gen, validate=mock.Mock())
            resource = mock.Mock(
                samples=mock.Mock(return_value={theme: "resource css"}),
                verify_stage=mock.Mock(),
                trial_override=lambda name: "/sm/puri/squeekboard=/safe/" + name,
            )
            with mock.patch.object(self.s, "load_theme_validator", return_value=checker), \
                 mock.patch.object(self.s, "load_resource_probe", return_value=resource):
                unchanged = self.s.candidate_style_environment(theme)
                self.assertNotIn("G_RESOURCE_OVERLAYS", unchanged)
                resource.samples.assert_not_called()
                overridden = self.s.candidate_style_environment(
                    theme, resource_overlay=True
                )
                self.assertEqual(
                    overridden["G_RESOURCE_OVERLAYS"],
                    "/sm/puri/squeekboard=/safe/midnight_blue",
                )
                self.assertEqual(set(overridden), {
                    "SQUEEKBOARD_KEYBOARDSDIR", "XDG_CONFIG_HOME", "G_RESOURCE_OVERLAYS"
                })
                resource.verify_stage.assert_called_once_with({theme: "resource css"})

    def test_overlay_fail_closed_before_start_and_never_creates_trial(self):
        with mock.patch.object(self.s, "check_baseline") as stock, \
             mock.patch.object(self.s, "load_inspector") as elf, \
             mock.patch.object(self.s, "tempfile") as temporary:
            with self.assertRaisesRegex(self.s.TrialError, "requires --uk-theme"):
                self.s.prepare(
                    Path("artifact.zip"), modify=True, resource_overlay=True
                )
            stock.assert_not_called()
            elf.assert_not_called()
            temporary.mkdtemp.assert_not_called()

    def test_resource_overlay_plan_checks_stage_before_creating_trial(self):
        candidate_env = {
            "SQUEEKBOARD_KEYBOARDSDIR": "/safe/layouts",
            "XDG_CONFIG_HOME": "/safe/theme",
            "G_RESOURCE_OVERLAYS": "/sm/puri/squeekboard=/safe/resource",
        }
        with mock.patch.object(self.s, "check_baseline", return_value=(111, {})), \
             mock.patch.object(self.s, "load_inspector") as inspector, \
             mock.patch.object(self.s, "unit_active", return_value=False), \
             mock.patch.object(self.s, "candidate_style_environment",
                               return_value=candidate_env) as style, \
             mock.patch.object(self.s, "tempfile") as temporary:
            _pid, _env, state = self.s.prepare(
                Path("artifact.zip"), modify=False, uk_theme="midnight_blue",
                resource_overlay=True,
            )
            self.assertIsNone(state)
            style.assert_called_once_with("midnight_blue", resource_overlay=True)
            inspector.return_value.inspect.assert_called_once()
            temporary.mkdtemp.assert_not_called()

    def test_read_state_accepts_only_matching_theme_and_resource_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "trials"
            trial = root / "trial-abc"
            trial.mkdir(parents=True)
            state = trial / "state.json"
            layout_root = Path(temp) / "layouts"
            resource_root = Path(temp) / "resource"
            theme = "midnight_blue"
            gen = mock.Mock(DEST=layout_root, styles=lambda: {theme: "CSS"})
            checker = mock.Mock(generator=lambda: gen)
            resource = mock.Mock(ROOT=resource_root, RESOURCE_PREFIX="/sm/puri/squeekboard")
            data = {
                "schema": 1,
                "env": {"WAYLAND_DISPLAY": "wayland-0"},
                "stock_pid": 123,
                "candidate": str(trial / "squeekboard-overlay-arm64"),
                "stock_unit": "acp-squeekboard-stock-abc",
                "trial_env": {
                    "SQUEEKBOARD_KEYBOARDSDIR": str(layout_root / "keyboards"),
                    "XDG_CONFIG_HOME": str(layout_root / "themes" / theme),
                    "G_RESOURCE_OVERLAYS":
                        "/sm/puri/squeekboard=" + str(resource_root / "palettes" / theme),
                },
            }
            with mock.patch.object(self.s, "ROOT", root), \
                 mock.patch.object(self.s, "load_theme_validator", return_value=checker), \
                 mock.patch.object(self.s, "load_resource_probe", return_value=resource):
                state.write_text(json.dumps(data))
                # On restoration the private theme files may be missing. Only
                # allowlisted paths, not CSS availability, may gate recovery.
                self.assertEqual(
                    self.s.read_state(state, require_candidate=False)["stock_pid"], 123
                )
                data["trial_env"]["G_RESOURCE_OVERLAYS"] = (
                    "/sm/puri/squeekboard=/tmp/unapproved"
                )
                state.write_text(json.dumps(data))
                with self.assertRaisesRegex(self.s.TrialError, "outside the pinned stage"):
                    self.s.read_state(state, require_candidate=False)
                data["trial_env"]["G_RESOURCE_OVERLAYS"] = (
                    "/sm/puri/squeekboard=" + str(resource_root / "palettes" / theme)
                )
                data["trial_env"]["XDG_CONFIG_HOME"] = str(layout_root / "themes" / "classic_dark")
                state.write_text(json.dumps(data))
                with self.assertRaises(self.s.TrialError):
                    self.s.read_state(state, require_candidate=False)

    def test_compact_layout_explicitly_requires_both_theme_flags(self):
        with mock.patch.object(self.s, "check_baseline") as baseline, \
             mock.patch.object(self.s, "load_inspector") as inspector, \
             mock.patch.object(self.s, "tempfile") as temporary:
            for kwargs in (
                {"compact_number": True},
                {"compact_number": True, "uk_theme": "midnight_blue"},
                {"compact_number": True, "resource_overlay": True},
            ):
                with self.subTest(kwargs=kwargs), \
                     self.assertRaisesRegex(self.s.TrialError, "requires both"):
                    self.s.prepare(Path("candidate.zip"), modify=True, **kwargs)
            baseline.assert_not_called()
            inspector.assert_not_called()
            temporary.mkdtemp.assert_not_called()

    def test_compact_candidate_only_and_accepted_v1_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "stable"
            root.mkdir()
            compact_path = str(Path(tmp) / "compact/keyboards")
            theme = "midnight_blue"
            generator = mock.Mock(DEST=root, styles=lambda: {theme: "CSS"})
            checker = mock.Mock(generator=lambda: generator, validate=mock.Mock())
            with mock.patch.object(self.s, "load_theme_validator", return_value=checker), \
                 mock.patch.object(self.s, "verified_resource_override",
                                   return_value="/sm/puri/squeekboard=/private/theme"), \
                 mock.patch.object(self.s, "verified_compact_keyboard_dir",
                                   return_value=compact_path) as compact:
                accepted = self.s.candidate_style_environment(
                    theme, resource_overlay=True
                )
                compact.assert_not_called()
                self.assertEqual(
                    accepted["SQUEEKBOARD_KEYBOARDSDIR"], str(root / "keyboards")
                )
                alternative = self.s.candidate_style_environment(
                    theme, resource_overlay=True, compact_number=True
                )
                compact.assert_called_once_with()
                self.assertEqual(
                    alternative["SQUEEKBOARD_KEYBOARDSDIR"], compact_path
                )
                self.assertEqual(
                    alternative["XDG_CONFIG_HOME"], accepted["XDG_CONFIG_HOME"]
                )
                self.assertEqual(
                    alternative["G_RESOURCE_OVERLAYS"],
                    accepted["G_RESOURCE_OVERLAYS"],
                )
                with self.assertRaisesRegex(self.s.TrialError, "requires resource-overlay"):
                    self.s.candidate_style_environment(theme, compact_number=True)

    def test_compact_private_files_must_verify_before_trial_creates_state(self):
        compact = mock.Mock()
        compact.CompactError = type("CompactError", (Exception,), {})
        compact.input_layouts.return_value = {"number/gb.yaml": "original"}
        compact.expected_layouts.return_value = (
            {"number/gb.yaml": "modified"}, 356.57, 160.456
        )
        compact.ROOT = Path("/private/compact")
        compact.verify.side_effect = compact.CompactError("tampered")
        with mock.patch.object(self.s, "load_compact_number_stage", return_value=compact):
            with self.assertRaisesRegex(self.s.TrialError, "verification failed"):
                self.s.verified_compact_keyboard_dir()
        compact.verify.assert_called_once()

    def test_compact_plan_is_read_only_and_uses_compact_environment(self):
        env = {
            "SQUEEKBOARD_KEYBOARDSDIR": "/private/compact/keyboards",
            "XDG_CONFIG_HOME": "/private/accepted/themes/midnight_blue",
            "G_RESOURCE_OVERLAYS": "/sm/puri/squeekboard=/private/css/midnight_blue",
        }
        with mock.patch.object(self.s, "check_baseline", return_value=(123, {})), \
             mock.patch.object(self.s, "load_inspector") as inspector, \
             mock.patch.object(self.s, "unit_active", return_value=False), \
             mock.patch.object(self.s, "candidate_style_environment",
                               return_value=env) as candidate, \
             mock.patch.object(self.s, "tempfile") as temporary:
            pid, baseline, state = self.s.prepare(
                Path("candidate.zip"), modify=False, uk_theme="midnight_blue",
                resource_overlay=True, compact_number=True,
            )
            self.assertEqual(pid, 123)
            self.assertEqual(baseline, {})
            self.assertIsNone(state)
            candidate.assert_called_once_with(
                "midnight_blue", resource_overlay=True, compact_number=True
            )
            inspector.return_value.inspect.assert_called_once()
            temporary.mkdtemp.assert_not_called()

    def test_state_allows_compact_with_matching_palette_without_needing_stage_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "trial-root"
            trial = root / "trial-test123"
            trial.mkdir(parents=True)
            state_path = trial / "state.json"
            stable_root = Path(temp) / "stable"
            compact_root = Path(temp) / "compact-not-on-disk"
            resource_root = Path(temp) / "resource"
            generation = mock.Mock(
                DEST=stable_root, styles=lambda: {"midnight_blue": "css"}
            )
            theme_checker = mock.Mock(generator=lambda: generation)
            compact = mock.Mock(ROOT=compact_root)
            resource = mock.Mock(
                ROOT=resource_root, RESOURCE_PREFIX="/sm/puri/squeekboard"
            )
            data = {
                "schema": 1,
                "stock_pid": 123,
                "env": {"WAYLAND_DISPLAY": "wayland-0"},
                "candidate": str(trial / "squeekboard-overlay-arm64"),
                "stock_unit": "acp-squeekboard-stock-test123",
                "trial_env": {
                    "SQUEEKBOARD_KEYBOARDSDIR": str(compact_root / "keyboards"),
                    "XDG_CONFIG_HOME": str(stable_root / "themes/midnight_blue"),
                    "G_RESOURCE_OVERLAYS": "/sm/puri/squeekboard=" +
                        str(resource_root / "palettes/midnight_blue"),
                },
            }
            with mock.patch.object(self.s, "ROOT", root), \
                 mock.patch.object(self.s, "load_theme_validator",
                                   return_value=theme_checker), \
                 mock.patch.object(self.s, "load_compact_number_stage",
                                   return_value=compact), \
                 mock.patch.object(self.s, "load_resource_probe",
                                   return_value=resource):
                state_path.write_text(json.dumps(data))
                self.assertEqual(
                    self.s.read_state(state_path, require_candidate=False)["stock_pid"],
                    123,
                )
                compact.verify.assert_not_called()
                data["trial_env"].pop("G_RESOURCE_OVERLAYS")
                state_path.write_text(json.dumps(data))
                with self.assertRaisesRegex(self.s.TrialError, "candidate-only CSS"):
                    self.s.read_state(state_path, require_candidate=False)
                data["trial_env"]["G_RESOURCE_OVERLAYS"] = (
                    "/sm/puri/squeekboard=" +
                    str(resource_root / "palettes/midnight_blue")
                )
                data["trial_env"]["SQUEEKBOARD_KEYBOARDSDIR"] = "/tmp/untrusted"
                state_path.write_text(json.dumps(data))
                with self.assertRaisesRegex(self.s.TrialError, "outside the pinned stage"):
                    self.s.read_state(state_path, require_candidate=False)

    def test_compact_test_does_not_modify_trial_timeouts_or_stock_recovery(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("TRIAL_SECONDS = 180", source)
        self.assertIn("ROLLBACK_SECONDS = 240", source)
        self.assertIn('parser.add_argument(\n        "--compact-number"', source)
        self.assertNotIn("dpkg -i", source)
        self.assertNotIn("apt-get install", source)

    def test_timeout_is_bounded_and_backup_outlasts_trial(self):
        self.assertEqual(self.s.TRIAL_SECONDS, 180)
        self.assertGreater(self.s.ROLLBACK_SECONDS, self.s.TRIAL_SECONDS + 15)

    def test_private_uk_theme_paths_are_verified_and_opt_in_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "squeekboard-c2-uk-theme-v1"
            root.mkdir()
            palette = "midnight_blue"
            generation = mock.Mock(DEST=root, styles=lambda: {palette: "css"})
            checker = mock.Mock(generator=lambda: generation, validate=mock.Mock())
            with mock.patch.object(self.s, "load_theme_validator", return_value=checker):
                overrides = self.s.candidate_style_environment(palette)
                self.assertEqual(overrides["SQUEEKBOARD_KEYBOARDSDIR"],
                                 str(root / "keyboards"))
                self.assertEqual(overrides["XDG_CONFIG_HOME"],
                                 str(root / "themes" / palette))
                checker.validate.assert_called_once()
                with self.assertRaisesRegex(self.s.TrialError, "Unknown ACP"):
                    self.s.candidate_style_environment("untrusted-theme")
                self.assertEqual(checker.validate.call_count, 1)

    def test_plan_checks_uk_stage_without_installing_or_interrupting(self):
        with mock.patch.object(self.s, "check_baseline", return_value=(1484, {})), \
             mock.patch.object(self.s, "load_inspector") as inspector, \
             mock.patch.object(self.s, "unit_active", return_value=False), \
             mock.patch.object(self.s, "candidate_style_environment",
                               return_value={"SQUEEKBOARD_KEYBOARDSDIR": "/safe/gb",
                                             "XDG_CONFIG_HOME": "/safe/theme"}) as verify, \
             mock.patch.object(self.s, "tempfile") as temporary:
            _pid, env, state = self.s.prepare(
                Path("source.zip"), modify=False, uk_theme="midnight_blue"
            )
            self.assertIsNone(state)
            self.assertEqual(env, {})
            verify.assert_called_once_with("midnight_blue")
            inspector.return_value.inspect.assert_called_once()
            temporary.mkdtemp.assert_not_called()

    def test_recovery_has_no_candidate_theme_or_keyboard_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "trial-abc"
            folder.mkdir()
            state_path = folder / "state.json"
            state_path.write_text(json.dumps({
                "schema": 1,
                "env": {"WAYLAND_DISPLAY": "wayland-0"},
                "trial_env": {"SQUEEKBOARD_KEYBOARDSDIR": "/trial/gb",
                              "XDG_CONFIG_HOME": "/trial/theme",
                              "G_RESOURCE_OVERLAYS":
                                  "/sm/puri/squeekboard=/trial/resource"},
                "stock_pid": 123,
                "candidate": str(folder / "squeekboard-overlay-arm64"),
                "stock_unit": "acp-squeekboard-stock-abc",
            }))
            calls = []
            def fake_run(*args, **_kwargs):
                calls.append(args)
                return mock.Mock(returncode=0, stderr="")
            with mock.patch.object(self.s, "ROOT", root), \
                 mock.patch.object(self.s, "read_state", return_value=json.loads(state_path.read_text())), \
                 mock.patch.object(self.s, "run", side_effect=fake_run), \
                 mock.patch.object(self.s, "candidate_pids", return_value=[]), \
                 mock.patch.object(self.s, "vendor_pids", side_effect=[[], [9876]]), \
                 mock.patch.object(self.s.time, "sleep"):
                self.s.restore_stock(state_path, stop_trial=False)
            command = next(c for c in calls if c[:1] == ("systemd-run",))
            self.assertTrue(any("--setenv=WAYLAND_DISPLAY=wayland-0" in x for x in command))
            self.assertFalse(any(
                "SQUEEKBOARD_KEYBOARDSDIR" in x or "XDG_CONFIG_HOME" in x
                or "G_RESOURCE_OVERLAYS" in x for x in command
            ))

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
        self.assertIn("--property=KillMode=control-group", commands[1])
        self.assertIn("--property=TimeoutStopSec=5s", commands[1])

    def test_timer_failure_prevents_trial_service_start(self):
        with mock.patch.object(
            self.s, "prepare", return_value=(1484, {}, Path("/tmp/mock/state.json"))
        ), mock.patch.object(
            self.s, "run", return_value=mock.Mock(returncode=1, stderr="not available")
        ) as runner:
            with self.assertRaisesRegex(self.s.TrialError, "rollback timer"):
                self.s.start(Path("candidate.zip"))
            self.assertEqual(runner.call_count, 1)

    def test_restore_stops_trial_before_lock_and_checks_candidate_is_gone(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "trial-abc"
            folder.mkdir()
            state = folder / "state.json"
            state.write_text(json.dumps({
                "schema": 1, "env": {"WAYLAND_DISPLAY": "wayland-0"},
                "candidate": str(folder / "squeekboard-overlay-arm64"),
                "stock_unit": "acp-squeekboard-stock-abc",
            }))
            calls = []
            def fake_run(*args, **_kwargs):
                calls.append(args)
                return mock.Mock(returncode=0, stderr="")
            with mock.patch.object(self.s, "ROOT", root), \
                 mock.patch.object(self.s, "run", side_effect=fake_run), \
                 mock.patch.object(self.s, "unit_active", return_value=False), \
                 mock.patch.object(self.s, "candidate_pids", return_value=[]) as check, \
                 mock.patch.object(self.s, "vendor_pids", side_effect=[[], [9876]]):
                self.s.restore_stock(state, stop_trial=True)
            self.assertEqual(calls[0][:3], ("systemctl", "--user", "stop"))
            self.assertEqual(calls[1][:3], ("systemd-run", "--user", "--collect"))
            self.assertTrue(check.called)

    def test_recovery_never_starts_stock_while_candidate_still_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "trial-abc"
            folder.mkdir()
            state = folder / "state.json"
            state.write_text(json.dumps({
                "schema": 1, "env": {"WAYLAND_DISPLAY": "wayland-0"},
                "candidate": str(folder / "squeekboard-overlay-arm64"),
                "stock_unit": "acp-squeekboard-stock-abc",
            }))
            with mock.patch.object(self.s, "ROOT", root), \
                 mock.patch.object(self.s, "candidate_pids", return_value=[999]), \
                 mock.patch.object(self.s, "vendor_pids") as stock, \
                 mock.patch.object(self.s, "run") as command, \
                 mock.patch.object(self.s.time, "sleep"):
                with self.assertRaisesRegex(self.s.TrialError, "still running"):
                    self.s.restore_stock(state, stop_trial=False)
                stock.assert_not_called()
                command.assert_not_called()

    def test_exact_candidate_pid_enumeration_does_not_kill_any_process(self):
        with mock.patch.object(self.s.os, "kill") as killer:
            self.assertEqual(self.s.candidate_pids(Path("/no/such/overlay")), [])
            killer.assert_not_called()

    def test_source_never_installs_or_changes_global_keyboard(self):
        body = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("dpkg -i", "apt-get install", "sudo ", "systemctl --system", "pkill -f"):
            self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
