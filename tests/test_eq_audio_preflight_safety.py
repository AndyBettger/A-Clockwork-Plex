from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audio" / "preflight-eq.sh"
ROADMAP = ROOT / "docs" / "eq-audio-installer-roadmap.md"


class EqAudioPreflightSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SCRIPT.read_text(encoding="utf-8")

    def test_script_is_bash_and_strict(self) -> None:
        self.assertTrue(self.source.startswith("#!/usr/bin/env bash"))
        self.assertIn("set -euo pipefail", self.source)

    def test_script_rejects_mutating_command_entrypoints(self) -> None:
        mutating_commands = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:apt|apt-get|install|cp|mv|rm|chmod|chown|"
            r"mkfifo|mkdir|systemctl\s+(?:start|stop|restart|enable|disable)|"
            r"modprobe|tee)\b"
        )
        self.assertIsNone(mutating_commands.search(self.source))
        self.assertNotIn("systemctl daemon-reload", self.source)
        self.assertNotIn("/boot/firmware/config.txt", self.source)
        self.assertNotIn("/boot/config.txt", self.source)
        self.assertNotIn("rpi-update", self.source)

    def test_expected_guard_paths_are_read_only(self) -> None:
        for marker in (
            "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf",
            "/etc/systemd/system/a-clockwork-plex-camilladsp.service",
            "/etc/a-clockwork-plex/camilladsp.yml",
            "/opt/a-clockwork-plex/camilladsp/camilladsp",
        ):
            self.assertIn(marker, self.source)
        self.assertIn("test ! -e", self.source)
        self.assertIn("lsmod", self.source)
        self.assertIn("aplay -l", self.source)
        self.assertIn("i2cdetect", self.source)

    def test_production_audio_interfaces_are_observed_only(self) -> None:
        for marker in (
            "acp_plexamp_volume",
            "acp_airplay_volume",
            "acp_alarm_volume",
            "acp_master",
            "acp_dmix",
        ):
            self.assertIn(marker, self.source)
        self.assertIn("aplay -L", self.source)
        self.assertNotIn("speaker-test", self.source)
        self.assertNotIn("aplay /", self.source)

    def test_required_platform_and_service_guards_are_present(self) -> None:
        self.assertIn("Raspberry Pi OS", self.source)
        self.assertIn('[[ "$(uname -m)" == aarch64 ]]', self.source)
        self.assertIn("systemctl is-active --quiet", self.source)
        self.assertIn("systemctl is-enabled --quiet", self.source)
        self.assertIn("EQ managed path already exists", self.source)
        self.assertIn("Preflight guard path is unexpectedly present", self.source)

    def test_before_after_state_comparison_is_mandatory(self) -> None:
        for marker in (
            'capture_host_state "$EVIDENCE_ROOT/host-before.tsv"',
            'capture_host_state "$EVIDENCE_ROOT/host-after.tsv"',
            'cmp -s "$EVIDENCE_ROOT/host-before.tsv" "$EVIDENCE_ROOT/host-after.tsv"',
            "route, services, managed paths, loopback and DAC parameters unchanged",
            "EQ_AUDIO_READ_ONLY_PREFLIGHT=PASS",
        ):
            self.assertIn(marker, self.source)
        self.assertIn("/var/tmp/a-clockwork-plex-eq-preflight.XXXXXX", self.source)
        self.assertNotIn('rm -rf "$EVIDENCE_ROOT"', self.source)

    def test_roadmap_tracks_the_preflight_gate(self) -> None:
        roadmap = ROADMAP.read_text(encoding="utf-8")
        self.assertIn("scripts/audio/preflight-eq.sh", roadmap)
        self.assertIn("read-only bedroom-Pi validation gate", roadmap)
        self.assertIn("accepted production SD remains protected", roadmap)
        self.assertIn("separate spare SD is the disposable acceptance target", roadmap)


if __name__ == "__main__":
    unittest.main()
