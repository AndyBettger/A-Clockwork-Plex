from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-platform-hardware.sh"
LIBRARY = ROOT / "installer" / "lib" / "platform_hardware.sh"
PACKAGES = ROOT / "installer" / "lib" / "packages.sh"


class PlatformHardwareInstallerTests(unittest.TestCase):
    def run_script(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_shell_syntax_and_prepare_only_are_safe(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        result = self.run_script("--project-user", "clockuser")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fresh-Pi hardware commissioning", result.stdout)
        self.assertIn("Prepare-only complete", result.stdout)
        self.assertIn("No package, boot configuration", result.stdout)

    def test_activation_requires_exact_confirmation_before_mutation(self) -> None:
        result = self.run_script(
            "--activate",
            "--confirm",
            "WRONG",
            "--project-user",
            "clockuser",
        )
        self.assertEqual(result.returncode, 64)

        source = SCRIPT.read_text(encoding="utf-8")
        confirmation = source.index('[[ "$CONFIRM" == "$ACP_PLATFORM_HARDWARE_CONFIRMATION" ]]')
        first_mutation = source.index("sudo -- raspi-config nonint do_i2c 0")
        self.assertLess(confirmation, first_mutation)

    def test_known_nfc_contract_is_exact(self) -> None:
        library = LIBRARY.read_text(encoding="utf-8")
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ACP_PN532_I2C_BUS=1", library)
        self.assertIn("ACP_PN532_I2C_ADDRESS=0x24", library)
        self.assertIn("ACP_DAC_CARD_ID=Pro", library)
        self.assertIn("sudo -- i2cdetect -y", source)
        self.assertIn("PN532_I2C=PASS", source)
        for group in ("i2c", "gpio", "spi"):
            self.assertIn(group, library)

    def test_immediate_pn532_probe_is_privileged_read_only_after_group_change(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        group_change = source.index('sudo -- "$USERMOD_BIN" -aG')
        probe = source.index("sudo -- i2cdetect -y")
        self.assertLess(group_change, probe)
        self.assertIn("Group changes made above do not affect the already-running login shell", source)
        self.assertNotIn("sudo -- i2cset", source)
        self.assertNotIn("sudo -- i2ctransfer", source)

    def test_dac_overlay_is_deliberately_not_guessed(self) -> None:
        library = LIBRARY.read_text(encoding="utf-8")
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("exact boot-overlay identity has not", library)
        self.assertIn("DAC-COMMISSIONING-REQUIRED", source)
        self.assertIn("DAC_POLICY=NO-GUESSED-OVERLAY", source)
        self.assertNotIn("dtoverlay=", library + source)

    def test_i2c_reboot_is_explicit_and_never_automatic(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("PLATFORM_HARDWARE=REBOOT-REQUIRED", source)
        self.assertIn("RESUME_COMMAND=", source)
        self.assertIn("exit 75", source)
        self.assertNotIn("sudo -- reboot", source)
        self.assertNotIn("shutdown -r", source)

    def test_global_os_and_firmware_upgrades_have_no_execution_path(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        for forbidden in (
            "sudo -- apt upgrade",
            "sudo -- apt-get upgrade",
            "sudo -- rpi-update",
            "sudo -- fwupdmgr",
        ):
            self.assertNotIn(forbidden, source)

    def test_package_owner_contains_hardware_support_packages(self) -> None:
        source = PACKAGES.read_text(encoding="utf-8")
        for package in ("i2c-tools", "python3-lgpio", "raspi-config"):
            self.assertRegex(source, rf"(?m)^\s*{package}\s*$")


if __name__ == "__main__":
    unittest.main()
