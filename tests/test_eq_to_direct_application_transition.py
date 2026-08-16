from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-application.sh"
UNINSTALL_EQ = ROOT / "scripts" / "audio" / "uninstall-eq.sh"
APPLICATION_TRANSACTION = ROOT / "installer" / "lib" / "application_transaction.sh"
DIRECT_SHA = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"
CAMILLA_SHA = "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa"

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


class EqToDirectApplicationTransitionTests(unittest.TestCase):
    def make_fixture(self, directory: str) -> tuple[Path, dict[str, str], Path]:
        root = Path(directory) / "root"
        (root / "project").mkdir(parents=True)
        (root / "tmp").mkdir(parents=True)

        shairport = root / "etc/shairport-sync.conf"
        shairport.parent.mkdir(parents=True)
        shairport.write_text(BASE_SHAIRPORT, encoding="utf-8")
        shairport.chmod(0o640)

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

        camilla = Path(directory) / "camilladsp-4.1.3"
        camilla.write_text(
            "#!/bin/bash\n"
            "if [[ \"${1:-}\" == \"--version\" ]]; then echo 'CamillaDSP 4.1.3'; exit 0; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        camilla.chmod(0o755)

        real_sha = shutil.which("sha256sum") or "/usr/bin/sha256sum"
        sha_wrapper = fake_bin / "sha256sum"
        sha_wrapper.write_text(
            "#!/bin/bash\n"
            "case \"${1:-}\" in\n"
            f"  *camilladsp*) echo '{CAMILLA_SHA}  $1';;\n"
            f"  *) exec {real_sha} \"$@\";;\n"
            "esac\n",
            encoding="utf-8",
        )
        sha_wrapper.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
        env["ACP_AIRPLAY_TEST_SHAIRPORT_BINARY"] = str(validator)
        return root, env, camilla

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

    def install_eq_appliance(
        self,
        root: Path,
        env: dict[str, str],
        camilla: Path,
    ) -> subprocess.CompletedProcess[str]:
        return self.run_installer(
            root,
            env,
            "--audio",
            "eq",
            "--camilladsp-binary",
            str(camilla),
            "--weather-observations",
            "ecowitt-push",
            "--activate",
            "--confirm",
            "INSTALL-APPLIANCE-APPLICATION",
        )

    def test_preinstalled_eq_converges_to_direct_and_discards_retained_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, env, camilla = self.make_fixture(directory)
            eq = self.install_eq_appliance(root, env, camilla)
            self.assertEqual(eq.returncode, 0, eq.stdout + eq.stderr)

            split_bus = root / "var/lib/a-clockwork-plex/split-bus"
            marker = split_bus / "installed"
            backup = split_bus / "pre-eq-backup"
            tombstone = split_bus / "pre-eq-backup.pending-direct-commit"
            self.assertTrue(marker.is_file())
            self.assertTrue((backup / "complete").is_file())

            direct = self.run_installer(
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

            self.assertEqual(direct.returncode, 0, direct.stdout + direct.stderr)
            self.assertIn("EQ -> Direct migrate: true", direct.stdout)
            self.assertIn("APPLICATION_TRANSACTION=COMMITTED", direct.stdout)
            self.assertFalse(marker.exists())
            self.assertFalse(backup.exists())
            self.assertFalse(tombstone.exists())

            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            self.assertEqual(hashlib.sha256(route.read_bytes()).hexdigest(), DIRECT_SHA)

    def test_failure_after_direct_restores_preexisting_eq_and_retained_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, env, camilla = self.make_fixture(directory)
            eq = self.install_eq_appliance(root, env, camilla)
            self.assertEqual(eq.returncode, 0, eq.stdout + eq.stderr)

            split_bus = root / "var/lib/a-clockwork-plex/split-bus"
            marker = split_bus / "installed"
            backup = split_bus / "pre-eq-backup"
            tombstone = split_bus / "pre-eq-backup.pending-direct-commit"
            manifest = split_bus / "install-manifest.tsv"
            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            camilla_service = root / "etc/systemd/system/a-clockwork-plex-camilladsp.service"

            sentinel = backup / "eq-to-direct-regression-sentinel"
            sentinel.write_text("retain me\n", encoding="utf-8")
            before = {
                "marker": marker.read_bytes(),
                "manifest": manifest.read_bytes(),
                "route": route.read_bytes(),
                "service": camilla_service.read_bytes(),
            }

            direct = self.run_installer(
                root,
                env,
                "--audio",
                "direct",
                "--weather-observations",
                "ecowitt-push",
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-APPLICATION",
                env_extra={"ACP_APPLICATION_TEST_FAIL_AFTER": "direct"},
            )

            self.assertEqual(direct.returncode, 1, direct.stdout + direct.stderr)
            self.assertIn("Whole-appliance managed pre-state restored", direct.stderr)
            self.assertEqual(marker.read_bytes(), before["marker"])
            self.assertEqual(manifest.read_bytes(), before["manifest"])
            self.assertEqual(route.read_bytes(), before["route"])
            self.assertEqual(camilla_service.read_bytes(), before["service"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "retain me\n")
            self.assertTrue((backup / "complete").is_file())
            self.assertFalse(tombstone.exists())

    def test_specialist_uninstall_can_retain_backup_for_enclosing_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, env, camilla = self.make_fixture(directory)
            eq = self.install_eq_appliance(root, env, camilla)
            self.assertEqual(eq.returncode, 0, eq.stdout + eq.stderr)

            split_bus = root / "var/lib/a-clockwork-plex/split-bus"
            marker = split_bus / "installed"
            backup = split_bus / "pre-eq-backup"
            result = subprocess.run(
                [
                    "bash",
                    str(UNINSTALL_EQ),
                    "--root",
                    str(root),
                    "--activate",
                    "--confirm",
                    "UNINSTALL-EQ-AUDIO",
                    "--retain-preinstall-backup",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(marker.exists())
            self.assertTrue((backup / "complete").is_file())
            self.assertIn("backup retained for enclosing transaction", result.stdout)

    def test_loopback_restore_hook_runs_before_captured_services_are_reactivated(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        transaction = APPLICATION_TRANSACTION.read_text(encoding="utf-8")

        self.assertIn("restore_hook=restore_eq_transition_loopback", installer)
        self.assertIn(
            'acp_application_transaction_restore "$TRANSACTION" "$restore_hook"',
            installer,
        )
        hook_call = transaction.index('elif ! "$pre_service_restore_hook"')
        service_restore = transaction.index('acp_transaction_restore_services "$directory"')
        self.assertLess(hook_call, service_restore)

    def test_retained_backup_is_staged_before_commit_and_restorable_until_commit(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        stage = installer.index("stage_eq_backup_for_commit || fail_transaction")
        commit = installer.index('acp_transaction_mark_complete "$TRANSACTION"')
        cleanup = installer.index("if ! cleanup_committed_eq_backup; then")
        rollback_restore = installer.index("if ! restore_staged_eq_backup; then")

        self.assertLess(stage, commit)
        self.assertLess(commit, cleanup)
        self.assertLess(
            rollback_restore,
            installer.index('acp_application_transaction_restore "$TRANSACTION"'),
        )


if __name__ == "__main__":
    unittest.main()
