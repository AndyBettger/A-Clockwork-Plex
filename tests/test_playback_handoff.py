from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from flask import Flask, jsonify

from app.playback_handoff import (
    AirPlayTakeoverPlaybackCoordinator,
    _install_screen_preserving_airplay_start,
)
from app.playback_handoff_retention import RetainedBidirectionalHandoffCoordinator


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"
RUNNER = ROOT / "app" / "runner.py"
TRANSPORT = ROOT / "app" / "playback_transport.py"
NAVIGATION = ROOT / "app" / "playback_navigation.py"
HANDOFF = ROOT / "app" / "playback_handoff.py"
RETENTION = ROOT / "app" / "playback_handoff_retention.py"


class AirPlayTakeoverPlaybackCoordinatorTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        remote: dict | None = None,
        plexamp: dict | None = None,
        pauses: list[str] | None = None,
        pause_ok: bool = True,
    ) -> AirPlayTakeoverPlaybackCoordinator:
        remote_state = remote if remote is not None else {
            "available": True,
            "playback_status": "Playing",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        plexamp_state = plexamp if plexamp is not None else {
            "available": True,
            "playback_state": "playing",
            "percent": 75,
        }
        pause_log = pauses if pauses is not None else []

        def pause_plexamp():
            pause_log.append("pause")
            if pause_ok:
                plexamp_state["playback_state"] = "paused"
                return True, None
            return False, "pause failed"

        return AirPlayTakeoverPlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "airplay",
                "airplay": {
                    "active": True,
                    "started_at": "2026-07-26T20:00:00+01:00",
                    "ended_at": None,
                    "metadata": {},
                },
            },
            plexamp_status=lambda: dict(plexamp_state),
            airplay_status=lambda: dict(remote_state),
            alarm_status=lambda: {"screen_required": False},
            alarm_audio_status=lambda: {"playback_active": False},
            airplay_command=lambda _action: (True, None),
            plexamp_pause=pause_plexamp,
            airplay_hold_seconds=600,
            reconcile_seconds=0.05,
        )

    def test_airplay_playing_pauses_plexamp_exactly_once(self):
        pauses: list[str] = []
        coordinator = self.coordinator(pauses=pauses)

        coordinator.record_event("airplay", "playing", {"origin": "shairport-start-wrapper"})
        first = coordinator.snapshot()
        second = coordinator.snapshot()

        self.assertEqual(pauses, ["pause"])
        handoff = first["handoffs"]["airplay_to_plexamp"]
        self.assertEqual(handoff["status"], "confirmed")
        self.assertEqual(handoff["command_count"], 1)
        self.assertEqual(second["handoffs"]["airplay_to_plexamp"]["command_count"], 1)
        self.assertEqual(first["sources"]["plexamp"]["state"], "paused")

    def test_quiet_plexamp_requires_no_pause(self):
        pauses: list[str] = []
        plexamp = {"available": True, "playback_state": "paused", "percent": 75}
        coordinator = self.coordinator(pauses=pauses, plexamp=plexamp)

        coordinator.record_event("airplay", "playing", {"origin": "shairport-start-wrapper"})
        handoff = coordinator.snapshot()["handoffs"]["airplay_to_plexamp"]

        self.assertEqual(pauses, [])
        self.assertEqual(handoff["status"], "not-needed")
        self.assertEqual(handoff["command_count"], 0)

    def test_new_playing_episode_can_pause_plexamp_again(self):
        pauses: list[str] = []
        remote = {
            "available": True,
            "playback_status": "Playing",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        plexamp = {"available": True, "playback_state": "playing", "percent": 75}
        coordinator = self.coordinator(pauses=pauses, remote=remote, plexamp=plexamp)

        coordinator.record_event("airplay", "playing", {"origin": "first-start"})
        remote["playback_status"] = "Paused"
        coordinator.record_event("airplay", "paused", {"origin": "test-pause"})
        plexamp["playback_state"] = "playing"
        remote["playback_status"] = "Playing"
        coordinator.record_event("airplay", "playing", {"origin": "second-start"})

        self.assertEqual(pauses, ["pause", "pause"])
        handoff = coordinator.snapshot()["handoffs"]["airplay_to_plexamp"]
        self.assertEqual(handoff["sequence"], 2)
        self.assertEqual(handoff["command_count"], 2)

    def test_failed_pause_is_not_retried_during_same_episode(self):
        pauses: list[str] = []
        coordinator = self.coordinator(pauses=pauses, pause_ok=False)

        coordinator.record_event("airplay", "playing", {"origin": "test-start"})
        coordinator.snapshot()
        coordinator.reconcile_once()

        self.assertEqual(pauses, ["pause"])
        handoff = coordinator.snapshot()["handoffs"]["airplay_to_plexamp"]
        self.assertEqual(handoff["status"], "failed")
        self.assertEqual(handoff["last_error"], "pause failed")


class ScreenAndLegacyBoundaryTests(unittest.TestCase):
    def test_airplay_start_preserves_open_plexamp_surface(self):
        app = Flask("screen-preserve-test")

        class Dashboard:
            mode = "plexamp"

            @classmethod
            def load_config(cls):
                return {}

            @classmethod
            def load_state(cls, _config):
                return {"mode": cls.mode}

            @classmethod
            def set_mode(cls, mode):
                cls.mode = mode

        @app.route("/api/airplay/start", endpoint="api_airplay_start")
        def start():
            Dashboard.mode = "airplay"
            return jsonify({"ok": True})

        _install_screen_preserving_airplay_start(app, Dashboard)
        response = app.test_client().get("/api/airplay/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dashboard.mode, "plexamp")
        self.assertTrue(getattr(app.view_functions["api_airplay_start"], "_acp_preserves_plexamp_screen"))

    def test_airplay_start_still_selects_airplay_from_other_surfaces(self):
        app = Flask("normal-start-test")

        class Dashboard:
            mode = "clock"

            @classmethod
            def load_config(cls):
                return {}

            @classmethod
            def load_state(cls, _config):
                return {"mode": cls.mode}

            @classmethod
            def set_mode(cls, mode):
                cls.mode = mode

        @app.route("/api/airplay/start", endpoint="api_airplay_start")
        def start():
            Dashboard.mode = "airplay"
            return jsonify({"ok": True})

        _install_screen_preserving_airplay_start(app, Dashboard)
        app.test_client().get("/api/airplay/start")
        self.assertEqual(Dashboard.mode, "airplay")

    def test_staged_promotion_factories_and_route_unwrapper_are_retired(self):
        sources = {
            "transport": TRANSPORT.read_text(encoding="utf-8"),
            "navigation": NAVIGATION.read_text(encoding="utf-8"),
            "handoff": HANDOFF.read_text(encoding="utf-8"),
            "retention": RETENTION.read_text(encoding="utf-8"),
        }
        retired_symbols = {
            "transport": ["def promote_playback_transport("],
            "navigation": ["def promote_airplay_navigation("],
            "handoff": [
                "def promote_airplay_takeover(",
                "def promote_bidirectional_handoff(",
                "def _remove_page_open_handoff(",
                "_acp_airplay_handoff_wrapped",
            ],
            "retention": ["def promote_retained_bidirectional_handoff("],
        }
        for module, symbols in retired_symbols.items():
            for symbol in symbols:
                self.assertNotIn(symbol, sources[module], f"{symbol} returned in {module}")

    def test_start_hook_contains_no_direct_plexamp_pause(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("PLEXAMP_URL", text)
        self.assertNotIn("/player/playback/pause", text)
        self.assertIn("PlaybackCoordinator owns any required Plexamp pause", text)
        self.assertNotIn("systemctl restart plexamp", text.lower())

    def test_runner_builds_final_authority_before_registering_apis(self):
        text = RUNNER.read_text(encoding="utf-8")
        authority_call = text.index("playback_coordinator = promote_playback_authority(application_state_hub")
        state_api_call = text.index("register_application_state_api(app, application_state_hub)")
        command_api_call = text.index("register_playback_command_api(app, application_state_hub)")
        self.assertLess(authority_call, state_api_call)
        self.assertLess(authority_call, command_api_call)
        self.assertNotIn("promote_airplay_takeover(application_state_hub", text)
        self.assertNotIn("promote_bidirectional_handoff(application_state_hub", text)

    def test_real_runner_uses_final_handoff_owner_and_plain_plexamp_route(self):
        code = (
            "from app.runner import app, application_state_hub, dashboard; "
            "from app.playback_handoff_retention import RetainedBidirectionalHandoffCoordinator; "
            "coordinator=application_state_hub.service('playback'); "
            "assert isinstance(coordinator, RetainedBidirectionalHandoffCoordinator); "
            "assert app.view_functions['plexamp'] is dashboard.plexamp; "
            "assert getattr(app.view_functions['api_airplay_start'], '_acp_playback_event_wrapped', False)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
