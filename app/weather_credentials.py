from __future__ import annotations

import os
import subprocess
from collections.abc import MutableMapping
from typing import Any, Callable

from flask import Flask, jsonify, request

try:
    from .weather_observations import (
        DEFAULT_API_KEY_ENV,
        WeatherObservationService,
        normalise_observation_config,
    )
except ImportError:  # Supports direct execution imports.
    from weather_observations import (
        DEFAULT_API_KEY_ENV,
        WeatherObservationService,
        normalise_observation_config,
    )


HELPER = "/usr/local/bin/a-clockwork-plex-weather-secret"
CommandRunner = Callable[[list[str], str | None], subprocess.CompletedProcess[str]]
ConfigProvider = Callable[[], dict[str, Any]]


def _default_runner(command: list[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def _safe_error(
    result: subprocess.CompletedProcess[str],
    fallback: str,
    *,
    secret: str = "",
) -> str:
    message = str(result.stderr or result.stdout or "").strip()
    if not message:
        return fallback
    if secret:
        message = message.replace(secret, "[redacted]")
    # Keep public errors short and single-line so this endpoint cannot become an
    # arbitrary privileged-helper diagnostic relay.
    return message.replace("\r", " ").replace("\n", " ")[:240]


class WeatherUndergroundCredentialManager:
    """Own the write-only WU credential and live commissioning actions."""

    def __init__(
        self,
        *,
        load_config: ConfigProvider,
        observations: WeatherObservationService,
        runner: CommandRunner = _default_runner,
        environment: MutableMapping[str, str] = os.environ,
        helper: str = HELPER,
    ) -> None:
        self._load_config = load_config
        self._observations = observations
        self._runner = runner
        self._environment = environment
        self._helper = helper

    def _api_key_env(self) -> str:
        settings = normalise_observation_config(self._load_config())
        wunderground = settings.get("weather_underground", {})
        return str(wunderground.get("api_key_env") or DEFAULT_API_KEY_ENV)

    def _commissioning_env(self) -> str:
        env_name = self._api_key_env()
        if env_name != DEFAULT_API_KEY_ENV:
            raise ValueError(
                "Settings commissioning requires the standard WEATHER_UNDERGROUND_API_KEY environment reference."
            )
        return env_name

    def status(self) -> dict[str, Any]:
        env_name = self._api_key_env()
        return {
            "ok": True,
            "configured": bool(str(self._environment.get(env_name) or "").strip()),
        }

    @staticmethod
    def _validate_secret(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Weather Underground API key must be text.")
        if not value or not value.strip():
            raise ValueError("Weather Underground API key is required.")
        if len(value.encode("utf-8")) > 4096:
            raise ValueError("Weather Underground API key is too long.")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ValueError("Weather Underground API key must be a single line.")
        return value

    def set_secret(self, value: Any) -> dict[str, Any]:
        secret = self._validate_secret(value)
        env_name = self._commissioning_env()
        command = ["sudo", "-n", self._helper, "set"]
        result = self._runner(command, secret)
        if result.returncode != 0:
            raise OSError(
                _safe_error(
                    result,
                    "Could not store Weather Underground credential.",
                    secret=secret,
                )
            )
        self._environment[env_name] = secret
        self._observations.wake()
        return {"ok": True, "configured": True, "message": "Weather Underground API key saved."}

    def remove_secret(self) -> dict[str, Any]:
        env_name = self._commissioning_env()
        command = ["sudo", "-n", self._helper, "remove"]
        result = self._runner(command, None)
        if result.returncode != 0:
            raise OSError(_safe_error(result, "Could not remove Weather Underground credential."))
        self._environment.pop(env_name, None)
        self._observations.wake()
        return {"ok": True, "configured": False, "message": "Weather Underground API key removed."}

    def test_connection(self) -> dict[str, Any]:
        settings = normalise_observation_config(self._load_config())
        if settings.get("provider") != "weather_underground":
            raise ValueError("Select Weather Underground as the observation provider and save Settings first.")
        station_id = str(settings.get("weather_underground", {}).get("station_id") or "").strip()
        if not station_id:
            raise ValueError("Save a Weather Underground station ID before testing the connection.")
        self._commissioning_env()
        if not self.status()["configured"]:
            raise ValueError("Set the Weather Underground API key before testing the connection.")

        snapshot = self._observations.refresh(force=True)
        error = str(snapshot.get("last_error") or "").strip()
        if error:
            raise RuntimeError(error[:240])
        if not snapshot.get("last_success_at"):
            raise RuntimeError("Weather Underground did not return a usable current observation.")
        return {
            "ok": True,
            "message": f"Weather Underground connection succeeded for station {station_id}.",
            "station_id": station_id,
            "last_success_at": snapshot.get("last_success_at"),
            "last_observation_at": snapshot.get("last_observation_at"),
            "field_count": snapshot.get("last_field_count"),
            "status": snapshot.get("status"),
        }


def register_weather_underground_credentials_api(
    app: Flask,
    manager: WeatherUndergroundCredentialManager,
) -> None:
    if "api_weather_underground_credentials" in app.view_functions:
        return

    @app.route("/api/weather/underground/credentials", methods=["GET", "POST", "DELETE"])
    def api_weather_underground_credentials():
        try:
            if request.method == "GET":
                return jsonify(manager.status())
            if request.method == "DELETE":
                return jsonify(manager.remove_secret())
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                raise ValueError("Credential request must be a JSON object.")
            return jsonify(manager.set_secret(payload.get("api_key")))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/weather/underground/test", methods=["POST"])
    def api_weather_underground_test():
        try:
            return jsonify(manager.test_connection())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
