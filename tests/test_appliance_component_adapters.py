from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-appliance-components.sh"
INSTALLER = ROOT / "appliance-installer.sh"
LIBRARY = ROOT / "installer" / "lib" / "components.sh"


class ApplianceComponentAdapterTests(unittest.TestCase):
    def run_checker(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(CHECKER), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_root_plan_reports_native_and_adapter_check_ownership(self) -> None:
        result = subprocess.run(
            ["bash", str(INSTALLER), "--plan"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Specialist component ownership", result.stdout)
        self.assertIn("dashboard-service", result.stdout)
        self.assertIn("native-check", result.stdout)
        self.assertIn("airplay-hooks", result.stdout)
        self.assertIn("adapter-check", result.stdout)
        self.assertIn(
            "bash scripts/check-appliance-components.sh --component airplay-hooks",
            result.stdout,
        )
        self.assertIn("Apply commands remain specialist-owned", result.stdout)
        self.assertIn("scripts/install-airplay-integration.sh", result.stdout)
        self.assertIn("No production file", result.stdout)

    def test_adapter_treats_missing_targets_as_fresh_pi_state_without_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_checker("--root", str(root))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("airplay-hooks:", result.stdout)
        self.assertIn("airplay-metadata:", result.stdout)
        self.assertIn("alarm-audio-helper:", result.stdout)
        self.assertIn("shairport-name-helper:", result.stdout)
        self.assertIn("missing", result.stdout)
        self.assertIn("scripts/install-airplay-integration.sh (shared guarded owner)", result.stdout)
        self.assertIn("COMPONENT_ADAPTER_CHECK=PASS", result.stdout)
        self.assertIn("No production file", result.stdout)

    def test_copy_owned_helpers_can_be_identified_as_current_under_alternate_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alarm_target = root / "usr/local/bin/a-clockwork-plex-alarm-audio"
            name_target = root / "usr/local/bin/a-clockwork-plex-shairport-name"
            alarm_target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "scripts/a-clockwork-plex-alarm-audio-helper.sh", alarm_target)
            shutil.copyfile(ROOT / "scripts/a-clockwork-plex-shairport-name.py", name_target)

            alarm = self.run_checker(
                "--root", str(root), "--component", "alarm-audio-helper"
            )
            name = self.run_checker(
                "--root", str(root), "--component", "shairport-name-helper"
            )

        self.assertEqual(alarm.returncode, 0, alarm.stderr)
        self.assertIn("helper target:    current", alarm.stdout)
        self.assertEqual(name.returncode, 0, name.stderr)
        self.assertIn("helper target:    current", name.stdout)

    def test_adapter_source_has_no_mutating_command_invocation(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        command = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:install|cp|mv|rm|chmod|chown|mkfifo|mkdir|"
            r"systemctl|modprobe|tee)\b"
        )
        self.assertIsNone(command.search(source))
        self.assertNotIn("> /etc/", source)
        self.assertNotIn("> /usr/local/", source)

    def test_component_library_describes_guarded_apply_without_root_execution(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")
        root_installer = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("adapter-check", source)
        self.assertIn("native-check", source)
        self.assertIn("acp_verify_component_sources", source)
        self.assertIn("acp_component_plan", source)
        self.assertIn(
            "bash scripts/install-airplay-integration.sh --activate --confirm INSTALL-AIRPLAY-INTEGRATION",
            source,
        )
        self.assertIn(
            "bash scripts/install-appliance-helpers.sh --activate --confirm INSTALL-APPLIANCE-HELPERS",
            source,
        )
        for mutating_entrypoint in (
            "install-airplay-integration.sh",
            "install-appliance-helpers.sh",
            "install-airplay-hooks.sh",
            "install-airplay-metadata-listener.sh",
            "install-alarm-audio-helper.sh",
            "install-shairport-name-helper.sh",
        ):
            invocation = re.compile(
                rf"(?m)^\s*(?:sudo\s+)?bash\s+scripts/{re.escape(mutating_entrypoint)}\b"
            )
            self.assertIsNone(invocation.search(root_installer))

    def test_unknown_adapter_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_checker(
                "--root", directory, "--component", "mystery-component"
            )

        self.assertEqual(result.returncode, 64)
        self.assertIn("Unsupported component", result.stderr)


if __name__ == "__main__":
    unittest.main()
