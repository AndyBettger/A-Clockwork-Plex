from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "browser" / "plexamp-bridge" / "native-portability.js"


class PlexampNativePortabilityTests(unittest.TestCase):
    def run_node(self, body: str) -> dict:
        script = f"""
const owner = require('./browser/plexamp-bridge/native-portability.js');

class FakeSettings {{
  constructor() {{
    this.audioConversionBitrate = 256;
    this.autoPlayEnabled = false;
    this.cacheSize = 32768;
    this.cachingWiFi = 10;
    this.loudnessLeveling = false;
    this.precacheNetworkSpeed = 0;
    this.sampleRateConversionQuality = 4;
    this.sampleRateMatching = 2;
    this.nestedPortable = {{ mode: 'normal', levels: [1, 2] }};

    this.playerName = 'Default player';
    this.audioDeviceUuid = 'default-device';
    this.premium = false;
    this.activeTab = 'home';
    this.equalizerPresets = [{{ name: 'Flat' }}];
    this.equalizerValues = {{ bass: 0 }};
    this.sessionToken = 'constructor-secret';
    this.opaqueRuntime = new Map([['runtime', true]]);
    this._resetCalls = 0;
  }}

  resetToDefaults() {{
    this._resetCalls += 1;
    this.playerName = 'MUTATED BY RESET';
    this.audioDeviceUuid = 'MUTATED BY RESET';
    this.activeTab = 'MUTATED BY RESET';
    this.equalizerPresets.splice(0);
    this.equalizerValues.bass = 99;
    this.sessionToken = 'MUTATED BY RESET';
    this.opaqueRuntime.clear();
  }}
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

    def test_owner_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", str(OWNER)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_apply_assigns_only_portable_keys_and_never_calls_global_reset(self):
        payload = self.run_node(
            r"""
const source = new FakeSettings();
source.cacheSize = 65536;
source.nestedPortable = { mode: 'source-choice', levels: [4, 5] };
const saved = owner.buildPortableSnapshot(source);

const target = new FakeSettings();
target.autoPlayEnabled = true;
target.cacheSize = 1024;
target.nestedPortable = { mode: 'target-choice', levels: [8, 9] };
target.playerName = 'Bedroom Plexamp';
target.audioDeviceUuid = 'bedroom-device';
target.premium = true;
target.activeTab = 'library';
target.equalizerPresets = [{ name: 'My EQ', values: [1, 2, 3] }];
target.equalizerValues = { bass: 3 };
target.sessionToken = 'keep-this-secret';
target.opaqueRuntime = new Map([['keep', 42]]);

const presetsRef = target.equalizerPresets;
const equalizerValuesRef = target.equalizerValues;
const opaqueRef = target.opaqueRuntime;
const plan = owner.buildPortablePlan(target, saved);
const beforeRollback = {
  autoPlayEnabled: target.autoPlayEnabled,
  cacheSize: target.cacheSize,
  nestedPortable: target.nestedPortable,
};
const applied = owner.applyPortableSettings(target, saved, plan.target_fingerprint, true);

const afterApply = {
  applied,
  autoPlayEnabled: target.autoPlayEnabled,
  cacheSize: target.cacheSize,
  nestedPortable: target.nestedPortable,
  playerName: target.playerName,
  audioDeviceUuid: target.audioDeviceUuid,
  premium: target.premium,
  activeTab: target.activeTab,
  equalizerPresets: target.equalizerPresets,
  equalizerValues: target.equalizerValues,
  sessionToken: target.sessionToken,
  opaqueRuntimeValue: target.opaqueRuntime.get('keep'),
  presetsIdentityPreserved: target.equalizerPresets === presetsRef,
  equalizerValuesIdentityPreserved: target.equalizerValues === equalizerValuesRef,
  opaqueIdentityPreserved: target.opaqueRuntime === opaqueRef,
  resetCalls: target._resetCalls,
};

const rolledBack = owner.rollbackPortableSettings(applied.rollback_token, true);
console.log(JSON.stringify({
  saved,
  plan,
  beforeRollback,
  afterApply,
  rolledBack,
  afterRollback: {
    autoPlayEnabled: target.autoPlayEnabled,
    cacheSize: target.cacheSize,
    nestedPortable: target.nestedPortable,
    playerName: target.playerName,
    activeTab: target.activeTab,
    equalizerPresets: target.equalizerPresets,
    sessionToken: target.sessionToken,
    opaqueRuntimeValue: target.opaqueRuntime.get('keep'),
    resetCalls: target._resetCalls,
  },
}));
"""
        )

        saved = payload["saved"]
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(saved["settings"]["cacheSize"], 65536)
        self.assertEqual(
            saved["settings"]["nestedPortable"],
            {"mode": "source-choice", "levels": [4, 5]},
        )
        self.assertNotIn("autoPlayEnabled", saved["settings"])
        for excluded in (
            "playerName",
            "audioDeviceUuid",
            "premium",
            "activeTab",
            "equalizerPresets",
            "equalizerValues",
            "sessionToken",
            "opaqueRuntime",
        ):
            self.assertNotIn(excluded, saved["settings"])

        self.assertTrue(payload["plan"]["restore_available"])
        after_apply = payload["afterApply"]
        self.assertTrue(after_apply["applied"]["applied"])

        # Omitted source-default values are actively returned to Plexamp's
        # constructor default, while saved deviations are restored exactly.
        self.assertFalse(after_apply["autoPlayEnabled"])
        self.assertEqual(after_apply["cacheSize"], 65536)
        self.assertEqual(
            after_apply["nestedPortable"],
            {"mode": "source-choice", "levels": [4, 5]},
        )

        # Non-portable state is not merely restored after a broad reset: it is
        # never touched by this owner in the first place.
        self.assertEqual(after_apply["playerName"], "Bedroom Plexamp")
        self.assertEqual(after_apply["audioDeviceUuid"], "bedroom-device")
        self.assertTrue(after_apply["premium"])
        self.assertEqual(after_apply["activeTab"], "library")
        self.assertEqual(after_apply["equalizerPresets"], [{"name": "My EQ", "values": [1, 2, 3]}])
        self.assertEqual(after_apply["equalizerValues"], {"bass": 3})
        self.assertEqual(after_apply["sessionToken"], "keep-this-secret")
        self.assertEqual(after_apply["opaqueRuntimeValue"], 42)
        self.assertTrue(after_apply["presetsIdentityPreserved"])
        self.assertTrue(after_apply["equalizerValuesIdentityPreserved"])
        self.assertTrue(after_apply["opaqueIdentityPreserved"])
        self.assertEqual(after_apply["resetCalls"], 0)

        self.assertTrue(payload["rolledBack"]["rolled_back"])
        self.assertTrue(payload["rolledBack"]["verified"])
        after_rollback = payload["afterRollback"]
        self.assertEqual(after_rollback["autoPlayEnabled"], payload["beforeRollback"]["autoPlayEnabled"])
        self.assertEqual(after_rollback["cacheSize"], payload["beforeRollback"]["cacheSize"])
        self.assertEqual(after_rollback["nestedPortable"], payload["beforeRollback"]["nestedPortable"])
        self.assertEqual(after_rollback["playerName"], "Bedroom Plexamp")
        self.assertEqual(after_rollback["activeTab"], "library")
        self.assertEqual(after_rollback["equalizerPresets"], [{"name": "My EQ", "values": [1, 2, 3]}])
        self.assertEqual(after_rollback["sessionToken"], "keep-this-secret")
        self.assertEqual(after_rollback["opaqueRuntimeValue"], 42)
        self.assertEqual(after_rollback["resetCalls"], 0)

    def test_stale_target_refuses_without_mutation(self):
        payload = self.run_node(
            r"""
const source = new FakeSettings();
source.cacheSize = 65536;
const saved = owner.buildPortableSnapshot(source);

const target = new FakeSettings();
target.cacheSize = 1024;
target.playerName = 'Do not touch';
const plan = owner.buildPortablePlan(target, saved);
target.cacheSize = 2048;
const result = owner.applyPortableSettings(target, saved, plan.target_fingerprint, true);
console.log(JSON.stringify({
  result,
  cacheSize: target.cacheSize,
  playerName: target.playerName,
  resetCalls: target._resetCalls,
}));
"""
        )
        self.assertEqual(payload["result"]["status"], "stale-target")
        self.assertFalse(payload["result"]["applied"])
        self.assertTrue(payload["result"]["fresh_preview_required"])
        self.assertEqual(payload["cacheSize"], 2048)
        self.assertEqual(payload["playerName"], "Do not touch")
        self.assertEqual(payload["resetCalls"], 0)

    def test_source_contains_no_global_reset_invocation(self):
        source = OWNER.read_text(encoding="utf-8")
        self.assertNotIn("settings.resetToDefaults()", source)
        self.assertNotIn("restoreNonPortable", source)
        self.assertIn("capturePortableSnapshot", source)
        self.assertIn("restorePortableSnapshot", source)


if __name__ == "__main__":
    unittest.main()
