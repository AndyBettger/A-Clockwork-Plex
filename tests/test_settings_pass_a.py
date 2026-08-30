from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

from app.settings_unified_scheduled import _clock_card_slot_count


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
SETTINGS_TEMPLATE = ROOT / "app" / "templates" / "settings.html"
CLIENT = ROOT / "app" / "static" / "js" / "settings-pass-a.js"
RESTORE_CLIENT = ROOT / "app" / "static" / "js" / "settings-about.js"
STYLE = ROOT / "app" / "static" / "css" / "settings-pass-a.css"
SAFE_LINKS = ROOT / "app" / "static" / "js" / "kiosk-safe-links.js"
SAFE_LINK_STYLE = ROOT / "app" / "static" / "css" / "kiosk-safe-links.css"
DIMMING_STYLE = ROOT / "app" / "static" / "css" / "display-dimming.css"
SCHEDULED_SETTINGS = ROOT / "app" / "settings_unified_scheduled.py"


class SettingsPassATests(unittest.TestCase):
    def test_new_clients_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, RESTORE_CLIENT, SAFE_LINKS):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_clock_card_slot_groups_match_the_compact_clock_layout(self):
        current = [
            "outdoor_temp",
            "indoor_temp",
            "humidity",
            "indoor_humidity",
            "wind_speed",
            "wind_gust",
            "daily_rain",
            "event_rain",
            "pressure",
            "solar",
            "uv",
            "max_daily_gust",
            "barometer",
        ]
        self.assertEqual(_clock_card_slot_count(current), 8)
        self.assertEqual(
            _clock_card_slot_count(current + ["extra_ninth_slot"]),
            9,
        )

    def test_clock_card_limit_is_guarded_in_browser_and_backend(self):
        client = CLIENT.read_text(encoding="utf-8")
        backend = SCHEDULED_SETTINGS.read_text(encoding="utf-8")
        self.assertIn("MAX_CLOCK_CARD_SLOTS = 8", client)
        self.assertIn("button.disabled = blocked", client)
        self.assertIn("of ${MAX_CLOCK_CARD_SLOTS} Clock slots selected", client)
        self.assertIn("_MAX_CLOCK_CARD_SLOTS = 8", backend)
        self.assertIn("Clock weather cards support at most", backend)

    def test_keyboard_scrolls_the_real_settings_detail_owner(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("target.closest('.settings-detail')", client)
        self.assertIn("detail.scrollBy", client)
        self.assertIn("--settings-keyboard-height", client)
        self.assertIn("body.keyboard-open .settings-detail", style)
        self.assertIn("scroll-padding-bottom", style)

    def test_redundant_status_badges_are_removed_and_alarm_count_is_a_heading_box(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("document.querySelector('[data-night-dim-status]')?.remove()", client)
        self.assertIn("document.querySelector('[data-shairport-health]')?.remove()", client)
        self.assertIn('[data-settings-subpage="audio:trims"] .settings-card-heading > .settings-chip', client)
        self.assertIn("No alarms set", client)
        self.assertIn("Alarm${count === 1 ? '' : 's'} Set", client)
        self.assertIn("alarm-count-summary", client)
        self.assertIn("#settings-alarm-schedule .alarm-schedule-heading", style)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", style)
        self.assertIn("#settings-alarm-schedule .alarm-count-summary", style)
        self.assertIn("min-height: 38px", style)
        self.assertIn("border-radius: 11px", style)
        self.assertIn("background: rgba(143, 211, 255, 0.075)", style)

    def test_service_status_refresh_is_automatic_and_has_no_visible_button(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("installServiceStatusRefresh", client)
        self.assertIn("refreshButton.hidden = true", client)
        self.assertIn("window.setTimeout(() => refreshButton.click(), 0)", client)
        self.assertIn('[data-settings-subpage="advanced:services"] [data-action="refresh-services"]', style)
        self.assertIn("display: none !important", style)

    def test_about_project_links_are_full_width_grid_cards(self):
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn('[data-settings-section="about"] .settings-link-grid', style)
        self.assertIn('[data-settings-section="about"] .settings-link-card', style)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", style)
        self.assertIn("width: 100%", style)
        self.assertIn("box-sizing: border-box", style)
        self.assertIn("align-content: start", style)

    def test_stale_restore_warning_is_owned_by_restore_client_and_guarded(self):
        client = CLIENT.read_text(encoding="utf-8")
        restore_client = RESTORE_CLIENT.read_text(encoding="utf-8")
        settings_template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("let restoreConflictDetail = ''", client)
        self.assertIn("const enforceConflictMessage = () =>", client)
        self.assertIn(
            "Restore blocked — no settings were changed. ${restoreConflictDetail}",
            client,
        )
        self.assertIn("new MutationObserver(() =>", client)
        self.assertIn("if (restoreConflictDetail) enforceConflictMessage()", client)
        self.assertIn("payload?.fresh_preview_required === true", client)

        self.assertIn("result.fresh_preview_required === true", restore_client)
        self.assertIn("response.status === 409", restore_client)
        self.assertIn(
            "Restore blocked — no settings were changed. ${restoreDetail}",
            restore_client,
        )
        self.assertIn("restoreMessage.classList.toggle('is-conflict', restoreWasBlocked)", restore_client)
        self.assertNotIn(
            "restoreMessage.textContent = 'Run Preview restore again before any retry.'",
            restore_client,
        )
        self.assertIn("20260830-stale-restore-owner-v1", settings_template)

    def test_kiosk_address_dialog_stays_below_pointer_transparent_night_overlay(self):
        modal_style = SAFE_LINK_STYLE.read_text(encoding="utf-8")
        dimming_style = DIMMING_STYLE.read_text(encoding="utf-8")
        modal_match = re.search(
            r"\.kiosk-link-modal\s*\{.*?z-index:\s*(\d+)",
            modal_style,
            re.DOTALL,
        )
        overlay_match = re.search(
            r"#acp-night-dim-overlay\s*\{.*?z-index:\s*(\d+).*?pointer-events:\s*none",
            dimming_style,
            re.DOTALL,
        )
        self.assertIsNotNone(modal_match)
        self.assertIsNotNone(overlay_match)
        self.assertLess(int(modal_match.group(1)), int(overlay_match.group(1)))

    def test_first_paint_and_new_assets_are_wired(self):
        base = BASE.read_text(encoding="utf-8")
        self.assertIn('<html lang="en-GB" class="acp-document-booting"', base)
        self.assertIn("settings-pass-a.css", base)
        self.assertIn("settings-pass-a.js", base)
        self.assertIn("20260802-kiosk-address-panel", base)

    def test_external_navigation_is_forbidden_from_the_kiosk_client(self):
        client = SAFE_LINKS.read_text(encoding="utf-8")
        self.assertNotIn("window.open", client)
        self.assertIn("showExternalAddress", client)
        self.assertIn("Copy address", client)
        self.assertIn("The kiosk never leaves the dashboard", client)


if __name__ == "__main__":
    unittest.main()
