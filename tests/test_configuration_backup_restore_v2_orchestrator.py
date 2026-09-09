from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "app" / "static" / "js" / "settings-backup-restore-v2.js"
SETTINGS_TEMPLATE = ROOT / "app" / "templates" / "settings.html"
BASE_TEMPLATE = ROOT / "app" / "templates" / "base.html"


class ConfigurationBackupRestoreV2OrchestratorTests(unittest.TestCase):
    def run_node(self, body: str) -> dict:
        script = f"""
const v2 = require('./app/static/js/settings-backup-restore-v2.js');

function serverBackup() {{
  return {{
    schema_version: 1,
    created_at: '2026-09-09T22:00:00+01:00',
    source: {{ application: 'A Clockwork Plex', app_version: '0.4.0', release_tag: 'v0.4.0' }},
    a_clockwork_plex: {{
      settings: {{ dashboard: {{ idle_timeout_seconds: 180 }}, display: {{}}, weather: {{}}, alarms: {{}}, airplay: {{}} }},
      audio: {{ eq: {{ enabled: true, bands: {{ bass: 0, mid: 0, treble: 0 }} }}, mixer: {{ master: 100 }} }},
    }},
    plexamp: {{
      source_version: '4.13.2',
      headless_preferences: {{ cacheSize: 32768, autoPlayEnabled: false }},
    }},
    export_report: {{
      warnings: [
        'Plexamp Settings directory is unavailable.',
        'Plexamp preference cacheSize was skipped: test-only warning',
        'Persistent mixer levels were skipped: retained warning',
      ],
      omitted: [
        {{ section: 'plexamp.browser_preferences', reason: 'legacy browser omission' }},
        {{ section: 'credentials', reason: 'credentials are deliberately excluded' }},
      ],
    }},
  }};
}}

function nativeSnapshot() {{
  return {{
    schema_version: 1,
    status: 'ready',
    read_only: true,
    settings_schema_fingerprint: 'deadbeef',
    portable_key_count: 9,
    saved_setting_count: 2,
    settings: {{ cacheSize: 65536, nestedPortable: {{ mode: 'portable' }} }},
  }};
}}

function homeSnapshot() {{
  return {{
    schema_version: 2,
    status: 'ready',
    read_only: true,
    target_fingerprint: 'cafebabe',
    home: {{
      schema_version: 2,
      order: [{{ type: 'custom', ref: 'custom-1' }}, {{ type: 'builtin', id: 'music.recent.added' }}],
      hidden: [{{ type: 'builtin', id: 'music.recent.plays' }}],
      presentation: [
        {{ target: {{ type: 'custom', ref: 'custom-1' }}, settings: {{ title: 'Portable artist section', type: 'carousel', size: 180 }} }},
      ],
      custom_sections: [{{ ref: 'custom-1', kind: 'artist', query_suffix: '/all?type=8' }}],
    }},
  }};
}}

function completeBackup() {{
  return v2.assembleBackupV2(serverBackup(), nativeSnapshot(), homeSnapshot());
}}

function plans(nativeChanges = 2, homeChanges = 1) {{
  return {{
    ok: true,
    schema_version: 2,
    status: 'ready',
    desired: v2.v2DesiredFromBackup(completeBackup()),
    native_plan: {{
      schema_version: 1,
      status: 'ready',
      read_only: true,
      restore_available: nativeChanges > 0,
      change_count: nativeChanges,
      changed_keys: nativeChanges ? ['cacheSize'] : [],
      settings_schema_fingerprint: 'deadbeef',
      target_fingerprint: '11111111',
    }},
    home_plan: {{
      schema_version: 2,
      status: 'ready',
      read_only: true,
      restore_available: homeChanges > 0,
      change_count: homeChanges > 0 ? 1 : 0,
      current_record_count: 0,
      target_fingerprint: '22222222',
    }},
    native_change_count: nativeChanges,
    home_change_count: homeChanges > 0 ? 1 : 0,
    change_count: nativeChanges + (homeChanges > 0 ? 1 : 0),
  }};
}}

function clients(log, overrides = {{}}) {{
  const native = {{
    async plan() {{ log.push('native.plan'); return plans().native_plan; }},
    async apply() {{
      log.push('native.apply');
      return {{ schema_version: 1, status: 'applied', applied: true, rolled_back: false, applied_change_count: 2, target_fingerprint: '33333333', rollback_token: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' }};
    }},
    async rollback() {{ log.push('native.rollback'); return {{ schema_version: 1, status: 'rolled-back', rolled_back: true, verified: true }}; }},
    async finalize() {{ log.push('native.finalize'); return {{ schema_version: 1, status: 'finalized', finalized: true }}; }},
    ...(overrides.native || {{}}),
  }};
  const home = {{
    async plan() {{ log.push('home.plan'); return plans().home_plan; }},
    async apply() {{
      log.push('home.apply');
      return {{ schema_version: 2, status: 'applied', applied: true, rolled_back: false, applied_change_count: 1, target_fingerprint: '44444444', rollback_token: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' }};
    }},
    async rollback() {{ log.push('home.rollback'); return {{ schema_version: 2, status: 'rolled-back', rolled_back: true, verified: true }}; }},
    async finalize() {{ log.push('home.finalize'); return {{ schema_version: 2, status: 'finalized', finalized: true }}; }},
    ...(overrides.home || {{}}),
  }};
  return {{ native, home }};
}}

{body}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_orchestrator_has_valid_javascript_syntax_and_remains_dormant(self):
        result = subprocess.run(
            ["node", "--check", str(ORCHESTRATOR)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertNotIn("settings-backup-restore-v2.js", SETTINGS_TEMPLATE.read_text(encoding="utf-8"))
        self.assertNotIn("settings-backup-restore-v2.js", BASE_TEMPLATE.read_text(encoding="utf-8"))

    def test_schema_v2_assembly_replaces_legacy_plexamp_owner_without_leaking_target_fingerprint(self):
        payload = self.run_node(
            r"""
const backup = completeBackup();
console.log(JSON.stringify({ backup }));
"""
        )
        backup = payload["backup"]
        self.assertEqual(backup["schema_version"], 2)
        self.assertEqual(backup["plexamp"]["source_version"], "4.13.2")
        self.assertNotIn("headless_preferences", backup["plexamp"])
        self.assertEqual(
            backup["plexamp"]["portable_settings"],
            {
                "schema_version": 1,
                "settings_schema_fingerprint": "deadbeef",
                "settings": {
                    "cacheSize": 65536,
                    "nestedPortable": {"mode": "portable"},
                },
            },
        )
        self.assertEqual(backup["plexamp"]["browser_preferences"]["schema_version"], 2)
        self.assertEqual(backup["plexamp"]["browser_preferences"]["home"]["schema_version"], 2)

        encoded = json.dumps(backup, sort_keys=True)
        self.assertNotIn("cafebabe", encoded)
        self.assertNotIn("legacy browser omission", encoded)
        self.assertNotIn("Plexamp Settings directory is unavailable", encoded)
        self.assertNotIn("Plexamp preference cacheSize", encoded)
        self.assertIn("Persistent mixer levels were skipped", encoded)
        self.assertIn("credentials are deliberately excluded", encoded)

    def test_browser_preview_is_read_only_and_combines_native_and_home_counts(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log);
  const preview = await v2.previewBrowserOwners(completeBackup(), pair.native, pair.home);
  console.log(JSON.stringify({ preview, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertTrue(payload["preview"]["ok"])
        self.assertEqual(payload["preview"]["status"], "ready")
        self.assertEqual(payload["preview"]["native_change_count"], 2)
        self.assertEqual(payload["preview"]["home_change_count"], 1)
        self.assertEqual(payload["preview"]["change_count"], 3)
        self.assertCountEqual(payload["log"], ["native.plan", "home.plan"])
        self.assertNotIn("apply", " ".join(payload["log"]))

    def test_success_applies_native_then_home_then_server_and_finalizes_only_after_server(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log);
  const result = await v2.runRestoreTransaction({
    backup: completeBackup(),
    browserPreview: plans(),
    nativeClient: pair.native,
    homeClient: pair.home,
    serverApply: async () => { log.push('server.apply'); return { ok: true, server_applied_change_count: 4 }; },
  });
  console.log(JSON.stringify({ result, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertTrue(payload["result"]["ok"])
        self.assertEqual(payload["result"]["status"], "applied")
        self.assertEqual(payload["result"]["browser_applied_change_count"], 3)
        self.assertTrue(payload["result"]["finalization"]["all_finalized"])
        self.assertEqual(payload["result"]["warnings"], [])
        self.assertEqual(
            payload["log"],
            [
                "native.apply",
                "home.apply",
                "server.apply",
                "home.finalize",
                "native.finalize",
            ],
        )

    def test_late_server_failure_rolls_home_then_native_back_in_reverse_order(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log);
  const result = await v2.runRestoreTransaction({
    backup: completeBackup(),
    browserPreview: plans(),
    nativeClient: pair.native,
    homeClient: pair.home,
    serverApply: async () => {
      log.push('server.apply');
      const error = new Error('injected server failure');
      error.owner = 'A Clockwork Plex';
      error.ownerRolledBack = true;
      throw error;
    },
  });
  console.log(JSON.stringify({ result, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertFalse(payload["result"]["ok"])
        self.assertEqual(payload["result"]["status"], "apply-failed")
        self.assertTrue(payload["result"]["browser_rollback"]["all_verified"])
        self.assertTrue(payload["result"]["owner_self_rolled_back"])
        self.assertEqual(
            payload["log"],
            [
                "native.apply",
                "home.apply",
                "server.apply",
                "home.rollback",
                "native.rollback",
            ],
        )
        self.assertNotIn("finalize", " ".join(payload["log"]))

    def test_home_failure_after_native_apply_rolls_native_back_and_never_enters_server(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log, {
    home: {
      async apply() {
        log.push('home.apply');
        return { schema_version: 2, status: 'apply-failed', applied: false, rolled_back: true };
      },
    },
  });
  const result = await v2.runRestoreTransaction({
    backup: completeBackup(),
    browserPreview: plans(),
    nativeClient: pair.native,
    homeClient: pair.home,
    serverApply: async () => { log.push('server.apply'); return { ok: true }; },
  });
  console.log(JSON.stringify({ result, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertFalse(payload["result"]["ok"])
        self.assertTrue(payload["result"]["owner_self_rolled_back"])
        self.assertTrue(payload["result"]["browser_rollback"]["all_verified"])
        self.assertEqual(payload["log"], ["native.apply", "home.apply", "native.rollback"])

    def test_stale_home_after_native_apply_rolls_native_back_and_requires_fresh_preview(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log, {
    home: {
      async apply() {
        log.push('home.apply');
        return { schema_version: 2, status: 'stale-target', applied: false, rolled_back: false, fresh_preview_required: true };
      },
    },
  });
  const result = await v2.runRestoreTransaction({
    backup: completeBackup(),
    browserPreview: plans(),
    nativeClient: pair.native,
    homeClient: pair.home,
    serverApply: async () => { log.push('server.apply'); return { ok: true }; },
  });
  console.log(JSON.stringify({ result, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertFalse(payload["result"]["ok"])
        self.assertEqual(payload["result"]["status"], "stale-target")
        self.assertTrue(payload["result"]["fresh_preview_required"])
        self.assertTrue(payload["result"]["browser_rollback"]["all_verified"])
        self.assertEqual(payload["log"], ["native.apply", "home.apply", "native.rollback"])

    def test_browser_only_restore_commits_without_calling_server(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log);
  const result = await v2.runRestoreTransaction({
    backup: completeBackup(),
    browserPreview: plans(),
    nativeClient: pair.native,
    homeClient: pair.home,
    serverApply: null,
  });
  console.log(JSON.stringify({ result, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertTrue(payload["result"]["ok"])
        self.assertIsNone(payload["result"]["server_result"])
        self.assertEqual(
            payload["log"],
            ["native.apply", "home.apply", "home.finalize", "native.finalize"],
        )

    def test_finalize_failure_does_not_relabel_a_verified_restore_as_failed(self):
        payload = self.run_node(
            r"""
(async () => {
  const log = [];
  const pair = clients(log, {
    home: {
      async finalize() {
        log.push('home.finalize');
        return { schema_version: 2, status: 'rollback-unavailable', finalized: false };
      },
    },
  });
  const result = await v2.runRestoreTransaction({
    backup: completeBackup(),
    browserPreview: plans(),
    nativeClient: pair.native,
    homeClient: pair.home,
    serverApply: async () => { log.push('server.apply'); return { ok: true }; },
  });
  console.log(JSON.stringify({ result, log }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        )
        self.assertTrue(payload["result"]["ok"])
        self.assertFalse(payload["result"]["finalization"]["all_finalized"])
        self.assertEqual(len(payload["result"]["warnings"]), 1)
        self.assertEqual(
            payload["log"],
            ["native.apply", "home.apply", "server.apply", "home.finalize", "native.finalize"],
        )


if __name__ == "__main__":
    unittest.main()
