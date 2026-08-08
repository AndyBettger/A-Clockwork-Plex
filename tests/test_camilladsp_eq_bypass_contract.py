from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts' / 'a-clockwork-plex-audio-eq.py'


class CamillaDspEqBypassContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location('acp_eq_helper_bypass', HELPER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.helper = module

    def test_bypass_preserves_curve_and_headroom_but_bypasses_only_tone_stage(self) -> None:
        state = {
            'schema_version': 2,
            'bypassed': True,
            'bands': {'bass': 6.0, 'mid': -2.0, 'treble': 3.0},
        }
        normalised = self.helper.normalise_state(state)
        rendered = self.helper.render_config(self.helper.Settings(), normalised)

        self.assertEqual(
            normalised['bands'],
            {'bass': 6.0, 'mid': -2.0, 'treble': 3.0},
        )
        self.assertIn(
            'parameters: {type: Lowshelf, freq: 125, gain: 6.0, slope: 6}',
            rendered,
        )
        self.assertIn(
            'parameters: {type: Peaking, freq: 1000, gain: -2.0, q: 0.7}',
            rendered,
        )
        self.assertIn(
            'parameters: {type: Highshelf, freq: 4000, gain: 3.0, slope: 6}',
            rendered,
        )
        self.assertIn('parameters: {gain: -6.5, scale: dB', rendered)
        self.assertIn(
            'bypassed: false, names: [headroom]',
            rendered,
        )
        self.assertIn(
            'bypassed: true, names: [bass, mid, treble]',
            rendered,
        )

        headroom = rendered.index('bypassed: false, names: [headroom]')
        tone = rendered.index('bypassed: true, names: [bass, mid, treble]')
        combine = rendered.index('name: combine_music_and_alarm', tone)
        limiter = rendered.index('names: [final_safety_limiter]', combine)
        self.assertLess(headroom, tone)
        self.assertLess(tone, combine)
        self.assertLess(combine, limiter)
        self.assertNotIn('bypassed: true, names: [headroom]', rendered)
        self.assertNotIn('bypassed: true, names: [final_safety_limiter]', rendered)

    def test_enabled_curve_keeps_fixed_headroom_and_enables_tone_stage(self) -> None:
        rendered = self.helper.render_config(
            self.helper.Settings(),
            {
                'schema_version': 2,
                'bypassed': False,
                'bands': {'bass': 1.0, 'mid': 0.0, 'treble': -1.0},
            },
        )
        self.assertIn(
            'bypassed: false, names: [headroom]',
            rendered,
        )
        self.assertIn(
            'bypassed: false, names: [bass, mid, treble]',
            rendered,
        )
        self.assertIn('parameters: {gain: -6.5, scale: dB', rendered)


if __name__ == '__main__':
    unittest.main()
