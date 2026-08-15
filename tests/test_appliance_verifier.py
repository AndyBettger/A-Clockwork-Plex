from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify-appliance.sh"
DIRECT_PROFILE = ROOT / "installer/profiles/direct/alarm-safe.conf"
DIRECT_SHA256 = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"


class ApplianceVerifierTests(unittest.TestCase):
    def make_common_fixture(self, directory: str, provider: str) -> tuple[Path, str, str]:
        root = Path(directory)
        user = "testclock"
        project_dir = f"/home/{user}/A-Clockwork-Plex"

        def write(logical: str, content: str, mode: int = 0o644) -> Path:
            path = root / logical.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            path.chmod(mode)
            return path

        write(
            "/etc/systemd/system/a-clockwork-plex.service",
            "\n".join(
                (
                    "[Service]",
                    f"User={user}",
                    f"Group={user}",
                    f"WorkingDirectory={project_dir}",
                    f"ExecStart={project_dir}/venv/bin/python {project_dir}/app/runner.py",
                    "",
                )
            ),
        )
        write(
            "/usr/local/bin/a-clockwork-plex-airplay-start",
            "\n".join(
                (
                    "#!/bin/bash",
                    'DASHBOARD_BASE="http://localhost:8088"',
                    'curl "$DASHBOARD_BASE/api/airplay/start"',
                    'echo "PlaybackCoordinator owns Plexamp pause"',
                    "",
                )
            ),
            0o755,
        )
        write(
            "/usr/local/bin/a-clockwork-plex-airplay-end",
            "\n".join(
                (
                    "#!/bin/bash",
                    'DASHBOARD_BASE="http://localhost:8088"',
                    "echo org.gnome.ShairportSync.RemoteControl",
                    'curl "$DASHBOARD_BASE/api/airplay/end"',
                    'curl "$DASHBOARD_BASE/api/playback/events"',
                    "",
                )
            ),
            0o755,
        )
        write(
            "/etc/systemd/system/a-clockwork-plex-airplay-metadata.service",
            "\n".join(
                (
                    "[Service]",
                    f"User={user}",
                    "Environment=SHAIRPORT_METADATA_PIPE=/tmp/shairport-sync-metadata",
                    f"WorkingDirectory={project_dir}",
                    f"ExecStart=/usr/bin/python3 {project_dir}/scripts/airplay-metadata-listener.py",
                    "",
                )
            ),
        )
        write("/usr/local/bin/a-clockwork-plex-alarm-audio", "#!/bin/bash\n", 0o755)
        write("/etc/sudoers.d/a-clockwork-plex-alarm-audio", "testclock ALL=(root) NOPASSWD: /bin/true\n", 0o440)
        write("/usr/local/bin/a-clockwork-plex-shairport-name", "#!/usr/bin/env python3\n", 0o755)
        write("/etc/sudoers.d/a-clockwork-plex-shairport-name", "testclock ALL=(root) NOPASSWD: /bin/true\n", 0o440)
        write(
            "/etc/shairport-sync.conf",
            "\n".join(
                (
                    'start_hook = "/usr/local/bin/a-clockwork-plex-airplay-start";',
                    'stop_hook = "/usr/local/bin/a-clockwork-plex-airplay-end";',
                    'metadata_pipe_name = "/tmp/shairport-sync-metadata";',
                    'output_device = "acp_airplay";',
                    "",
                )
            ),
        )
        write(
            f"/home/{user}/.config/autostart/a-clockwork-plex-dashboard.desktop",
            f"[Desktop Entry]\nExec={project_dir}/scripts/launch-dashboard-kiosk.sh\n",
        )

        config = {
            "weather": {
                "provider": "weather_underground" if provider == "weather-underground" else "ecowitt_push",
                "ecowitt_push": {"path": "/ecowitt", "fresh_seconds": 180},
                "weather_underground": {
                    "station_id": "ITEST1" if provider == "weather-underground" else "",
                    "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
                    "refresh_seconds": 60,
                    "stale_seconds": 300,
                    "request_timeout_seconds": 10,
                },
                "forecast": {"provider": "open_meteo", "enabled": True},
            }
        }
        write(f"{project_dir}/config.json", json.dumps(config))

        route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        route.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DIRECT_PROFILE, route)
        return root, user, project_dir

    def run_verifier(
        self,
        root: Path,
        user: str,
        project_dir: str,
        provider: str,
        *,
        audio: str = "direct",
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            [
                "bash",
                str(VERIFIER),
                "--root",
                str(root),
                "--audio",
                audio,
                "--weather-observations",
                provider,
                "--project-user",
                user,
                "--project-dir",
                project_dir,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=merged,
            check=False,
        )

    def test_direct_ecowitt_fixture_passes_filesystem_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, user, project_dir = self.make_common_fixture(directory, "ecowitt-push")
            result = self.run_verifier(root, user, project_dir, "ecowitt-push")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"direct-route             sha256={DIRECT_SHA256}", result.stdout)
        self.assertIn("weather-provider         ecowitt-push", result.stdout)
        self.assertIn("forecast-provider        open_meteo", result.stdout)
        self.assertIn("live-runtime             skipped", result.stdout)
        self.assertIn("APPLIANCE_VERIFY=PASS", result.stdout)

    def test_current_airplay_contract_is_verified_instead_of_retired_event_helper(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("/api/airplay/start", source)
        self.assertIn("/api/airplay/end", source)
        self.assertIn("/api/playback/events", source)
        self.assertIn("org.gnome.ShairportSync.RemoteControl", source)
        self.assertIn("scripts/airplay-metadata-listener.py", source)
        self.assertIn("Environment=SHAIRPORT_METADATA_PIPE=/tmp/shairport-sync-metadata", source)
        self.assertNotIn("/api/airplay/event", source)
        self.assertNotIn("/usr/local/bin/a-clockwork-plex-airplay-metadata-listener", source)

    def test_verifier_rejects_retired_airplay_wrapper_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, user, project_dir = self.make_common_fixture(directory, "ecowitt-push")
            start = root / "usr/local/bin/a-clockwork-plex-airplay-start"
            start.write_text("#!/bin/bash\ncurl /api/airplay/event\n", encoding="utf-8")
            result = self.run_verifier(root, user, project_dir, "ecowitt-push")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  airplay-start", result.stdout)
        self.assertIn("APPLIANCE_VERIFY=FAIL", result.stdout)

    def test_direct_weather_underground_fixture_passes_without_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, user, project_dir = self.make_common_fixture(directory, "weather-underground")
            result = self.run_verifier(root, user, project_dir, "weather-underground")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("weather-provider         weather-underground", result.stdout)
        self.assertIn("wu-station               ITEST1", result.stdout)
        self.assertIn("wu-key-env               WEATHER_UNDERGROUND_API_KEY (name only)", result.stdout)
        self.assertNotIn("api-secret-value", result.stdout)
        self.assertIn("APPLIANCE_VERIFY=PASS", result.stdout)

    def test_verifier_rejects_wrong_direct_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, user, project_dir = self.make_common_fixture(directory, "ecowitt-push")
            (root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf").write_text(
                "not the accepted direct route\n", encoding="utf-8"
            )
            result = self.run_verifier(root, user, project_dir, "ecowitt-push")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  direct-route", result.stdout)
        self.assertIn("APPLIANCE_VERIFY=FAIL", result.stdout)

    def test_verifier_rejects_secret_material_in_weather_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, user, project_dir = self.make_common_fixture(directory, "weather-underground")
            config_path = root / project_dir.lstrip("/") / "config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["weather"]["weather_underground"]["api_key"] = "must-not-be-here"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            result = self.run_verifier(root, user, project_dir, "weather-underground")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  weather-secret", result.stdout)
        self.assertNotIn("must-not-be-here", result.stdout)

    def test_protected_sudoers_verification_uses_read_only_root_boundary(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")

        self.assertIn("require_protected_file()", source)
        self.assertIn('sudo -n test -f "$path"', source)
        self.assertIn('sudo -n test -L "$path"', source)
        self.assertIn(
            "require_protected_file alarm-sudoers '/etc/sudoers.d/a-clockwork-plex-alarm-audio'",
            source,
        )
        self.assertIn(
            "require_protected_file shairport-name-sudoers '/etc/sudoers.d/a-clockwork-plex-shairport-name'",
            source,
        )
        self.assertNotIn(
            "require_file alarm-sudoers '/etc/sudoers.d/a-clockwork-plex-alarm-audio'",
            source,
        )
        self.assertNotIn(
            "require_file shairport-name-sudoers '/etc/sudoers.d/a-clockwork-plex-shairport-name'",
            source,
        )

    def test_alternate_root_protected_files_do_not_require_sudo(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_directory:
            root, user, project_dir = self.make_common_fixture(directory, "ecowitt-push")
            fake_sudo = Path(bin_directory) / "sudo"
            fake_sudo.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
            fake_sudo.chmod(0o755)
            result = self.run_verifier(
                root,
                user,
                project_dir,
                "ecowitt-push",
                env={"PATH": f"{bin_directory}:{os.environ.get('PATH', '')}"},
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS  alarm-sudoers", result.stdout)
        self.assertIn("PASS  shairport-name-sudoers", result.stdout)
        self.assertIn("APPLIANCE_VERIFY=PASS", result.stdout)

    def test_verifier_is_statically_read_only_against_production(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        mutation = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:apt|apt-get|install|cp|mv|chmod|chown|mkfifo|mkdir|"
            r"systemctl\s+(?:start|stop|restart|enable|disable|daemon-reload)|modprobe|tee)\b"
        )
        self.assertIsNone(mutation.search(source))
        self.assertNotIn("> /etc/", source)
        self.assertNotIn("> /usr/local/", source)
        self.assertIn("verify-audio.sh", source)
        self.assertIn("/api/weather/observations", source)
        self.assertIn("/api/audio/eq", source)

    def test_invalid_profiles_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad_audio = subprocess.run(
                ["bash", str(VERIFIER), "--root", directory, "--audio", "mystery"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            bad_weather = subprocess.run(
                [
                    "bash",
                    str(VERIFIER),
                    "--root",
                    directory,
                    "--weather-observations",
                    "mystery",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(bad_audio.returncode, 64)
        self.assertEqual(bad_weather.returncode, 64)


if __name__ == "__main__":
    unittest.main()
