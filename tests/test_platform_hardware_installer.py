from __future__ import annotations

import subprocess
import tempfile
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

    def render_dac_config(self, source: Path, destination: Path, mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; acp_render_dac_pro_config "$2" "$3" "$4"',
                "bash",
                str(LIBRARY),
                str(source),
                str(destination),
                mode,
            ],
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
        self.assertIn("accepted DAC result", result.stdout)
        self.assertIn("RPi DAC Pro", result.stdout)
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

    def test_known_nfc_and_dac_contracts_are_exact(self) -> None:
        library = LIBRARY.read_text(encoding="utf-8")
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ACP_PN532_I2C_BUS=1", library)
        self.assertIn("ACP_PN532_I2C_ADDRESS=0x24", library)
        self.assertIn("ACP_DAC_CARD_ID=Pro", library)
        self.assertIn("ACP_DAC_OVERLAY=rpi-dacpro", library)
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

    def test_explicit_dac_renderer_preserves_unrelated_config_and_is_marker_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "config.txt"
            destination = root / "candidate.txt"
            source.write_text(
                "# keep me\n"
                "dtparam=i2c_arm=on\n"
                "# BEGIN A CLOCKWORK PLEX DAC PRO\n"
                "dtoverlay=wrong-old-value\n"
                "# END A CLOCKWORK PLEX DAC PRO\n"
                "dtoverlay=vc4-kms-v3d\n",
                encoding="utf-8",
            )
            result = self.render_dac_config(source, destination, "explicit")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = destination.read_text(encoding="utf-8")
            self.assertIn("# keep me", text)
            self.assertIn("dtparam=i2c_arm=on", text)
            self.assertIn("dtoverlay=vc4-kms-v3d", text)
            self.assertNotIn("wrong-old-value", text)
            self.assertEqual(text.count("# BEGIN A CLOCKWORK PLEX DAC PRO"), 1)
            self.assertEqual(text.count("# END A CLOCKWORK PLEX DAC PRO"), 1)
            self.assertEqual(text.count("dtoverlay=rpi-dacpro"), 1)
            self.assertNotIn("\ndtoverlay=\n", text)

    def test_iqaudio_renderer_uses_documented_hat_suppression_then_dac_pro_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "config.txt"
            destination = root / "candidate.txt"
            source.write_text("dtparam=audio=on\n", encoding="utf-8")
            result = self.render_dac_config(source, destination, "iqaudio")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = destination.read_text(encoding="utf-8")
            self.assertIn("dtparam=audio=on", text)
            self.assertIn("\ndtoverlay=\ndtoverlay=rpi-dacpro\n", text)

    def test_dac_owner_prefers_eeprom_success_and_fails_closed_for_wrong_hat(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        library = LIBRARY.read_text(encoding="utf-8")

        card_pass = source.index("DAC_PRO=PASS")
        boot_config_lookup = source.index("BOOT_CONFIG=")
        self.assertLess(card_pass, boot_config_lookup)
        self.assertIn("RASPBERRY-PI-DAC-PRO-EEPROM-DETECTED-BUT-CARD-MISSING", source)
        self.assertIn("IDENTIFIED-HAT-IS-NOT-DAC-PRO", source)
        self.assertIn("UNRECOGNISED-HAT-VENDOR", source)
        self.assertIn("*IQaudIO*", source)
        self.assertIn("DAC.*Pro", library)

    def test_dac_config_change_is_transactional_and_requires_operator_reboot(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        capture = source.index('acp_transaction_capture_path "$TRANSACTION" "$BOOT_CONFIG"')
        install = source.index('sudo -- install -m "$CURRENT_MODE" "$CANDIDATE" "$BOOT_CONFIG"')
        reboot = source.index("REBOOT_REASON=DAC-PRO-BOOT-CONFIG-INSTALLED")
        self.assertLess(capture, install)
        self.assertLess(install, reboot)
        self.assertIn("acp_transaction_restore_paths", source)
        self.assertIn("exit 75", source)
        self.assertNotIn("sudo -- reboot", source)
        self.assertNotIn("shutdown -r", source)

    def test_global_os_firmware_and_hat_eeprom_updates_have_no_execution_path(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        for forbidden in (
            "sudo -- apt upgrade",
            "sudo -- apt-get upgrade",
            "sudo -- rpi-update",
            "sudo -- fwupdmgr",
            "eepmake",
            "eepflash",
            "flashrom",
        ):
            self.assertNotIn(forbidden, source)

    def test_package_owner_contains_hardware_support_packages(self) -> None:
        source = PACKAGES.read_text(encoding="utf-8")
        for package in ("i2c-tools", "python3-lgpio", "raspi-config"):
            self.assertRegex(source, rf"(?m)^\s*{package}\s*$")


if __name__ == "__main__":
    unittest.main()
