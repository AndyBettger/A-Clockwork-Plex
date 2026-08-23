from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify

from app.application_state import ApplicationStateHub, register_application_state_api
from app.playback_coordinator import PlaybackCoordinator


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


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
        runtime_path: Path | None = None,
        hold_completion=None,
        now_provider=None,
        remote: dict | None = None,
        stored_state: dict | None = None,
        hold_seconds: int = 600,
    ) -> PlaybackCoordinator:
        state = stored_state or {
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
        }
        remote_state = remote or {
            "available": airplay_active,
            "playback_status": airplay_state,
            "error": None,
        }
        return PlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: state,
            plexamp_status=lambda: {
                "available": True,
                "playback_state": plexamp_state,
                "percent": 75,
                "error": None,
            },
            airplay_status=lambda: remote_state,
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
            runtime_path=runtime_path,
            hold_completion=hold_completion,
            now_provider=now_provider,
            airplay_hold_seconds=hold_seconds,
            reconcile_seconds=0.05,
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
        coordinator = self.coordinator(
            stored_state=state,
            remote={"available": True, "playback_status": "Playing"},
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

    def test_pause_event_arms_persisted_coordinator_hold(self):
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as directory:
            runtime_path = Path(directory) / "playback-runtime.json"
            coordinator = self.coordinator(
                runtime_path=runtime_path,
                now_provider=clock.now,
                airplay_active=True,
                remote={"available": True, "playback_status": "Playing"},
            )
            coordinator.record_event("airplay", "paused", {"origin": "test"})
            hold = coordinator.snapshot()["sources"]["airplay"]["hold"]

            self.assertTrue(runtime_path.exists())
            self.assertEqual(hold["owner"], "playback-coordinator")
            self.assertTrue(hold["active"])
            self.assertEqual(hold["phase"], "holding")
            self.assertEqual(hold["remaining_seconds"], 600)
            self.assertEqual(coordinator.snapshot()["decision_reason"], "airplay-pause-hold")

    def test_hold_runtime_survives_coordinator_restart(self):
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as directory:
            runtime_path = Path(directory) / "playback-runtime.json"
            first = self.coordinator(
                runtime_path=runtime_path,
                now_provider=clock.now,
                airplay_active=True,
                remote={"available": True, "playback_status": "Playing"},
            )
            first.record_event("airplay", "paused", {"origin": "test"})
            clock.advance(120)
            second = self.coordinator(
                runtime_path=runtime_path,
                now_provider=clock.now,
                airplay_active=True,
                remote={"available": True, "playback_status": "Playing"},
            )
            hold = second.snapshot()["sources"]["airplay"]["hold"]
            self.assertTrue(hold["active"])
            self.assertEqual(hold["phase"], "holding")
            self.assertEqual(hold["remaining_seconds"], 480)

    def test_hold_expiry_ends_session_without_source_transport_commands(self):
        clock = FakeClock()
        completed: list[str] = []
        state = {
            "mode": "airplay",
            "airplay": {"active": True, "metadata": {}},
        }
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(
                stored_state=state,
                runtime_path=Path(directory) / "playback-runtime.json",
                now_provider=clock.now,
                remote={"available": True, "playback_status": "Playing"},
                hold_completion=completed.append,
            )
            coordinator.record_event("airplay", "paused", {"origin": "test"})
            clock.advance(601)
            result = coordinator.reconcile_once()
            snapshot = coordinator.snapshot()

            self.assertEqual(result, "expired")
            self.assertEqual(completed, ["pause-hold-expired"])
            self.assertFalse(snapshot["sources"]["airplay"]["connected"])
            self.assertEqual(snapshot["sources"]["airplay"]["hold"]["phase"], "expired")
            self.assertFalse(snapshot["command_capabilities"]["source_control"])
            self.assertTrue(snapshot["command_capabilities"]["screen_return_on_hold_end"])
            lifecycle_events = {
                event["event"]
                for event in snapshot["events"]["recent_events"]
                if event.get("kind") == "coordinator"
            }
            self.assertIn("hold_expired", lifecycle_events)

    def test_sender_disconnect_during_hold_ends_session_immediately(self):
        clock = FakeClock()
        completed: list[str] = []
        remote = {"available": True, "playback_status": "Paused"}
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(
                runtime_path=Path(directory) / "playback-runtime.json",
                now_provider=clock.now,
                airplay_active=True,
                remote=remote,
                hold_completion=completed.append,
            )
            coordinator.record_event("airplay", "paused", {"origin": "test"})
            remote["available"] = False

            self.assertEqual(coordinator.reconcile_once(), "disconnected")
            self.assertEqual(completed, ["sender-disconnected-during-hold"])
            self.assertFalse(coordinator.snapshot()["sources"]["airplay"]["connected"])

    def test_resume_event_cancels_hold(self):
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(
                runtime_path=Path(directory) / "playback-runtime.json",
                now_provider=clock.now,
                airplay_active=True,
                remote={"available": True, "playback_status": "Playing"},
            )
            coordinator.record_event("airplay", "paused", {"origin": "test"})
            coordinator.record_event("airplay", "playing", {"origin": "test-resume"})
            clock.advance(700)

            self.assertEqual(coordinator.reconcile_once(), "idle")
            hold = coordinator.snapshot()["sources"]["airplay"]["hold"]
            self.assertFalse(hold["active"])
            self.assertEqual(hold["phase"], "playing")
            self.assertEqual(coordinator.snapshot()["sources"]["airplay"]["state"], "playing")

    def test_worker_starts_and_stops_cleanly(self):
        coordinator = self.coordinator()
        coordinator.start()
        self.assertTrue(coordinator.worker_status()["running"])
        coordinator.shutdown()
        self.assertFalse(coordinator.worker_status()["running"])

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
        self.assertEqual(state["authority"], "airplay-hold-owner")

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
        self.assertEqual(response.get_json()["playback"]["authority"], "airplay-hold-owner")

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
        self.assertTrue(accepted.get_json()["playback"]["sources"]["airplay"]["hold"]["active"])
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
