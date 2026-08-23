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
        self.assertIn("NO PLEXAMP SETTING VALUES ARE READ", source)
        self.assertIn("SAFE_VALUE_KEYS", source)
        self.assertIn("--show-safe-values", source)
        self.assertIn("--scan-browser-keys", source)

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
        self.assertNotIn("structured key audit", result.stdout)

    def test_preference_auditor_value_mode_decodes_only_explicit_typed_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / ".local/share/Plexamp/Settings"
            settings.mkdir(parents=True)
            fixtures = {
                "audioConversionBitrate": "N256",
                "autoPlayEnabled": "Bfalse",
                "cacheSize": "N32768",
                "cachingWiFi": "N10",
                "loudnessLeveling": "Bfalse",
                "precacheNetworkSpeed": "N0",
                "sampleRateConversionQuality": "N4",
                "sampleRateMatching": "N2",
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
            "audioConversionBitrate = 256",
            "autoPlayEnabled = false",
            "cacheSize = 32768",
            "cachingWiFi = 10",
            "loudnessLeveling = false",
            "precacheNetworkSpeed = 0",
            "sampleRateConversionQuality = 4",
            "sampleRateMatching = 2",
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

    def test_preference_auditor_rejects_wrong_typed_scalar_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / ".local/share/Plexamp/Settings"
            settings.mkdir(parents=True)
            (settings / "%40Plexamp%3Asettings%3AautoPlayEnabled").write_text(
                "N1", encoding="utf-8"
            )
            (settings / "%40Plexamp%3Asettings%3AcacheSize").write_text(
                "Btrue", encoding="utf-8"
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
        self.assertIn(
            "autoPlayEnabled = <not shown: unexpected typed scalar format>",
            result.stdout,
        )
        self.assertIn(
            "cacheSize = <not shown: unexpected typed scalar format>",
            result.stdout,
        )

    def test_browser_key_scan_emits_only_structured_loopback_names_never_values(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            leveldb = (
                home
                / ".config/a-clockwork-plex/chromium-profile/Default/Local Storage/leveldb"
            )
            leveldb.mkdir(parents=True)
            payload = b"".join(
                (
                    b"junk_http://localhost:32500\x00\x01@Plexamp:settings:homeLayout\x00",
                    b"HOME-VALUE-MUST-NOT-LEAK",
                    b"junk_http://localhost:32500\x00\x01authToken\x00",
                    b"AUTH-VALUE-MUST-NOT-LEAK",
                    b"junk_http://localhost:8088\x00\x01acpTheme\x00",
                    b"THEME-VALUE-MUST-NOT-LEAK",
                    b"junk_https://example.com\x00\x01outsideKey\x00",
                    b"OUTSIDE-VALUE-MUST-NOT-LEAK",
                )
            )
            (leveldb / "000001.log").write_bytes(payload)
            (leveldb / "000002.ldb").write_bytes(
                b"x_http://127.0.0.1:32500\x00\x01@Plexamp:settings:sidebarLayout\x00"
                b"SIDEBAR-VALUE-MUST-NOT-LEAK"
            )
            (leveldb / "MANIFEST-000001").write_bytes(
                b"MANIFEST-VALUE-MUST-NOT-LEAK"
            )

            result = subprocess.run(
                [
                    "python3",
                    str(AUDIT_SCRIPT),
                    "--home",
                    str(home),
                    "--scan-browser-keys",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Chromium Local Storage structured key audit:", result.stdout)
        self.assertIn("http://localhost:32500", result.stdout)
        self.assertIn("http://localhost:8088", result.stdout)
        self.assertIn("http://127.0.0.1:32500", result.stdout)
        self.assertIn("@Plexamp:settings:homeLayout", result.stdout)
        self.assertIn("@Plexamp:settings:sidebarLayout", result.stdout)
        self.assertIn("acpTheme", result.stdout)
        self.assertIn("Sensitive-looking key records suppressed: 1", result.stdout)
        self.assertNotIn("authToken", result.stdout)
        self.assertNotIn("example.com", result.stdout)
        self.assertNotIn("outsideKey", result.stdout)
        for forbidden in (
            "HOME-VALUE-MUST-NOT-LEAK",
            "AUTH-VALUE-MUST-NOT-LEAK",
            "THEME-VALUE-MUST-NOT-LEAK",
            "OUTSIDE-VALUE-MUST-NOT-LEAK",
            "SIDEBAR-VALUE-MUST-NOT-LEAK",
            "MANIFEST-VALUE-MUST-NOT-LEAK",
        ):
            self.assertNotIn(forbidden, result.stdout)
        self.assertIn(
            "No Plexamp setting values or Chromium Local Storage values were decoded or printed.",
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
