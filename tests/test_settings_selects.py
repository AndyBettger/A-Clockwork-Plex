from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECT_CLIENT = ROOT / "app" / "static" / "js" / "settings-selects.js"
SELECT_STYLE = ROOT / "app" / "static" / "css" / "settings-selects.css"
BASE_TEMPLATE = ROOT / "app" / "templates" / "base.html"
DISPLAY_DIM_STYLE = ROOT / "app" / "static" / "css" / "display-dimming.css"


class SettingsSelectTests(unittest.TestCase):
    def test_settings_select_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", str(SELECT_CLIENT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_settings_template_loads_in_document_select_assets(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("css/settings-selects.css", template)
        self.assertIn("js/settings-selects.js", template)
        self.assertIn("20260803-night-safe-selects", template)

    def test_original_select_remains_the_settings_data_authority(self):
        client = SELECT_CLIENT.read_text(encoding="utf-8")
        self.assertIn("select.value = value", client)
        self.assertIn("new Event('input', { bubbles: true })", client)
        self.assertIn("new Event('change', { bubbles: true })", client)
        self.assertIn("form.querySelectorAll('select').forEach(enhance)", client)
        self.assertIn("new MutationObserver(queueRefresh)", client)
        self.assertNotIn("fetch('/api/settings'", client)
        self.assertNotIn("method: 'POST'", client)

    def test_dropdown_menu_stays_below_global_night_overlay(self):
        client = SELECT_CLIENT.read_text(encoding="utf-8")
        style = SELECT_STYLE.read_text(encoding="utf-8")
        dimming = DISPLAY_DIM_STYLE.read_text(encoding="utf-8")
        self.assertIn("document.body.appendChild(layer)", client)
        self.assertIn("z-index: 2147482500", style)
        self.assertIn("z-index: 2147483000", dimming)
        self.assertIn("acp-settings-select-menu", style)
        self.assertIn("role', 'listbox'", client)
        self.assertIn("role', 'option'", client)

    def test_dynamic_and_programmatic_select_updates_are_reflected(self):
        client = SELECT_CLIENT.read_text(encoding="utf-8")
        self.assertIn("window.setInterval(refresh, 2000)", client)
        self.assertIn("window.addEventListener('acp:settings-selects-refresh'", client)
        self.assertIn("attributeFilter: ['disabled', 'label', 'selected', 'value']", client)
        self.assertIn("window.clearInterval(syncTimer)", client)


if __name__ == "__main__":
    unittest.main()
