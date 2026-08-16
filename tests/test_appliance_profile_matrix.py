from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"
PREFLIGHT = ROOT / "scripts/preflight-appliance.sh"
PACKAGE_CHECK = ROOT / "scripts/check-appliance-packages.sh"
VERIFY = ROOT / "scripts/verify-appliance.sh"
HELPER_INSTALL = ROOT / "scripts/install-appliance-helpers.sh"
EQ_INSTALL = ROOT / "scripts/audio/install-eq.sh"
EQ_UNINSTALL = ROOT / "scripts/audio/uninstall-eq.sh"
DIRECT_PROFILE = ROOT / "installer/profiles/direct/alarm-safe.conf"
AIRPLAY_RENDERER_PATH = ROOT / "scripts/a-clockwork-plex-airplay-wrappers.py"
DIRECT_SHA = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"
CAMILLA_SHA = "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa"

AIRPLAY_SPEC = importlib.util.spec_from_file_location(
    "acp_profile_matrix_airplay_wrappers", AIRPLAY_RENDERER_PATH
)
AIRPLAY_RENDERER = importlib.util.module_from_spec(AIRPLAY_SPEC)
assert AIRPLAY_SPEC and AIRPLAY_SPEC.loader
AIRPLAY_SPEC.loader.exec_module(AIRPLAY_RENDERER)


class ApplianceProfileMatrixTests(unittest.TestCase):
    def write(self, root: Path, logical: str, content: str, mode: int = 0o644) -> Path:
        path = root / logical.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(mode)
        return path

    def prepare_common_installed_fixture(self, root: Path, weather: str) -> tuple[str, str]:
        user = "testclock"
        project_dir = f"/home/{user}/A-Clockwork-Plex"
        self.write(
            root,
            "/etc/systemd/system/a-clockwork-plex.service",
            f"[Service]\nUser={user}\nGroup={user}\nWorkingDirectory={project_dir}\n"
            f"ExecStart={project_dir}/venv/bin/python {project_dir}/app/runner.py\n",
        )
        self.write(
            root,
            "/usr/local/bin/a-clockwork-plex-airplay-start",
            AIRPLAY_RENDERER.render_start_wrapper(),
            0o755,
        )
        self.write(
            root,
            "/usr/local/bin/a-clockwork-plex-airplay-end",
            AIRPLAY_RENDERER.render_end_wrapper(),
            0o755,
        )
        self.write(
            root,
            "/etc/systemd/system/a-clockwork-plex-airplay-metadata.service",
            f"[Service]\nUser={user}\n"
            "Environment=SHAIRPORT_METADATA_PIPE=/tmp/shairport-sync-metadata\n"
            f"ExecStart=/usr/bin/python3 {project_dir}/scripts/airplay-metadata-listener.py\n",
        )
        self.write(root, "/usr/local/bin/a-clockwork-plex-alarm-audio", "#!/bin/bash\n", 0o755)
        self.write(root, "/etc/sudoers.d/a-clockwork-plex-alarm-audio", "test\n", 0o440)
        self.write(root, "/usr/local/bin/a-clockwork-plex-shairport-name", "#!/usr/bin/env python3\n", 0o755)
        self.write(root, "/etc/sudoers.d/a-clockwork-plex-shairport-name", "test\n", 0o440)
        self.write(
            root,
            "/etc/shairport-sync.conf",
            'start_hook = "/usr/local/bin/a-clockwork-plex-airplay-start";\n'
            'stop_hook = "/usr/local/bin/a-clockwork-plex-airplay-end";\n'
            'metadata_pipe_name = "/tmp/shairport-sync-metadata";\n'
            'output_device = "acp_airplay";\n',
        )
        self.write(
            root,
            f"/home/{user}/.config/autostart/a-clockwork-plex-dashboard.desktop",
            f"[Desktop Entry]\nExec={project_dir}/scripts/launch-dashboard-kiosk.sh\n",
        )
        config = {
            "weather": {
                "provider": "weather_underground" if weather == "weather-underground" else "ecowitt_push",
                "ecowitt_push": {"path": "/ecowitt", "fresh_seconds": 180},
                "weather_underground": {
                    "station_id": "ITEST1" if weather == "weather-underground" else "",
                    "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
                    "refresh_seconds": 60,
                    "stale_seconds": 300,
                    "request_timeout_seconds": 10,
                },
                "forecast": {"provider": "open_meteo", "enabled": True},
            }
        }
        self.write(root, f"{project_dir}/config.json", json.dumps(config))
        route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        route.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DIRECT_PROFILE, route)
        return user, project_dir

    def fake_camilla_environment(self, directory: str) -> tuple[Path, dict[str, str]]:
        fake_dir = Path(directory) / "fake-bin"
        fake_dir.mkdir()
        camilla = Path(directory) / "camilladsp-4.1.3"
        camilla.write_text(
            "#!/bin/bash\n"
            "if [[ \"${1:-}\" == \"--version\" ]]; then echo 'CamillaDSP 4.1.3'; exit 0; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        camilla.chmod(0o755)
        real_sha = shutil.which("sha256sum") or "/usr/bin/sha256sum"
        wrapper = fake_dir / "sha256sum"
        wrapper.write_text(
            "#!/bin/bash\n"
            "case \"${1:-}\" in\n"
            f"  *camilladsp*) echo '{CAMILLA_SHA}  $1';;\n"
            f"  *) exec {real_sha} \"$@\";;\n"
            "esac\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{fake_dir}:{env.get('PATH', '')}"
        return camilla, env

    def command(self, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_all_four_profiles_have_coherent_plan_preflight_install_state_and_verifier(self) -> None:
        for audio in ("direct", "eq"):
            for weather in ("ecowitt-push", "weather-underground"):
                with self.subTest(audio=audio, weather=weather), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / "root"
                    root.mkdir()
                    user, project_dir = self.prepare_common_installed_fixture(root, weather)

                    plan = self.command(
                        [
                            "bash",
                            str(INSTALLER),
                            "--audio",
                            audio,
                            "--weather-observations",
                            weather,
                            "--project-user",
                            user,
                            "--non-interactive",
                        ]
                    )
                    self.assertEqual(plan.returncode, 0, plan.stderr)
                    self.assertIn(f"Audio profile:        {audio}", plan.stdout)
                    self.assertIn(f"Weather observations: {weather}", plan.stdout)

                    packages = self.command(
                        [
                            "bash",
                            str(PACKAGE_CHECK),
                            "--source-only",
                            "--audio",
                            audio,
                            "--weather-observations",
                            weather,
                        ]
                    )
                    self.assertEqual(packages.returncode, 0, packages.stderr)
                    self.assertIn("APPLIANCE_PACKAGE_CHECK=SOURCE-PASS", packages.stdout)

                    preflight = self.command(
                        [
                            "bash",
                            str(PREFLIGHT),
                            "--source-only",
                            "--audio",
                            audio,
                            "--weather-observations",
                            weather,
                            "--project-user",
                            user,
                        ]
                    )
                    self.assertEqual(preflight.returncode, 0, preflight.stderr)
                    self.assertIn("APPLIANCE_PREFLIGHT=SOURCE-PASS", preflight.stdout)

                    helpers = self.command(
                        [
                            "bash",
                            str(HELPER_INSTALL),
                            "--root",
                            str(root),
                            "--activate",
                            "--confirm",
                            "INSTALL-APPLIANCE-HELPERS",
                            "--project-user",
                            user,
                        ]
                    )
                    self.assertEqual(helpers.returncode, 0, helpers.stdout + helpers.stderr)
                    self.assertIn("Restricted appliance helpers installed successfully", helpers.stdout)

                    env = None
                    if audio == "eq":
                        camilla, env = self.fake_camilla_environment(directory)
                        prepare = self.command(
                            [
                                "bash",
                                str(EQ_INSTALL),
                                "--root",
                                str(root),
                                "--prepare-only",
                                "--baseline",
                                "alarm-safe-direct",
                                "--binary",
                                str(camilla),
                            ],
                            env=env,
                        )
                        self.assertEqual(prepare.returncode, 0, prepare.stdout + prepare.stderr)
                        activate = self.command(
                            [
                                "bash",
                                str(EQ_INSTALL),
                                "--root",
                                str(root),
                                "--activate",
                                "--confirm",
                                "INSTALL-EQ-AUDIO",
                                "--baseline",
                                "alarm-safe-direct",
                                "--binary",
                                str(camilla),
                            ],
                            env=env,
                        )
                        self.assertEqual(activate.returncode, 0, activate.stdout + activate.stderr)

                    verified = self.command(
                        [
                            "bash",
                            str(VERIFY),
                            "--root",
                            str(root),
                            "--audio",
                            audio,
                            "--weather-observations",
                            weather,
                            "--project-user",
                            user,
                            "--project-dir",
                            project_dir,
                        ],
                        env=env,
                    )
                    self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
                    self.assertIn("APPLIANCE_VERIFY=PASS", verified.stdout)

                    if audio == "eq":
                        uninstall = self.command(
                            [
                                "bash",
                                str(EQ_UNINSTALL),
                                "--root",
                                str(root),
                                "--activate",
                                "--confirm",
                                "UNINSTALL-EQ-AUDIO",
                            ],
                            env=env,
                        )
                        self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
                        route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
                        observed = self.command([shutil.which("sha256sum") or "/usr/bin/sha256sum", str(route)])
                        self.assertEqual(observed.returncode, 0, observed.stderr)
                        self.assertTrue(observed.stdout.startswith(DIRECT_SHA), observed.stdout)


if __name__ == "__main__":
    unittest.main()
