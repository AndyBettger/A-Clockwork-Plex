from __future__ import annotations

import ast
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare-plexamp-upgrade-rehearsal.sh"
AUDIT_SCRIPT = ROOT / "scripts" / "audit-plexamp-preferences.py"
HOME_RUNTIME_PROBE = ROOT / "scripts" / "inspect-plexamp-home-runtime.py"


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

    def test_home_runtime_probe_is_bounded_read_only_and_syntax_valid(self):
        source = HOME_RUNTIME_PROBE.read_text(encoding="utf-8")
        ast.parse(source, filename=str(HOME_RUNTIME_PROBE))
        for token in (
            "PLEXAMP_HOSTS = {\"localhost\", \"127.0.0.1\"}",
            "parsed.port != 32500",
            '"method": "Runtime.evaluate"',
            "Object.getOwnPropertyDescriptors",
            "values_exposed: false",
            "getters_invoked: false",
            "SENSITIVE_NAME",
            "Object.prototype.hasOwnProperty.call(descriptor, 'value')",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        for forbidden in (
            "--expression",
            "Runtime.callFunctionOn",
            "Page.navigate",
            "Storage.clearDataForOrigin",
            "Network.setCookie",
            "DOM.setAttributeValue",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        help_result = subprocess.run(
            ["python3", str(HOME_RUNTIME_PROBE), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("No Plexamp values are emitted", help_result.stdout)

        unsafe_port = subprocess.run(
            ["python3", str(HOME_RUNTIME_PROBE), "--debug-port", "80"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(unsafe_port.returncode, 1)
        self.assertIn("unprivileged TCP port", unsafe_port.stderr)

    def test_preference_auditor_default_mode_is_content_blind(self):
        source = AUDIT_SCRIPT.read_text(encoding="utf-8")
        for token in (
            "SAFE_VALUE_KEYS",
            "--show-safe-values",
            "--scan-browser-keys",
            "--fingerprint-browser-records",
            "--fingerprint-browser-customizations",
            "MMKV_LOOPBACK_STORAGE_KEY",
            "MMKV_CUSTOMIZATION_PREFIX",
        ):
            self.assertIn(token, source)

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / ".local/share/Plexamp/Settings"
            settings.mkdir(parents=True)
            (settings / "%40Plexamp%3Asettings%3AaudioDeviceUuid").write_text(
                "DEVICE-VALUE-MUST-NOT-LEAK", encoding="utf-8"
            )
            (settings / "%40Plexamp%3Asettings%3AauthToken").write_text(
                "AUTH-MUST-NOT-LEAK", encoding="utf-8"
            )
            result = subprocess.run(
                ["python3", str(AUDIT_SCRIPT), "--home", str(home)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("audioDeviceUuid", result.stdout)
        self.assertNotIn("authToken", result.stdout)
        self.assertNotIn("DEVICE-VALUE-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("AUTH-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("Explicit portable-preference value audit", result.stdout)

    def test_value_mode_decodes_only_explicit_typed_allowlist(self):
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
        ):
            self.assertNotIn(forbidden, result.stdout)

    def test_value_mode_rejects_wrong_typed_scalar_encoding(self):
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

        self.assertIn(
            "autoPlayEnabled = <not shown: unexpected typed scalar format>",
            result.stdout,
        )
        self.assertIn(
            "cacheSize = <not shown: unexpected typed scalar format>",
            result.stdout,
        )

    def test_browser_key_scan_emits_direct_and_mmkv_names_never_values(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            leveldb = (
                home
                / ".config/a-clockwork-plex/chromium-profile/Default/Local Storage/leveldb"
            )
            leveldb.mkdir(parents=True)
            payload = b"".join(
                (
                    b"junk_http://localhost:32500\x00\x01@Plexamp:settings:activeTab\x00",
                    b"DIRECT-VALUE-MUST-NOT-LEAK",
                    b"junk_http://localhost:32500\x00\x01mmkv.default\\homeSources\x00",
                    b"MMKV-HOME-MUST-NOT-LEAK",
                    b"junk_http://localhost:32500\x00\x01mmkv.default\\authToken\x00",
                    b"MMKV-AUTH-MUST-NOT-LEAK",
                    b"junk_https://example.com\x00\x01outsideKey\x00",
                    b"OUTSIDE-VALUE-MUST-NOT-LEAK",
                )
            )
            (leveldb / "000001.log").write_bytes(payload)
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
        self.assertIn("@Plexamp:settings:activeTab", result.stdout)
        self.assertIn("mmkv.default\\homeSources", result.stdout)
        self.assertIn("MMKV web-key records recognised: 1", result.stdout)
        self.assertNotIn("authToken", result.stdout)
        self.assertNotIn("example.com", result.stdout)
        for forbidden in (
            "DIRECT-VALUE-MUST-NOT-LEAK",
            "MMKV-HOME-MUST-NOT-LEAK",
            "MMKV-AUTH-MUST-NOT-LEAK",
            "OUTSIDE-VALUE-MUST-NOT-LEAK",
        ):
            self.assertNotIn(forbidden, result.stdout)

    def test_broad_browser_fingerprint_excludes_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            leveldb = (
                home
                / ".config/a-clockwork-plex/chromium-profile/Default/Local Storage/leveldb"
            )
            leveldb.mkdir(parents=True)
            (leveldb / "000001.log").write_bytes(
                b"x_http://localhost:32500\x00\x01@Plexamp:settings:activeTab\x00HOME"
                + b"A" * 4096
                + b"x_http://localhost:32500\x00\x01mmkv.default\\homeLayout\x00LAYOUT"
                + b"B" * 4096
                + b"x_http://localhost:32500\x00\x01@Plexamp:resources\x00"
                + b"RESOURCE-SECRET-MUST-NOT-LEAK"
            )
            result = subprocess.run(
                [
                    "python3",
                    str(AUDIT_SCRIPT),
                    "--home",
                    str(home),
                    "--fingerprint-browser-records",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("@Plexamp:settings:activeTab", result.stdout)
        self.assertIn(" | mmkv.default | ", result.stdout)
        self.assertIn("@Plexamp:resources is deliberately excluded", result.stdout)
        self.assertNotIn("RESOURCE-SECRET-MUST-NOT-LEAK", result.stdout)

    def test_customization_fingerprint_is_exact_and_detects_order_change_only(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            leveldb = (
                home
                / ".config/a-clockwork-plex/chromium-profile/Default/Local Storage/leveldb"
            )
            leveldb.mkdir(parents=True)
            log = leveldb / "000001.log"

            base_key = (
                b"x_http://localhost:32500\x00\x01"
                b"mmkv.default\\discovery:customizations:context::/library/sections/9:\x00"
            )
            order_key = (
                b"x_http://localhost:32500\x00\x01"
                b"mmkv.default\\discovery:customizations:context::/library/sections/9:order\x00"
            )
            cache_key = (
                b"x_http://localhost:32500\x00\x01"
                b"mmkv.default\\music.popular.9:cachedItems\x00"
            )
            resource_key = (
                b"x_http://localhost:32500\x00\x01@Plexamp:resources\x00"
            )

            def payload(order_value: bytes) -> bytes:
                return b"".join(
                    (
                        base_key,
                        b"BASE-VALUE-MUST-NOT-LEAK",
                        b"A" * 4096,
                        order_key,
                        order_value,
                        b"B" * 4096,
                        cache_key,
                        b"CACHE-VALUE-MUST-NOT-LEAK",
                        b"C" * 4096,
                        resource_key,
                        b"RESOURCE-VALUE-MUST-NOT-LEAK",
                    )
                )

            log.write_bytes(payload(b"ORDER-A-MUST-NOT-LEAK"))
            before = subprocess.run(
                [
                    "python3",
                    str(AUDIT_SCRIPT),
                    "--home",
                    str(home),
                    "--fingerprint-browser-customizations",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            log.write_bytes(payload(b"ORDER-B-MUST-NOT-LEAK"))
            after = subprocess.run(
                [
                    "python3",
                    str(AUDIT_SCRIPT),
                    "--home",
                    str(home),
                    "--fingerprint-browser-customizations",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertIn(
            "Chromium Plexamp Home-layout customization fingerprints:",
            before.stdout,
        )
        self.assertIn("discovery:customizations:context::/library/sections/9:", before.stdout)
        self.assertIn(
            "discovery:customizations:context::/library/sections/9:order",
            before.stdout,
        )
        self.assertNotIn(" | mmkv.default\\music.popular.9:cachedItems | ", before.stdout)
        self.assertNotIn("@Plexamp:resources |", before.stdout)

        before_lines = [
            line for line in before.stdout.splitlines() if " | mmkv.default\\" in line
        ]
        after_lines = [
            line for line in after.stdout.splitlines() if " | mmkv.default\\" in line
        ]
        self.assertEqual(len(before_lines), 2)
        self.assertEqual(len(after_lines), 2)
        self.assertEqual(before_lines[0], after_lines[0])
        self.assertNotEqual(before_lines[1], after_lines[1])

        for forbidden in (
            "BASE-VALUE-MUST-NOT-LEAK",
            "ORDER-A-MUST-NOT-LEAK",
            "ORDER-B-MUST-NOT-LEAK",
            "CACHE-VALUE-MUST-NOT-LEAK",
            "RESOURCE-VALUE-MUST-NOT-LEAK",
        ):
            self.assertNotIn(forbidden, before.stdout)
            self.assertNotIn(forbidden, after.stdout)

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
