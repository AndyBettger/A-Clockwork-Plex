from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'scripts' / 'install-master-eq.sh'
LAB = ROOT / 'scripts' / 'test-master-eq-lab.sh'


class EqLaboratorySafetyTests(unittest.TestCase):
    def test_shell_scripts_have_valid_syntax(self):
        for script in (INSTALLER, LAB):
            result = subprocess.run(
                ['bash', '-n', str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_bare_installer_is_blocked(self):
        result = subprocess.run(
            ['bash', str(INSTALLER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn('Production EQ installation is disabled', result.stderr)

    def test_installer_preserves_only_explicit_lab_and_rollback_entry_points(self):
        text = INSTALLER.read_text(encoding='utf-8')
        self.assertIn('--experimental-lab', text)
        self.assertIn('--rollback', text)
        self.assertNotIn('apt-get install', text)
        self.assertNotIn('cat > "$EQ_CONFIG"', text)

    def test_lab_help_requires_no_audio_or_system_access(self):
        result = subprocess.run(
            ['bash', str(LAB), '--help'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('does not edit /etc/alsa', result.stdout)
        self.assertIn('--run', result.stdout)
        self.assertIn('--prepare-only', result.stdout)

    def test_lab_defaults_to_prepare_only(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('RUN_TESTS=false', text)
        self.assertIn('if [[ "$RUN_TESTS" != true ]]', text)
        self.assertNotIn('systemctl restart', text)
        self.assertNotIn('shairport-sync.conf', text)


if __name__ == '__main__':
    unittest.main()
