"""C3 browser-to-native hot-CSS bridge: strict local/opt-in ownership tests."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "app/squeekboard_theme_sync.py"
spec = importlib.util.spec_from_file_location("acp_c3_theme_sync_test", PATH)
assert spec and spec.loader
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)


class C3ThemeSyncTests(unittest.TestCase):
    def request(self, *, remote="127.0.0.1", host="localhost:8088",
                origin="http://localhost:8088", mime="application/json", length=142):
        return types.SimpleNamespace(
            remote_addr=remote, host=host, scheme="http", mimetype=mime,
            content_length=length,
            headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"},
        )

    def test_local_same_origin_json_is_required_for_mutation(self):
        self.assertTrue(bridge.local_browser_request(self.request(), mutation=True))
        self.assertTrue(bridge.local_browser_request(
            self.request(host="127.0.0.1:8088", origin="http://127.0.0.1:8088"),
            mutation=True))
        self.assertTrue(bridge.local_browser_request(
            self.request(remote="::1", host="[::1]:8088", origin="http://[::1]:8088"),
            mutation=True))
        for kwargs in (
            {"remote": "192.168.0.15"},
            {"host": "plexamp.local", "origin": "http://plexamp.local"},
            {"host": "evil.test", "origin": "http://evil.test"},
            {"origin": "https://other.example"},
            {"mime": "text/plain"},
            {"length": 99999},
            {"length": None},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(bridge.local_browser_request(
                    self.request(**kwargs), mutation=True))
        forwarded = self.request()
        forwarded.headers["X-Forwarded-Host"] = "public.example"
        self.assertFalse(bridge.local_browser_request(forwarded, mutation=True))

    def test_real_planner_resolves_day_classic_night_and_astronomy(self):
        cases = (
            ({"daytimeTheme": "midnight_blue",
              "night": {"active": False, "interacting": False,
                        "effectiveStyle": "classic"}}, "midnight_blue"),
            ({"daytimeTheme": "midnight_blue",
              "night": {"active": True, "interacting": False,
                        "effectiveStyle": "classic"}}, "midnight_blue_night_classic_idle"),
            ({"daytimeTheme": "amber_terminal",
              "night": {"active": True, "interacting": True,
                        "effectiveStyle": "classic"}}, "amber_terminal_night_classic_active"),
            ({"daytimeTheme": "midnight_blue",
              "night": {"active": True, "interacting": False,
                        "effectiveStyle": "astronomy"}}, "astronomy_night_idle"),
            ({"daytimeTheme": "unknown",
              "night": {"active": False, "interacting": False,
                        "effectiveStyle": "classic"}}, "classic_dark"),
        )
        for data, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(bridge.validated_payload(data)[0], expected)

    def test_refuses_extra_fields_types_and_client_supplied_palette(self):
        valid = {"daytimeTheme": "classic_dark",
                 "night": {"active": False, "interacting": False,
                           "effectiveStyle": "classic"}}
        for value in (
            None, [], {"palette": "midnight_blue"},
            dict(valid, palette="../../gtk.css"),
            dict(valid, night={"active": False, "interacting": False,
                               "effectiveStyle": "classic", "scheduled": True}),
            dict(valid, night={"active": 1, "interacting": False,
                               "effectiveStyle": "classic"}),
            dict(valid, night={"active": True, "interacting": "yes",
                               "effectiveStyle": "classic"}),
            dict(valid, night={"active": True, "interacting": False,
                               "effectiveStyle": "unknown"}),
        ):
            with self.subTest(value=value), self.assertRaises(bridge.SyncError):
                bridge.validated_payload(value)

    def test_disabled_trial_never_loads_stage_or_writes(self):
        state = {"daytimeTheme": "classic_dark",
                 "night": {"active": False, "interacting": False,
                           "effectiveStyle": "classic"}}
        with mock.patch.object(bridge, "opted_in_trial", return_value=None), \
             mock.patch.object(bridge, "load_script", wraps=bridge.load_script) as load:
            result = bridge.apply(state)
        self.assertEqual(result["enabled"], False)
        self.assertFalse(result["changed"])
        self.assertNotIn(mock.call("stage-squeekboard-hot-css.py"), load.mock_calls)

    def test_user_manager_query_isolated_from_dashboard_system_service_env(self):
        """A system service has no reliable inherited user D-Bus environment."""
        original = os.environ.copy()
        completed = mock.Mock(returncode=0)
        with mock.patch.object(bridge.os, "geteuid", return_value=1000), \
             mock.patch.object(Path, "is_socket", return_value=True), \
             mock.patch.object(bridge.subprocess, "run",
                               return_value=completed) as run:
            self.assertTrue(bridge.user_unit_active("acp-squeekboard-c3-trial.service"))
            env = run.call_args.kwargs["env"]
            runtime = "/run/user/" + str(os.getuid())
            self.assertEqual(env["XDG_RUNTIME_DIR"], runtime)
            self.assertEqual(env["DBUS_SESSION_BUS_ADDRESS"],
                             "unix:path=" + runtime + "/bus")
            self.assertEqual(run.call_args.args[0],
                             ("systemctl", "--user", "is-active", "--quiet",
                              "acp-squeekboard-c3-trial.service"))
            self.assertFalse(bridge.user_unit_active("untrusted.service"))
            self.assertEqual(run.call_count, 1)
        self.assertEqual(os.environ, original)

    def test_missing_user_bus_fails_closed_without_running_systemctl(self):
        with mock.patch.object(bridge.os, "geteuid", return_value=1000), \
             mock.patch.object(Path, "is_socket", return_value=False), \
             mock.patch.object(bridge.subprocess, "run") as run:
            self.assertFalse(bridge.user_unit_active("acp-squeekboard-c3-trial.service"))
            run.assert_not_called()

    def test_opted_in_trial_requires_both_units_and_one_valid_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state = base / "trial-abc" / "state.json"
            state.parent.mkdir()
            state.write_text(json.dumps({"theme_sync": True}))
            state.chmod(0o600)
            candidate = state.parent / "squeekboard-c3-hot-css-arm64"
            mock_trial = types.SimpleNamespace(
                ROOT=base, TRIAL_UNIT="acp-squeekboard-c3-trial",
                ROLLBACK_UNIT="acp-squeekboard-c3-restore",
                C2_TRIAL_UNIT="acp-squeekboard-overlay-trial",
                C2_ROLLBACK_UNIT="acp-squeekboard-overlay-restore",
                unit_active=mock.Mock(side_effect=lambda u: "c3-" in u),
                read_state=mock.Mock(return_value={
                    "created_at": time.time(), "candidate": str(candidate),
                }),
                candidate_pids=mock.Mock(return_value=[2345]),
                vendor_pids=mock.Mock(return_value=[]),
            )
            def legacy_only(unit):
                return "c3-" in unit and "c3-dev" not in unit
            with mock.patch.object(bridge, "load_script", return_value=mock_trial), \
                 mock.patch.object(bridge.os, "geteuid", return_value=1000), \
                 mock.patch.object(bridge, "user_unit_active",
                                   side_effect=legacy_only) as units:
                self.assertEqual(bridge.opted_in_trial(), state)
                units.side_effect = lambda u: False
                self.assertIsNone(bridge.opted_in_trial())
                units.side_effect = legacy_only
                mock_trial.candidate_pids.return_value = []
                self.assertIsNone(bridge.opted_in_trial())
                mock_trial.candidate_pids.return_value = [2345]
                mock_trial.vendor_pids.return_value = [1]
                self.assertIsNone(bridge.opted_in_trial())

    def test_application_is_atomic_idempotent_candidate_only(self):
        data = {"daytimeTheme": "midnight_blue",
                "night": {"active": False, "interacting": False,
                          "effectiveStyle": "classic"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trial-abc" / "state.json"
            path.parent.mkdir()
            choices = {"classic_dark": b"classic", "midnight_blue": b"blue"}
            stage = mock.Mock(palettes=lambda: choices)
            current = ["classic_dark"]
            def update(_styles, name):
                previous = current[0]
                current[0] = name
                return previous, previous != name
            stage.select.side_effect = update
            original_load = bridge.load_script
            def load(filename):
                if filename == "stage-squeekboard-hot-css.py":
                    return stage
                return original_load(filename)
            with mock.patch.object(bridge, "opted_in_trial", return_value=path), \
                 mock.patch.object(bridge, "load_script", side_effect=load):
                first = bridge.apply(data)
                again = bridge.apply(data)
                self.assertEqual(first["palette"], "midnight_blue")
                self.assertTrue(first["changed"])
                self.assertFalse(again["changed"])
                self.assertEqual(stage.select.call_count, 2)
                self.assertTrue((path.parent / "theme-sync.lock").is_file())
                self.assertEqual(stat.S_IMODE(
                    (path.parent / "theme-sync.lock").stat().st_mode), 0o600)

    def test_symlinked_lock_is_rejected_without_select(self):
        data = {"daytimeTheme": "classic_dark",
                "night": {"active": False, "interacting": False,
                          "effectiveStyle": "classic"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "trial-xyz" / "state.json"
            path.parent.mkdir()
            outside = root / "outside"
            outside.write_text("safe")
            (path.parent / "theme-sync.lock").symlink_to(outside)
            stage = mock.Mock()
            original_load = bridge.load_script
            with mock.patch.object(bridge, "opted_in_trial", return_value=path), \
                 mock.patch.object(bridge, "load_script",
                                   side_effect=lambda filename: stage
                                   if filename == "stage-squeekboard-hot-css.py"
                                   else original_load(filename)):
                with self.assertRaises(OSError):
                    bridge.apply(data)
            stage.select.assert_not_called()
            self.assertEqual(outside.read_text(), "safe")

    def test_browser_watcher_has_no_osk_ownership_or_manual_palette_override(self):
        source = (ROOT / "app/static/js/osk-theme-sync.js").read_text()
        template = (ROOT / "app/templates/base.html").read_text()
        self.assertIn("osk-theme-sync.js", template)
        self.assertIn("ACPDashboardPreferences?.read?.()", source)
        self.assertIn("ACPDisplayDimming?.status?.()", source)
        self.assertIn("acp:dashboard-preferences-changed", source)
        self.assertIn("acp:display-night-interaction-ended", source)
        self.assertIn("method: 'POST'", source)
        for bad in ("systemctl", "window.location.reload", "sessionStorage",
                    "SQUEEKBOARD_KEYBOARDSDIR", ".focus(", "document.activeElement"):
            self.assertNotIn(bad, source)

    def test_eight_second_night_preview_triggers_immediate_c3_sync(self):
        """Do not wait for 5s polling to notice a short 8s preview window."""
        dimming = (ROOT / "app/static/js/display-dimming.js").read_text()
        watcher = (ROOT / "app/static/js/osk-theme-sync.js").read_text()
        base = (ROOT / "app/templates/base.html").read_text()
        self.assertIn("function preview(seconds = 8)", dimming)
        preview = dimming.split("function preview(seconds = 8)", 1)[1].split(
            "function configure(", 1
        )[0]
        self.assertIn("schedulePreviewExpiry();", preview)
        self.assertIn("refresh();", preview)
        self.assertIn("acp:display-night-preview-started", preview)
        self.assertIn("detail: status()", preview)
        self.assertLess(preview.index("refresh();"),
                        preview.index("acp:display-night-preview-started"))
        self.assertIn("'acp:display-night-preview-started'", watcher)
        self.assertIn("'acp:display-night-preview-ended'", watcher)
        self.assertIn("window.addEventListener(event, tick)", watcher)
        self.assertIn("20261014-c3-preview-event-v1", base)
        self.assertIn("20261017-c3-background-timer-v1", base)


    def test_server_routes_and_trial_opt_in_are_explicit(self):
        api = (ROOT / "app/main.py").read_text()
        runner = (ROOT / "scripts/try-squeekboard-hot-css.py").read_text()
        self.assertIn('"/api/osk/c3/theme-sync/status"', api)
        self.assertIn('"/api/osk/c3/theme-sync"', api)
        self.assertIn("local_browser_request(request, mutation=True)", api)
        self.assertIn('parser.add_argument("--theme-sync", action="store_true"', runner)
        self.assertIn("theme_sync: bool = False", runner)
        self.assertIn('if args.theme_sync and not args.start:', runner)
        self.assertIn("reset_private_theme_after_stock(state)", runner)


if __name__ == "__main__":
    unittest.main()
