from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"
CONFIRMATION = "APPLY-A-CLOCKWORK-PLEX"


class RootInstallerApplyGateTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        installer = root / "install.sh"
        installer.write_text(INSTALLER.read_text(encoding="utf-8"), encoding="utf-8")

        required = (
            "scripts/install-dashboard-integration.sh",
            "scripts/install-weather-config.sh",
            "scripts/install-appliance-packages.sh",
            "scripts/install-appliance-application.sh",
            "scripts/install-appliance-helpers.sh",
            "scripts/install-airplay-integration.sh",
            "scripts/install-platform-hardware.sh",
            "scripts/install-plexamp-runtime.sh",
            "scripts/install-nfc-listener.sh",
            "scripts/check-appliance-components.sh",
            "scripts/check-appliance-packages.sh",
            "scripts/preflight-appliance.sh",
            "scripts/verify-appliance.sh",
            "scripts/audio/install-direct.sh",
            "scripts/audio/install-eq.sh",
            "scripts/audio/uninstall-eq.sh",
            "scripts/audio/verify-audio.sh",
            "installer/lib/components.sh",
            "installer/lib/packages.sh",
            "installer/lib/prerequisites.sh",
            "installer/lib/platform_hardware.sh",
            "installer/lib/plexamp_runtime.sh",
            "installer/lib/direct_audio.sh",
            "installer/lib/transaction.sh",
            "installer/lib/application_transaction.sh",
            "installer/profiles/direct/alarm-safe.conf",
            "vendor/plexamp-nfc-listener/SOURCE.md",
        )
        for relative in required:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        (root / "installer/lib/components.sh").write_text(
            "acp_verify_component_sources() { return 0; }\n"
            "acp_component_plan() { echo COMPONENT_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "installer/lib/packages.sh").write_text(
            "acp_package_plan() { echo PACKAGE_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "installer/lib/prerequisites.sh").write_text(
            "acp_prerequisite_plan() { echo PREREQUISITE_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "installer/lib/platform_hardware.sh").write_text(
            "acp_platform_hardware_plan() { echo HARDWARE_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "installer/lib/plexamp_runtime.sh").write_text(
            "acp_plexamp_runtime_plan() { echo PLEXAMP_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "installer/lib/direct_audio.sh").write_text(
            "acp_verify_direct_audio_sources() { return 0; }\n"
            "acp_direct_audio_plan() { echo DIRECT_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "scripts/check-appliance-packages.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PACKAGE_GATE\n"
            "printf '01-package-gate %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n",
            encoding="utf-8",
        )
        (root / "scripts/preflight-appliance.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PREFLIGHT_GATE\n"
            "if [[ \" $* \" == *\" --fresh-bootstrap-pending \"* ]]; then\n"
            "  printf '02-fresh-stage-zero %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "elif [[ \" $* \" == *\" --bootstrap-pending \"* ]]; then\n"
            "  printf '02-platform-preflight %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "elif [[ \" $* \" == *\" --player-pending \"* ]]; then\n"
            "  printf '05-player-pending %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "elif grep -q '^07-nfc ' \"$ACP_TEST_GATE_LOG\" 2>/dev/null; then\n"
            "  printf '08-full-preflight %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "else\n"
            "  printf '04-full-preflight %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "fi\n",
            encoding="utf-8",
        )
        (root / "scripts/install-appliance-packages.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PACKAGE_BOOTSTRAP\n"
            "printf '03-package-bootstrap %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n",
            encoding="utf-8",
        )
        (root / "scripts/install-platform-hardware.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PLATFORM_HARDWARE\n"
            "printf '04-hardware %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "exit \"${ACP_TEST_HARDWARE_EXIT:-0}\"\n",
            encoding="utf-8",
        )
        (root / "scripts/install-plexamp-runtime.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PLEXAMP_RUNTIME\n"
            "printf '06-plexamp %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "exit \"${ACP_TEST_PLEXAMP_EXIT:-0}\"\n",
            encoding="utf-8",
        )
        (root / "scripts/install-nfc-listener.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo NFC_LISTENER\n"
            "printf '07-nfc %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n",
            encoding="utf-8",
        )
        (root / "scripts/install-appliance-application.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo APPLIANCE_VERIFY=PASS\n"
            "echo APPLICATION_TRANSACTION=COMMITTED\n"
            "if grep -q '^08-full-preflight ' \"$ACP_TEST_GATE_LOG\" 2>/dev/null; then\n"
            "  printf '09-application %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "else\n"
            "  printf '05-application %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n"
            "fi\n",
            encoding="utf-8",
        )
        return installer

    def run_fixture(
        self,
        installer: Path,
        *arguments: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        gate_log = installer.parent / "gate.log"
        env = os.environ.copy()
        env["ACP_TEST_GATE_LOG"] = str(gate_log)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(installer), *arguments],
            cwd=installer.parent,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_default_plan_remains_read_only_and_does_not_run_apply_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(installer, "--audio", "direct")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode:                 read-only plan", result.stdout)
            self.assertIn("Fresh bootstrap:      false", result.stdout)
            self.assertIn("No production file, package, service, route, mixer, PCM or configuration was changed", result.stdout)
            self.assertNotIn("PACKAGE_GATE", result.stdout)
            self.assertNotIn("PREFLIGHT_GATE", result.stdout)
            self.assertNotIn("PACKAGE_BOOTSTRAP", result.stdout)
            self.assertFalse((installer.parent / "gate.log").exists())

    def test_fresh_plan_is_read_only_and_exposes_staged_blocking_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(installer, "--fresh-bootstrap", "--audio", "direct")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Fresh bootstrap:      true", result.stdout)
            self.assertIn("HARDWARE_PLAN", result.stdout)
            self.assertIn("PLEXAMP_PLAN", result.stdout)
            self.assertIn("--fresh-bootstrap-pending", result.stdout)
            self.assertIn("--player-pending", result.stdout)
            self.assertIn("Hardware/player exit 78", result.stdout)
            self.assertFalse((installer.parent / "gate.log").exists())

    def test_apply_requires_exact_confirmation_before_any_gate(self) -> None:
        for arguments in (
            ("--audio", "direct", "--apply"),
            ("--audio", "direct", "--apply", "--confirm", "WRONG"),
        ):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                installer = self.make_fixture(Path(directory))
                result = self.run_fixture(installer, *arguments)

                self.assertEqual(result.returncode, 2)
                self.assertIn(CONFIRMATION, result.stderr)
                self.assertNotIn("PACKAGE_GATE", result.stdout)
                self.assertNotIn("PREFLIGHT_GATE", result.stdout)
                self.assertFalse((installer.parent / "gate.log").exists())

    def test_confirmed_compatibility_apply_preserves_original_gate_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(
                installer,
                "--audio",
                "direct",
                "--apply",
                "--confirm",
                CONFIRMATION,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PACKAGE_GATE", result.stdout)
            self.assertGreaterEqual(result.stdout.count("PREFLIGHT_GATE"), 2)
            self.assertIn("PACKAGE_BOOTSTRAP", result.stdout)
            self.assertNotIn("PLATFORM_HARDWARE", result.stdout)
            self.assertNotIn("PLEXAMP_RUNTIME", result.stdout)
            self.assertNotIn("NFC_LISTENER", result.stdout)
            self.assertIn("APPLICATION_TRANSACTION=COMMITTED", result.stdout)
            self.assertIn("ROOT_INSTALL=COMMITTED", result.stdout)
            self.assertIn("INSTALL_ROUTE=compatibility", result.stdout)
            self.assertIn("APPLICATION_VERIFY=PASS", result.stdout)

            lines = (installer.parent / "gate.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 5)
            self.assertTrue(lines[0].startswith("01-package-gate "), lines)
            self.assertTrue(lines[1].startswith("02-platform-preflight "), lines)
            self.assertTrue(lines[2].startswith("03-package-bootstrap "), lines)
            self.assertTrue(lines[3].startswith("04-full-preflight "), lines)
            self.assertTrue(lines[4].startswith("05-application "), lines)
            self.assertIn("--audio direct --weather-observations ecowitt-push", lines[0])
            self.assertIn("--bootstrap-pending", lines[1])
            self.assertNotIn("--bootstrap-pending", lines[3])
            self.assertIn("--activate --confirm INSTALL-APPLIANCE-PACKAGES", lines[2])
            self.assertIn("--activate --confirm INSTALL-APPLIANCE-APPLICATION", lines[4])
            self.assertIn(f"--project-dir {installer.parent}", lines[4])

    def test_confirmed_fresh_apply_runs_all_staged_owners_before_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(
                installer,
                "--fresh-bootstrap",
                "--audio",
                "direct",
                "--apply",
                "--confirm",
                CONFIRMATION,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ROOT_INSTALL=COMMITTED", result.stdout)
            self.assertIn("INSTALL_ROUTE=fresh-bootstrap", result.stdout)
            lines = (installer.parent / "gate.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 9)
            expected = (
                "01-package-gate ",
                "02-fresh-stage-zero ",
                "03-package-bootstrap ",
                "04-hardware ",
                "05-player-pending ",
                "06-plexamp ",
                "07-nfc ",
                "08-full-preflight ",
                "09-application ",
            )
            for line, prefix in zip(lines, expected, strict=True):
                self.assertTrue(line.startswith(prefix), lines)
            self.assertIn("--fresh-bootstrap-pending", lines[1])
            self.assertIn("--player-pending", lines[4])
            self.assertIn("--confirm INSTALL-PLATFORM-HARDWARE", lines[3])
            self.assertIn("--confirm INSTALL-PLEXAMP-RUNTIME", lines[5])
            self.assertIn("--confirm INSTALL-NFC-LISTENER", lines[6])

    def test_fresh_hardware_reboot_checkpoint_stops_player_nfc_and_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(
                installer,
                "--fresh-bootstrap",
                "--audio",
                "direct",
                "--apply",
                "--confirm",
                CONFIRMATION,
                extra_env={"ACP_TEST_HARDWARE_EXIT": "75"},
            )

            self.assertEqual(result.returncode, 75, result.stderr)
            self.assertIn("ROOT_INSTALL=REBOOT-REQUIRED", result.stdout)
            self.assertIn("REBOOT_POLICY=OPERATOR-CONTROLLED", result.stdout)
            self.assertIn("RESUME_COMMAND=", result.stdout)
            self.assertIn("--fresh-bootstrap", result.stdout)
            lines = (installer.parent / "gate.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 4)
            self.assertTrue(lines[-1].startswith("04-hardware "), lines)
            self.assertFalse(any("player-pending" in line for line in lines))
            self.assertFalse(any("plexamp" in line for line in lines))
            self.assertFalse(any("nfc" in line for line in lines))
            self.assertFalse(any("application" in line for line in lines))

    def test_fresh_plexamp_blocker_propagates_without_starting_nfc_or_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(
                installer,
                "--fresh-bootstrap",
                "--audio",
                "direct",
                "--apply",
                "--confirm",
                CONFIRMATION,
                extra_env={"ACP_TEST_PLEXAMP_EXIT": "78"},
            )

            self.assertEqual(result.returncode, 78, result.stderr)
            self.assertIn("ROOT_INSTALL=BLOCKED-BEFORE-NFC", result.stdout)
            self.assertIn("PLEXAMP_RUNTIME_EXIT=78", result.stdout)
            lines = (installer.parent / "gate.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 6)
            self.assertTrue(lines[-1].startswith("06-plexamp "), lines)
            self.assertFalse(any(line.startswith("07-nfc ") for line in lines))
            self.assertFalse(any("application" in line for line in lines))

    def test_weather_underground_apply_forwards_secret_file_path_not_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            secret = installer.parent / "wu-key"
            secret_value = "super-secret-test-key-value"
            secret.write_text(secret_value + "\n", encoding="utf-8")
            secret.chmod(0o600)

            result = self.run_fixture(
                installer,
                "--audio",
                "direct",
                "--weather-observations",
                "weather-underground",
                "--wu-station-id",
                "ITEST1",
                "--wu-api-key-file",
                str(secret),
                "--apply",
                "--confirm",
                CONFIRMATION,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = (installer.parent / "gate.log").read_text(encoding="utf-8").splitlines()
            log = "\n".join(lines)
            self.assertIn(f"--weather-api-key-file {secret}", lines[1])
            self.assertIn(f"--weather-api-key-file {secret}", lines[3])
            self.assertIn(f"--wu-api-key-file {secret}", lines[4])
            self.assertIn("--wu-station-id ITEST1", lines[4])
            self.assertNotIn(secret_value, log)
            self.assertNotIn(secret_value, result.stdout)
            self.assertNotIn(secret_value, result.stderr)

    def test_weather_underground_apply_requires_station_and_secret_file_before_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(
                installer,
                "--audio",
                "direct",
                "--weather-observations",
                "weather-underground",
                "--apply",
                "--confirm",
                CONFIRMATION,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("--wu-station-id", result.stderr)
            self.assertFalse((installer.parent / "gate.log").exists())

    def test_confirm_is_rejected_without_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(installer, "--audio", "direct", "--confirm", CONFIRMATION)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--confirm is only valid with --apply", result.stderr)
            self.assertFalse((installer.parent / "gate.log").exists())

    def test_eq_apply_requires_camilladsp_binary_before_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = self.make_fixture(Path(directory))
            result = self.run_fixture(installer, "--apply", "--confirm", CONFIRMATION)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--camilladsp-binary PATH", result.stderr)
            self.assertFalse((installer.parent / "gate.log").exists())

    def test_help_and_source_keep_delegated_transaction_boundary_explicit(self) -> None:
        result = subprocess.run(
            ["bash", str(INSTALLER), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"--apply --confirm {CONFIRMATION}", result.stdout)
        self.assertIn("--fresh-bootstrap", result.stdout)
        self.assertIn("application transaction", result.stdout)
        self.assertIn("final appliance verifier inside its commit boundary", INSTALLER.read_text(encoding="utf-8"))

        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('bash "$REPO_ROOT/scripts/install-appliance-packages.sh"', source)
        self.assertIn('bash "$REPO_ROOT/scripts/install-platform-hardware.sh"', source)
        self.assertIn('bash "$REPO_ROOT/scripts/install-plexamp-runtime.sh"', source)
        self.assertIn('bash "$REPO_ROOT/scripts/install-nfc-listener.sh"', source)
        self.assertIn('bash "$REPO_ROOT/scripts/install-appliance-application.sh"', source)
        self.assertIn('--weather-api-key-file "$WU_API_KEY_FILE"', source)
        self.assertIn("--bootstrap-pending", source)
        self.assertIn("--fresh-bootstrap-pending", source)
        self.assertIn("--player-pending", source)
        self.assertIn("ROOT_INSTALL=REBOOT-REQUIRED", source)
        self.assertNotIn("MUTATION_BLOCKED", source)
        self.assertNotIn("acp_application_transaction_begin", source)
        self.assertNotIn("install-shared-audio.sh\" --activate", source)
        self.assertNotIn("install-master-eq.sh", source)


if __name__ == "__main__":
    unittest.main()
