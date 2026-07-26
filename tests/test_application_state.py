from __future__ import annotations

import subprocess
import sys
import unittest
from datetime import datetime, timedelta

from flask import Flask, jsonify

from app.application_state import ApplicationStateHub, register_application_state_api
from app.playback_coordinator import PlaybackCoordinator


class PlaybackCoordinatorTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        mode: str = "clock",
        airplay_active: bool = False,
        airplay_state: str = "Stopped",
        airplay_event: str | None = None,
        airplay_updated_at: str | None = None,
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
                    "metadata": {
                        "last_event": airplay_event,
                        "updated_at": airplay_updated_at,
                    },
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
            alarm_status=lambda: {
                "screen_required": alarm_screen,
                "running": True,
                "history": [{"large": "diagnostic history must stay out of shared state"}],
            },
            alarm_audio_status=lambda: {
                "playback_active": alarm_audio,
                "manager_running": True,
                "history": [{"large": "audio history must stay out of shared state"}],
            },
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

    def test_fresh_iphone_pause_beats_stale_mpris_playing(self):
        state = self.coordinator(
            mode="airplay",
            airplay_active=True,
            airplay_state="Playing",
            airplay_event="pause",
            airplay_updated_at=datetime.now().astimezone().isoformat(),
        ).snapshot()
        airplay = state["sources"]["airplay"]
        self.assertEqual(airplay["state"], "paused")
        self.assertEqual(airplay["state_source"], "fresh-metadata-event")
        self.assertEqual(airplay["observed"]["raw_playback_status"], "Playing")

    def test_journalled_pause_survives_metadata_freshness_window(self):
        state = {
            "mode": "airplay",
            "airplay": {
                "active": True,
                "started_at": "2026-07-26T04:00:00+01:00",
                "ended_at": None,
                "metadata": {
                    "last_event": "pause",
                    "updated_at": datetime.now().astimezone().isoformat(),
                },
            },
        }
        coordinator = PlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: state,
            plexamp_status=lambda: {"available": True, "playback_state": "paused"},
            airplay_status=lambda: {"available": True, "playback_status": "Playing"},
            alarm_status=lambda: {"screen_required": False},
            alarm_audio_status=lambda: {"playback_active": False},
        )

        first = coordinator.snapshot()["sources"]["airplay"]
        state["airplay"]["metadata"]["updated_at"] = (
            datetime.now().astimezone() - timedelta(minutes=2)
        ).isoformat()
        second = coordinator.snapshot()["sources"]["airplay"]

        self.assertEqual(first["state"], "paused")
        self.assertEqual(second["state"], "paused")
        self.assertEqual(second["state_source"], "coordinator-event-journal")

    def test_explicit_event_can_override_a_lagging_observer(self):
        coordinator = self.coordinator(airplay_active=False, airplay_state="Stopped")
        coordinator.record_event("airplay", "playing", {"origin": "test-adapter"})
        state = coordinator.snapshot()
        self.assertEqual(state["active_source"], "airplay")
        self.assertTrue(state["sources"]["airplay"]["connected"])
        self.assertEqual(state["sources"]["airplay"]["state"], "playing")
        self.assertEqual(state["sources"]["airplay"]["state_source"], "coordinator-explicit-event")

    def test_observed_event_journal_records_transitions_not_polls(self):
        coordinator = self.coordinator()
        first = coordinator.snapshot()["events"]["sequence"]
        second = coordinator.snapshot()["events"]["sequence"]
        self.assertEqual(first, second)

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
        self.assertEqual(state["authority"], "event-assisted-observer")

    def test_shared_state_keeps_alarm_diagnostics_compact(self):
        state = self.coordinator().snapshot()
        alarm = state["sources"]["alarm"]
        self.assertNotIn("history", alarm["scheduler"])
        self.assertNotIn("history", alarm["audio"])
        self.assertTrue(alarm["scheduler"]["running"])


class ApplicationStateHubTests(unittest.TestCase):
    def coordinator(self) -> PlaybackCoordinator:
        return PlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "clock",
                "airplay": {"active": False, "metadata": {}},
            },
            plexamp_status=lambda: {"available": True, "playback_state": "paused"},
            airplay_status=lambda: {"available": False, "playback_status": "Stopped"},
            alarm_status=lambda: {"screen_required": False},
            alarm_audio_status=lambda: {"playback_active": False},
        )

    def playback_hub(self) -> tuple[ApplicationStateHub, PlaybackCoordinator]:
        coordinator = self.coordinator()
        hub = ApplicationStateHub()
        hub.register_service("playback", coordinator)
        hub.register_provider("playback", coordinator.snapshot)
        return hub, coordinator

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
        hub, _coordinator = self.playback_hub()
        register_application_state_api(app, hub)

        response = app.test_client().get("/api/state")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["state"]["playback"]["active_source"], "none")

    def test_compact_playback_state_endpoint(self):
        app = Flask("playback-state-test")
        hub, _coordinator = self.playback_hub()
        register_application_state_api(app, hub)
        response = app.test_client().get("/api/playback/state")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["playback"]["authority"], "event-assisted-observer")

    def test_event_endpoint_accepts_valid_events_and_rejects_unknown_events(self):
        app = Flask("playback-event-test")
        hub, _coordinator = self.playback_hub()
        register_application_state_api(app, hub)
        client = app.test_client()

        accepted = client.post(
            "/api/playback/events",
            json={"source": "airplay", "event": "paused", "details": {"origin": "test"}},
        )
        rejected = client.post(
            "/api/playback/events",
            json={"source": "airplay", "event": "made_up"},
        )

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.get_json()["event"]["event"], "paused")
        self.assertEqual(rejected.status_code, 400)

    def test_legacy_airplay_routes_emit_coordinator_events(self):
        app = Flask("legacy-event-test")

        @app.route("/api/airplay/start", endpoint="api_airplay_start")
        def start():
            return jsonify({"ok": True})

        @app.route("/api/airplay/end", endpoint="api_airplay_end")
        def end():
            return jsonify({"ok": True})

        hub, coordinator = self.playback_hub()
        register_application_state_api(app, hub)
        client = app.test_client()

        client.get("/api/airplay/start")
        self.assertEqual(coordinator.event_snapshot()["last_event"]["event"], "playing")
        client.get("/api/airplay/end")
        self.assertEqual(coordinator.event_snapshot()["last_event"]["event"], "disconnected")

    def test_real_runner_registers_application_state_routes(self):
        code = (
            "from app.runner import app; "
            "routes = {rule.rule for rule in app.url_map.iter_rules()}; "
            "required = {'/api/state', '/api/playback/state', '/api/playback/events'}; "
            "assert required <= routes, sorted(routes)"
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
