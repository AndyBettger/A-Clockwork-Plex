from __future__ import annotations

import unittest
import shutil
import subprocess
from pathlib import Path


TEMPLATE = Path("app/templates/settings.html")
PRESENTER = Path("app/static/js/settings-weather-observations.js")


class SettingsWeatherObservationControlsTests(unittest.TestCase):
    def test_weather_station_page_exposes_supported_observation_settings(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        expected_paths = (
            "weather.observations.provider",
            "weather.observations.ecowitt_push.path",
            "weather.observations.ecowitt_push.fresh_seconds",
            "weather.observations.weather_underground.station_id",
            "weather.observations.weather_underground.refresh_seconds",
            "weather.observations.weather_underground.stale_seconds",
            "weather.observations.weather_underground.request_timeout_seconds",
        )
        for path in expected_paths:
            self.assertIn(f'data-setting-path="{path}"', source)

        self.assertIn('value="ecowitt_push"', source)
        self.assertIn('value="weather_underground"', source)
        self.assertIn('data-observation-provider-panel="ecowitt_push"', source)
        self.assertIn('data-observation-provider-panel="weather_underground"', source)

        self.assertNotIn("Dashboard observation refresh", source)
        self.assertNotIn('data-setting-path="weather.auto_refresh_seconds"', source)

    def test_secret_remains_outside_revisioned_settings_model(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertNotIn('data-setting-path="weather.observations.weather_underground.api_key"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.apikey"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.secret"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.token"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.api_key"', presenter)
        self.assertIn('type="password"', presenter)
        self.assertIn('data-wu-api-key', presenter)
        self.assertIn('write-only', presenter)
        self.assertIn("elements.input.value = ''", presenter)

    def test_configured_secret_stays_hidden_until_replace(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")
        layout = Path("app/static/css/settings.css").read_text(encoding="utf-8")
        template = TEMPLATE.read_text(encoding="utf-8")
        for expected in (
            "credentialStatusKnown = false",
            "credentialEditing = false",
            "const editing = credentialStatusKnown && (!credentialConfigured || credentialEditing)",
            "field.hidden = !editing",
            "grid?.classList.toggle('is-credential-locked', !editing)",
            'data-wu-credential-grid',
            "input.disabled = !editing || credentialBusy",
            "if (document.activeElement === input) {",
            "window.ACPTouchKeyboard?.close?.();",
            "credentialEditing = true",
            "Save replacement",
            "Cancel replacement",
            "Replacement cancelled. The saved key is unchanged.",
            "if (!key.trim())",
            "The existing key remains active until a replacement is saved.",
            "renderCredentialStatus(); // Fail closed",
            'data-wu-api-key-field hidden',
            'data-keyboard="text" data-wu-api-key disabled',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, presenter)
        self.assertIn("[data-wu-commissioning] [hidden]", layout)
        self.assertIn("display: none !important", layout)
        self.assertIn("20261013-wu-editor-accepted-v3", template)
        self.assertNotIn("installCredentialKeyboardProbe", presenter)
        self.assertNotIn("wuKeyboardProbe", presenter)
        self.assertNotIn("Show keyboard layout diagnostics", presenter)
        self.assertNotIn("elements.input?.focus()", presenter)
        self.assertIn("detail.scrollBy({ top: fieldBottom - bottom + 16", presenter)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_credential_editor_states_in_node_vm(self) -> None:
        javascript = r"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app/static/js/settings-weather-observations.js', 'utf8');
const begin = source.indexOf('  function credentialElements() {');
const end = source.indexOf('  async function requestJson(', begin);
assert.ok(begin > 0 && end > begin);
const calls = {};
const button = () => ({disabled: false, hidden: false, textContent: ''});
const field = {hidden: false};
let blurs = 0;
const input = {value: 'should-not-appear', disabled: false, blur: () => {blurs++;}};
const label = {textContent: ''}, save = button(), cancel = button(),
      remove = button(), test = button();
const classes = new Set();
let keyboardCloses = 0;
const grid = {classList: {toggle: (key, enabled) => {
  if (enabled) classes.add(key);
  else classes.delete(key);
}}};
const controls = {
  '[data-wu-api-key]': input,
  '[data-wu-api-key-field]': field,
  '[data-wu-credential-grid]': grid,
  '[data-wu-credential-status]': label,
  '[data-wu-credential-message]': {textContent: ''},
  '[data-action="save-wu-api-key"]': save,
  '[data-action="cancel-wu-key-edit"]': cancel,
  '[data-action="remove-wu-api-key"]': remove,
  '[data-action="test-wu-connection"]': test
};
const context = {
  assert, console, field, input, label, save, cancel, remove, classes,
  wuPanel: {querySelector: name => controls[name]},
  document: {activeElement: input},
  window: {ACPTouchKeyboard: {close: () => { keyboardCloses++; }}}
};
const code = `
let credentialConfigured = false;
let credentialStatusKnown = false;
let credentialEditing = false;
let credentialBusy = false;
${source.slice(begin, end)}
renderCredentialStatus();
assert.strictEqual(field.hidden, true, 'status unknown: input hidden');
assert.strictEqual(input.disabled, true, 'status unknown: input disabled');
assert.strictEqual(save.disabled, true, 'status unknown: action disabled');
assert.strictEqual(label.textContent, 'Checking…');
renderCredentialStatus(true);
assert.strictEqual(field.hidden, true, 'configured: no empty password field');
assert.strictEqual(input.value, '', 'existing secret is never read or displayed');
assert.strictEqual(save.textContent, 'Replace API key');
assert.strictEqual(remove.disabled, false);
assert.strictEqual(cancel.hidden, true);
assert.strictEqual(classes.has('is-credential-locked'), true);
credentialEditing = true;
renderCredentialStatus();
assert.strictEqual(field.hidden, false, 'replace deliberately opens editor');
assert.strictEqual(input.disabled, false);
assert.strictEqual(save.textContent, 'Save replacement');
assert.strictEqual(cancel.hidden, false);
input.value = 'unsent';
credentialEditing = false;
renderCredentialStatus();
assert.strictEqual(input.value, '', 'cancel/re-hide clears unsent key');
assert.strictEqual(field.hidden, true);
assert.strictEqual(save.textContent, 'Replace API key');
assert.strictEqual(credentialConfigured, true, 'cancel preserves configured state');
renderCredentialStatus(false);
assert.strictEqual(field.hidden, false, 'after removal: allow new credential');
assert.strictEqual(input.disabled, false);
assert.strictEqual(save.textContent, 'Set API key');
assert.strictEqual(remove.disabled, true);
assert.strictEqual(classes.has('is-credential-locked'), false);
credentialBusy = true;
renderCredentialStatus();
assert.strictEqual(input.disabled, true);
assert.strictEqual(save.disabled, true);
console.log('WU status, replace, cancel, removal and busy UI: PASS');
`;
vm.runInNewContext(code, context);
assert.ok(keyboardCloses > 0, 'hiding editor dismisses ACP custom keyboard');
"""
        run = subprocess.run(
            ["node", "-e", javascript],
            capture_output=True, text=True, timeout=20,
        )
        # The VM assertions and the host keyboard-close assertion determine
        # success; Node's VM console output is not a reliable test oracle.
        self.assertEqual(run.returncode, 0, run.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_replace_click_reveals_field_without_opening_osk(self) -> None:
        javascript = r"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app/static/js/settings-weather-observations.js', 'utf8');
const begin = source.indexOf("    elements.save?.addEventListener('click', async () => {");
const end = source.indexOf("    elements.cancel?.addEventListener('click', () => {", begin);
assert.ok(begin >= 0 && end > begin);
let focused = 0;
let keyboardOpened = 0;
let sent = 0;
let movement = null;
const detail = {
  getBoundingClientRect: () => ({top: 140, bottom: 600}),
  scrollBy: args => { movement = args; }
};
const field = {
  hidden: true,
  closest: selector => selector === '.settings-detail' ? detail : null,
  getBoundingClientRect: () => ({top: 548, bottom: 672})
};
const input = {
  value: '',
  focus: () => { focused++; keyboardOpened++; }
};
const message = {textContent: ''};
const handlers = {};
const elements = {
  input, field, message,
  save: {addEventListener: (type, fn) => { handlers[type] = fn; }}
};
const context = {
  elements, window: {requestAnimationFrame: fn => fn()},
  credentialStatusKnown: true, credentialConfigured: true,
  credentialEditing: false, credentialBusy: false,
  renderCredentialStatus: () => { field.hidden = !context.credentialEditing; },
  requestJson: async () => { sent++; throw Error('must never POST on Replace click'); }
};
vm.runInNewContext(source.slice(begin, end), context);
(async () => {
  await handlers.click();
  assert.strictEqual(context.credentialEditing, true);
  assert.strictEqual(field.hidden, false, 'replacement input revealed');
  assert.strictEqual(focused, 0, 'Replace does not focus the hidden/new input');
  assert.strictEqual(keyboardOpened, 0, 'Replace does not open the DOM keyboard');
  assert.strictEqual(sent, 0, 'existing secret not replaced or removed');
  assert.ok(String(message.textContent).includes('Tap the new API key field'));
  assert.strictEqual(movement.top, 88, 'scroll editor into normal visible area');
  assert.strictEqual(movement.behavior, 'auto');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        run = subprocess.run(
            ["node", "-e", javascript], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_commissioning_uses_dedicated_credential_and_test_endpoints(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("/api/weather/underground/credentials", presenter)
        self.assertIn("/api/weather/underground/test", presenter)
        self.assertIn("method: 'POST'", presenter)
        self.assertIn("method: 'DELETE'", presenter)
        self.assertIn("JSON.stringify({ api_key: key })", presenter)
        self.assertIn("Test connection", presenter)
        self.assertNotIn("localStorage", presenter)
        self.assertNotIn("sessionStorage", presenter)

    def test_forecast_copy_keeps_open_meteo_independent_of_observation_provider(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("current observations use the provider selected under Station", source)
        self.assertIn("<strong>Open-Meteo</strong>", source)
        self.assertNotIn("Ecowitt remains the observation source", source)

    def test_observation_presenter_still_presents_unified_runtime_state(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("settings-weather-observations.js", template)
        self.assertIn("ACPUnifiedSettings?.getSnapshot", presenter)
        self.assertIn("data-observation-provider-panel", presenter)
        self.assertIn("credentials_required", presenter)
        self.assertIn("configuration_required", presenter)
        self.assertNotIn("/api/weather/observations", presenter)

    def test_pressure_history_control_is_not_presented_as_a_working_bootstrap(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn(
            'data-setting-path="weather.observations.weather_underground.pressure_history_hours"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
