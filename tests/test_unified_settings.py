from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask

from app.configuration_backup import (
    ConfigurationBackupService,
    register_configuration_backup_api,
)
from app.settings_unified import UnifiedSettingsService, register_unified_settings_api


class FakeForecast:
    def __init__(self) -> None:
        self.wake_count = 0
        self.refresh_calls: list[bool] = []

    def snapshot(self):
        return {"status": "ready", "enabled": True, "forecast": {"provider": "open_meteo"}}

    def wake(self):
        self.wake_count += 1

    def refresh(self, *, force=False):
        self.refresh_calls.append(force)
        return self.snapshot()


class FakeEqualizer:
    def __init__(self, available=True) -> None:
        self.available = available
        self.bands = {"bass": 0.0, "mid": 0.0, "treble": 0.0}
        self.bypassed = False
        self.calls: list[tuple] = []

    def status(self):
        return {
            "available": self.available,
            "installed": self.available,
            "bypassed": self.bypassed,
            "bands": {
                band: {"db": value, "stored_db": value}
                for band, value in self.bands.items()
            },
            "error": None if self.available else "EQ backend unavailable",
        }

    def set_band(self, band, value, *, persist=True):
        if not self.available:
            raise RuntimeError("EQ backend unavailable")
        self.bands[band] = float(value)
        self.calls.append(("band", band, float(value), persist))
        return self.status()

    def set_bypass(self, enabled):
        self.bypassed = bool(enabled)
        self.calls.append(("bypass", bool(enabled)))
        return self.status()


class FakeShairportName:
    def __init__(self, name="Bedroom Plexamp", installed=True) -> None:
        self.name = name
        self.installed = installed
        self.calls: list[str] = []

    def status(self):
        return {
            "ok": self.installed,
            "available": self.installed,
            "installed": self.installed,
            "receiver_name": self.name,
            "service_active": True,
            "error": None if self.installed else "helper missing",
        }

    def apply(self, name):
        if not self.installed:
            raise RuntimeError("helper missing")
        self.calls.append(str(name))
        self.name = str(name)
        return self.status()


class FakeScheduler:
    def __init__(self) -> None:
        self.wake_count = 0
        self.recalculate_count = 0

    def wake(self):
        self.wake_count += 1

    def status(self):
        return {"running": True}

    def recalculate(self):
        self.recalculate_count += 1
        return self.status()


class FakeAlarmAudio:
    def __init__(self) -> None:
        self.stop_count = 0
        self.disarm_count = 0

    def stop_playback(self, **_kwargs):
        self.stop_count += 1

    def disarm_occurrence(self):
        self.disarm_count += 1


def tone_manifest():
    return {
        "schema_version": 1,
        "default_tone_id": "classic-klaxon",
        "fallback_tone_id": "emergency-buzzer",
        "preview_seconds": 10,
        "tones": [
            {"id": "classic-klaxon", "label": "Classic Klaxon"},
            {"id": "emergency-buzzer", "label": "Emergency Buzzer"},
        ],
    }


def config_fixture():
    return {
        "dashboard": {
            "default_mode": "clock",
            "clock_format": "24h",
            "idle_timeout_seconds": 180,
        },
        "weather": {
            "station_name": "Weather or Not",
            "reporting_station_name": "Bedroom Station",
            "auto_refresh_seconds": 60,
            "display_units": "metric",
            "units": {"temperature": "c", "pressure": "hpa", "rain": "mm", "wind": "mph"},
            "clock_cards": ["outdoor_temp", "pressure"],
            "forecast": {
                "enabled": True,
                "provider": "open_meteo",
                "latitude": 51.5,
                "longitude": -0.12,
                "timezone": "Europe/London",
                "forecast_days": 7,
                "refresh_minutes": 30,
                "request_timeout_seconds": 8,
                "stale_after_hours": 6,
            },
        },
        "alarm": {
            "schema_version": 2,
            "enabled": True,
            "default_time": "11:00",
            "snooze_minutes": 8,
            "defaults": {
                "snooze_minutes": 8,
                "ring_minutes": 3,
                "occurrence_expiry_minutes": 120,
                "tone_id": "classic-klaxon",
                "fallback_tone_id": "emergency-buzzer",
                "source_type": "tone",
            },
            "alarms": [
                {
                    "id": "wake-up",
                    "enabled": True,
                    "label": "Wake up",
                    "time": "11:00",
                    "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    "snooze_minutes": 8,
                    "ring_minutes": 3,
                    "occurrence_expiry_minutes": 120,
                    "source": {
                        "type": "tone",
                        "tone_id": "classic-klaxon",
                        "fallback_tone_id": "emergency-buzzer",
                    },
                    "volume": {"start_percent": 60, "target_percent": 85, "fade_seconds": 10},
                }
            ],
        },
        "alarm_audio": {
            "master_enabled": True,
            "scheduled_enabled": True,
            "shared_mixer_enabled": True,
            "hardware_device": "hw:CARD=Pro,DEV=0",
            "backend": "aplay",
            "alsa_device": "acp_alarm",
            "test_duration_seconds": 12,
        },
        "airplay": {
            "display_name": "Bedroom Plexamp",
            "default_volume_percent": 60,
            "apply_default_volume_on_start": True,
            "pause_hold_seconds": 600,
        },
        "audio": {"eq": {"enabled": True, "bands": {"bass": 0.0, "mid": 0.0, "treble": 0.0}}},
        "plexamp": {
            "url": "http://localhost:32500",
            "pause_url": "http://localhost:32500/player/playback/pause",
            "service_name": "plexamp.service",
        },
    }


class UnifiedSettingsTests(unittest.TestCase):
    def build(self):
        stored = config_fixture()
        saves = []
        forecast = FakeForecast()
        equalizer = FakeEqualizer()
        shairport = FakeShairportName()
        scheduler = FakeScheduler()
        alarm_audio = FakeAlarmAudio()
        idle_modes = []

        def load_config():
            return deepcopy(stored)

        def save_config(config):
            stored.clear()
            stored.update(deepcopy(config))
            saves.append(deepcopy(config))

        service = UnifiedSettingsService(
            load_config=load_config,
            save_config=save_config,
            tone_manifest=tone_manifest,
            clock_card_ids={"outdoor_temp", "pressure", "daily_rain"},
            forecast=forecast,
            equalizer=equalizer,
            shairport_name=shairport,
            alarm_scheduler=scheduler,
            alarm_audio=alarm_audio,
            screen_idle_mode=idle_modes.append,
        )
        return service, stored, saves, forecast, equalizer, shairport, scheduler, alarm_audio, idle_modes

    def test_snapshot_exposes_one_revision_and_all_configuration_domains(self):
        service, *_rest = self.build()
        snapshot = service.snapshot()

        self.assertTrue(snapshot["ok"])
        self.assertEqual(len(snapshot["revision"]), 16)
        self.assertEqual(
            set(snapshot["settings"]),
            {"dashboard", "display", "weather", "alarms", "alarm_audio", "airplay", "audio", "plexamp"},
        )
        self.assertEqual(snapshot["settings"]["weather"]["units"]["wind"], "mph")
        self.assertTrue(snapshot["capabilities"]["transactional_save"])
        self.assertTrue(snapshot["capabilities"]["actions_are_separate"])

    def test_custom_weather_units_remain_independently_selectable(self):
        service, stored, saves, *_rest = self.build()
        snapshot = service.snapshot()
        settings = deepcopy(snapshot["settings"])
        settings["weather"]["units"] = {
            "temperature": "c",
            "pressure": "inhg",
            "rain": "mm",
            "wind": "kmh",
        }

        saved = service.apply({"revision": snapshot["revision"], "settings": settings})

        self.assertEqual(len(saves), 1)
        self.assertEqual(stored["weather"]["units"]["temperature"], "c")
        self.assertEqual(stored["weather"]["units"]["pressure"], "inhg")
        self.assertEqual(stored["weather"]["units"]["rain"], "mm")
        self.assertEqual(stored["weather"]["units"]["wind"], "kmh")
        self.assertEqual(saved["settings"]["weather"]["units"]["wind"], "kmh")

    def test_receiver_name_requires_confirmation_then_updates_real_helper_and_config(self):
        service, stored, saves, _forecast, _eq, shairport, *_rest = self.build()
        snapshot = service.snapshot()
        settings = deepcopy(snapshot["settings"])
        settings["airplay"]["receiver_name"] = "Mostly Harmless Bedroom"

        with self.assertRaises(PermissionError):
            service.apply({"revision": snapshot["revision"], "settings": settings})

        saved = service.apply(
            {
                "revision": snapshot["revision"],
                "settings": settings,
                "confirm_airplay_restart": True,
            }
        )
        self.assertEqual(shairport.calls, ["Mostly Harmless Bedroom"])
        self.assertEqual(stored["airplay"]["display_name"], "Mostly Harmless Bedroom")
        self.assertEqual(len(saves), 1)
        self.assertTrue(saved["changed"]["airplay_receiver_restarted"])

    def test_alarm_forecast_and_screen_hooks_run_without_mutating_live_eq(self):
        service, stored, saves, forecast, equalizer, _shairport, scheduler, _audio, idle_modes = self.build()
        snapshot = service.snapshot()
        settings = deepcopy(snapshot["settings"])
        settings["dashboard"]["idle_return_mode"] = "weather"
        settings["weather"]["forecast"]["refresh_minutes"] = 60
        settings["alarms"]["alarms"][0]["time"] = "10:30"
        settings["audio"]["eq"] = {
            "enabled": True,
            "bands": {"bass": 1.5, "mid": -0.5, "treble": 2.0},
        }

        result = service.apply({"revision": snapshot["revision"], "settings": settings})

        self.assertEqual(len(saves), 1)
        self.assertEqual(stored["dashboard"]["idle_return_mode"], "weather")
        self.assertEqual(idle_modes, ["weather"])
        self.assertEqual(scheduler.wake_count, 1)
        self.assertEqual(scheduler.recalculate_count, 1)
        self.assertEqual(forecast.wake_count, 1)
        self.assertEqual(forecast.refresh_calls, [True])
        self.assertEqual(equalizer.calls, [])
        self.assertNotIn("audio", stored)
        self.assertFalse(result["changed"]["eq_applied"])

    def test_stale_revision_rejects_without_writing_or_applying(self):
        service, _stored, saves, _forecast, equalizer, shairport, *_rest = self.build()
        settings = service.snapshot()["settings"]

        with self.assertRaises(RuntimeError):
            service.apply({"revision": "out-of-date", "settings": settings})

        self.assertEqual(saves, [])
        self.assertEqual(equalizer.calls, [])
        self.assertEqual(shairport.calls, [])

    def test_api_returns_structured_restart_confirmation(self):
        service, *_rest = self.build()
        app = Flask(__name__)
        register_unified_settings_api(app, service)
        client = app.test_client()
        snapshot = client.get("/api/settings").get_json()
        settings = snapshot["settings"]
        settings["airplay"]["receiver_name"] = "New Receiver"

        response = client.post(
            "/api/settings",
            json={"revision": snapshot["revision"], "settings": settings},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["confirmation_required"], "airplay_restart")


class ConfigurationBackupTests(unittest.TestCase):
    def build_service(self, root: Path) -> ConfigurationBackupService:
        version_path = root / "app-version.json"
        version_path.write_text(
            json.dumps(
                {
                    "name": "A Clockwork Plex",
                    "version": "0.4.0",
                    "tag": "v0.4.0",
                    "release_name": "Unified Bedside Appliance",
                }
            ),
            encoding="utf-8",
        )
        plexamp = root / ".local/share/Plexamp/Settings"
        plexamp.mkdir(parents=True)
        values = {
            "audioConversionBitrate": "N256",
            "autoPlayEnabled": "Bfalse",
            "cacheSize": "N32768",
            "cachingWiFi": "N10",
            "loudnessLeveling": "Bfalse",
            "precacheNetworkSpeed": "N0",
            "sampleRateConversionQuality": "N4",
            "sampleRateMatching": "N2",
            "audioDeviceUuid": "DEVICE-SECRET-MUST-NOT-LEAK",
            "premium": "ACCOUNT-STATE-MUST-NOT-LEAK",
            "authToken": "AUTH-MUST-NOT-LEAK",
        }
        for key, value in values.items():
            encoded = "%40Plexamp%3Asettings%3A" + key
            (plexamp / encoded).write_text(value, encoding="utf-8")
        runtime = root / "plexamp"
        runtime.mkdir()
        (runtime / "package.json").write_text(
            json.dumps({"name": "Plexamp", "version": "4.13.2"}),
            encoding="utf-8",
        )

        settings = {
            "dashboard": {
                "startup_mode": "clock",
                "idle_return_mode": "weather",
                "idle_timeout_seconds": 240,
            },
            "display": {
                "clock_format": "24h",
                "daytime_theme": "astronomy-would-be-invalid-here",
                "night_dim_enabled": True,
                "night_dim_start": "22:00",
                "night_dim_end": "07:00",
            },
            "weather": {
                "station_name": "Weather or Not",
                "reporting_station_name": "Bedroom Station",
                "auto_refresh_seconds": 60,
                "units": {"temperature": "c", "pressure": "hpa", "rain": "mm", "wind": "mph"},
                "clock_cards": ["outdoor_temp", "pressure"],
                "forecast": {
                    "enabled": True,
                    "provider": "open_meteo",
                    "latitude": 51.03,
                    "longitude": -0.80,
                    "timezone": "Europe/London",
                    "forecast_days": 16,
                },
                "historical_rainfall": {"period": "current_year"},
                "observations": {
                    "provider": "weather_underground",
                    "ecowitt_push": {"path": "/ecowitt", "fresh_seconds": 180},
                    "weather_underground": {
                        "station_id": "IEXAMPLE1",
                        "api_key_env": "SECRET_ENV_REFERENCE_MUST_NOT_EXPORT",
                        "api_key": "WU-SECRET-MUST-NOT-LEAK",
                        "refresh_seconds": 60,
                        "stale_seconds": 300,
                        "request_timeout_seconds": 8,
                        "pressure_history_hours": 6,
                    },
                },
            },
            "alarms": {"enabled": True, "alarms": [{"id": "wake", "time": "07:00"}]},
            "alarm_audio": {
                "hardware_device": "hw:CARD=Pro,DEV=0",
                "alsa_device": "acp_alarm",
            },
            "airplay": {
                "receiver_name": "Bedroom Plexamp",
                "default_volume_percent": 60,
                "apply_default_volume_on_start": True,
                "pause_hold_seconds": 420,
            },
            "audio": {
                "eq": {
                    "enabled": True,
                    "bands": {"bass": 1.0, "mid": 0.0, "treble": -0.5},
                }
            },
            "plexamp": {
                "url": "http://localhost:32500",
                "pause_url": "http://localhost:32500/player/playback/pause",
                "service_name": "plexamp.service",
            },
        }
        mixer = {
            "channels": {
                "master": {"percent": 80},
                "plexamp": {"percent": 95},
                "airplay": {"percent": 90},
                "alarm": {"percent": 85},
            }
        }
        fixed_now = datetime(
            2026,
            8,
            23,
            23,
            59,
            0,
            tzinfo=timezone(timedelta(hours=1)),
        )
        return ConfigurationBackupService(
            settings_snapshot=lambda: {"ok": True, "settings": deepcopy(settings)},
            app_version_path=version_path,
            home=root,
            mixer_snapshot=lambda: deepcopy(mixer),
            now_provider=lambda: fixed_now,
        )

    def test_export_is_versioned_portable_and_excludes_secret_or_machine_state(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.build_service(Path(directory))
            backup = service.build()

        self.assertEqual(backup["schema_version"], 1)
        self.assertEqual(backup["created_at"], "2026-08-23T23:59:00+01:00")
        self.assertEqual(backup["source"]["app_version"], "0.4.0")
        self.assertEqual(backup["plexamp"]["source_version"], "4.13.2")
        self.assertEqual(
            backup["plexamp"]["headless_preferences"],
            {
                "audioConversionBitrate": 256,
                "autoPlayEnabled": False,
                "cacheSize": 32768,
                "cachingWiFi": 10,
                "loudnessLeveling": False,
                "precacheNetworkSpeed": 0,
                "sampleRateConversionQuality": 4,
                "sampleRateMatching": 2,
            },
        )
        self.assertEqual(
            backup["a_clockwork_plex"]["audio"]["mixer"],
            {"master": 80, "plexamp": 95, "airplay": 90, "alarm": 85},
        )
        self.assertEqual(
            backup["a_clockwork_plex"]["settings"]["weather"]["observations"]
            ["weather_underground"]["station_id"],
            "IEXAMPLE1",
        )

        encoded = json.dumps(backup, sort_keys=True)
        for forbidden in (
            "WU-SECRET-MUST-NOT-LEAK",
            "SECRET_ENV_REFERENCE_MUST_NOT_EXPORT",
            "DEVICE-SECRET-MUST-NOT-LEAK",
            "ACCOUNT-STATE-MUST-NOT-LEAK",
            "AUTH-MUST-NOT-LEAK",
            "hardware_device",
            "alsa_device",
            "pause_url",
            "service_name",
            "api_key_env",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertIn("plexamp.browser_preferences", encoded)
        self.assertIn("Chromium profile/LevelDB files are never copied", encoded)

    def test_backup_api_is_read_only_download_with_no_store_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.build_service(Path(directory))
            app = Flask(__name__)
            register_configuration_backup_api(app, service)
            response = app.test_client().get("/api/settings/backup")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn(
            'filename="A-Clockwork-Plex-backup-2026-08-23_235900.json"',
            response.headers["Content-Disposition"],
        )
        payload = json.loads(response.get_data(as_text=True))
        self.assertEqual(payload["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
