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
        self.assertIn("default Home order", text)
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

    def test_native_plexamp_reset_uses_application_defaults_and_retained_rollback(self) -> None:
        source = NATIVE_EXTENSION.read_text(encoding="utf-8")
        self.assertIn("global.app.rootStore", source)
        self.assertIn("win?.app?.rootStore?.settings", source)
        self.assertNotIn("webpackChunk", source)
        self.assertNotIn("PRESERVED_PORTABLE_HEADLESS_KEYS", source)
        self.assertNotIn("restoreProtectedHeadless", source)

        script = r"""
const bridge = require('./browser/plexamp-bridge/native-reset.js');
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

const settings = new FakeSettings();
settings.foo = 9;
settings.playerName = 'Bedroom Plexamp';
settings.audioDeviceUuid = 'managed-output';
const beforeHeadless = [256, false, 32768, 10, false, 0, 4, 2];
ordinaryHeadlessKeys.forEach((key, index) => { settings[key] = beforeHeadless[index]; });

const located = bridge.locateSettings({ app: { rootStore: { settings } } });
if (located !== settings) throw new Error('application-global Plexamp settings were not located');

const plan = bridge.buildResetPlan(settings);
if (plan.status !== 'ready' || plan.change_count !== 9 || !plan.reset_available) {
  throw new Error(`unexpected native plan ${JSON.stringify(plan)}`);
}
const applied = bridge.applySettingsReset(settings, plan.target_fingerprint, true);
if (!applied.applied || applied.applied_change_count !== 9 || !applied.rollback_token) {
  throw new Error(`native reset failed ${JSON.stringify(applied)}`);
}
if (settings.foo !== 1 || settings.playerName !== 'Factory player' || settings.audioDeviceUuid !== '') {
  throw new Error('native reset did not use Plexamp-style defaults');
}
const defaults = new FakeSettings();
ordinaryHeadlessKeys.forEach((key) => {
  if (settings[key] !== defaults[key]) {
    throw new Error(`ordinary Headless preference did not reset with Plexamp: ${key}`);
  }
});
const rolled = bridge.rollbackSettingsReset(applied.rollback_token, true);
if (!rolled.rolled_back || !rolled.verified) {
  throw new Error(`native rollback failed ${JSON.stringify(rolled)}`);
}
if (settings.foo !== 9 || settings.playerName !== 'Bedroom Plexamp' || settings.audioDeviceUuid !== 'managed-output') {
  throw new Error('native rollback did not restore exact commissioning values');
}
ordinaryHeadlessKeys.forEach((key, index) => {
  if (settings[key] !== beforeHeadless[index]) {
    throw new Error(`rollback did not restore Headless preference: ${key}`);
  }
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_home_reset_clears_modern_and_legacy_order_visibility_with_rollback(self) -> None:
        script = r"""
const bridge = require('./browser/plexamp-bridge/reset.js');

const orderKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:order';
const hiddenKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:hub.a:hidden';
const legacyOrderKey = 'mmkv.default\\discovery:customizations:order';
const legacyHiddenKey = 'mmkv.default\\discovery:customizations:hidden';
const authKey = 'mmkv.default\\authToken';
const editingKey = 'mmkv.default\\discovery:customizations:ctx::/library/sections/9:hub.a:editing';

const values = new Map([
  [orderKey, JSON.stringify({0:['hub.a','hub.b']})],
  [hiddenKey, JSON.stringify({_:true})],
  [legacyOrderKey, JSON.stringify(['legacy.a'])],
  [legacyHiddenKey, JSON.stringify(['legacy.hidden'])],
  [authKey, 'AUTH-MUST-STAY'],
  [editingKey, 'EDITING-MUST-STAY'],
]);
const storage = {
  get length() { return values.size; },
  key(index) { return Array.from(values.keys())[index] ?? null; },
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { values.set(key, String(value)); },
  removeItem(key) { values.delete(key); },
};

const plan = bridge.planHomeReset(storage);
if (
  plan.status !== 'ready'
  || plan.change_count !== 4
  || plan.order_record_count !== 2
  || plan.hidden_record_count !== 2
  || plan.legacy_record_count !== 2
) throw new Error(`unexpected Home plan ${JSON.stringify(plan)}`);

const applied = bridge.applyHomeReset(storage, plan.target_fingerprint, true);
if (!applied.applied || applied.applied_change_count !== 4 || !applied.rollback_token) {
  throw new Error(`Home reset failed ${JSON.stringify(applied)}`);
}
for (const key of [orderKey, hiddenKey, legacyOrderKey, legacyHiddenKey]) {
  if (values.has(key)) throw new Error(`resettable Home record remained: ${key}`);
}
if (values.get(authKey) !== 'AUTH-MUST-STAY' || values.get(editingKey) !== 'EDITING-MUST-STAY') {
  throw new Error('Home reset touched unrelated state');
}

const rolled = bridge.rollbackHomeReset(applied.rollback_token, true);
if (!rolled.rolled_back || !rolled.verified) {
  throw new Error(`Home rollback failed ${JSON.stringify(rolled)}`);
}
for (const key of [orderKey, hiddenKey, legacyOrderKey, legacyHiddenKey]) {
  if (!values.has(key)) throw new Error(`rollback missed Home record: ${key}`);
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
