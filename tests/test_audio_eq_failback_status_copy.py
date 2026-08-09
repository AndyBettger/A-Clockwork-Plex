from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EQ_JS = ROOT / 'app' / 'static' / 'js' / 'audio-eq.js'


class AudioEqFailbackStatusCopyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = AUDIO_EQ_JS.read_text(encoding='utf-8')

    def test_health_text_distinguishes_failback_from_uninstalled(self) -> None:
        self.assertIn('function eqHealthText(eq = {})', self.source)
        self.assertIn("if (eq.available === true) return eq.bypassed === true ? 'Bypassed' : 'Active';", self.source)
        self.assertIn("eq.route_mode === 'direct-failback'", self.source)
        self.assertIn("eq.backend_state === 'direct-failback'", self.source)
        self.assertIn("eq.selected_route_mode === 'direct-failback'", self.source)
        self.assertIn("if (installed && failback) return 'Direct failback';", self.source)
        self.assertIn("if (installed) return 'Unavailable';", self.source)
        self.assertIn("return 'Install required';", self.source)
        self.assertIn('const healthText = eqHealthText(latest);', self.source)

    def test_old_available_only_install_required_ternary_is_removed(self) -> None:
        self.assertNotIn(
            "const healthText = available ? (bypassed ? 'Bypassed' : 'Active') : 'Install required';",
            self.source,
        )


if __name__ == '__main__':
    unittest.main()
