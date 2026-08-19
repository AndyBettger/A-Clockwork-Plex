from __future__ import annotations

import hashlib
import re
import subprocess
import unittest
from pathlib import Path


DIRECT_ROUTE_SHA256 = "654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9"
LEGACY_DIRECT_SHA256 = "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"
INSTALLER = "appliance-installer.sh"


class DirectAudioProfileTests(unittest.TestCase):
    def test_direct_profile_is_exact_physically_proven_alarm_safe_route(self):
        direct = Path("installer/profiles/direct/alarm-safe.conf").read_bytes()
        failback = Path(
            "installer/profiles/eq-split-bus/direct-alarm-bypass.conf"
        ).read_bytes()

        self.assertEqual(hashlib.sha256(direct).hexdigest(), DIRECT_ROUTE_SHA256)
        self.assertEqual(direct, failback)

    def test_direct_profile_keeps_music_under_master_but_alarm_bypasses_it(self):
        source = Path("installer/profiles/direct/alarm-safe.conf").read_text(
            encoding="utf-8"
        )

        plexamp = re.search(r"pcm\.acp_plexamp_volume \{(.*?)\n\}", source, re.S)
        airplay = re.search(r"pcm\.acp_airplay_volume \{(.*?)\n\}", source, re.S)
        alarm = re.search(r"pcm\.acp_alarm_volume \{(.*?)\n\}", source, re.S)

        self.assertIsNotNone(plexamp)
        self.assertIsNotNone(airplay)
        self.assertIsNotNone(alarm)
        self.assertIn('slave.pcm "acp_master"', plexamp.group(1))
        self.assertIn('slave.pcm "acp_master"', airplay.group(1))
        self.assertIn('slave.pcm "acp_dmix"', alarm.group(1))
        self.assertNotIn('slave.pcm "acp_master"', alarm.group(1))

    def test_legacy_shared_audio_is_not_the_final_direct_profile(self):
        legacy = Path("scripts/install-shared-audio.sh").read_text(encoding="utf-8")
        match = re.search(
            r"pcm\.acp_alarm_volume \{(.*?)\n\}\n\npcm\.acp_alarm",
            legacy,
            re.S,
        )

        self.assertIsNotNone(match)
        self.assertIn('slave.pcm "acp_master"', match.group(1))
        direct_library = Path("installer/lib/direct_audio.sh").read_text(encoding="utf-8")
        self.assertIn(DIRECT_ROUTE_SHA256, direct_library)
        self.assertIn(LEGACY_DIRECT_SHA256, direct_library)
        self.assertIn("not the final Direct-audio profile", direct_library)

    def test_direct_component_library_is_read_only(self):
        source = Path("installer/lib/direct_audio.sh").read_text(encoding="utf-8")

        mutation_command = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:systemctl|modprobe|mv|cp|rm|install)\b"
        )
        self.assertIsNone(mutation_command.search(source))
        self.assertNotIn("> /etc/", source)
        self.assertIn("acp_verify_direct_audio_sources", source)
        self.assertIn("acp_direct_audio_plan", source)

    def test_top_level_direct_plan_reports_alarm_safe_boundary_without_mutation(self):
        result = subprocess.run(
            ["bash", INSTALLER, "--audio", "direct", "--weather-observations", "ecowitt-push"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(DIRECT_ROUTE_SHA256, result.stdout)
        self.assertIn("bypasses Music Master", result.stdout)
        self.assertIn("install-shared-audio.sh is not an appliance-installer authority", result.stdout)
        self.assertIn("No production file", result.stdout)

    def test_top_level_eq_plan_uses_explicit_alarm_safe_first_install_baseline(self):
        result = subprocess.run(
            ["bash", INSTALLER, "--audio", "eq", "--non-interactive"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fresh-appliance EQ will explicitly request", result.stdout)
        self.assertIn("--baseline alarm-safe-direct", result.stdout)
        self.assertIn("historical Phase 6 direct baseline", result.stdout)
        self.assertIn("exact", result.stdout)
        self.assertIn("rollback guarantee is not weakened", result.stdout)
        self.assertIn("No production file", result.stdout)
        self.assertNotIn("--apply is implemented", result.stdout)


if __name__ == "__main__":
    unittest.main()
