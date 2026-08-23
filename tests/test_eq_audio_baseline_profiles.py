from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "audio" / "install-eq.sh"
UNINSTALL = ROOT / "scripts" / "audio" / "uninstall-eq.sh"
CAMILLA_HASH = "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa"
PHASE6_DIRECT_HASH = "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"
ALARM_SAFE_DIRECT_HASH = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"


class EqAudioBaselineProfileTests(unittest.TestCase):
    def make_fixture(self, directory: str, direct_hash: str):
        base = Path(directory)
        root = base / "rootfs"
        active = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        active.parent.mkdir(parents=True)
        active.write_text("fixture-direct-route\n", encoding="utf-8")

        binary = base / "camilladsp"
        binary.write_text(
            "#!/bin/bash\n"
            "if [[ \"${1:-}\" == '--version' ]]; then\n"
            "  printf 'CamillaDSP 4.1.3\\n'\n"
            "fi\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)

        tools = base / "tools"
        tools.mkdir()
        sha = tools / "sha256sum"
        sha.write_text(
            "#!/bin/bash\n"
            "case \"${1:-}\" in\n"
            f"  {binary}|*camilladsp-4.1.3/camilladsp) printf '{CAMILLA_HASH}  %s\\n' \"$1\" ;;\n"
            "  *99-a-clockwork-plex-shared.conf|*pre-eq-active-route.conf) "
            f"printf '{direct_hash}  %s\\n' \"$1\" ;;\n"
            "  *) /usr/bin/sha256sum \"$@\" ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        sha.chmod(0o755)

        env = {**os.environ, "PATH": f"{tools}:/usr/local/bin:/usr/bin:/bin"}
        return root, active, binary, env

    def run_command(self, command: list[str], env: dict[str, str]):
        return subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def install_command(
        self,
        root: Path,
        binary: Path,
        *,
        baseline: str | None = None,
        activate: bool = False,
    ) -> list[str]:
        command = [
            "/bin/bash",
            str(INSTALL),
        ]
        if activate:
            command.extend(["--activate", "--confirm", "INSTALL-EQ-AUDIO"])
        command.extend(
            [
                "--binary",
                str(binary),
                "--project-user",
                "testuser",
                "--root",
                str(root),
            ]
        )
        if baseline is not None:
            command.extend(["--baseline", baseline])
        return command

    def test_default_plan_preserves_phase6_direct_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, binary, env = self.make_fixture(directory, PHASE6_DIRECT_HASH)
            result = self.run_command(self.install_command(root, binary), env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Direct baseline:  phase6-direct", result.stdout)
            self.assertIn(f"Baseline SHA-256: {PHASE6_DIRECT_HASH}", result.stdout)

    def test_alarm_safe_plan_is_explicit_and_uses_alarm_safe_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, binary, env = self.make_fixture(directory, ALARM_SAFE_DIRECT_HASH)
            result = self.run_command(
                self.install_command(root, binary, baseline="alarm-safe-direct"),
                env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Direct baseline:  alarm-safe-direct", result.stdout)
            self.assertIn(f"Baseline SHA-256: {ALARM_SAFE_DIRECT_HASH}", result.stdout)

    def test_alarm_safe_first_install_and_uninstall_restore_exact_captured_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, active, binary, env = self.make_fixture(directory, ALARM_SAFE_DIRECT_HASH)
            original = active.read_bytes()

            install = self.run_command(
                self.install_command(
                    root,
                    binary,
                    baseline="alarm-safe-direct",
                    activate=True,
                ),
                env,
            )
            self.assertEqual(install.returncode, 0, install.stderr)

            backup = root / "var/lib/a-clockwork-plex/split-bus/pre-eq-backup"
            self.assertEqual(
                (backup / "pre-eq-active-route.sha256").read_text(encoding="utf-8").strip(),
                ALARM_SAFE_DIRECT_HASH,
            )
            self.assertEqual((backup / "pre-eq-active-route.conf").read_bytes(), original)

            uninstall = self.run_command(
                [
                    "/bin/bash",
                    str(UNINSTALL),
                    "--activate",
                    "--confirm",
                    "UNINSTALL-EQ-AUDIO",
                    "--root",
                    str(root),
                ],
                env,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertEqual(active.read_bytes(), original)
            self.assertFalse(backup.exists())

    def test_alarm_safe_selector_rejects_phase6_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, binary, env = self.make_fixture(directory, PHASE6_DIRECT_HASH)
            result = self.run_command(
                self.install_command(
                    root,
                    binary,
                    baseline="alarm-safe-direct",
                    activate=True,
                ),
                env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ALARM_SAFE_DIRECT_HASH, result.stderr)
            self.assertIn(PHASE6_DIRECT_HASH, result.stderr)

    def test_unknown_baseline_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, binary, env = self.make_fixture(directory, PHASE6_DIRECT_HASH)
            result = self.run_command(
                self.install_command(root, binary, baseline="mystery-direct"),
                env,
            )

            self.assertEqual(result.returncode, 64)
            self.assertIn("Unsupported direct baseline", result.stderr)


if __name__ == "__main__":
    unittest.main()
