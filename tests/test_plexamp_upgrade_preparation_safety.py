from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare-plexamp-upgrade-rehearsal.sh"
AUDIT_SCRIPT = ROOT / "scripts" / "audit-plexamp-preferences.py"


class PlexampUpgradePreparationSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_script_is_read_only(self):
        text = SCRIPT.read_text(encoding="utf-8")
        forbidden = [
            "systemctl stop",
            "systemctl start",
            "systemctl restart",
            "./upgrade.sh",
            "bash upgrade.sh",
            "curl ",
            "wget ",
            "sudo ",
            "rm -f /etc",
            "install -o root",
        ]
        for token in forbidden:
            self.assertNotIn(token, text)

    def test_captures_upgrade_and_audio_device_evidence(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("upgrade-sh.sha256", text)
        self.assertIn("audioDeviceUuid", text)
        self.assertIn("systemctl cat plexamp.service", text)
        self.assertIn("aplay -L", text)
        self.assertIn("98-a-clockwork-plex-control-aliases.conf", text)

    def test_preference_auditor_default_mode_is_content_blind_and_filters_sensitive_names(self):
        source = AUDIT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("NO FILE CONTENTS ARE READ", source)
        self.assertIn("SAFE_VALUE_KEYS", source)
        self.assertIn("--show-safe-values", source)

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / ".local/share/Plexamp/Settings"
            settings.mkdir(parents=True)
            (settings / "%40Plexamp%3Asettings%3AaudioDeviceUuid").write_text(
                "VALUE-MUST-NOT-LEAK", encoding="utf-8"
            )
            (settings / "%40Plexamp%3Asettings%3AauthToken").write_text(
                "AUTH-MUST-NOT-LEAK", encoding="utf-8"
            )
            (settings / "%40Plexamp%3Astate").write_text(
                "STATE-MUST-NOT-LEAK", encoding="utf-8"
            )

            browser = home / ".config/a-clockwork-plex/chromium-profile/Default"
            (browser / "Local Storage").mkdir(parents=True)
            (browser / "IndexedDB").mkdir()

            result = subprocess.run(
                ["python3", str(AUDIT_SCRIPT), "--home", str(home)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("audioDeviceUuid", result.stdout)
        self.assertIn("Candidate non-sensitive preference keys: 1", result.stdout)
        self.assertIn("Excluded/unclassified files: 2", result.stdout)
        self.assertIn("Local Storage", result.stdout)
        self.assertIn("IndexedDB", result.stdout)
        self.assertNotIn("authToken", result.stdout)
        self.assertNotIn("@Plexamp:state", result.stdout)
        self.assertNotIn("VALUE-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("AUTH-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("STATE-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("Explicit portable-preference value audit", result.stdout)

    def test_preference_auditor_value_mode_reads_only_explicit_ordinary_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / ".local/share/Plexamp/Settings"
            settings.mkdir(parents=True)
            fixtures = {
                "audioConversionBitrate": "320\n",
                "autoPlayEnabled": "true\n",
                "cacheSize": "65536\n",
                "cachingWiFi": "false\n",
                "loudnessLeveling": "true\n",
                "precacheNetworkSpeed": "50\n",
                "sampleRateConversionQuality": "4\n",
                "sampleRateMatching": "1\n",
                "audioDeviceUuid": "DEVICE-VALUE-MUST-NOT-LEAK",
                "playerName": "PLAYER-NAME-MUST-NOT-LEAK",
                "premium": "PREMIUM-MUST-NOT-LEAK",
                "futureOrdinaryPreference": "UNKNOWN-MUST-NOT-LEAK",
                "authToken": "AUTH-MUST-NOT-LEAK",
            }
            for key, value in fixtures.items():
                encoded = "%40Plexamp%3Asettings%3A" + key
                (settings / encoded).write_text(value, encoding="utf-8")

            browser = home / ".config/a-clockwork-plex/chromium-profile/Default"
            (browser / "Local Storage").mkdir(parents=True)
            (browser / "Session Storage").mkdir()
            (browser / "Local Storage" / "leveldb-secret").write_text(
                "BROWSER-MUST-NOT-LEAK", encoding="utf-8"
            )

            result = subprocess.run(
                [
                    "python3",
                    str(AUDIT_SCRIPT),
                    "--home",
                    str(home),
                    "--show-safe-values",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in (
            "audioConversionBitrate = 320",
            "autoPlayEnabled = true",
            "cacheSize = 65536",
            "cachingWiFi = false",
            "loudnessLeveling = true",
            "precacheNetworkSpeed = 50",
            "sampleRateConversionQuality = 4",
            "sampleRateMatching = 1",
        ):
            self.assertIn(expected, result.stdout)
        for key in ("audioDeviceUuid", "playerName", "premium"):
            self.assertIn(f"{key}:", result.stdout)
        for forbidden in (
            "DEVICE-VALUE-MUST-NOT-LEAK",
            "PLAYER-NAME-MUST-NOT-LEAK",
            "PREMIUM-MUST-NOT-LEAK",
            "UNKNOWN-MUST-NOT-LEAK",
            "AUTH-MUST-NOT-LEAK",
            "BROWSER-MUST-NOT-LEAK",
        ):
            self.assertNotIn(forbidden, result.stdout)
        self.assertIn(
            "No unknown Plexamp values and no Chromium storage values were opened or printed.",
            result.stdout,
        )

    def test_preference_auditor_treats_missing_profiles_as_an_inert_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["python3", str(AUDIT_SCRIPT), "--home", directory],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plexamp Settings: NOT FOUND", result.stdout)
        self.assertIn("Chromium profile: NOT FOUND", result.stdout)


if __name__ == "__main__":
    unittest.main()
