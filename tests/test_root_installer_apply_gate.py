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
            "scripts/install-dashboard-service.sh",
            "scripts/install-dashboard-kiosk.sh",
            "scripts/install-airplay-hooks.sh",
            "scripts/install-airplay-metadata-listener.sh",
            "scripts/install-alarm-audio-helper.sh",
            "scripts/install-shairport-name-helper.sh",
            "scripts/install-appliance-helpers.sh",
            "scripts/install-airplay-integration.sh",
            "scripts/check-appliance-components.sh",
            "scripts/check-appliance-packages.sh",
            "scripts/preflight-appliance.sh",
            "scripts/verify-appliance.sh",
            "scripts/audio/install-direct.sh",
            "scripts/audio/install-eq.sh",
            "scripts/audio/verify-audio.sh",
            "installer/lib/components.sh",
            "installer/lib/packages.sh",
            "installer/lib/prerequisites.sh",
            "installer/lib/direct_audio.sh",
            "installer/lib/transaction.sh",
            "installer/profiles/direct/alarm-safe.conf",
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
        (root / "installer/lib/direct_audio.sh").write_text(
            "acp_verify_direct_audio_sources() { return 0; }\n"
            "acp_direct_audio_plan() { echo DIRECT_PLAN; }\n",
            encoding="utf-8",
        )
        (root / "installer/lib/transaction.sh").write_text(
            "acp_transaction_begin() { :; }\n"
            "acp_transaction_restore_paths() { :; }\n",
            encoding="utf-8",
        )
        (root / "scripts/check-appliance-packages.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PACKAGE_GATE\n"
            "printf 'package %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n",
            encoding="utf-8",
        )
        (root / "scripts/preflight-appliance.sh").write_text(
            "#!/usr/bin/env bash\n"
            "echo PREFLIGHT_GATE\n"
            "printf 'preflight %s\\n' \"$*\" >>\"$ACP_TEST_GATE_LOG\"\n",
            encoding="utf-8",
        )
        return installer

    def run_fixture(self, installer: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        gate_log = installer.parent / "gate.log"
        env = os.environ.copy()
        env["ACP_TEST_GATE_LOG"] = str(gate_log)
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
            self.assertIn("No production file, package, service, route, mixer, PCM or configuration was changed", result.stdout)
            self.assertNotIn("PACKAGE_GATE", result.stdout)
            self.assertNotIn("PREFLIGHT_GATE", result.stdout)
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

    def test_confirmed_apply_runs_read_only_gates_then_fails_closed(self) -> None:
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

            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("PACKAGE_GATE", result.stdout)
            self.assertIn("PREFLIGHT_GATE", result.stdout)
            self.assertIn("Outer transaction boundary: READY, NOT STARTED", result.stdout)
            self.assertIn("MUTATION_BLOCKED=PACKAGE-WEATHER-DASHBOARD-STAGES-INCOMPLETE", result.stdout)
            log = (installer.parent / "gate.log").read_text(encoding="utf-8")
            self.assertIn("package --audio direct --weather-observations ecowitt-push", log)
            self.assertIn("preflight --audio direct --weather-observations ecowitt-push", log)

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

    def test_help_and_source_keep_mutation_boundary_explicit(self) -> None:
        result = subprocess.run(
            ["bash", str(INSTALLER), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"--apply --confirm {CONFIRMATION}", result.stdout)
        self.assertIn("fail closed before any production mutation", result.stdout)

        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('declare -F acp_transaction_begin', source)
        self.assertNotIn('acp_transaction_begin "', source)
        self.assertNotIn('install-direct.sh" --activate', source)
        self.assertNotIn('install-eq.sh" --activate', source)
        self.assertNotIn('install-appliance-helpers.sh" --activate', source)
        self.assertNotIn('install-airplay-integration.sh" --activate', source)


if __name__ == "__main__":
    unittest.main()
