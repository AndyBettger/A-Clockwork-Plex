from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "browser" / "plexamp-bridge" / "home-portability-v2.js"
MANIFEST = ROOT / "browser" / "plexamp-bridge" / "manifest.json"


class PlexampHomePortabilityV2Tests(unittest.TestCase):
    def run_node(self, body: str) -> dict:
        script = f"""
const owner = require('./browser/plexamp-bridge/home-portability-v2.js');

class FakeStorage {{
  constructor(initial = {{}}) {{
    this.map = new Map(Object.entries(initial));
  }}
  get length() {{ return this.map.size; }}
  key(index) {{ return Array.from(this.map.keys())[index] ?? null; }}
  getItem(key) {{ return this.map.has(key) ? this.map.get(key) : null; }}
  setItem(key, value) {{ this.map.set(String(key), String(value)); }}
  removeItem(key) {{ this.map.delete(String(key)); }}
  dump() {{ return Object.fromEntries(Array.from(this.map.entries()).sort(([a], [b]) => a.localeCompare(b))); }}
}}

function rootStore(server, section, premium = true) {{
  return {{
    app: {{ server, library: `/library/sections/${{section}}` }},
    settings: {{ premium }},
  }};
}}

function write(storage, key, value) {{
  const raw = owner.encodeMmkv(value);
  if (raw === null) throw new Error(`Could not encode ${{key}}`);
  storage.setItem(key, raw);
}}

function mixedSource() {{
  const root = rootStore('srvSourceABC123', 9, true);
  const scope = owner.deriveTargetScope(root);
  const storage = new FakeStorage();
  const custom1 = 'custom.hub.artist.ffffffff-ffff-4fff-8fff-ffffffffffff';
  const custom2 = 'custom.hub.album.11111111-1111-4111-8111-111111111111';

  write(storage, `${{scope.structureBaseKey}}:customHubs`, [
    {{
      key: '/library/sections/9/all?type=8',
      hubIdentifier: custom1,
      source: scope.structureContext,
    }},
    {{
      key: '/library/sections/9/all?type=9',
      hubIdentifier: custom2,
      source: scope.structureContext,
    }},
  ]);
  write(storage, `${{scope.structureBaseKey}}:order`, [
    custom1,
    'music.recent.plays',
    custom2,
    'music.recent.added',
  ]);
  write(storage, `${{scope.structureBaseKey}}:music.recent.plays:hidden`, true);
  write(storage, `${{scope.presentationBaseKey}}:music.recent.added:viewSettings`, {{
    type: 'carousel',
    subtype: 'block',
    size: 180,
  }});
  write(storage, `${{scope.presentationBaseKey}}:${{custom1}}:viewSettings`, {{
    title: 'ACP Artist Section',
    type: 'carousel',
    size: 180,
  }});
  write(storage, `${{scope.presentationBaseKey}}:${{custom2}}:viewSettings`, {{
    title: 'ACP Album Section',
    type: 'grid',
    size: 220,
  }});

  return {{ root, scope, storage, custom1, custom2 }};
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

    def test_owner_has_valid_javascript_syntax_and_is_production_activated(self):
        result = subprocess.run(
            ["node", "--check", str(OWNER)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.5.0")
        self.assertIn("portability.js", manifest["content_scripts"][0]["js"])
        resources = {
            name
            for block in manifest["web_accessible_resources"]
            for name in block["resources"]
        }
        self.assertIn("home-portability-v2.js", resources)

        source = OWNER.read_text(encoding="utf-8")
        self.assertNotIn("localStorage.clear", source)
        self.assertNotIn("Runtime.evaluate", source)
        self.assertNotIn("remote-debugging", source)

    def test_clean_post_reset_target_derives_two_roles_without_storage_records(self):
        payload = self.run_node(
            r"""
const root = rootStore('srvTargetXYZ789', 42, true);
const storage = new FakeStorage();
const scope = owner.deriveTargetScope(root);
const snapshot = owner.buildPortableSnapshot(storage, root);
console.log(JSON.stringify({ scope, snapshot }));
"""
        )
        scope = payload["scope"]
        self.assertEqual(scope["section"], "42")
        self.assertEqual(scope["structureContext"], "srvTargetXYZ789")
        self.assertEqual(
            scope["presentationContext"],
            "discovery:customizations:srvTargetXYZ789",
        )
        self.assertEqual(
            scope["structureBaseKey"],
            "mmkv.default\\discovery:customizations:srvTargetXYZ789::/library/sections/42",
        )
        self.assertEqual(
            scope["presentationBaseKey"],
            "mmkv.default\\discovery:customizations:discovery:customizations:srvTargetXYZ789::/library/sections/42",
        )

        snapshot = payload["snapshot"]
        self.assertEqual(snapshot["status"], "ready")
        self.assertTrue(snapshot["read_only"])
        self.assertRegex(snapshot["target_fingerprint"], r"^[a-f0-9]{8}$")
        self.assertEqual(
            snapshot["home"],
            {
                "schema_version": 2,
                "order": [],
                "hidden": [],
                "presentation": [],
                "custom_sections": [],
            },
        )

    def test_mmkv_wrapper_is_exact_single_underscore_contract(self):
        payload = self.run_node(
            r"""
console.log(JSON.stringify({
  encoded: owner.encodeMmkv({ value: 1 }),
  valid: owner.decodeMmkv('{"_":{"value":1}}'),
  wrongName: owner.decodeMmkv('{"x":{"value":1}}'),
  extra: owner.decodeMmkv('{"_":{"value":1},"x":2}'),
  scalarOuter: owner.decodeMmkv('true'),
}));
"""
        )
        self.assertEqual(payload["encoded"], '{"_":{"value":1}}')
        self.assertEqual(payload["valid"], {"ok": True, "value": {"value": 1}})
        self.assertFalse(payload["wrongName"]["ok"])
        self.assertFalse(payload["extra"]["ok"])
        self.assertFalse(payload["scalarOuter"]["ok"])

    def test_portable_custom_query_cannot_embed_source_library_path(self):
        payload = self.run_node(
            r"""
function portableHome(querySuffix) {
  return {
    schema_version: 2,
    order: [{ type: 'custom', ref: 'custom-1' }],
    hidden: [],
    presentation: [{
      target: { type: 'custom', ref: 'custom-1' },
      settings: { title: 'Portable artist section', type: 'carousel', size: 180 },
    }],
    custom_sections: [{ ref: 'custom-1', kind: 'artist', query_suffix: querySuffix }],
  };
}

const root = rootStore('srvTargetXYZ789', 42, true);
const storage = new FakeStorage();
const before = storage.dump();
const relative = portableHome('/all?type=8');
const sourceBound = portableHome('/library/sections/9/all?type=8');
const validRelative = owner.validatePortableHome(relative);
const rejectedSourceBound = owner.validatePortableHome(sourceBound);
const plan = owner.buildRestorePlan(storage, root, sourceBound);
const materialized = owner.materializePortableHome(
  sourceBound,
  root,
  () => '22222222-2222-4222-8222-222222222222',
);
console.log(JSON.stringify({
  validRelative,
  rejectedSourceBound,
  plan,
  materialized,
  before,
  after: storage.dump(),
}));
"""
        )
        self.assertIsNotNone(payload["validRelative"])
        self.assertIsNone(payload["rejectedSourceBound"])
        self.assertEqual(payload["plan"]["status"], "invalid-request")
        self.assertFalse(payload["plan"]["restore_available"])
        self.assertEqual(payload["materialized"]["status"], "invalid-request")
        self.assertEqual(payload["after"], payload["before"])

    def test_mixed_source_exports_only_logical_home_and_canonical_custom_refs(self):
        payload = self.run_node(
            r"""
const source = mixedSource();
const snapshot = owner.buildPortableSnapshot(source.storage, source.root);
console.log(JSON.stringify({ snapshot }));
"""
        )
        snapshot = payload["snapshot"]
        self.assertEqual(snapshot["status"], "ready")
        home = snapshot["home"]

        self.assertEqual(
            home["custom_sections"],
            [
                {"ref": "custom-1", "kind": "artist", "query_suffix": "/all?type=8"},
                {"ref": "custom-2", "kind": "album", "query_suffix": "/all?type=9"},
            ],
        )
        self.assertEqual(
            home["order"],
            [
                {"type": "custom", "ref": "custom-1"},
                {"type": "builtin", "id": "music.recent.plays"},
                {"type": "custom", "ref": "custom-2"},
                {"type": "builtin", "id": "music.recent.added"},
            ],
        )
        self.assertEqual(home["hidden"], [{"type": "builtin", "id": "music.recent.plays"}])

        custom_presentations = {
            row["target"]["ref"]: row["settings"]
            for row in home["presentation"]
            if row["target"]["type"] == "custom"
        }
        self.assertEqual(custom_presentations["custom-1"]["title"], "ACP Artist Section")
        self.assertEqual(custom_presentations["custom-2"]["title"], "ACP Album Section")

        portable_text = json.dumps(home, sort_keys=True)
        self.assertNotIn("srvSourceABC123", portable_text)
        self.assertNotIn("/library/sections/9", portable_text)
        self.assertNotIn("ffffffff-ffff-4fff-8fff-ffffffffffff", portable_text)
        self.assertNotIn("11111111-1111-4111-8111-111111111111", portable_text)
        self.assertNotIn("mmkv.default", portable_text)

    def test_materialization_remaps_context_library_and_generated_ids(self):
        payload = self.run_node(
            r"""
const source = mixedSource();
const desired = owner.buildPortableSnapshot(source.storage, source.root).home;
const target = rootStore('srvTargetXYZ789', 42, true);
const uuids = [
  '22222222-2222-4222-8222-222222222222',
  'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
];
const materialized = owner.materializePortableHome(desired, target, () => uuids.shift());
console.log(JSON.stringify({ materialized }));
"""
        )
        materialized = payload["materialized"]
        self.assertEqual(materialized["status"], "ready")
        records = materialized["records"]
        text = json.dumps(records, sort_keys=True)

        self.assertIn("srvTargetXYZ789", text)
        self.assertIn("/library/sections/42", text)
        self.assertIn("22222222-2222-4222-8222-222222222222", text)
        self.assertIn("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", text)
        self.assertNotIn("srvSourceABC123", text)
        self.assertNotIn("/library/sections/9", text)
        self.assertNotIn("ffffffff-ffff-4fff-8fff-ffffffffffff", text)
        self.assertNotIn("11111111-1111-4111-8111-111111111111", text)

        custom_record = next(record for record in records if record["key"].endswith(":customHubs"))
        custom_items = json.loads(custom_record["raw"])["_"]
        self.assertEqual(custom_items[0]["source"], "srvTargetXYZ789")
        self.assertEqual(custom_items[0]["key"], "/library/sections/42/all?type=8")
        self.assertEqual(custom_items[1]["key"], "/library/sections/42/all?type=9")

        presentation_keys = [record["key"] for record in records if record["key"].endswith(":viewSettings")]
        self.assertTrue(presentation_keys)
        self.assertTrue(
            all(
                "mmkv.default\\discovery:customizations:discovery:customizations:srvTargetXYZ789::/library/sections/42:"
                in key
                for key in presentation_keys
            )
        )

    def test_clean_target_apply_verifies_logically_despite_fresh_uuid_remap_and_rolls_back_empty(self):
        payload = self.run_node(
            r"""
const source = mixedSource();
const desired = owner.buildPortableSnapshot(source.storage, source.root).home;
const targetRoot = rootStore('srvTargetXYZ789', 42, true);
const targetStorage = new FakeStorage();
const before = owner.buildPortableSnapshot(targetStorage, targetRoot);
const plan = owner.buildRestorePlan(targetStorage, targetRoot, desired);
const uuids = [
  'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  '22222222-2222-4222-8222-222222222222',
];
const applied = owner.applyPortableHome(
  targetStorage,
  targetRoot,
  desired,
  plan.target_fingerprint,
  true,
  () => uuids.shift(),
);
const afterApply = owner.buildPortableSnapshot(targetStorage, targetRoot);
const rawAfterApply = targetStorage.dump();
const rolledBack = owner.rollbackPortableHome(applied.rollback_token, true);
const afterRollback = owner.buildPortableSnapshot(targetStorage, targetRoot);
console.log(JSON.stringify({
  before,
  plan,
  applied,
  afterApply,
  rawAfterApply,
  rolledBack,
  afterRollback,
  rawAfterRollback: targetStorage.dump(),
}));
"""
        )
        self.assertEqual(payload["before"]["status"], "ready")
        self.assertTrue(payload["plan"]["restore_available"])
        self.assertEqual(payload["applied"]["status"], "applied")
        self.assertTrue(payload["applied"]["applied"])
        self.assertEqual(payload["afterApply"]["status"], "ready")

        source_home = self.run_node(
            r"""
const source = mixedSource();
console.log(JSON.stringify({ home: owner.buildPortableSnapshot(source.storage, source.root).home }));
"""
        )["home"]
        self.assertEqual(payload["afterApply"]["home"], source_home)
        self.assertTrue(payload["rawAfterApply"])

        self.assertTrue(payload["rolledBack"]["rolled_back"])
        self.assertTrue(payload["rolledBack"]["verified"])
        self.assertEqual(payload["afterRollback"]["home"], payload["before"]["home"])
        self.assertEqual(payload["rawAfterRollback"], {})
        self.assertEqual(
            payload["afterRollback"]["target_fingerprint"],
            payload["before"]["target_fingerprint"],
        )

    def test_existing_target_round_trips_exact_raw_records(self):
        payload = self.run_node(
            r"""
const source = mixedSource();
const desired = owner.buildPortableSnapshot(source.storage, source.root).home;
const root = rootStore('srvTargetXYZ789', 42, true);
const scope = owner.deriveTargetScope(root);
const storage = new FakeStorage();
write(storage, `${scope.structureBaseKey}:order`, ['music.recent.added', 'music.recent.plays']);
write(storage, `${scope.structureBaseKey}:music.recent.added:hidden`, true);
write(storage, `${scope.presentationBaseKey}:music.recent.plays:viewSettings`, { type: 'grid', size: 123 });
const exactBefore = storage.dump();
const plan = owner.buildRestorePlan(storage, root, desired);
const uuids = [
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
];
const applied = owner.applyPortableHome(storage, root, desired, plan.target_fingerprint, true, () => uuids.shift());
const rolledBack = owner.rollbackPortableHome(applied.rollback_token, true);
console.log(JSON.stringify({ applied, rolledBack, exactBefore, exactAfter: storage.dump() }));
"""
        )
        self.assertTrue(payload["applied"]["applied"])
        self.assertTrue(payload["rolledBack"]["rolled_back"])
        self.assertTrue(payload["rolledBack"]["verified"])
        self.assertEqual(payload["exactAfter"], payload["exactBefore"])

    def test_stale_apply_and_stale_rollback_refuse_without_collateral_mutation(self):
        payload = self.run_node(
            r"""
const source = mixedSource();
const desired = owner.buildPortableSnapshot(source.storage, source.root).home;
const root = rootStore('srvTargetXYZ789', 42, true);
const scope = owner.deriveTargetScope(root);

const staleApplyStorage = new FakeStorage();
const stalePlan = owner.buildRestorePlan(staleApplyStorage, root, desired);
write(staleApplyStorage, `${scope.structureBaseKey}:order`, ['music.recent.plays']);
const beforeStaleApply = staleApplyStorage.dump();
const staleApply = owner.applyPortableHome(
  staleApplyStorage,
  root,
  desired,
  stalePlan.target_fingerprint,
  true,
  () => '55555555-5555-4555-8555-555555555555',
);

const rollbackStorage = new FakeStorage();
const plan = owner.buildRestorePlan(rollbackStorage, root, desired);
const uuids = [
  '66666666-6666-4666-8666-666666666666',
  '77777777-7777-4777-8777-777777777777',
];
const applied = owner.applyPortableHome(rollbackStorage, root, desired, plan.target_fingerprint, true, () => uuids.shift());
write(rollbackStorage, `${scope.structureBaseKey}:music.extra:hidden`, true);
const beforeStaleRollback = rollbackStorage.dump();
const staleRollback = owner.rollbackPortableHome(applied.rollback_token, true);

console.log(JSON.stringify({
  staleApply,
  beforeStaleApply,
  afterStaleApply: staleApplyStorage.dump(),
  staleRollback,
  beforeStaleRollback,
  afterStaleRollback: rollbackStorage.dump(),
}));
"""
        )
        self.assertEqual(payload["staleApply"]["status"], "stale-target")
        self.assertFalse(payload["staleApply"]["applied"])
        self.assertEqual(payload["afterStaleApply"], payload["beforeStaleApply"])

        self.assertEqual(payload["staleRollback"]["status"], "rollback-stale-target")
        self.assertFalse(payload["staleRollback"]["rolled_back"])
        self.assertEqual(payload["afterStaleRollback"], payload["beforeStaleRollback"])

    def test_fail_closed_storage_classification_and_custom_bundle_validation(self):
        payload = self.run_node(
            r"""
function snapshotWith(writer) {
  const root = rootStore('srvTargetXYZ789', 42, true);
  const scope = owner.deriveTargetScope(root);
  const storage = new FakeStorage();
  writer(storage, scope);
  return owner.buildPortableSnapshot(storage, root);
}

const editing = snapshotWith((storage, scope) => {
  write(storage, `${scope.structureBaseKey}:music.recent.plays:editing`, true);
});
const unknown = snapshotWith((storage, scope) => {
  write(storage, `${scope.structureBaseKey}:music.recent.plays:mystery`, true);
});
const malformedWrapper = snapshotWith((storage, scope) => {
  storage.setItem(`${scope.structureBaseKey}:order`, JSON.stringify({ x: [] }));
});
const danglingCustom = snapshotWith((storage, scope) => {
  write(storage, `${scope.structureBaseKey}:order`, [
    'custom.hub.artist.88888888-8888-4888-8888-888888888888',
  ]);
});
const wrongSource = snapshotWith((storage, scope) => {
  const custom = 'custom.hub.artist.99999999-9999-4999-8999-999999999999';
  write(storage, `${scope.structureBaseKey}:customHubs`, [{
    key: '/library/sections/42/all?type=8',
    hubIdentifier: custom,
    source: 'some-other-context',
  }]);
  write(storage, `${scope.presentationBaseKey}:${custom}:viewSettings`, { title: 'Wrong source' });
});
const missingTitle = snapshotWith((storage, scope) => {
  const custom = 'custom.hub.artist.aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
  write(storage, `${scope.structureBaseKey}:customHubs`, [{
    key: '/library/sections/42/all?type=8',
    hubIdentifier: custom,
    source: scope.structureContext,
  }]);
  write(storage, `${scope.presentationBaseKey}:${custom}:viewSettings`, { type: 'carousel', size: 180 });
});

console.log(JSON.stringify({ editing, unknown, malformedWrapper, danglingCustom, wrongSource, missingTitle }));
"""
        )
        self.assertEqual(payload["editing"]["status"], "editing-active")
        self.assertEqual(payload["unknown"]["status"], "unclassified-customization-key")
        self.assertEqual(payload["malformedWrapper"]["status"], "unsupported-mmkv-wrapper")
        self.assertEqual(payload["danglingCustom"]["status"], "dangling-custom-reference")
        self.assertEqual(payload["wrongSource"]["status"], "unsupported-custom-hub-item")
        self.assertEqual(payload["missingTitle"]["status"], "custom-title-missing")

    def test_custom_sections_require_live_target_capability_but_capability_is_not_portable(self):
        payload = self.run_node(
            r"""
const source = mixedSource();
const sourceSnapshot = owner.buildPortableSnapshot(source.storage, source.root);
const targetRoot = rootStore('srvTargetXYZ789', 42, false);
const targetStorage = new FakeStorage();
const before = targetStorage.dump();
const plan = owner.buildRestorePlan(targetStorage, targetRoot, sourceSnapshot.home);
const materialized = owner.materializePortableHome(
  sourceSnapshot.home,
  targetRoot,
  () => 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
);
console.log(JSON.stringify({ sourceSnapshot, plan, materialized, before, after: targetStorage.dump() }));
"""
        )
        self.assertEqual(payload["sourceSnapshot"]["status"], "ready")
        portable_text = json.dumps(payload["sourceSnapshot"]["home"], sort_keys=True)
        self.assertNotIn("premium", portable_text.lower())
        self.assertEqual(payload["plan"]["status"], "custom-sections-capability-unavailable")
        self.assertFalse(payload["plan"]["restore_available"])
        self.assertEqual(payload["materialized"]["status"], "custom-sections-capability-unavailable")
        self.assertEqual(payload["after"], payload["before"])

    def test_target_scoped_recent_played_hub_is_logical_and_remapped(self):
        payload = self.run_node(
            r"""
const sourceRoot = rootStore('sourceServer0123456789abcdef', 9, true);
const sourceScope = owner.deriveTargetScope(sourceRoot);
const sourceStorage = new FakeStorage();
const sourceDynamic = `music.recent.played.${sourceScope.structureContext}./hubs/sections/${sourceScope.section}`;
write(sourceStorage, `${sourceScope.structureBaseKey}:order`, [
  'music.recent.added.',
  sourceDynamic,
  'music.mixes.',
]);
const snapshot = owner.buildPortableSnapshot(sourceStorage, sourceRoot);
const portableText = JSON.stringify(snapshot.home);

const targetRoot = rootStore('targetServerfedcba9876543210', 42, true);
const materialized = owner.materializePortableHome(snapshot.home, targetRoot);
const orderRecord = materialized.records.find((record) => record.key.endsWith(':order'));
const targetOrder = orderRecord ? JSON.parse(orderRecord.raw)._ : [];

const rawSourceBound = {
  ...snapshot.home,
  order: [{ type: 'builtin', id: sourceDynamic }],
};
const rejectedRaw = owner.validatePortableHome(rawSourceBound);

console.log(JSON.stringify({
  snapshot,
  portableText,
  materialized,
  targetOrder,
  rejectedRaw,
}));
"""
        )
        self.assertEqual(payload["snapshot"]["status"], "ready")
        self.assertEqual(
            payload["snapshot"]["home"]["order"],
            [
                {"type": "builtin", "id": "music.recent.added."},
                {"type": "builtin", "id": "target-library.music.recent.played"},
                {"type": "builtin", "id": "music.mixes."},
            ],
        )
        self.assertNotIn("sourceServer0123456789abcdef", payload["portableText"])
        self.assertNotIn("/hubs/sections/9", payload["portableText"])
        self.assertEqual(payload["materialized"]["status"], "ready")
        self.assertEqual(
            payload["targetOrder"],
            [
                "music.recent.added.",
                "music.recent.played.targetServerfedcba9876543210./hubs/sections/42",
                "music.mixes.",
            ],
        )
        self.assertIsNone(payload["rejectedRaw"])


if __name__ == "__main__":
    unittest.main()
