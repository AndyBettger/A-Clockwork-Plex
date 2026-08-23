from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-dashboard-kiosk.sh"
LAUNCHER = ROOT / "scripts" / "launch-dashboard-kiosk.sh"
BRIDGE_DIR = ROOT / "browser" / "plexamp-bridge"
BRIDGE_MANIFEST = BRIDGE_DIR / "manifest.json"
BRIDGE_CONTENT = BRIDGE_DIR / "content.js"


class DashboardKioskInstallSafetyTests(unittest.TestCase):
    def test_launcher_waits_for_dashboard_and_uses_dedicated_profile(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("http://localhost:8088/", text)
        self.assertIn("http://localhost:8088/api/state", text)
        self.assertIn("--kiosk", text)
        self.assertIn("--user-data-dir=", text)
        self.assertIn("a-clockwork-plex/chromium-profile", text)
        self.assertNotIn('DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:32500', text)

    def test_launcher_loads_only_the_local_repository_bridge_when_present(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("browser/plexamp-bridge", text)
        self.assertIn("--load-extension=", text)
        self.assertIn('[[ -f "$BRIDGE_DIR/manifest.json" && -f "$BRIDGE_DIR/content.js" ]]', text)
        self.assertNotIn("--remote-debugging-port", text)
        self.assertNotIn("--remote-debugging-address", text)

    def test_plexamp_bridge_manifest_is_permission_free_and_loopback_scoped(self):
        manifest = json.loads(BRIDGE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertNotIn("permissions", manifest)
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("background", manifest)
        scripts = manifest["content_scripts"]
        self.assertEqual(len(scripts), 1)
        self.assertEqual(
            set(scripts[0]["matches"]),
            {"http://localhost:32500/*", "http://127.0.0.1:32500/*"},
        )
        self.assertTrue(scripts[0]["all_frames"])
        self.assertEqual(scripts[0]["js"], ["content.js"])

    def test_plexamp_bridge_content_has_no_network_or_cookie_authority(self):
        text = BRIDGE_CONTENT.read_text(encoding="utf-8")
        self.assertIn("discovery:customizations:", text)
        self.assertIn(":hidden", text)
        self.assertIn(":order", text)
        self.assertIn("postMessage", text)
        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "document.cookie",
            "chrome.cookies",
            "chrome.storage",
            "@Plexamp:resources",
            "cachedItems",
        ):
            self.assertNotIn(forbidden, text)

    def test_plexamp_bridge_emits_only_logical_order_and_hidden_state(self):
        node = r"""
const bridge = require(process.argv[1]);
const values = new Map([
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:order', JSON.stringify(['music.recent.added.9', 'custom.hub.library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f'])],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:custom.hub.library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f:hidden', 'true'],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:custom.hub.library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f:editing', 'true'],
  ['mmkv.default\\music.popular.9:cachedItems', 'CACHE-MUST-NOT-LEAK'],
  ['mmkv.default\\authToken', 'AUTH-MUST-NOT-LEAK'],
]);
const keys = Array.from(values.keys());
const storage = {
  get length() { return keys.length; },
  key(index) { return keys[index] ?? null; },
  getItem(key) { return values.has(key) ? values.get(key) : null; },
};
process.stdout.write(JSON.stringify(bridge.buildSnapshot(storage)));
"""
        result = subprocess.run(
            ["node", "-e", node, str(BRIDGE_CONTENT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(
            payload["home"]["order"],
            [
                "music.recent.added.9",
                "custom.hub.library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f",
            ],
        )
        self.assertEqual(
            payload["home"]["hidden"],
            ["custom.hub.library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f"],
        )
        self.assertNotIn("editing", result.stdout)
        self.assertNotIn("CACHE-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("AUTH-MUST-NOT-LEAK", result.stdout)

    def test_installer_defaults_to_read_only_and_requires_confirmation(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('MODE="check"', text)
        self.assertIn('CONFIRM_TOKEN="INSTALL-DASHBOARD-KIOSK"', text)
        self.assertIn("Check-only mode", text)
        self.assertIn('if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]', text)
        self.assertIn("Run this as desktop user", text)

    def test_installer_is_scoped_to_browser_autostart(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("localhost|127\\.0\\.0\\.1):32500", text)
        self.assertIn("chromium", text)
        self.assertIn("disabled-by-a-clockwork-plex", text)
        self.assertIn("BACKUP_DIR", text)
        self.assertIn("rollback()", text)
        self.assertNotIn("systemctl restart plexamp", text.lower())
        self.assertNotIn("systemctl restart shairport", text.lower())
        self.assertNotIn("install-shared-audio", text)
        self.assertNotIn("install-master-eq", text)

    def test_desktop_entry_targets_the_repository_launcher(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-dashboard.desktop", text)
        self.assertIn('Exec=/usr/bin/env bash "$LAUNCHER"', text)
        self.assertIn("X-GNOME-Autostart-enabled=true", text)
        self.assertIn("desktop-file-validate", text)

    def test_shell_scripts_have_valid_syntax(self):
        for path in (INSTALLER, LAUNCHER):
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
