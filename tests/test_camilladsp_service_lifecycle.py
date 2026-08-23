from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAMILLA_UNIT = (
    ROOT
    / "installer"
    / "profiles"
    / "eq-split-bus"
    / "systemd"
    / "a-clockwork-plex-camilladsp.service"
)
AUDIO_VERIFIER = ROOT / "scripts" / "audio" / "verify-audio.sh"


class CamillaDSPServiceLifecycleTests(unittest.TestCase):
    def test_camilla_unit_recovers_clean_self_exit_without_losing_failback(self) -> None:
        source = CAMILLA_UNIT.read_text(encoding="utf-8")

        self.assertIn("Restart=on-success\n", source)
        self.assertIn("RestartSec=1\n", source)
        self.assertIn(
            "OnFailure=a-clockwork-plex-audio-failback.service\n",
            source,
        )
        self.assertNotIn("Restart=no\n", source)

    def test_audio_verifier_pins_camilla_lifecycle_contract(self) -> None:
        source = AUDIO_VERIFIER.read_text(encoding="utf-8")

        self.assertIn("'Restart=on-success'", source)
        self.assertIn("'RestartSec=1'", source)
        self.assertIn(
            "'OnFailure=a-clockwork-plex-audio-failback.service'",
            source,
        )
        self.assertIn(
            "The installed CamillaDSP unit does not recover clean self-exits.",
            source,
        )
        self.assertIn(
            "The installed CamillaDSP unit has lost direct-audio failback ownership.",
            source,
        )


if __name__ == "__main__":
    unittest.main()
