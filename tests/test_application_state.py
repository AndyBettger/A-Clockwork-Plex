from __future__ import annotations

import subprocess
import sys
import unittest

from flask import Flask

from app.application_state import ApplicationStateHub, register_application_state_api
from app.playback_coordinator import PlaybackCoordinator


class PlaybackCoordinatorTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        mode: str = "clock",
        airplay_active: bool = False,
        airplay_state: str = "Stopped",
        plexamp_state: str = "paused",
        alarm_screen: bool = False,
        alarm_audio: bool = False,
    ) -> PlaybackCoordinator:
        return PlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": mode,
                "airplay": {
                    "active": airplay_active,
                    "started_at": "2026-07-26T04:00:00+01:00" if airplay_active else None,
                    "ended_at": None,
                    "metadata": {"last_event": "pause" if airplay_active else None},
                },
            },
            plexamp_status=lambda: {
                "available": True,
                "playback_state": plexamp_state,
                "percent": 75,
                "error": None,
            },
            airplay_status=lambda: {
                "available": airplay_active,
                "playback_status": airplay_state,
                "error": None,
            },
            alarm_status=lambda: {"screen_required": alarm_screen},
            alarm_audio_status=lambda: {"playback_active": alarm_audio},
        )

    def test_held_airplay_session_owns_source_while_paused(self):
        state = self.coordinator(
            mode="airplay",
            airplay_active=True,
            airplay_state="Paused",
            plexamp_state="paused",
        ).snapshot()
        self.assertEqual(state["active_source"], "airplay")
        self.assertEqual(state["recommended_screen"], "airplay")
        self.assertEqual(state["sources"]["airplay"]["state"], "paused")
        self.assertTrue(state["screen_in_sync"])

    def test_alarm_has_priority_over_music_sources(self):
        state = self.coordinator(
            mode="airplay",
            airplay_active=True,
            airplay_state="Playing",
            plexamp_state="playing",
            alarm_screen=True,
        ).snapshot()
        self.assertEqual(state["active_source"], "alarm")
        self.assertEqual(state["recommended_screen"], "alarm")
        self.assertFalse(state["screen_in_sync"])

    def test_plexamp_is_recommended_when_it_is_only_playing_source(self):
        state = self.coordinator(mode="clock", plexamp_state="playing").snapshot()
        self.assertEqual(state["active_source"], "plexamp")
        self.assertEqual(state["recommended_screen"], "plexamp")
        self.assertFalse(state["commands_enabled"])
        self.assertEqual(state["authority"], "observer")


class ApplicationStateHubTests(unittest.TestCase):
    def test_revision_changes_only_when_domain_state_changes(self):
        payload = {"value": 1}
        hub = ApplicationStateHub()
        hub.register_provider("example", lambda: dict(payload))

        first = hub.snapshot()
        second = hub.snapshot()
        payload["value"] = 2
        third = hub.snapshot()

        self.assertEqual(first["revision"], second["revision"])
        self.assertGreater(third["revision"], second["revision"])

    def test_provider_failure_is_isolated(self):
        hub = ApplicationStateHub()
        hub.register_provider("healthy", lambda: {"available": True})

        def broken():
            raise RuntimeError("weather station unavailable")

        hub.register_provider("weather", broken)
        snapshot = hub.snapshot()

        self.assertTrue(snapshot["components"]["healthy"]["healthy"])
        self.assertFalse(snapshot["components"]["weather"]["healthy"])
        self.assertIn("weather provider failed", snapshot["state"]["weather"]["error"])

    def test_api_exposes_versioned_snapshot(self):
        app = Flask("application-state-test")
        hub = ApplicationStateHub()
        hub.register_provider("playback", lambda: {"active_source": "none"})
        register_application_state_api(app, hub)

        response = app.test_client().get("/api/state")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["state"]["playback"]["active_source"], "none")

    def test_real_runner_registers_application_state_route(self):
        code = (
            "from app.runner import app; "
            "routes = {rule.rule for rule in app.url_map.iter_rules()}; "
            "assert '/api/state' in routes, sorted(routes)"
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
