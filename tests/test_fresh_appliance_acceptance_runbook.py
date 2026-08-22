from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "development" / "testing" / "fresh-appliance-acceptance-runbook.md"


def fenced_code(text: str) -> str:
    """Return fenced code only so explanatory prose may name forbidden options."""
    return "\n".join(text.split("```")[1::2])


class FreshApplianceAcceptanceRunbookTests(unittest.TestCase):
    def test_runbook_protects_production_with_spare_sd_boundary(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("accepted production SD card", text)
        self.assertIn("Label/store that card safely", text)
        self.assertIn("Do not reformat it for this test", text)
        self.assertIn("spare SD card", text)
        self.assertIn("Stop on the first unexplained failure", text)
        self.assertIn("test hostname", text)
        self.assertNotIn('if [ "$(hostname -s)" = "plexamp-bedroom" ]', text)

    def test_runbook_pins_direct_eq_player_node_camilla_and_hardware_identities(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        for identity in (
            "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9",
            "1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9",
            "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa",
            "d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a",
            "86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041",
            "73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71",
            "rpi-dacpro",
            "0x24",
            "APPLY-A-CLOCKWORK-PLEX",
        ):
            self.assertIn(identity, text)

    def test_runbook_uses_public_setup_and_unambiguous_guarded_engine(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("bash setup.sh", text)
        self.assertIn("appliance-installer.sh", text)
        self.assertIn("no root `install.sh`", text)
        self.assertNotIn("bash install.sh", text)
        self.assertIn("--fresh-bootstrap", text)
        self.assertIn("fresh stage-zero preflight", text)
        self.assertIn("exit `75` reboot-required contract", text)
        self.assertIn("ROOT_INSTALL=REBOOT-REQUIRED", text)

    def test_runbook_requires_integrated_camilla_and_claim_handoff(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("integrated CamillaDSP acquisition", text)
        self.assertIn("integrated Plexamp claim launch/resume", text)
        self.assertIn("automatically launches the installed Plexamp Headless process", text)
        self.assertIn("PLEXAMP_RUNTIME=CLAIM-REQUIRED", text)
        self.assertIn("https://plex.tv/claim", text)
        self.assertIn("must **not** have to run `scripts/fetch-camilladsp-4.1.3.sh`", text)
        self.assertIn("must **not** have to run:", text)
        self.assertIn("/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node js/index.js", text)
        self.assertNotIn("--camilladsp-binary \"$CAMILLA\"", text)

    def test_runbook_requires_plexamp_gui_output_commissioning(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("A Clockwork Plex - Plexamp", text)
        self.assertIn("Follows system output", text)
        self.assertIn("password-manager", text)

    def test_wu_acceptance_is_settings_based_and_never_puts_secret_on_cli(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        commands = fenced_code(text)
        self.assertIn("# 6. Commission Weather Underground through Settings", text)
        self.assertIn("Set API key", text)
        self.assertIn("Replace API key", text)
        self.assertIn("Test connection", text)
        self.assertIn("WU_CONFIG_SECRET_FIELDS=NONE", text)
        self.assertIn("/etc/default/a-clockwork-plex-weather", text)
        self.assertNotIn("--wu-api-key-file", commands)
        self.assertNotIn("--weather-api-key-file", commands)

    def test_runbook_requires_functional_alarm_and_selected_v3_presentation(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("selected Version 3 fourteen-segment geometry", text)
        self.assertIn("final accepted daytime theme", text)
        self.assertIn("Classic/Astronomy night behavior", text)
        self.assertIn("Snooze", text)
        self.assertIn("fresh fade cycle", text)
        self.assertIn("Music Master must not silence the alarm lane", text)

    def test_runbook_requires_bootstrap_application_and_audio_verifiers(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("scripts/verify-fresh-bootstrap.sh", text)
        self.assertIn("FRESH_BOOTSTRAP_VERIFY=PASS", text)
        self.assertIn("scripts/verify-appliance.sh", text)
        self.assertIn("APPLIANCE_VERIFY=PASS", text)
        self.assertIn("scripts/audio/verify-audio.sh", text)
        self.assertIn("a-clockwork-plex-camilladsp.service", text)

    def test_repeat_setup_and_clean_checkout_are_release_gates(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        repeat = text.index("# 9. Repeat the public setup command")
        clean = text.index("# 10. Confirm normal operation leaves the checkout clean")
        self.assertLess(repeat, clean)
        self.assertIn("no renewed Plexamp claim requirement", text)
        self.assertIn("no unnecessary reboot checkpoint", text)
        self.assertIn("git status --porcelain", text)
        self.assertIn("Phase 7 does not close until that physical result is committed", text)
        self.assertIn("PR #2 remains Draft/open/unmerged", text)


if __name__ == "__main__":
    unittest.main()
