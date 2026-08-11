from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-application.sh"
DIRECT_SHA = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"

BASE_SHAIRPORT = '''general =
{
    name = "Test Clock";
    interpolation = "soxr";
};

alsa =
{
    output_device = "old-output";
    mixer_control_name = "Master";
};
'''


class ApplianceApplicationInstallerTests(unittest.TestCase):
    def make_fixture(self, directory: str) -> tuple[Path, Path, dict[str, str]]:
        root = Path(directory) / "root"
        (root / "project").mkdir(parents=True)
        (root / "tmp").mkdir(parents=True)
        config = root / "etc/shairport-sync.conf"
        config.parent.mkdir(parents=True)
        config.write_text(BASE_SHAIRPORT, encoding="utf-8")
        config.chmod(0o640)

        fake_bin = Path(directory) / "fake-bin"
        fake_bin.mkdir()
        for name in ("systemd-analyze", "desktop-file-validate"):
            path = fake_bin / name
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        validator = Path(directory) / "fake-shairport-sync"
        validator.write_text(
            "#!/bin/bash\nprintf '%s\\n' '>> Display Config End.'\nexit 0\n",
            encoding="utf-8",
        )
        validator.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
        env["ACP_AIRPLAY_TEST_SHAIRPORT_BINARY"] = str(validator)
        return root, config, env

    def run_installer(
        self,
        root: Path,
        env: dict[str, str],
        *extra: str,
        env_extra: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        run_env = dict(env)
        if env_extra:
            run_env.update(env_extra)
        return subprocess.run(
            [
                "bash",
                str(INSTALLER),
                "--root",
                str(root),
                "--project-user",
                "testclock",
                "--project-dir",
                "/project",
                *extra,
            ],
            cwd=ROOT,
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_prepare_only_and_confirmation_boundary_are_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, shairport, env = self.make_fixture(directory)
            before = shairport.read_bytes()
            prepare = self.run_installer(root, env, "--audio", "direct")
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            self.assertIn("Mode:                 prepare-only", prepare.stdout)
            self.assertIn("Package/venv baseline", prepare.stdout)
            self.assertEqual(shairport.read_bytes(), before)

            rejected = self.run_installer(
                root,
                env,
                "--audio",
                "direct",
                "--activate",
                "--confirm",
                "WRONG",
            )
            self.assertEqual(rejected.returncode, 64)
            self.assertIn("INSTALL-APPLIANCE-APPLICATION", rejected.stderr)
            self.assertEqual(shairport.read_bytes(), before)

    def test_direct_ecowitt_transaction_reaches_whole_appliance_verifier_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _shairport, env = self.make_fixture(directory)
            result = self.run_installer(
                root,
                env,
                "--audio",
                "direct",
                "--weather-observations",
                "ecowitt-push",
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-APPLICATION",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("APPLIANCE_VERIFY=PASS", result.stdout)
            self.assertIn("APPLICATION_TRANSACTION=COMMITTED", result.stdout)

            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            digest = subprocess.check_output(["sha256sum", str(route)], text=True).split()[0]
            self.assertEqual(digest, DIRECT_SHA)
            dashboard = root / "etc/systemd/system/a-clockwork-plex.service"
            self.assertIn("WorkingDirectory=/project", dashboard.read_text(encoding="utf-8"))
            kiosk = root / "home/testclock/.config/autostart/a-clockwork-plex-dashboard.desktop"
            self.assertTrue(kiosk.is_file())
            self.assertTrue((root / "usr/local/bin/a-clockwork-plex-alarm-audio").is_file())
            self.assertTrue((root / "usr/local/bin/a-clockwork-plex-airplay-start").is_file())
            fifo = root / "tmp/shairport-sync-metadata"
            self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))

            config = json.loads((root / "project/config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["weather"]["provider"], "ecowitt_push")
            self.assertEqual(config["weather"]["forecast"]["provider"], "open_meteo")

    def test_late_injected_failure_restores_entire_managed_prestate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, shairport, env = self.make_fixture(directory)
            project_config = root / "project/config.json"
            project_config.write_text('{"weather":{"provider":"old"}}\n', encoding="utf-8")
            project_config.chmod(0o640)
            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            route.parent.mkdir(parents=True)
            route.write_text("old route\n", encoding="utf-8")
            route.chmod(0o600)
            helper = root / "usr/local/bin/a-clockwork-plex-alarm-audio"
            helper.parent.mkdir(parents=True)
            helper.write_text("old helper\n", encoding="utf-8")
            helper.chmod(0o700)

            before = {
                "shairport": shairport.read_bytes(),
                "shairport_mode": stat.S_IMODE(shairport.stat().st_mode),
                "config": project_config.read_bytes(),
                "config_mode": stat.S_IMODE(project_config.stat().st_mode),
                "route": route.read_bytes(),
                "route_mode": stat.S_IMODE(route.stat().st_mode),
                "helper": helper.read_bytes(),
                "helper_mode": stat.S_IMODE(helper.stat().st_mode),
            }

            result = self.run_installer(
                root,
                env,
                "--audio",
                "direct",
                "--weather-observations",
                "ecowitt-push",
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-APPLICATION",
                env_extra={"ACP_APPLICATION_TEST_FAIL_AFTER": "airplay"},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Whole-appliance managed pre-state restored", result.stderr)
            self.assertEqual(shairport.read_bytes(), before["shairport"])
            self.assertEqual(stat.S_IMODE(shairport.stat().st_mode), before["shairport_mode"])
            self.assertEqual(project_config.read_bytes(), before["config"])
            self.assertEqual(stat.S_IMODE(project_config.stat().st_mode), before["config_mode"])
            self.assertEqual(route.read_bytes(), before["route"])
            self.assertEqual(stat.S_IMODE(route.stat().st_mode), before["route_mode"])
            self.assertEqual(helper.read_bytes(), before["helper"])
            self.assertEqual(stat.S_IMODE(helper.stat().st_mode), before["helper_mode"])
            self.assertFalse((root / "etc/systemd/system/a-clockwork-plex.service").exists())
            self.assertFalse((root / "home/testclock/.config/autostart/a-clockwork-plex-dashboard.desktop").exists())
            self.assertFalse((root / "usr/local/bin/a-clockwork-plex-airplay-start").exists())
            self.assertFalse((root / "tmp/shairport-sync-metadata").exists())

    def test_source_keeps_final_verifier_inside_commit_boundary(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("install-dashboard-integration.sh", text)
        self.assertIn("install-weather-config.sh", text)
        self.assertIn("install-direct.sh", text)
        self.assertIn("install-eq.sh", text)
        self.assertIn("install-appliance-helpers.sh", text)
        self.assertIn("install-airplay-integration.sh", text)
        self.assertIn("verify-appliance.sh", text)
        self.assertIn("fail_transaction verifier", text)
        self.assertIn("acp_transaction_mark_complete", text)
        self.assertIn("uninstall-eq.sh", text)
        self.assertNotIn("install-shared-audio.sh", text)
        self.assertNotIn("install-master-eq.sh", text)

    def test_shell_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(INSTALLER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
