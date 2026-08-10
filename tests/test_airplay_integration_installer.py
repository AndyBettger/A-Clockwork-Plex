from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-airplay-integration.sh"


BASE_CONFIG = '''general =
{
    name = "Bedroom Clock";
    interpolation = "soxr";
};

alsa =
{
    output_device = "old-output";
    mixer_control_name = "Master";
};

sessioncontrol =
{
    run_this_after_play_ends = "/tmp/retired";
    session_timeout = 12;
};
'''


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


class AirPlayIntegrationInstallerTests(unittest.TestCase):
    def make_root(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "root"
        (root / "etc").mkdir(parents=True)
        (root / "tmp").mkdir(parents=True)
        (root / "usr" / "local" / "bin").mkdir(parents=True)
        (root / "etc" / "systemd" / "system").mkdir(parents=True)
        (root / "etc" / "sudoers.d").mkdir(parents=True)
        config = root / "etc" / "shairport-sync.conf"
        config.write_text(BASE_CONFIG, encoding="utf-8")
        config.chmod(0o640)
        return root, config

    def make_validator(self, directory: str, *, good: bool = True) -> Path:
        validator = Path(directory) / "fake-shairport-sync"
        if good:
            validator.write_text(
                "#!/bin/bash\nprintf '%s\\n' '>> Display Config End.'\nsleep 1\n",
                encoding="utf-8",
            )
        else:
            validator.write_text(
                "#!/bin/bash\nprintf '%s\\n' 'candidate rejected'\nexit 1\n",
                encoding="utf-8",
            )
        validator.chmod(0o755)
        return validator

    def run_installer(
        self,
        root: Path,
        validator: Path,
        *arguments: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["ACP_AIRPLAY_TEST_SHAIRPORT_BINARY"] = str(validator)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(INSTALLER), "--root", str(root), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_prepare_only_validates_candidates_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory)
            before = config.read_bytes()

            result = self.run_installer(root, validator, "--prepare-only")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Candidate config SHA:", result.stdout)
            self.assertIn("No production file, FIFO, service, route, mixer, PCM or configuration was changed.", result.stdout)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((root / "usr/local/bin/a-clockwork-plex-airplay-start").exists())
            self.assertFalse((root / "tmp/shairport-sync-metadata").exists())
            self.assertFalse((root / "etc/systemd/system/a-clockwork-plex-airplay-metadata.service").exists())

    def test_wrong_confirmation_token_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory)
            before = config.read_bytes()

            result = self.run_installer(
                root,
                validator,
                "--activate",
                "--confirm",
                "WRONG",
            )

            self.assertEqual(result.returncode, 64)
            self.assertIn("INSTALL-AIRPLAY-INTEGRATION", result.stderr)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((root / "tmp/shairport-sync-metadata").exists())

    def test_activation_installs_integrated_config_wrappers_fifo_and_unit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory)
            legacy_wrapper = root / "usr/local/bin/a-clockwork-plex-airplay-session-end"
            legacy_policy = root / "etc/sudoers.d/a-clockwork-plex-airplay"
            legacy_wrapper.write_text("old session end\n", encoding="utf-8")
            legacy_policy.write_text("old policy\n", encoding="utf-8")

            result = self.run_installer(
                root,
                validator,
                "--activate",
                "--confirm",
                "INSTALL-AIRPLAY-INTEGRATION",
                "--project-user",
                "andy",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Guarded AirPlay integration installed successfully", result.stdout)
            text = config.read_text(encoding="utf-8")
            self.assertIn('name = "Bedroom Clock";', text)
            self.assertIn('interpolation = "soxr";', text)
            self.assertIn('mixer_control_name = "Master";', text)
            self.assertIn('output_device = "acp_airplay";', text)
            self.assertIn('run_this_before_entering_active_state = "/usr/local/bin/a-clockwork-plex-airplay-start";', text)
            self.assertIn('run_this_after_exiting_active_state = "/usr/local/bin/a-clockwork-plex-airplay-end";', text)
            self.assertNotIn("run_this_after_play_ends", text)
            self.assertNotIn("session_timeout", text)
            self.assertIn('pipe_name = "/tmp/shairport-sync-metadata";', text)
            self.assertEqual(mode(config), 0o640)

            start = root / "usr/local/bin/a-clockwork-plex-airplay-start"
            end = root / "usr/local/bin/a-clockwork-plex-airplay-end"
            self.assertEqual(mode(start), 0o755)
            self.assertEqual(mode(end), 0o755)
            self.assertIn("/api/airplay/start", start.read_text(encoding="utf-8"))
            self.assertIn("/api/playback/events", end.read_text(encoding="utf-8"))
            self.assertFalse(legacy_wrapper.exists())
            self.assertFalse(legacy_policy.exists())

            fifo = root / "tmp/shairport-sync-metadata"
            self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
            self.assertEqual(mode(fifo), 0o666)
            unit = root / "etc/systemd/system/a-clockwork-plex-airplay-metadata.service"
            unit_text = unit.read_text(encoding="utf-8")
            self.assertIn("User=andy", unit_text)
            self.assertIn("Environment=SHAIRPORT_METADATA_PIPE=/tmp/shairport-sync-metadata", unit_text)
            self.assertIn("scripts/airplay-metadata-listener.py", unit_text)

    def test_injected_failure_restores_exact_files_modes_and_fifo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory)
            start = root / "usr/local/bin/a-clockwork-plex-airplay-start"
            end = root / "usr/local/bin/a-clockwork-plex-airplay-end"
            retired = root / "usr/local/bin/a-clockwork-plex-airplay-session-end"
            policy = root / "etc/sudoers.d/a-clockwork-plex-airplay"
            unit = root / "etc/systemd/system/a-clockwork-plex-airplay-metadata.service"
            originals = {
                start: (b"old start\n", 0o700),
                end: (b"old end\n", 0o740),
                retired: (b"old retired\n", 0o755),
                policy: (b"old sudoers\n", 0o440),
                unit: (b"old metadata unit\n", 0o600),
                config: (config.read_bytes(), 0o640),
            }
            for path, (content, permissions) in originals.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                path.chmod(permissions)
            fifo = root / "tmp/shairport-sync-metadata"
            os.mkfifo(fifo, 0o620)

            result = self.run_installer(
                root,
                validator,
                "--activate",
                "--confirm",
                "INSTALL-AIRPLAY-INTEGRATION",
                extra_env={"ACP_AIRPLAY_TEST_FAIL_AFTER_INSTALL": "1"},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Captured AirPlay integration pre-state restored", result.stderr)
            for path, (content, permissions) in originals.items():
                self.assertEqual(path.read_bytes(), content, path)
                self.assertEqual(mode(path), permissions, path)
            self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
            self.assertEqual(mode(fifo), 0o620)

    def test_injected_failure_restores_absent_fifo_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory)
            before = config.read_bytes()

            result = self.run_installer(
                root,
                validator,
                "--activate",
                "--confirm",
                "INSTALL-AIRPLAY-INTEGRATION",
                extra_env={"ACP_AIRPLAY_TEST_FAIL_AFTER_INSTALL": "1"},
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((root / "tmp/shairport-sync-metadata").exists())
            self.assertFalse((root / "usr/local/bin/a-clockwork-plex-airplay-start").exists())
            self.assertFalse((root / "usr/local/bin/a-clockwork-plex-airplay-end").exists())
            self.assertFalse((root / "etc/systemd/system/a-clockwork-plex-airplay-metadata.service").exists())

    def test_non_fifo_metadata_path_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory)
            metadata_path = root / "tmp/shairport-sync-metadata"
            metadata_path.write_text("not a fifo\n", encoding="utf-8")
            before = config.read_bytes()

            result = self.run_installer(root, validator, "--prepare-only")

            self.assertEqual(result.returncode, 1)
            self.assertIn("must be absent or a FIFO", result.stderr)
            self.assertEqual(config.read_bytes(), before)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), "not a fifo\n")

    def test_failed_candidate_validation_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.make_root(directory)
            validator = self.make_validator(directory, good=False)
            before = config.read_bytes()

            result = self.run_installer(root, validator, "--prepare-only")

            self.assertEqual(result.returncode, 1)
            self.assertIn("Shairport candidate validation failed", result.stderr)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((root / "tmp/shairport-sync-metadata").exists())

    def test_test_validator_override_is_non_production_only(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("if ! acp_is_production_root &&", source)
        self.assertIn("ACP_AIRPLAY_TEST_SHAIRPORT_BINARY", source)
        self.assertIn("VALIDATOR_BINARY=/usr/bin/shairport-sync", source)
        self.assertIn("ACP_AIRPLAY_TEST_FAIL_AFTER_INSTALL", source)
        self.assertIn('[[ "$ROOT" != / &&', source)


if __name__ == "__main__":
    unittest.main()
