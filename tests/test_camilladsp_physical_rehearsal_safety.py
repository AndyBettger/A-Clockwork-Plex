from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-camilladsp-physical-rehearsal.sh'


class CamillaDspPhysicalRehearsalSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_is_prepare_only_before_privileged_actions(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('MODE=prepare', text)
        self.assertIn('if [[ "$MODE" == prepare ]]', text)
        self.assertGreater(text.index('sudo -v'), text.index('if [[ "$MODE" == prepare ]]'))
        self.assertGreater(text.index('sudo systemctl stop'), text.index('if [[ "$MODE" == prepare ]]'))
        self.assertGreater(text.index('sudo install -o root'), text.index('if [[ "$MODE" == prepare ]]'))

    def test_activation_requires_explicit_real_dac_token(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('REQUIRED_CONFIRMATION="STAGE-SEVEN-REAL-DAC"', text)
        self.assertIn('--confirm TOKEN', text)
        self.assertIn('Physical activation is blocked', text)
        self.assertNotIn('--keep-active', text)
        self.assertNotIn('--no-auto-restore', text)

    def test_rehearsal_preserves_public_pcm_names_and_source_trims(self):
        text = LAB.read_text(encoding='utf-8')
        for pcm in (
            'pcm.acp_dmix',
            'pcm.acp_master_volume',
            'pcm.acp_master',
            'pcm.acp_plexamp_volume',
            'pcm.acp_plexamp',
            'pcm.acp_airplay_volume',
            'pcm.acp_airplay',
            'pcm.acp_alarm_volume',
            'pcm.acp_alarm',
        ):
            self.assertIn(pcm, text)
        self.assertIn('name "A Clockwork Master"', text)
        self.assertIn('name "A Clockwork Plexamp"', text)
        self.assertIn('name "A Clockwork AirPlay"', text)
        self.assertIn('name "A Clockwork Alarm"', text)

    def test_physical_route_is_fixed_to_current_format_and_guarded(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('SAMPLE_RATE=44100', text)
        self.assertIn('FORMAT=S16_LE', text)
        self.assertIn('device: "hw:$LOOPBACK_INDEX,1,0"', text)
        self.assertIn('device: "hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE"', text)
        self.assertIn('enable_rate_adjust: true', text)
        self.assertIn('target_level: $TARGET_LEVEL', text)
        self.assertIn('clip_limit: $LIMIT_DB', text)
        self.assertIn('REHEARSAL_IPC_KEY=1094932536', text)
        self.assertIn('low-level-tone-route', text)

    def test_rollback_is_mandatory_and_restores_exact_state(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('trap on_exit EXIT', text)
        self.assertIn('ROLLBACK_NEEDED=true', text)
        self.assertIn('rollback-alsa-config', text)
        self.assertIn('rollback-camilladsp-stopped', text)
        self.assertIn('rollback-mixer-state', text)
        self.assertIn('restore_original_services', text)
        self.assertIn('sudo cp -a "$SNAPSHOT_DIR/original-alsa.conf" "$ALSA_CONFIG"', text)
        self.assertNotIn('systemctl enable', text)
        self.assertNotIn('modprobe snd_aloop', text)
        self.assertNotIn('/etc/shairport-sync.conf', text)

    def test_only_expected_services_are_managed(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn(
            'SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)',
            text,
        )
        self.assertNotIn('reboot', text)
        self.assertNotIn('poweroff', text)


if __name__ == '__main__':
    unittest.main()
