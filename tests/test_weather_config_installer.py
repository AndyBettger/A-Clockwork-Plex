import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install-weather-config.sh"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "a-clockwork-plex.service"
CONFIG_EXAMPLE = REPO_ROOT / "config.example.json"


class WeatherConfigInstallerTests(unittest.TestCase):
    def make_root(self, base: Path) -> tuple[Path, Path, Path]:
        root = base / "root"
        project = root / "project"
        project.mkdir(parents=True)
        config = project / "config.json"
        env_file = root / "etc" / "default" / "a-clockwork-plex-weather"
        return root, config, env_file

    def base_config(self) -> dict:
        return {
            "dashboard": {"port": 8088},
            "weather": {
                "provider": "ecowitt_push",
                "display_units": "metric",
                "weather_underground": {
                    "station_id": "OLDSTATION",
                    "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
                    "api_key": "legacy-inline-secret",
                    "refresh_seconds": 60,
                },
                "forecast": {
                    "enabled": True,
                    "provider": "open_meteo",
                    "latitude": 51.0,
                    "longitude": -1.0,
                },
            },
        }

    def run_installer(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=REPO_ROOT,
            env=child_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_prepare_only_is_read_only_and_does_not_print_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, config, env_file = self.make_root(Path(tmp))
            original = json.dumps(self.base_config(), indent=2).encode()
            config.write_bytes(original)
            env_file.parent.mkdir(parents=True)
            env_file.write_bytes(b'WEATHER_UNDERGROUND_API_KEY="old-secret"\n')
            original_env = env_file.read_bytes()
            key_file = Path(tmp) / "wu.key"
            key_file.write_text("super-secret-value\n", encoding="utf-8")

            result = self.run_installer(
                "--root", str(root),
                "--provider", "weather-underground",
                "--wu-station-id", "imyStation_1",
                "--wu-api-key-file", str(key_file),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(env_file.read_bytes(), original_env)
            self.assertNotIn("super-secret-value", result.stdout + result.stderr)
            self.assertIn("Prepare-only complete", result.stdout)

    def test_weather_underground_activation_uses_env_file_and_preserves_forecast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, config, env_file = self.make_root(Path(tmp))
            config.write_text(json.dumps(self.base_config(), indent=2), encoding="utf-8")
            key_file = Path(tmp) / "wu.key"
            key_file.write_text('abc\\def"ghi\n', encoding="utf-8")

            result = self.run_installer(
                "--root", str(root),
                "--activate", "--confirm", "INSTALL-WEATHER-CONFIG",
                "--provider", "weather-underground",
                "--wu-station-id", "imyStation_1",
                "--wu-api-key-file", str(key_file),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(config.read_text(encoding="utf-8"))
            weather = payload["weather"]
            self.assertEqual(weather["provider"], "weather_underground")
            self.assertEqual(weather["weather_underground"]["station_id"], "IMYSTATION_1")
            self.assertEqual(
                weather["weather_underground"]["api_key_env"],
                "WEATHER_UNDERGROUND_API_KEY",
            )
            self.assertNotIn("api_key", weather["weather_underground"])
            self.assertEqual(weather["forecast"], self.base_config()["weather"]["forecast"])
            self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)
            env_text = env_file.read_text(encoding="utf-8")
            self.assertIn("WEATHER_UNDERGROUND_API_KEY=", env_text)
            self.assertNotIn("legacy-inline-secret", config.read_text(encoding="utf-8"))
            self.assertNotIn('abc\\def"ghi', result.stdout + result.stderr)

    def test_ecowitt_activation_removes_managed_wu_secret_without_touching_forecast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, config, env_file = self.make_root(Path(tmp))
            payload = self.base_config()
            payload["weather"]["provider"] = "weather_underground"
            config.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            env_file.parent.mkdir(parents=True)
            env_file.write_text('WEATHER_UNDERGROUND_API_KEY="old-secret"\n', encoding="utf-8")
            os.chmod(env_file, 0o600)

            result = self.run_installer(
                "--root", str(root),
                "--activate", "--confirm", "INSTALL-WEATHER-CONFIG",
                "--provider", "ecowitt-push",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            installed = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(installed["weather"]["provider"], "ecowitt_push")
            self.assertEqual(installed["weather"]["forecast"], payload["weather"]["forecast"])
            self.assertNotIn("api_key", installed["weather"]["weather_underground"])
            self.assertFalse(env_file.exists())

    def test_injected_failure_after_config_restores_exact_bytes_and_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, config, env_file = self.make_root(Path(tmp))
            original_config = b'{"weather":{"provider":"ecowitt_push"},"sentinel":"exact bytes"}\n'
            config.write_bytes(original_config)
            env_file.parent.mkdir(parents=True)
            original_env = b'WEATHER_UNDERGROUND_API_KEY="previous-secret"\n'
            env_file.write_bytes(original_env)
            os.chmod(env_file, 0o640)
            original_mode = stat.S_IMODE(env_file.stat().st_mode)
            key_file = Path(tmp) / "wu.key"
            key_file.write_text("replacement-secret\n", encoding="utf-8")

            result = self.run_installer(
                "--root", str(root),
                "--activate", "--confirm", "INSTALL-WEATHER-CONFIG",
                "--provider", "weather-underground",
                "--wu-station-id", "TEST123",
                "--wu-api-key-file", str(key_file),
                env={"ACP_WEATHER_TEST_FAIL_AFTER_CONFIG": "1"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(config.read_bytes(), original_config)
            self.assertEqual(env_file.read_bytes(), original_env)
            self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), original_mode)
            self.assertIn("exact managed pre-state was restored", result.stderr)

    def test_injected_failure_after_secret_restores_prior_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, config, env_file = self.make_root(Path(tmp))
            self.assertFalse(config.exists())
            self.assertFalse(env_file.exists())
            key_file = Path(tmp) / "wu.key"
            key_file.write_text("replacement-secret\n", encoding="utf-8")

            result = self.run_installer(
                "--root", str(root),
                "--activate", "--confirm", "INSTALL-WEATHER-CONFIG",
                "--provider", "weather-underground",
                "--wu-station-id", "TEST123",
                "--wu-api-key-file", str(key_file),
                env={"ACP_WEATHER_TEST_FAIL_AFTER_SECRET": "1"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(config.exists())
            self.assertFalse(env_file.exists())

    def test_confirmation_gate_precedes_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, config, env_file = self.make_root(Path(tmp))
            original = b'{"weather":{"provider":"ecowitt_push"}}\n'
            config.write_bytes(original)

            result = self.run_installer(
                "--root", str(root),
                "--activate", "--confirm", "WRONG",
                "--provider", "ecowitt-push",
            )

            self.assertEqual(result.returncode, 64)
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse(env_file.exists())

    def test_runtime_and_systemd_contracts_use_only_environment_secret(self) -> None:
        example = json.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
        weather = example["weather"]
        self.assertEqual(weather["provider"], "ecowitt_push")
        self.assertEqual(
            weather["weather_underground"]["api_key_env"],
            "WEATHER_UNDERGROUND_API_KEY",
        )
        self.assertNotIn("api_key", weather["weather_underground"])
        self.assertIn(
            "EnvironmentFile=-/etc/default/a-clockwork-plex-weather",
            SYSTEMD_UNIT.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
