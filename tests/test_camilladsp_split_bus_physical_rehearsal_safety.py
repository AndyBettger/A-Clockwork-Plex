from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "scripts" / "test-camilladsp-split-bus-physical-rehearsal.sh"


class CamillaDspSplitBusPhysicalRehearsalSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_is_prepare_only_before_privileged_actions(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("MODE=prepare", text)
        gate = text.index('if [[ "$MODE" == prepare ]]')
        self.assertGreater(text.index("sudo -v", gate), gate)
        self.assertGreater(text.index("sudo systemctl stop", gate), gate)
        self.assertGreater(text.index('sudo install -o root', gate), gate)

    def test_activation_is_explicit_time_limited_and_never_persistent(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn('REQUIRED_CONFIRMATION="STAGE-B-SPLIT-BUS-REAL-DAC"', text)
        self.assertIn("--confirm TOKEN", text)
        self.assertIn("Duration must be from 120 to 1500 seconds", text)
        self.assertIn("trap on_exit EXIT", text)
        self.assertNotIn("--keep-active", text)
        self.assertNotIn("--no-auto-restore", text)
        self.assertNotIn("systemctl enable", text)
        self.assertNotIn("modprobe snd_aloop", text)
        self.assertNotIn("install-master-eq.sh", text)

    def test_public_source_pcms_are_preserved_but_alarm_bypasses_master(self):
        text = LAB.read_text(encoding="utf-8")
        for pcm in (
            "pcm.acp_dmix",
            "pcm.acp_master_volume",
            "pcm.acp_master",
            "pcm.acp_plexamp_volume",
            "pcm.acp_plexamp",
            "pcm.acp_airplay_volume",
            "pcm.acp_airplay",
            "pcm.acp_alarm_volume",
            "pcm.acp_alarm",
        ):
            self.assertIn(pcm, text)
        self.assertIn('slave.pcm "acp_music_route"', text)
        self.assertIn('slave.pcm "acp_alarm_route"', text)
        alarm_block = text[text.index("pcm.acp_alarm_volume"):text.index("pcm.acp_alarm {")]
        self.assertNotIn('slave.pcm "acp_master"', alarm_block)

    def test_four_channel_capture_and_final_limiter_order_are_explicit(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("BUS_CHANNELS=4", text)
        self.assertIn('ttable {\n        0.0 1\n        1.1 1', text)
        self.assertIn('ttable {\n        0.2 1\n        1.3 1', text)
        self.assertIn("channels: {in: 4, out: 2}", text)
        self.assertIn("names: [bass, mid, treble, headroom]", text)
        self.assertIn("name: combine_music_and_alarm", text)
        self.assertIn("names: [final_safety_limiter]", text)
        self.assertLess(
            text.index("names: [bass, mid, treble, headroom]"),
            text.index("name: combine_music_and_alarm"),
        )
        self.assertLess(
            text.index("name: combine_music_and_alarm"),
            text.index("names: [final_safety_limiter]"),
        )

    def test_rollback_restores_config_services_and_live_mixer_levels(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("ROLLBACK_NEEDED=true", text)
        self.assertIn("rollback-alsa-config", text)
        self.assertIn("rollback-camilladsp-stopped", text)
        self.assertIn("rollback-mixer-state", text)
        self.assertIn("restore_mixer_levels", text)
        self.assertIn('sudo "$MIXER_HELPER" live "$channel" "$percent"', text)
        self.assertIn('sudo cp -a "$SNAPSHOT_DIR/original-alsa.conf" "$ALSA_CONFIG"', text)
        self.assertIn("restore_original_services", text)

    def test_manual_gate_covers_hold_real_alarm_and_live_only_master(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("complete ten-minute hold", text)
        self.assertIn("real scheduled alarm", text)
        self.assertIn("master-zero", text)
        self.assertIn("master-restore", text)
        self.assertIn("Do not use the Settings volume faders", text)
        self.assertIn("Snooze", text)
        self.assertIn("Dismiss", text)

    def test_only_expected_services_and_physical_devices_are_touched(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn(
            "SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)",
            text,
        )
        self.assertIn('device: "hw:$LOOPBACK_INDEX,1,0"', text)
        self.assertIn('device: "hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE"', text)
        self.assertNotIn("/etc/shairport-sync.conf", text)
        self.assertNotIn("reboot", text)
        self.assertNotIn("poweroff", text)


if __name__ == "__main__":
    unittest.main()
