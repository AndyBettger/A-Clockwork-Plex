from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "fresh-appliance-acceptance-runbook.md"


class FreshApplianceAcceptanceRunbookTests(unittest.TestCase):
    def test_runbook_hard_guards_the_accepted_bedroom_pi(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn('if [ "$(hostname -s)" = "plexamp-bedroom" ]', text)
        self.assertIn("STOP: this is the accepted bedroom appliance", text)
        self.assertIn("Stop on the first failed gate", text)

    def test_runbook_pins_accepted_direct_eq_and_camilla_identities(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn(
            "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9",
            text,
        )
        self.assertIn(
            "1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9",
            text,
        )
        self.assertIn(
            "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa",
            text,
        )
        self.assertIn("APPLY-A-CLOCKWORK-PLEX", text)
        self.assertIn("Install required", text)

    def test_runbook_preserves_fresh_bootstrap_order_and_reboot_evidence(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("--bootstrap-pending", text)
        self.assertIn("APPLIANCE_PREFLIGHT=PLATFORM-PASS", text)
        self.assertIn("PACKAGE_VENV_BASELINE=RETAINED", text)
        self.assertIn("$HOME/.acp-phase7-evidence-path", text)
        self.assertIn('EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"', text)

    def test_wu_acceptance_uses_key_file_and_diagnostic_history_only(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("inspect-weather-underground-payloads.py", text)
        self.assertIn("--api-key-file \"$WU_KEY_FILE\"", text)
        self.assertIn("--wu-api-key-file \"$WU_KEY_FILE\"", text)
        self.assertIn("--weather-api-key-file \"$WU_KEY_FILE\"", text)
        self.assertIn("WU_PAYLOAD_INSPECTION=PASS", text)
        self.assertIn("YES — REVIEW REQUIRED", text)
        self.assertIn("Neither result authorises history ingestion", text)
        self.assertNotIn('cat "$WU_KEY_FILE"', text)
        self.assertNotIn('echo "$WU_KEY_FILE"', text)

    def test_repeat_install_and_result_evidence_are_required(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("# 13. Repeat whole-appliance installation", text)
        self.assertIn("60-repeat-install.txt", text)
        self.assertIn("61-repeat-verifier.txt", text)
        self.assertIn("Final physical result document is committed", text)
        self.assertIn("PR #2 remains Draft/open/unmerged", text)


if __name__ == "__main__":
    unittest.main()
