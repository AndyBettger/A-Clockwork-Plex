from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "prepare-stage-c-route-package.sh"


class StageCRoutePackageSafetyTests(unittest.TestCase):
    def test_generator_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(GENERATOR)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generator_has_no_activation_interface(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertNotIn("--activate", text)
        self.assertNotIn("--confirm", text)
        self.assertIn("no activation mode", text.lower())
        self.assertIn("No activation path exists in this script.", text)

    def test_prepare_layer_performs_no_privileged_or_audio_mutation(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?m)^\s*sudo(?:\s|$)", text))
        self.assertNotIn("modprobe snd_aloop", text)
        self.assertNotIn("modprobe -r", text)
        self.assertNotIn("systemctl start", text)
        self.assertNotIn("systemctl stop", text)
        self.assertNotIn("systemctl restart", text)
        self.assertNotIn("systemctl enable", text)
        self.assertNotIn("systemctl disable", text)
        self.assertNotIn("aplay -D", text)
        self.assertNotIn("amixer ", text)
        self.assertNotIn("alsactl ", text)

    def test_host_contract_is_pinned_to_physical_discovery(self):
        text = GENERATOR.read_text(encoding="utf-8")
        for expected in (
            'EXPECTED_CAMILLADSP_VERSION="4.1.3"',
            'EXPECTED_CAMILLADSP_SHA256="e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa"',
            'EXPECTED_CURRENT_ALSA_SHA256="08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"',
            'DAC_CARD="${DAC_CARD:-Pro}"',
            'LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"',
            'LOOPBACK_ID="${LOOPBACK_ID:-ACP_Loopback}"',
            "parameter_starts_with pcm_substreams 2",
            "parameter_starts_with pcm_notify 1",
            "SAMPLE_RATE=44100",
            "FORMAT=S16_LE",
            "PERIOD_SIZE=1024",
            "BUFFER_SIZE=8192",
        ):
            self.assertIn(expected, text)

    def test_both_physically_proven_route_shapes_are_generated(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIn('slave.pcm "acp_music_route"', text)
        self.assertIn('slave.pcm "acp_alarm_route"', text)
        self.assertIn('slave.pcm "acp_dmix"', text)
        self.assertIn("Music-only EQ and headroom, independent alarm, final limiter", text)
        self.assertIn("final_safety_limiter", text)
        self.assertIn("clip_limit: $LIMIT_DB", text)
        for pcm in ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm"):
            self.assertIn(pcm, text)

    def test_generated_runtime_assets_remain_deliberately_blocked(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("stage-c1-candidate-only", text)
        self.assertIn("activation_approved': False", text)
        self.assertIn("mutation is deliberately blocked", text)
        self.assertIn("return 78", text)
        self.assertIn(
            "ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved",
            text,
        )
        self.assertNotIn("activation-approved\nEOF", text)

    def test_package_contains_expected_review_assets(self):
        text = GENERATOR.read_text(encoding="utf-8")
        for expected in (
            "a-clockwork-plex-aloop.conf",
            "split-bus.conf",
            "direct-alarm-bypass.conf",
            "camilladsp-split-bus.yml",
            "a-clockwork-plex-split-bus",
            "a-clockwork-plex-audio-route",
            "a-clockwork-plex-audio-route.service",
            "a-clockwork-plex-camilladsp.service",
            "a-clockwork-plex-audio-failback.service",
            "manifest.tsv",
            "results.tsv",
            "report.txt",
            "visudo -cf",
            "--check \"$CAMILLA_CONFIG\"",
            "python3 -m py_compile",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
