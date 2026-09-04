from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
DEPENDENCIES = ROOT / "installer" / "repository-dependencies.txt"
RESET_CLIENT = ROOT / "app" / "static" / "js" / "settings-reset-defaults.js"
RESET_CSS = ROOT / "app" / "static" / "css" / "settings-reset-defaults.css"
SETTINGS_ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"
HOME_CLIENT_BRIDGE = ROOT / "app" / "static" / "js" / "plexamp-home-reset-bridge.js"
NATIVE_CLIENT_BRIDGE = ROOT / "app" / "static" / "js" / "plexamp-native-reset-bridge.js"
HOME_EXTENSION = ROOT / "browser" / "plexamp-bridge" / "reset.js"
NATIVE_EXTENSION = ROOT / "browser" / "plexamp-bridge" / "native-reset.js"
BRIDGE_MANIFEST = ROOT / "browser" / "plexamp-bridge" / "manifest.json"


class PlexampCommissioningWiringTests(unittest.TestCase):
    def test_setup_commissions_player_baseline_and_audio_after_guarded_install(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("run_plexamp_commissioning", text)
        self.assertIn(
            'python3 "$REPO_ROOT/scripts/commission-plexamp.py" commission --home "$PROJECT_HOME"',
            text,
        )
        self.assertIn("claimed player name is recorded as this appliance's reset baseline", text)
        self.assertIn("managed audio output is verified", text)
        self.assertLess(text.index("run_guarded_installer"), text.index("run_plexamp_commissioning"))

    def test_fresh_install_dependency_closure_contains_commissioning_owner(self) -> None:
        text = DEPENDENCIES.read_text(encoding="utf-8")
        self.assertIn("app/plexamp_commissioning.py", text)
        self.assertIn("scripts/commission-plexamp.py", text)

    def test_new_commissioning_python_and_setup_shell_compile(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "py_compile",
                "app/plexamp_commissioning.py",
                "scripts/commission-plexamp.py",
                "app/configuration_reset.py",
                "app/runner.py",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        shell = subprocess.run(
            ["bash", "-n", "setup.sh"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(shell.returncode, 0, shell.stderr)

    def test_reset_client_integrates_native_home_and_commissioning_owners(self) -> None:
        text = RESET_CLIENT.read_text(encoding="utf-8")
        self.assertIn("A Clockwork Plex + managed Plexamp", text)
        self.assertIn("Plexamp settings + Home customisation", text)
        self.assertIn("player name will return to the name captured during appliance setup", text)
        self.assertIn("audio output will return to A Clockwork Plex - Plexamp", text)
        self.assertIn("Plexamp's own Reset to Defaults semantics", text)
        self.assertIn("Home order, visibility and custom sections are preserved", text)
        self.assertIn("per-section defaults", text)
        self.assertIn("ACPPlexampHomeReset", text)
        self.assertIn("ACPPlexampNativeReset", text)
        self.assertIn("rollbackBrowserOwners", text)
        self.assertIn("owner_tokens?.a_clockwork_plex", text)
        self.assertIn("plexamp_commissioning_change_count", text)
        self.assertNotIn("factory-baseline authority", text)

        manifest = BRIDGE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn('"version": "1.3.0"', manifest)
        self.assertIn('"js": ["content.js", "reset.js"]', manifest)
        self.assertIn('"web_accessible_resources"', manifest)
        self.assertIn('"resources": ["native-reset.js"]', manifest)
        self.assertNotIn('"world": "MAIN"', manifest)
        home_extension = HOME_EXTENSION.read_text(encoding="utf-8")
        self.assertIn("chrome.runtime.getURL('native-reset.js')", home_extension)
        self.assertIn("installNativeResetBridge(document)", home_extension)

        for script in (
            RESET_CLIENT,
            HOME_CLIENT_BRIDGE,
            NATIVE_CLIENT_BRIDGE,
            HOME_EXTENSION,
            NATIVE_EXTENSION,
        ):
            result = subprocess.run(
                ["node", "--check", str(script)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{script}: {result.stderr}")

    def test_native_plexamp_reset_uses_defaults_player_volume_and_retained_rollback(self) -> None:
        source = NATIVE_EXTENSION.read_text(encoding="utf-8")
        self.assertIn("global.app.rootStore", source)
        self.assertIn("win?.app?.rootStore?.settings", source)
        self.assertIn("changed_keys", source)
        self.assertIn("PLAYER_VOLUME_TARGET = 100", source)
        self.assertIn("/player/playback/setParameters", source)
        self.assertNotIn("webpackChunk", source)
        self.assertNotIn("PRESERVED_PORTABLE_HEADLESS_KEYS", source)
        self.assertNotIn("restoreProtectedHeadless", source)

        script = r"""
const bridge = require('./browser/plexamp-bridge/native-reset.js');

(async () => {
  const ordinaryHeadlessKeys = [
    'audioConversionBitrate',
    'autoPlayEnabled',
    'cacheSize',
    'cachingWiFi',
    'loudnessLeveling',
    'precacheNetworkSpeed',
    'sampleRateConversionQuality',
    'sampleRateMatching',
  ];

  class FakeSettings {
    constructor() {
      this.foo = 1;
      this.bar = 'default';
      this.playerName = 'Factory player';
      this.audioDeviceUuid = '';
      this.premium = true;
      this._source = 'library';
      this.audioConversionBitrate = 128;
      this.autoPlayEnabled = true;
      this.cacheSize = 4096;
      this.cachingWiFi = 1;
      this.loudnessLeveling = true;
      this.precacheNetworkSpeed = 100;
      this.sampleRateConversionQuality = 1;
      this.sampleRateMatching = 0;
    }
    resetToDefaults() {
      const defaults = new FakeSettings();
      for (const key of Object.keys(this)) {
        if (!key.startsWith('_') && key !== 'premium') this[key] = defaults[key];
      }
    }
  }

  class FakeTimeline {
    constructor(type, volume) { this.type = type; this.volume = volume; }
    getAttribute(name) { return name === 'type' ? this.type : name === 'volume' ? String(this.volume) : null; }
  }
  class FakeDocument {
    constructor(volume) { this.volume = volume; }
    getElementsByTagName(name) { return name === 'Timeline' ? [new FakeTimeline('music', this.volume)] : []; }
  }
  class FakeDOMParser {
    parseFromString(payload) {
      const match = String(payload).match(/volume="([0-9.]+)"/);
      return new FakeDocument(match ? Number(match[1]) : NaN);
    }
  }

  const settings = new FakeSettings();
  settings.foo = 9;
  settings.playerName = 'Bedroom Plexamp';
  settings.audioDeviceUuid = 'managed-output';
  const beforeHeadless = [256, false, 32768, 10, false, 0, 4, 2];
  ordinaryHeadlessKeys.forEach((key, index) => { settings[key] = beforeHeadless[index]; });

  let playerVolume = 87;
  const win = {
    app: { rootStore: { settings } },
    DOMParser: FakeDOMParser,
    setTimeout(callback) { callback(); },
    async fetch(url) {
      const text = String(url);
      if (text.startsWith('/player/timeline/poll?')) {
        return { ok: true, async text() { return `<MediaContainer><Timeline type="music" volume="${playerVolume}" /></MediaContainer>`; } };
      }
      if (text.startsWith('/player/playback/setParameters?')) {
        const parsed = new URL(text, 'http://localhost:32500');
        playerVolume = Number(parsed.searchParams.get('volume'));
        return { ok: true, async text() { return ''; } };
      }
      return { ok: false, async text() { return ''; } };
    },
  };

  const located = bridge.locateSettings(win);
  if (located !== settings) throw new Error('application-global Plexamp settings were not located');

  const plan = await bridge.planNativeReset(win, settings);
  if (plan.status !== 'ready' || plan.change_count !== 10 || !plan.reset_available || !plan.player_volume_changed) {
    throw new Error(`unexpected native plan ${JSON.stringify(plan)}`);
  }
  const expectedNames = new Set(['foo', ...ordinaryHeadlessKeys, 'playerVolume']);
  if (!Array.isArray(plan.changed_keys) || plan.changed_keys.length !== expectedNames.size) {
    throw new Error(`native changed-key diagnostics missing ${JSON.stringify(plan)}`);
  }
  for (const key of plan.changed_keys) {
    if (!expectedNames.has(key)) throw new Error(`unexpected native changed key ${key}`);
  }
  if (plan.changed_keys.includes('playerName') || plan.changed_keys.includes('audioDeviceUuid')) {
    throw new Error('commissioning-owned key leaked into native diagnostics');
  }

  const applied = await bridge.applyNativeReset(win, settings, plan.target_fingerprint, true);
  if (!applied.applied || applied.applied_change_count !== 10 || !applied.rollback_token) {
    throw new Error(`native reset failed ${JSON.stringify(applied)}`);
  }
  if (playerVolume !== 100) throw new Error(`Plexamp player volume did not reset to 100: ${playerVolume}`);
  if (settings.foo !== 1 || settings.playerName !== 'Factory player' || settings.audioDeviceUuid !== '') {
    throw new Error('native reset did not use Plexamp-style defaults');
  }
  const defaults = new FakeSettings();
  ordinaryHeadlessKeys.forEach((key) => {
    if (settings[key] !== defaults[key]) {
      throw new Error(`ordinary Headless preference did not reset with Plexamp: ${key}`);
    }
  });

  const rolled = await bridge.rollbackSettingsReset(applied.rollback_token, true);
  if (!rolled.rolled_back || !rolled.verified) {
    throw new Error(`native rollback failed ${JSON.stringify(rolled)}`);
  }
  if (playerVolume !== 87) throw new Error(`player-volume rollback did not restore 87: ${playerVolume}`);
  if (settings.foo !== 9 || settings.playerName !== 'Bedroom Plexamp' || settings.audioDeviceUuid !== 'managed-output') {
    throw new Error('native rollback did not restore exact commissioning values');
  }
  ordinaryHeadlessKeys.forEach((key, index) => {
    if (settings[key] !== beforeHeadless[index]) {
      throw new Error(`rollback did not restore Headless preference: ${key}`);
    }
  });
})().catch((error) => { console.error(error); process.exit(1); });
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_home_reset_resets_view_settings_but_preserves_home_structure(self) -> None:
        script = r"""
const bridge = require('./browser/plexamp-bridge/reset.js');

const builtInViewKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:hub.a:viewSettings';
const customViewKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:hub.custom:viewSettings';
const orderKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:order';
const hiddenKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:hub.a:hidden';
const editingKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:hub.a:editing';
const customHubKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:customHubs';
const authKey = 'mmkv.default\\authToken';
const cacheKey = 'mmkv.default\\music.popular.9:cachedItems';

function fixture({ failMutationAt = 0 } = {}) {
  const builtInRaw = JSON.stringify({0:{size:'large',style:'carousel'}});
  const customRaw = JSON.stringify({0:{title:'My custom row',size:'large',style:'carousel'}});
  const values = new Map([
    [builtInViewKey, builtInRaw],
    [customViewKey, customRaw],
    [orderKey, JSON.stringify({0:['hub.a','hub.custom']})],
    [hiddenKey, JSON.stringify({0:true})],
    [editingKey, 'true'],
    [customHubKey, JSON.stringify({0:['hub.custom']})],
    [authKey, 'AUTH-MUST-STAY'],
    [cacheKey, 'CACHE-MUST-STAY'],
  ]);
  let mutationCalls = 0;
  const maybeFail = () => {
    mutationCalls += 1;
    if (failMutationAt && mutationCalls === failMutationAt) throw new Error('injected-mutation-failure');
  };
  const storage = {
    get length() { return values.size; },
    key(index) { return Array.from(values.keys())[index] ?? null; },
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { maybeFail(); values.set(key, String(value)); },
    removeItem(key) { maybeFail(); values.delete(key); },
  };
  return { values, storage, builtInRaw, customRaw };
}

const successFixture = fixture();
const plan = bridge.planHomeReset(successFixture.storage);
if (
  plan.status !== 'ready'
  || plan.change_count !== 2
  || plan.view_settings_record_count !== 2
  || !plan.reset_available
) throw new Error(`unexpected Home presentation plan ${JSON.stringify(plan)}`);

const success = bridge.applyHomeReset(successFixture.storage, plan.target_fingerprint, true);
if (!success.applied || success.applied_change_count !== 2 || !success.rollback_token) {
  throw new Error(`Home presentation reset failed ${JSON.stringify(success)}`);
}
if (successFixture.values.has(builtInViewKey)) {
  throw new Error('built-in Home viewSettings were not cleared to Plexamp defaults');
}
const customAfter = JSON.parse(successFixture.values.get(customViewKey));
if (JSON.stringify(customAfter) !== JSON.stringify({0:{title:'My custom row'}})) {
  throw new Error(`custom Home title was not preserved exactly ${JSON.stringify(customAfter)}`);
}
for (const [key, expected] of [
  [orderKey, JSON.stringify({0:['hub.a','hub.custom']})],
  [hiddenKey, JSON.stringify({0:true})],
  [editingKey, 'true'],
  [customHubKey, JSON.stringify({0:['hub.custom']})],
  [authKey, 'AUTH-MUST-STAY'],
  [cacheKey, 'CACHE-MUST-STAY'],
]) {
  if (successFixture.values.get(key) !== expected) throw new Error(`Home reset altered preserved record ${key}`);
}

const rolled = bridge.rollbackHomeReset(success.rollback_token, true);
if (!rolled.rolled_back || !rolled.verified) {
  throw new Error(`Home rollback failed ${JSON.stringify(rolled)}`);
}
if (
  successFixture.values.get(builtInViewKey) !== successFixture.builtInRaw
  || successFixture.values.get(customViewKey) !== successFixture.customRaw
) throw new Error('Home rollback did not restore exact viewSettings bytes');

const staleFixture = fixture();
const stalePlan = bridge.planHomeReset(staleFixture.storage);
staleFixture.values.set(builtInViewKey, JSON.stringify({0:{size:'small'}}));
const stale = bridge.applyHomeReset(staleFixture.storage, stalePlan.target_fingerprint, true);
if (stale.status !== 'stale-target' || stale.applied || !stale.fresh_preview_required) {
  throw new Error(`stale Home presentation reset was not refused ${JSON.stringify(stale)}`);
}

const failureFixture = fixture({ failMutationAt: 2 });
const failurePlan = bridge.planHomeReset(failureFixture.storage);
const failed = bridge.applyHomeReset(failureFixture.storage, failurePlan.target_fingerprint, true);
if (failed.status !== 'apply-failed' || failed.applied || !failed.rolled_back) {
  throw new Error(`injected Home failure did not roll back ${JSON.stringify(failed)}`);
}
if (
  failureFixture.values.get(builtInViewKey) !== failureFixture.builtInRaw
  || failureFixture.values.get(customViewKey) !== failureFixture.customRaw
) throw new Error('failure rollback did not restore exact Home viewSettings bytes');

const ambiguous = fixture();
ambiguous.values.set(
  'mmkv.default\\discovery:customizations:other::/library/sections/7:hub.z:viewSettings',
  JSON.stringify({0:{size:'large'}}),
);
const ambiguousPlan = bridge.planHomeReset(ambiguous.storage);
if (ambiguousPlan.status !== 'ambiguous-context' || ambiguousPlan.reset_available) {
  throw new Error(`ambiguous Home context did not fail closed ${JSON.stringify(ambiguousPlan)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_reset_review_layout_reserves_status_width_at_appliance_resolution(self) -> None:
        css = RESET_CSS.read_text(encoding="utf-8")
        advanced = SETTINGS_ADVANCED.read_text(encoding="utf-8")

        self.assertIn(
            "grid-template-columns: minmax(0, 1.7fr) minmax(280px, 1fr)",
            css,
        )
        self.assertIn("[data-reset-review-status]:not([hidden])", css)
        self.assertIn("grid-template-columns: 1fr", css)
        self.assertIn("white-space: normal", css)
        self.assertIn("min-width: 0", css)
        self.assertIn("20260903-reset-review-layout-v3", advanced)


if __name__ == "__main__":
    unittest.main()
