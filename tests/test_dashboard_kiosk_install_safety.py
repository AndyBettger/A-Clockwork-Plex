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
DASHBOARD_BRIDGE = ROOT / "app" / "static" / "js" / "plexamp-browser-bridge.js"


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
        self.assertEqual(scripts[0]["js"], ["content.js", "reset.js"])

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
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:order', JSON.stringify({'0': ['music.recent.added.9', 'custom.hub/library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f']})],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:custom.hub/library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f:hidden', JSON.stringify({'0': true})],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:custom.hub/library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f:editing', 'true'],
  ['mmkv.default\\music.popular.9:cachedItems', 'CACHE-MUST-NOT-LEAK'],
  ['mmkv.default\\authToken', 'AUTH-MUST-NOT-LEAK'],
]);
const keys = Array.from(values.keys());
const reads = [];
const storage = {
  get length() { return keys.length; },
  key(index) { return keys[index] ?? null; },
  getItem(key) {
    reads.push(key);
    return values.has(key) ? values.get(key) : null;
  },
};
process.stdout.write(JSON.stringify({ snapshot: bridge.buildSnapshot(storage), reads }));
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
        snapshot = payload["snapshot"]
        self.assertEqual(snapshot["status"], "ready")
        self.assertEqual(
            snapshot["home"]["order"],
            [
                "music.recent.added.9",
                "custom.hub/library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f",
            ],
        )
        self.assertEqual(
            snapshot["home"]["hidden"],
            ["custom.hub/library-grid.12066189-245a-4c4c-98ec-4768a4d4d15f"],
        )
        self.assertEqual(len(payload["reads"]), 2)
        self.assertTrue(all(key.endswith((":order", ":hidden")) for key in payload["reads"]))
        self.assertFalse(any(":editing" in key for key in payload["reads"]))
        self.assertFalse(any("cachedItems" in key for key in payload["reads"]))
        self.assertFalse(any("authToken" in key for key in payload["reads"]))
        self.assertNotIn("CACHE-MUST-NOT-LEAK", result.stdout)
        self.assertNotIn("AUTH-MUST-NOT-LEAK", result.stdout)

    def test_dashboard_bridge_accepts_slash_bearing_home_identifiers(self):
        node = r"""
global.window = {};
require(process.argv[1]);
const validate = window.ACPPlexampBrowserPreferences.validateSnapshot;
const accepted = validate({
  schema_version: 1,
  status: 'ready',
  home: {
    order: ['music.recent.added.9', 'music/recent/played.9'],
    hidden: ['music/recent/played.9'],
  },
});
const rejected = validate({
  schema_version: 1,
  status: 'ready',
  home: {
    order: ['music:recent:played.9'],
    hidden: [],
  },
});
process.stdout.write(JSON.stringify({ accepted, rejected }));
"""
        result = subprocess.run(
            ["node", "-e", node, str(DASHBOARD_BRIDGE)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["accepted"]["status"], "ready")
        self.assertEqual(payload["accepted"]["home"]["hidden"], ["music/recent/played.9"])
        self.assertIsNone(payload["rejected"])

    def test_plexamp_bridge_keeps_plain_legacy_shapes_compatible(self):
        node = r"""
const bridge = require(process.argv[1]);
const values = new Map([
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:order', JSON.stringify(['music.recent.added.9', 'music.recent.played.9'])],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:music.recent.played.9:hidden', 'true'],
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
        self.assertEqual(payload["home"]["hidden"], ["music.recent.played.9"])
        self.assertEqual(len(payload["home"]["order"]), 2)

    def test_plexamp_bridge_rejects_ambiguous_wrappers_without_values(self):
        node = r"""
const bridge = require(process.argv[1]);
const hiddenValue = JSON.stringify({ a: true, b: false });
const orderValue = JSON.stringify({ a: ['PRIVATE-HUB-A'], b: ['PRIVATE-HUB-B'] });
const values = new Map([
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:order', orderValue],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:public.hub:hidden', hiddenValue],
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
        self.assertTrue(payload["status"].startswith("unsupported-hidden-format-jobj2-"))
        self.assertNotIn("PRIVATE-HUB-A", result.stdout)
        self.assertNotIn("PRIVATE-HUB-B", result.stdout)
        self.assertNotIn('"a":true', result.stdout)

    def test_plexamp_bridge_reports_only_character_classes_for_rejected_order_ids(self):
        node = r"""
const bridge = require(process.argv[1]);
const orderValue = JSON.stringify({'0': ['PRIVATE:HOME/ONE', 'normal.hub/two']});
const values = new Map([
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:order', orderValue],
  ['mmkv.default\\discovery:customizations:context123::/library/sections/9:normal.hub/two:hidden', JSON.stringify({'0': false})],
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
        self.assertEqual(
            payload["status"],
            "unsupported-order-format-items2-max16-empty0-over0-nonstring0-bad3a",
        )
        self.assertNotIn("PRIVATE:HOME/ONE", result.stdout)
        self.assertNotIn("normal.hub/two", result.stdout)

    def test_home_plan_maps_saved_layout_onto_target_and_preserves_target_only_hubs(self):
        node = r"""
const bridge = require(process.argv[1]);
const values = new Map([
  ['mmkv.default\\discovery:customizations:targetctx::/library/sections/9:order', JSON.stringify({'0': ['hub.a', 'hub.b', 'hub.c']})],
  ['mmkv.default\\discovery:customizations:targetctx::/library/sections/9:hub.c:hidden', JSON.stringify({'0': true})],
]);
const storage = {
  get length() { return values.size; },
  key(index) { return Array.from(values.keys())[index] ?? null; },
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { values.set(key, String(value)); },
  removeItem(key) { values.delete(key); },
};
const plan = bridge.planHome(storage, {
  order: ['hub.b', 'hub.a', 'hub.missing'],
  hidden: ['hub.a', 'hub.missing'],
});
process.stdout.write(JSON.stringify(plan));
"""
        result = subprocess.run(
            ["node", "-e", node, str(BRIDGE_CONTENT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["status"], "ready")
        self.assertTrue(plan["read_only"])
        self.assertTrue(plan["restore_available"])
        self.assertEqual(plan["change_count"], 2)
        self.assertTrue(plan["order_changed"])
        self.assertEqual(plan["hidden_change_count"], 1)
        self.assertEqual(plan["missing_item_count"], 1)
        self.assertEqual(plan["target_only_item_count"], 1)
        self.assertEqual(plan["target_known_item_count"], 3)
        self.assertRegex(plan["target_fingerprint"], r"^[a-f0-9]{8}$")

    def test_home_apply_writes_only_target_context_and_verifies_effective_layout(self):
        node = r"""
const bridge = require(process.argv[1]);
const authKey = 'mmkv.default\\authToken';
const cacheKey = 'mmkv.default\\music.popular.9:cachedItems';
const values = new Map([
  ['mmkv.default\\discovery:customizations:targetctx::/library/sections/9:order', JSON.stringify({'0': ['hub.a', 'hub.b', 'hub.c']})],
  ['mmkv.default\\discovery:customizations:targetctx::/library/sections/9:hub.c:hidden', JSON.stringify({'0': true})],
  [authKey, 'AUTH-MUST-STAY'],
  [cacheKey, 'CACHE-MUST-STAY'],
]);
const storage = {
  get length() { return values.size; },
  key(index) { return Array.from(values.keys())[index] ?? null; },
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { values.set(key, String(value)); },
  removeItem(key) { values.delete(key); },
};
const desired = {
  order: ['hub.b', 'hub.a', 'hub.missing'],
  hidden: ['hub.a', 'hub.missing'],
};
const plan = bridge.planHome(storage, desired);
const applied = bridge.applyHome(storage, desired, plan.target_fingerprint, true);
const snapshot = bridge.buildSnapshot(storage);
process.stdout.write(JSON.stringify({
  applied,
  snapshot,
  auth: values.get(authKey),
  cache: values.get(cacheKey),
  missingKeyCreated: Array.from(values.keys()).some((key) => key.includes('hub.missing')),
}));
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
        self.assertEqual(payload["applied"]["status"], "applied")
        self.assertTrue(payload["applied"]["applied"])
        self.assertEqual(payload["applied"]["applied_change_count"], 2)
        self.assertEqual(payload["snapshot"]["home"]["order"], ["hub.b", "hub.a", "hub.c"])
        self.assertEqual(payload["snapshot"]["home"]["hidden"], ["hub.a", "hub.c"])
        self.assertEqual(payload["auth"], "AUTH-MUST-STAY")
        self.assertEqual(payload["cache"], "CACHE-MUST-STAY")
        self.assertFalse(payload["missingKeyCreated"])

    def test_home_apply_refuses_stale_target_before_mutation(self):
        node = r"""
const bridge = require(process.argv[1]);
const orderKey = 'mmkv.default\\discovery:customizations:targetctx::/library/sections/9:order';
const values = new Map([[orderKey, JSON.stringify({'0': ['hub.a', 'hub.b', 'hub.c']})]]);
const writes = [];
const storage = {
  get length() { return values.size; },
  key(index) { return Array.from(values.keys())[index] ?? null; },
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { writes.push(['set', key]); values.set(key, String(value)); },
  removeItem(key) { writes.push(['remove', key]); values.delete(key); },
};
const desired = { order: ['hub.b', 'hub.a', 'hub.c'], hidden: [] };
const plan = bridge.planHome(storage, desired);
values.set(orderKey, JSON.stringify({'0': ['hub.a', 'hub.c', 'hub.b']}));
const beforeApply = values.get(orderKey);
const applied = bridge.applyHome(storage, desired, plan.target_fingerprint, true);
process.stdout.write(JSON.stringify({ applied, writes, unchanged: values.get(orderKey) === beforeApply }));
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
        self.assertEqual(payload["applied"]["status"], "stale-target")
        self.assertTrue(payload["applied"]["fresh_preview_required"])
        self.assertFalse(payload["applied"]["applied"])
        self.assertEqual(payload["writes"], [])
        self.assertTrue(payload["unchanged"])

    def test_home_apply_rolls_back_exact_raw_state_after_injected_write_failure(self):
        node = r"""
const bridge = require(process.argv[1]);
const orderKey = 'mmkv.default\\discovery:customizations:targetctx::/library/sections/9:order';
const hiddenC = 'mmkv.default\\discovery:customizations:targetctx::/library/sections/9:hub.c:hidden';
const values = new Map([
  [orderKey, JSON.stringify({'0': ['hub.a', 'hub.b', 'hub.c']})],
  [hiddenC, JSON.stringify({'0': true})],
]);
const before = JSON.stringify(Array.from(values.entries()).sort());
let failOnce = true;
const storage = {
  get length() { return values.size; },
  key(index) { return Array.from(values.keys())[index] ?? null; },
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) {
    if (key.endsWith(':hub.a:hidden') && failOnce) {
      failOnce = false;
      throw new Error('injected');
    }
    values.set(key, String(value));
  },
  removeItem(key) { values.delete(key); },
};
const desired = { order: ['hub.b', 'hub.a', 'hub.c'], hidden: ['hub.a'] };
const plan = bridge.planHome(storage, desired);
const applied = bridge.applyHome(storage, desired, plan.target_fingerprint, true);
const after = JSON.stringify(Array.from(values.entries()).sort());
process.stdout.write(JSON.stringify({ applied, exact: before === after, snapshot: bridge.buildSnapshot(storage) }));
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
        self.assertEqual(payload["applied"]["status"], "apply-failed")
        self.assertFalse(payload["applied"]["applied"])
        self.assertTrue(payload["applied"]["rolled_back"])
        self.assertEqual(payload["applied"]["rollback_failure_count"], 0)
        self.assertTrue(payload["exact"])
        self.assertEqual(payload["snapshot"]["home"]["order"], ["hub.a", "hub.b", "hub.c"])
        self.assertEqual(payload["snapshot"]["home"]["hidden"], ["hub.c"])

    def test_dashboard_home_client_validates_plan_and_apply_contracts(self):
        node = r"""
global.window = {};
require(process.argv[1]);
const api = window.ACPPlexampBrowserPreferences;
const goodPlan = api.validatePlan({
  schema_version: 1,
  status: 'ready',
  read_only: true,
  restore_available: true,
  change_count: 2,
  order_changed: true,
  hidden_change_count: 1,
  missing_item_count: 1,
  target_only_item_count: 1,
  target_known_item_count: 3,
  target_fingerprint: '1234abcd',
});
const badPlan = api.validatePlan({
  schema_version: 1,
  status: 'ready',
  read_only: false,
  restore_available: true,
  change_count: 2,
  order_changed: true,
  hidden_change_count: 1,
  missing_item_count: 1,
  target_only_item_count: 1,
  target_known_item_count: 3,
  target_fingerprint: '1234abcd',
});
const goodApply = api.validateApply({
  schema_version: 1,
  status: 'applied',
  applied: true,
  rolled_back: false,
  applied_change_count: 2,
  missing_item_count: 1,
  target_only_item_count: 1,
  target_fingerprint: '89abcdef',
});
process.stdout.write(JSON.stringify({ goodPlan, badPlan, goodApply }));
"""
        result = subprocess.run(
            ["node", "-e", node, str(DASHBOARD_BRIDGE)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["goodPlan"]["restore_available"])
        self.assertIsNone(payload["badPlan"])
        self.assertTrue(payload["goodApply"]["applied"])
        self.assertEqual(payload["goodApply"]["applied_change_count"], 2)

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
