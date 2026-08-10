from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "audio" / "install-direct.sh"
PROFILE = ROOT / "installer" / "profiles" / "direct" / "alarm-safe.conf"
DIRECT_SHA = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"


class DirectAudioInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        root: Path,
        *arguments: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            ["bash", str(INSTALLER), "--root", str(root), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=merged,
            check=False,
        )

    def test_profile_source_has_accepted_checksum(self) -> None:
        self.assertEqual(hashlib.sha256(PROFILE.read_bytes()).hexdigest(), DIRECT_SHA)

    def test_prepare_only_does_not_change_existing_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            route.parent.mkdir(parents=True)
            route.write_text("original\n", encoding="utf-8")

            result = self.run_installer(root, "--prepare-only")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(route.read_text(encoding="utf-8"), "original\n")
            self.assertIn("No production file, service, route, mixer or PCM was changed", result.stdout)

    def test_guarded_alternate_root_activation_installs_exact_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-DIRECT-AUDIO",
            )

            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(route.is_file())
            self.assertEqual(hashlib.sha256(route.read_bytes()).hexdigest(), DIRECT_SHA)
            self.assertIn("Alarm-safe Direct audio installed successfully", result.stdout)

    def test_wrong_confirmation_token_is_rejected_without_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            route.parent.mkdir(parents=True)
            route.write_text("original\n", encoding="utf-8")

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "WRONG",
            )

            self.assertEqual(result.returncode, 64)
            self.assertEqual(route.read_text(encoding="utf-8"), "original\n")
            self.assertIn("INSTALL-DIRECT-AUDIO", result.stderr)

    def test_injected_nonproduction_failure_restores_exact_previous_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            route.parent.mkdir(parents=True)
            original = b"previous-route\n"
            route.write_bytes(original)
            os.chmod(route, 0o640)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-DIRECT-AUDIO",
                env={"ACP_DIRECT_TEST_FAIL_AFTER_ROUTE": "1"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(route.read_bytes(), original)
            self.assertEqual(oct(route.stat().st_mode & 0o777), "0o640")
            self.assertIn("restoring captured state", result.stderr)
            self.assertIn("pre-state restored", result.stderr)

    def test_injected_failure_removes_route_when_it_was_initially_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-DIRECT-AUDIO",
                env={"ACP_DIRECT_TEST_FAIL_AFTER_ROUTE": "1"},
            )

            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(route.exists())

    def test_failure_injection_is_nonproduction_only(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('[[ "$ROOT" != / && "${ACP_DIRECT_TEST_FAIL_AFTER_ROUTE:-0}" == 1 ]]', source)
        self.assertIn("acp_transaction_capture_service", source)
        self.assertIn("acp_transaction_restore_services", source)
        self.assertNotIn("install-shared-audio.sh", source)


if __name__ == "__main__":
    unittest.main()
