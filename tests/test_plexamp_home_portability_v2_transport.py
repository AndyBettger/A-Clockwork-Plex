from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "browser" / "plexamp-bridge" / "home-portability-v2.js"
DASHBOARD_BRIDGE = ROOT / "app" / "static" / "js" / "plexamp-home-portability-v2-bridge.js"
PORTABILITY_LOADER = ROOT / "browser" / "plexamp-bridge" / "portability.js"
MANIFEST = ROOT / "browser" / "plexamp-bridge" / "manifest.json"


class PlexampHomePortabilityV2TransportTests(unittest.TestCase):
    def run_node(self, body: str) -> dict:
        result = subprocess.run(
            ["node", "-e", body],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_dashboard_and_page_world_transport_have_valid_javascript_syntax(self):
        for path in (OWNER, DASHBOARD_BRIDGE, PORTABILITY_LOADER):
            result = subprocess.run(
                ["node", "--check", str(path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_production_manifest_activates_complete_portability_transport(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.5.0")
        self.assertNotIn("permissions", manifest)
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("background", manifest)

        scripts = manifest["content_scripts"]
        self.assertEqual(len(scripts), 1)
        self.assertEqual(scripts[0]["js"], ["content.js", "reset.js", "portability.js"])
        self.assertEqual(
            set(scripts[0]["matches"]),
            {"http://localhost:32500/*", "http://127.0.0.1:32500/*"},
        )
        self.assertTrue(scripts[0]["all_frames"])

        resources = manifest["web_accessible_resources"]
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            set(resources[0]["resources"]),
            {"native-reset.js", "native-portability.js", "home-portability-v2.js"},
        )
        self.assertEqual(
            set(resources[0]["matches"]),
            {"http://localhost:32500/*", "http://127.0.0.1:32500/*"},
        )

        loader = PORTABILITY_LOADER.read_text(encoding="utf-8")
        self.assertIn("native-portability.js", loader)
        self.assertIn("home-portability-v2.js", loader)
        self.assertNotIn("eval(", loader)
        self.assertNotIn("remote-debugging", loader)

    def test_dashboard_validator_accepts_relative_home_and_rejects_source_bound_query(self):
        payload = self.run_node(
            r"""
const bridge = require('./app/static/js/plexamp-home-portability-v2-bridge.js');
const relative = {
  schema_version: 2,
  order: [{ type: 'custom', ref: 'custom-1' }],
  hidden: [],
  presentation: [{
    target: { type: 'custom', ref: 'custom-1' },
    settings: { title: 'Portable artist section', type: 'carousel', size: 180 },
  }],
  custom_sections: [{ ref: 'custom-1', kind: 'artist', query_suffix: '/all?type=8' }],
};
const sourceBound = JSON.parse(JSON.stringify(relative));
sourceBound.custom_sections[0].query_suffix = '/library/sections/9/all?type=8';
const validPlan = bridge.validatePlan({
  schema_version: 2,
  status: 'ready',
  read_only: true,
  restore_available: true,
  change_count: 1,
  current_record_count: 0,
  target_fingerprint: '1234abcd',
});
const validApply = bridge.validateApply({
  schema_version: 2,
  status: 'applied',
  applied: true,
  rolled_back: false,
  applied_change_count: 1,
  target_fingerprint: 'abcd1234',
  rollback_token: '0123456789abcdef0123456789abcdef',
});
console.log(JSON.stringify({
  relative: bridge.validateHome(relative),
  sourceBound: bridge.validateHome(sourceBound),
  validPlan,
  validApply,
}));
"""
        )
        self.assertIsNotNone(payload["relative"])
        self.assertIsNone(payload["sourceBound"])
        self.assertTrue(payload["validPlan"]["restore_available"])
        self.assertEqual(payload["validPlan"]["change_count"], 1)
        self.assertTrue(payload["validApply"]["applied"])
        self.assertRegex(payload["validApply"]["rollback_token"], r"^[a-f0-9]{32}$")

    def test_page_world_message_contract_round_trips_apply_rollback_and_finalize(self):
        payload = self.run_node(
            r"""
const owner = require('./browser/plexamp-bridge/home-portability-v2.js');

class FakeStorage {
  constructor() { this.map = new Map(); }
  get length() { return this.map.size; }
  key(index) { return Array.from(this.map.keys())[index] ?? null; }
  getItem(key) { return this.map.has(key) ? this.map.get(key) : null; }
  setItem(key, value) { this.map.set(String(key), String(value)); }
  removeItem(key) { this.map.delete(String(key)); }
  dump() { return Object.fromEntries(Array.from(this.map.entries()).sort(([a], [b]) => a.localeCompare(b))); }
}

const replies = [];
const parent = { postMessage(payload, origin) { replies.push({ payload, origin }); } };
let handler = null;
const storage = new FakeStorage();
const win = {
  parent,
  app: {
    rootStore: {
      app: { server: 'srvTargetXYZ789', library: '/library/sections/42' },
      settings: { premium: true },
    },
  },
  localStorage: storage,
  addEventListener(type, callback) { if (type === 'message') handler = callback; },
};
owner.install(win);
if (typeof handler !== 'function') throw new Error('message handler not installed');

function send(type, extra = {}, origin = 'http://localhost:8088', nonce = 'nonce-12345678') {
  const before = replies.length;
  handler({ source: parent, origin, data: { type, nonce, ...extra } });
  return replies.length > before ? replies.at(-1) : null;
}

const desired = {
  schema_version: 2,
  order: [{ type: 'builtin', id: 'music.recent.plays' }],
  hidden: [],
  presentation: [],
  custom_sections: [],
};

const blockedOrigin = send('acp-plexamp-home-portability-snapshot-request-v2', {}, 'https://example.com');
const blockedNonce = send('acp-plexamp-home-portability-snapshot-request-v2', {}, 'http://localhost:8088', 'short');
const snapshot = send('acp-plexamp-home-portability-snapshot-request-v2');
const plan = send('acp-plexamp-home-portability-plan-request-v2', { home: desired });
const applied = send('acp-plexamp-home-portability-apply-request-v2', {
  home: desired,
  target_fingerprint: plan.payload.result.target_fingerprint,
  confirm_restore: true,
});
const afterApply = storage.dump();
const rolledBack = send('acp-plexamp-home-portability-rollback-request-v2', {
  rollback_token: applied.payload.result.rollback_token,
  confirm_rollback: true,
});
const afterRollback = storage.dump();

const planAgain = send('acp-plexamp-home-portability-plan-request-v2', { home: desired });
const appliedAgain = send('acp-plexamp-home-portability-apply-request-v2', {
  home: desired,
  target_fingerprint: planAgain.payload.result.target_fingerprint,
  confirm_restore: true,
});
const finalized = send('acp-plexamp-home-portability-finalize-request-v2', {
  rollback_token: appliedAgain.payload.result.rollback_token,
});
const rollbackAfterFinalize = send('acp-plexamp-home-portability-rollback-request-v2', {
  rollback_token: appliedAgain.payload.result.rollback_token,
  confirm_rollback: true,
});

console.log(JSON.stringify({
  blockedOrigin,
  blockedNonce,
  snapshot,
  plan,
  applied,
  afterApply,
  rolledBack,
  afterRollback,
  finalized,
  rollbackAfterFinalize,
  replyCount: replies.length,
}));
"""
        )
        self.assertIsNone(payload["blockedOrigin"])
        self.assertIsNone(payload["blockedNonce"])
        self.assertEqual(payload["snapshot"]["origin"], "http://localhost:8088")
        self.assertEqual(payload["snapshot"]["payload"]["result"]["status"], "ready")
        self.assertTrue(payload["snapshot"]["payload"]["result"]["read_only"])

        plan = payload["plan"]["payload"]["result"]
        self.assertEqual(plan["status"], "ready")
        self.assertTrue(plan["restore_available"])
        self.assertEqual(plan["change_count"], 1)
        self.assertRegex(plan["target_fingerprint"], r"^[a-f0-9]{8}$")

        applied = payload["applied"]["payload"]["result"]
        self.assertEqual(applied["status"], "applied")
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["applied_change_count"], 1)
        self.assertRegex(applied["rollback_token"], r"^[a-f0-9]{32}$")
        self.assertTrue(payload["afterApply"])

        rolled_back = payload["rolledBack"]["payload"]["result"]
        self.assertEqual(rolled_back["status"], "rolled-back")
        self.assertTrue(rolled_back["rolled_back"])
        self.assertTrue(rolled_back["verified"])
        self.assertEqual(payload["afterRollback"], {})

        finalized = payload["finalized"]["payload"]["result"]
        self.assertEqual(finalized["status"], "finalized")
        self.assertTrue(finalized["finalized"])
        rollback_after_finalize = payload["rollbackAfterFinalize"]["payload"]["result"]
        self.assertEqual(rollback_after_finalize["status"], "rollback-unavailable")
        self.assertFalse(rollback_after_finalize["rolled_back"])

    def test_transport_has_no_broad_browser_or_network_authority(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (OWNER, DASHBOARD_BRIDGE, PORTABILITY_LOADER)
        )
        self.assertNotIn("localStorage.clear", combined)
        self.assertNotIn("Runtime.evaluate", combined)
        self.assertNotIn("remote-debugging", combined)
        self.assertNotIn("document.cookie", combined)
        self.assertNotIn("fetch(", DASHBOARD_BRIDGE.read_text(encoding="utf-8"))
        self.assertIn("http://localhost:8088", OWNER.read_text(encoding="utf-8"))
        self.assertIn("http://127.0.0.1:8088", OWNER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
