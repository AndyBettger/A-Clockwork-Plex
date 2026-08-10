from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


class FullInstallerPlanTests(unittest.TestCase):
    def run_installer(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "install.sh", *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_default_plan_is_read_only_and_eq_capable(self):
        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Mode:                 read-only plan", result.stdout)
        self.assertIn("Audio profile:        eq", result.stdout)
        self.assertIn("Weather observations: ecowitt-push", result.stdout)
        self.assertIn("Forecast provider:    open-meteo (retained)", result.stdout)
        self.assertIn("scripts/audio/install-eq.sh", result.stdout)
        self.assertIn("No production file", result.stdout)

    def test_repeatable_noninteractive_weather_underground_plan(self):
        result = self.run_installer(
            "--audio",
            "direct",
            "--weather-observations",
            "weather-underground",
            "--non-interactive",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Audio profile:        direct", result.stdout)
        self.assertIn("Weather observations: weather-underground", result.stdout)
        self.assertIn("Non-interactive:      true", result.stdout)
        self.assertIn("API key supplied outside config.json", result.stdout)
        self.assertIn("Open-Meteo remains the forecast provider", result.stdout)
        self.assertIn("Direct audio is a first-class profile", result.stdout)

    def test_apply_is_explicitly_blocked_until_phase7_activation_exists(self):
        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 2)
        self.assertIn("--apply is not implemented yet", result.stderr)

    def test_invalid_profiles_are_rejected(self):
        audio = self.run_installer("--audio", "mystery")
        weather = self.run_installer("--weather-observations", "wow")

        self.assertEqual(audio.returncode, 2)
        self.assertIn("unsupported audio profile", audio.stderr)
        self.assertEqual(weather.returncode, 2)
        self.assertIn("unsupported weather observation provider", weather.stderr)

    def test_plan_does_not_embed_legacy_audio_install_as_authority(self):
        source = Path("install.sh").read_text(encoding="utf-8")

        self.assertIn("legacy install-shared-audio.sh", source)
        self.assertNotIn("bash scripts/install-shared-audio.sh", source)
        self.assertNotIn("sudo bash scripts/install-shared-audio.sh", source)


if __name__ == "__main__":
    unittest.main()
