from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "audio" / "preflight-eq.sh"
ROADMAP = ROOT / "docs" / "eq-audio-installer-roadmap.md"


class EqAudioPreflightSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PREFLIGHT.read_text(encoding="utf-8")

    def test_shell_syntax_and_help(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(PREFLIGHT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        help_result = subprocess.run(
            ["bash", str(PREFLIGHT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("read-only host/parser gate", help_result.stdout)
        self.assertIn("ordinary Plexamp playback may remain", help_result.stdout)

    def test_preflight_has_no_privileged_or_audio_mutation_command(self) -> None:
        self.assertNotRegex(
            self.source,
            re.compile(r"(?m)^\s*(?:sudo|rm|cp|mv|install|modprobe|amixer|alsactl)\b"),
        )
        self.assertNotRegex(
            self.source,
            re.compile(r"\bsystemctl\s+(?:start|stop|restart|enable|disable|reload)\b"),
        )
        self.assertNotIn("aplay -D", self.source)
        self.assertNotIn("arecord", self.source)
        self.assertNotIn("source \"$REPO_ROOT/installer/lib/", self.source)
        for path in ("/etc/", "/usr/local/", "/var/lib/"):
            self.assertNotRegex(
                self.source,
                re.compile(rf">\s*['\"]?{re.escape(path)}"),
            )

    def test_real_parsers_are_used_inside_private_boundaries(self) -> None:
        for marker in (
            'ALSA_CONFIG_PATH="$config" aplay -L',
            '"$CAMILLADSP_BINARY" --check "$PROFILE/camilladsp-split-bus.yml"',
            '"$CAMILLADSP_BINARY" --check "$rendered"',
            'systemd-analyze verify',
            'SYSTEMD_UNIT_PATH="$unit_dir"',
            'visudo -cf "$rendered"',
            'ExecStart=/bin/true',
        ):
            self.assertIn(marker, self.source)
        for pcm in ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm"):
            self.assertIn(pcm, self.source)

    def test_exact_binary_and_direct_baseline_are_pinned(self) -> None:
        self.assertIn(
            "CAMILLADSP_SHA256=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa",
            self.source,
        )
        self.assertIn(
            "DIRECT_ROUTE_SHA256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9",
            self.source,
        )
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
        self.assertIn("No bedroom-Pi installation", roadmap)


if __name__ == "__main__":
    unittest.main()
