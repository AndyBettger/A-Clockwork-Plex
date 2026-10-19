"""Native OS keyboard browser-trial guard; original ACP DOM keyboard is the default."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODE = ROOT / "app/static/js/osk-keyboard-choice.js"
KEYBOARD = ROOT / "app/static/js/settings-keyboard.js"
STYLE = ROOT / "app/static/css/touch-keyboard.css"
BASE = ROOT / "app/templates/base.html"
SETTINGS = ROOT / "app/templates/settings.html"


class KeyboardChoiceContracts(unittest.TestCase):
    def test_native_trial_is_opt_in_scoped_and_reversible(self):
        script = MODE.read_text(encoding="utf-8")
        for expected in (
            "sessionStorage",
            "5 * 60 * 1000",
            "setNative(enable)",
            "window.ACPKeyboardChoice",
            "acp:keyboard-choice-changed",
            "data-osk-trial-toggle",
            "input[data-keyboard]",
            "originalHints.delete(input)",
            "setTimeout(clearTrial, remaining + 20)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, script)
        for forbidden in ("localStorage", "fetch(", "systemctl", "pkill", "sudo ", "document.execCommand"):
            self.assertNotIn(forbidden, script)

    def test_existing_dom_keyboard_is_preserved_as_fallback(self):
        script = KEYBOARD.read_text(encoding="utf-8")
        self.assertIn("function useSystemKeyboard()", script)
        self.assertIn("if (useSystemKeyboard())", script)
        self.assertIn("function openKeyboard(input)", script)
        self.assertIn("function openRemoteText(sessionId, kind)", script)
        self.assertIn("acp:keyboard-choice-changed", script)
        self.assertIn("window.ACPTouchKeyboard", script)
        self.assertIn("const layouts = {", script)
        self.assertIn("data-keyboard", script)
        self.assertIn('postRemote(\'done\'', script)

    def test_mode_ui_and_global_guard_are_wired(self):
        base = BASE.read_text(encoding="utf-8")
        settings = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("osk-keyboard-choice.js", base)
        self.assertLess(base.index("osk-keyboard-choice.js"), base.index("settings-keyboard.js"))
        self.assertIn('data-settings-subpage-target="advanced:keyboard"', settings)
        self.assertIn('data-settings-subpage="advanced:keyboard"', settings)
        self.assertIn('data-osk-trial-toggle', settings)
        self.assertIn('data-osk-trial-status', settings)
        self.assertIn('data-osk-native-probes hidden', settings)
        self.assertIn('data-osk-probe="numeric-text"', settings)
        self.assertIn('data-osk-probe="numeric-number"', settings)
        self.assertIn('type="text" inputmode="numeric"', settings)
        self.assertIn('type="number" inputmode="numeric"', settings)
        self.assertIn("panel.hidden = !enabled", MODE.read_text(encoding="utf-8"))
        self.assertIn("20261019-c3-auto-single-osk-v1", base)
        self.assertIn("20261019-c3-native-field-scroll-v1", settings)
        self.assertIn("separately started Squeekboard trial lasts up to 180 seconds", MODE.read_text(encoding="utf-8"))
        self.assertNotIn('data-setting-path="osk', settings)
        self.assertIn('html[data-acp-keyboard-choice="native"] .touch-keyboard', STYLE.read_text(encoding="utf-8"))

    def test_native_only_scroll_reserve_and_numeric_rollback_contract(self):
        mode = MODE.read_text(encoding="utf-8")
        layout = (ROOT / "app/static/css/settings-ipad.css").read_text(encoding="utf-8")
        self.assertIn("native-osk-field-focused", mode)
        self.assertIn('input[type="password"]', mode)
        self.assertIn("input.disabled || input.readOnly", mode)
        self.assertIn('data-wu-api-key', (ROOT / "app/static/js/settings-weather-observations.js").read_text(encoding="utf-8"))
        self.assertIn("field.bottom - visibleBottom + gap", mode)
        self.assertIn("Math.min(bounds.bottom, viewportHeight - keyboardHeight)", mode)
        self.assertIn("window.setTimeout(syncFocusedField, 0)", mode)
        self.assertIn("originalTypes.delete(input)", mode)
        self.assertIn("input.dataset.keyboard === 'number'", mode)
        self.assertIn("input.setAttribute('type', 'number')", mode)
        self.assertIn('body[data-active-page="settings"].native-osk-field-focused .settings-detail-panel:not([hidden])', layout)
        self.assertIn("padding-bottom: calc(14px + clamp(245px, 44vh, 330px))", layout)
        self.assertNotIn("native-osk-field-focused .settings-ipad-page", layout)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_browser_session_state_and_hints_in_node(self):
        javascript = r"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const script = fs.readFileSync('app/static/js/osk-keyboard-choice.js', 'utf8');
let now = 100000;
let expiredCallback;
const handlers = {};
const storage = new Map();
const attrs = new Map([['inputmode', 'none']]);
const input = {
  dataset: {keyboard: 'text'},
  matches: selector => selector === 'input[data-keyboard]',
  getAttribute: key => attrs.has(key) ? attrs.get(key) : null,
  setAttribute: (key, value) => attrs.set(key, value),
  removeAttribute: key => attrs.delete(key)
};
const button = {
  textContent: '',
  setAttribute: (key, value) => attrs.set('button-'+key, value)
};
const label = {textContent: ''};
const probePanel = {hidden: true};
const document = {
  readyState: 'complete',
  documentElement: {dataset: {}},
  querySelectorAll: selector => {
    if (selector === 'input[data-keyboard]') return [input];
    if (selector === '[data-osk-trial-toggle]') return [button];
    if (selector === '[data-osk-trial-status]') return [label];
    if (selector === '[data-osk-native-probes]') return [probePanel];
    return [];
  },
  addEventListener: (key, callback) => handlers[key] = callback
};
const window = {
  sessionStorage: {
    getItem: key => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key)
  },
  setTimeout: cb => { expiredCallback = cb; return 123; },
  clearTimeout: () => {},
  dispatchEvent: () => {},
};
const ctx = {
  window, document,
  Date: {now: () => now},
  CustomEvent: class { constructor(key, opts) { this.type = key; this.detail = opts.detail; } }
};
vm.runInNewContext(script, ctx);
assert.strictEqual(window.ACPKeyboardChoice.isNative(), false, 'ACP keyboard default');
assert.strictEqual(label.textContent.includes('existing ACP keyboard'), true);
assert.strictEqual(probePanel.hidden, true);
assert.strictEqual(input.getAttribute('inputmode'), 'none');
assert.strictEqual(window.ACPKeyboardChoice.setNative(true), true);
assert.strictEqual(window.ACPKeyboardChoice.isNative(), true);
assert.strictEqual(input.getAttribute('inputmode'), 'text');
assert.strictEqual(document.documentElement.dataset.acpKeyboardChoice, 'native');
assert.strictEqual(probePanel.hidden, false, 'native-only purpose probes visible');
assert.strictEqual(attrs.get('button-aria-pressed'), 'true');
window.ACPKeyboardChoice.setNative(false);
assert.strictEqual(window.ACPKeyboardChoice.isNative(), false);
assert.strictEqual(input.getAttribute('inputmode'), 'none');
assert.strictEqual(document.documentElement.dataset.acpKeyboardChoice, 'acp');
assert.strictEqual(probePanel.hidden, true, 'probes hidden after restoring ACP');
window.ACPKeyboardChoice.setNative(true);
now += 300010;
expiredCallback();
assert.strictEqual(window.ACPKeyboardChoice.isNative(), false);
assert.strictEqual(input.getAttribute('inputmode'), 'none');
assert.strictEqual(label.textContent.includes('existing ACP keyboard'), true);
console.log('Native OSK opt-in, hints, restore and timeout: PASS');
"""
        p = subprocess.run(
            ["node", "-e", javascript],
            cwd=ROOT, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("PASS", p.stdout)


    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_numeric_mode_focus_reveal_and_reversible_type_in_node(self):
        javascript = r"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const script = fs.readFileSync('app/static/js/osk-keyboard-choice.js', 'utf8');
let now = 100000;
const timers = [];
const listeners = {};
const storage = new Map();
const classes = new Set();
const attrs = new Map([['inputmode', 'none'], ['type', 'text']]);
const pane = {
  scrollTop: 0,
  getBoundingClientRect: () => ({top: 80, bottom: 500})
};
const input = {
  dataset: {keyboard: 'number'},
  type: 'text',
  matches: selector => selector === 'input[data-keyboard]' || selector.includes('input[type="number"]'),
  closest: selector => selector === '.settings-detail' ? pane : null,
  getBoundingClientRect: () => ({top: 600, bottom: 640}),
  getAttribute: name => attrs.has(name) ? attrs.get(name) : null,
  setAttribute: (name, value) => {
    attrs.set(name, value);
    if (name === 'type') input.type = value;
  },
  removeAttribute: name => {
    attrs.delete(name);
    if (name === 'type') input.type = 'text';
  }
};
const document = {
  readyState: 'complete',
  activeElement: input,
  body: {
    classList: {
      add: name => classes.add(name),
      remove: name => classes.delete(name)
    }
  },
  documentElement: {dataset: {}},
  querySelectorAll: selector => selector === 'input[data-keyboard]' ? [input] : [],
  addEventListener: (name, fn) => { listeners[name] = fn; }
};
const window = {
  sessionStorage: {
    getItem: key => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key)
  },
  setTimeout: (fn, ms) => { timers.push({fn, ms}); return timers.length; },
  clearTimeout: () => {},
  requestAnimationFrame: fn => { fn(); return 1; },
  dispatchEvent: () => {}
};
vm.runInNewContext(script, {
  window, document, Date: {now: () => now},
  CustomEvent: class { constructor(name, opts) { this.type = name; this.detail = opts.detail; } }
});
assert.strictEqual(input.type, 'text', 'accepted ACP field unchanged initially');
assert.strictEqual(window.ACPKeyboardChoice.setNative(true), true);
assert.strictEqual(input.type, 'number', 'physical numeric-purpose result applied in trial');
assert.strictEqual(input.getAttribute('inputmode'), 'numeric');
assert.strictEqual(classes.has('native-osk-field-focused'), true);
assert.ok(pane.scrollTop > 230 && pane.scrollTop < 270, 'scroll field above keyboard while outer shell remains full height');
document.activeElement = null;
listeners.focusout();
const blurTimer = timers.find(t => t.ms === 0);
assert.ok(blurTimer);
blurTimer.fn();
assert.strictEqual(classes.has('native-osk-field-focused'), false, 'blur removes native reserve');
document.activeElement = input;
listeners.focusin({target: input});
assert.strictEqual(classes.has('native-osk-field-focused'), true);
window.ACPKeyboardChoice.setNative(false);
assert.strictEqual(input.type, 'text', 'ACP mode restores original numeric field type');
assert.strictEqual(input.getAttribute('inputmode'), 'none', 'ACP keyboard suppression restored');
assert.strictEqual(classes.has('native-osk-field-focused'), false, 'mode restore releases pane');
const secret = {
  type: 'password', disabled: false, readOnly: false,
  matches: selector => selector.includes('input[type="password"]'),
  closest: selector => selector === '.settings-detail' ? pane : null,
  getBoundingClientRect: () => ({top: 610, bottom: 660})
};
document.activeElement = secret;
const beforeSecretScroll = pane.scrollTop;
window.ACPKeyboardChoice.setNative(true);
assert.strictEqual(classes.has('native-osk-field-focused'), true, 'unmarked password receives focus reserve');
assert.ok(pane.scrollTop > beforeSecretScroll, 'dynamic password field scrolls clear of OSK');
assert.strictEqual(secret.type, 'password', 'no change to secret input type');
window.ACPKeyboardChoice.setNative(false);
assert.strictEqual(classes.has('native-osk-field-focused'), false, 'password restore clears reserve');
const checkbox = {
  type: 'checkbox', disabled: false, readOnly: false,
  matches: () => false,
  closest: selector => selector === '.settings-detail' ? pane : null
};
document.activeElement = checkbox;
window.ACPKeyboardChoice.setNative(true);
assert.strictEqual(classes.has('native-osk-field-focused'), false, 'non-text controls excluded');
window.ACPKeyboardChoice.setNative(false);
console.log('Number, dynamic password, non-text filter and ACP fallback: PASS');
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            cwd=ROOT, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
