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
        self.assertNotIn('data-setting-path="osk', settings)
        self.assertIn('html[data-acp-keyboard-choice="native"] .touch-keyboard', STYLE.read_text(encoding="utf-8"))

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
const document = {
  readyState: 'complete',
  documentElement: {dataset: {}},
  querySelectorAll: selector => {
    if (selector === 'input[data-keyboard]') return [input];
    if (selector === '[data-osk-trial-toggle]') return [button];
    if (selector === '[data-osk-trial-status]') return [label];
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
assert.strictEqual(input.getAttribute('inputmode'), 'none');
assert.strictEqual(window.ACPKeyboardChoice.setNative(true), true);
assert.strictEqual(window.ACPKeyboardChoice.isNative(), true);
assert.strictEqual(input.getAttribute('inputmode'), 'text');
assert.strictEqual(document.documentElement.dataset.acpKeyboardChoice, 'native');
assert.strictEqual(attrs.get('button-aria-pressed'), 'true');
window.ACPKeyboardChoice.setNative(false);
assert.strictEqual(window.ACPKeyboardChoice.isNative(), false);
assert.strictEqual(input.getAttribute('inputmode'), 'none');
assert.strictEqual(document.documentElement.dataset.acpKeyboardChoice, 'acp');
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


if __name__ == "__main__":
    unittest.main()
