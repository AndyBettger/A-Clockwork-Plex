from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from app.weather_credentials import (
    WeatherUndergroundCredentialManager,
    register_weather_underground_credentials_api,
)


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "a-clockwork-plex-weather-secret.py"
SECRET = "test-wu-secret-DO-NOT-LOG"


class FakeObservations:
    def __init__(self) -> None:
        self.wake_count = 0
        self.refresh_count = 0
        self.result = {
            "ok": True,
            "status": "ready",
            "last_success_at": "2026-08-13T03:00:00+01:00",
            "last_observation_at": "2026-08-13T02:59:30+01:00",
            "last_field_count": 8,
            "last_error": None,
        }

    def wake(self) -> None:
        self.wake_count += 1

    def refresh(self, force: bool = False):
        self.refresh_count += 1
        self.last_force = force
        return dict(self.result)


def wu_config(provider: str = "weather_underground") -> dict:
    return {
        "weather": {
            "provider": provider,
            "weather_underground": {
                "station_id": "IHOME123",
                "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
                "refresh_seconds": 60,
                "stale_seconds": 300,
                "request_timeout_seconds": 8,
                "pressure_history_hours": 6,
            },
        }
    }


class WeatherCredentialManagerTests(unittest.TestCase):
    def make_manager(self, *, environment=None, runner=None, provider="weather_underground"):
        observations = FakeObservations()
        calls = []

        def recording_runner(command, stdin):
            calls.append((list(command), stdin))
            return subprocess.CompletedProcess(command, 0, "stored\n", "")

        manager = WeatherUndergroundCredentialManager(
            load_config=lambda: wu_config(provider),
            observations=observations,
            environment=environment if environment is not None else {},
            runner=runner or recording_runner,
        )
        return manager, observations, calls

    def test_set_secret_uses_stdin_not_argv_and_updates_environment_after_success(self) -> None:
        environment = {}
        manager, observations, calls = self.make_manager(environment=environment)

        result = manager.set_secret(SECRET)

        self.assertTrue(result["configured"])
        self.assertEqual(environment["WEATHER_UNDERGROUND_API_KEY"], SECRET)
        self.assertEqual(observations.wake_count, 1)
        self.assertEqual(calls[0][0], ["sudo", "-n", "/usr/local/bin/a-clockwork-plex-weather-secret", "set"])
        self.assertEqual(calls[0][1], SECRET)
        self.assertNotIn(SECRET, " ".join(calls[0][0]))
        self.assertNotIn(SECRET, str(result))

    def test_failed_helper_does_not_mutate_live_environment_or_echo_secret(self) -> None:
        environment = {}

        def failed(command, stdin):
            self.assertEqual(stdin, SECRET)
            return subprocess.CompletedProcess(command, 1, "", "write failed")

        manager, observations, _calls = self.make_manager(environment=environment, runner=failed)
        with self.assertRaises(OSError) as raised:
            manager.set_secret(SECRET)

        self.assertNotIn("WEATHER_UNDERGROUND_API_KEY", environment)
        self.assertEqual(observations.wake_count, 0)
        self.assertNotIn(SECRET, str(raised.exception))

    def test_remove_secret_uses_restricted_command_and_clears_environment(self) -> None:
        environment = {"WEATHER_UNDERGROUND_API_KEY": SECRET}
        manager, observations, calls = self.make_manager(environment=environment)

        result = manager.remove_secret()

        self.assertFalse(result["configured"])
        self.assertNotIn("WEATHER_UNDERGROUND_API_KEY", environment)
        self.assertEqual(calls[0], (["sudo", "-n", "/usr/local/bin/a-clockwork-plex-weather-secret", "remove"], None))
        self.assertEqual(observations.wake_count, 1)

    def test_connection_test_requires_saved_wu_settings_and_credential(self) -> None:
        manager, _observations, _calls = self.make_manager(environment={}, provider="ecowitt_push")
        with self.assertRaisesRegex(ValueError, "Select Weather Underground"):
            manager.test_connection()

        manager, _observations, _calls = self.make_manager(environment={})
        with self.assertRaisesRegex(ValueError, "Set the Weather Underground API key"):
            manager.test_connection()

    def test_connection_test_returns_only_sanitized_observation_status(self) -> None:
        environment = {"WEATHER_UNDERGROUND_API_KEY": SECRET}
        manager, observations, _calls = self.make_manager(environment=environment)

        result = manager.test_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["station_id"], "IHOME123")
        self.assertEqual(result["field_count"], 8)
        self.assertEqual(observations.refresh_count, 1)
        self.assertTrue(observations.last_force)
        self.assertNotIn(SECRET, str(result))

    def test_api_never_returns_secret(self) -> None:
        environment = {}
        manager, _observations, _calls = self.make_manager(environment=environment)
        app = Flask(__name__)
        register_weather_underground_credentials_api(app, manager)
        client = app.test_client()

        response = client.post(
            "/api/weather/underground/credentials",
            json={"api_key": SECRET},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SECRET, response.get_data(as_text=True))
        status = client.get("/api/weather/underground/credentials")
        self.assertEqual(status.get_json(), {"ok": True, "configured": True})
        self.assertNotIn(SECRET, status.get_data(as_text=True))


class WeatherSecretHelperTests(unittest.TestCase):
    def run_helper(self, path: Path, operation: str, stdin: str = ""):
        env = os.environ.copy()
        env["ACP_WEATHER_SECRET_TEST_FILE"] = str(path)
        return subprocess.run(
            [os.environ.get("PYTHON", "python3"), str(HELPER), operation],
            input=stdin,
            text=True,
            capture_output=True,
            env=env,
            cwd=ROOT,
            check=False,
        )

    def test_helper_preserves_unrelated_lines_and_never_prints_secret(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("non-root test override is deliberately disabled for root")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.env"
            path.write_text('OTHER_SETTING="keep-me"\nWEATHER_UNDERGROUND_API_KEY="old"\n', encoding="utf-8")

            result = self.run_helper(path, "set", SECRET)

            self.assertEqual(result.returncode, 0, result.stderr)
            content = path.read_text(encoding="utf-8")
            self.assertIn('OTHER_SETTING="keep-me"', content)
            self.assertIn('WEATHER_UNDERGROUND_API_KEY="test-wu-secret-DO-NOT-LOG"', content)
            self.assertNotIn(SECRET, result.stdout + result.stderr)
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")

            removed = self.run_helper(path, "remove")
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), 'OTHER_SETTING="keep-me"\n')

    def test_helper_rejects_multiline_secret_without_mutating_existing_file(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("non-root test override is deliberately disabled for root")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.env"
            path.write_text('OTHER_SETTING="keep-me"\n', encoding="utf-8")
            before = path.read_bytes()

            result = self.run_helper(path, "set", "one\ntwo")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
