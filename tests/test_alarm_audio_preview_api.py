from __future__ import annotations

import unittest
from pathlib import Path

from flask import Flask

from app.alarm_audio_preview import register_alarm_audio_preview_api


class FakeAlarmAudio:
    def __init__(self, *, error: str | None = None) -> None:
        self.error = error
        self.requested: list[str] = []

    def preview_tone(self, tone_id: str):
        self.requested.append(tone_id)
        if self.error:
            raise ValueError(self.error)
        return {
            "preview_duration_seconds": 8,
            "preview_volume_percent": 15,
        }

    @staticmethod
    def status():
        return {
            "playback_active": True,
            "standalone_audio_test": True,
        }


class FakeDashboard:
    def __init__(self, audio: FakeAlarmAudio) -> None:
        self.alarm_audio = audio

    @staticmethod
    def tone_labels():
        return {"classic-klaxon": "Classic Klaxon"}


class AlarmAudioPreviewApiTests(unittest.TestCase):
    def build_client(self, audio: FakeAlarmAudio):
        app = Flask(__name__)
        register_alarm_audio_preview_api(app, FakeDashboard(audio))
        return app.test_client()

    def test_preview_api_reports_fixed_server_policy(self):
        audio = FakeAlarmAudio()
        response = self.build_client(audio).post(
            "/api/alarms/audio/preview",
            json={"tone_id": "classic-klaxon"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(audio.requested, ["classic-klaxon"])
        self.assertEqual(payload["preview"]["duration_seconds"], 8)
        self.assertEqual(payload["preview"]["volume_percent"], 15)
        self.assertTrue(payload["audio"]["standalone_audio_test"])
        self.assertIn("Classic Klaxon", payload["message"])

    def test_preview_api_rejects_missing_tone(self):
        response = self.build_client(FakeAlarmAudio()).post(
            "/api/alarms/audio/preview",
            json={},
        )
        self.assertEqual(response.status_code, 400)

    def test_preview_api_preserves_audio_safety_lock(self):
        response = self.build_client(
            FakeAlarmAudio(error="Alarm audio is locked. Enable the master safety switch first.")
        ).post(
            "/api/alarms/audio/preview",
            json={"tone_id": "classic-klaxon"},
        )
        self.assertEqual(response.status_code, 409)

    def test_runner_registers_preview_after_scheduled_audio_promotion(self):
        runner = (Path(__file__).resolve().parents[1] / "app" / "runner.py").read_text(encoding="utf-8")
        promote = runner.index("scheduled_alarm_audio = promote_scheduled_alarm_audio(dashboard)")
        register = runner.index("register_alarm_audio_preview_api(app, dashboard)")
        self.assertLess(promote, register)


if __name__ == "__main__":
    unittest.main()
