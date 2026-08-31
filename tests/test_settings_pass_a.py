from __future__ import annotations

import json
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
KEYBOARD_CLIENT = ROOT / "app" / "static" / "js" / "settings-keyboard.js"
RESTORE_CLIENT = ROOT / "app" / "static" / "js" / "settings-about.js"
STYLE = ROOT / "app" / "static" / "css" / "settings-pass-a.css"
SETTINGS_STYLE = ROOT / "app" / "static" / "css" / "settings.css"
SHARED_KEYBOARD_STYLE = ROOT / "app" / "static" / "css" / "touch-keyboard.css"
RESTORE_STYLE = ROOT / "app" / "static" / "css" / "settings-backup-restore.css"
SAFE_LINKS = ROOT / "app" / "static" / "js" / "kiosk-safe-links.js"
SAFE_LINK_STYLE = ROOT / "app" / "static" / "css" / "kiosk-safe-links.css"
DIMMING_STYLE = ROOT / "app" / "static" / "css" / "display-dimming.css"
SCHEDULED_SETTINGS = ROOT / "app" / "settings_unified_scheduled.py"
PLEXAMP_BRIDGE = ROOT / "browser" / "plexamp-search-bridge" / "content.js"
PLEXAMP_SEARCH_MANIFEST = ROOT / "browser" / "plexamp-search-bridge" / "manifest.json"
KIOSK_LAUNCHER = ROOT / "scripts" / "launch-dashboard-kiosk.sh"


class SettingsPassATests(unittest.TestCase):
    def test_new_clients_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, KEYBOARD_CLIENT, RESTORE_CLIENT, SAFE_LINKS, PLEXAMP_BRIDGE):
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

    def test_touch_keyboard_shift_is_one_shot_visible_and_theme_aware(self):
        keyboard = KEYBOARD_CLIENT.read_text(encoding="utf-8")
        style = SHARED_KEYBOARD_STYLE.read_text(encoding="utf-8")

        self.assertIn("shift: 'Shift'", keyboard)
        self.assertNotIn("shifted ? 'ABC' : 'Shift'", keyboard)
        self.assertIn("if (shifted && /^[a-z]$/.test(key)) return key.toUpperCase()", keyboard)
        self.assertIn("button.setAttribute('aria-pressed', shifted ? 'true' : 'false')", keyboard)
        self.assertIn("button.classList.toggle('is-active', shifted)", keyboard)
        self.assertIn("const letterKey = /^[a-z]$/.test(key)", keyboard)
        self.assertIn("insertText(shifted && letterKey ? key.toUpperCase() : key)", keyboard)
        self.assertIn("if (shifted && letterKey)", keyboard)
        self.assertIn("label.textContent = ''", keyboard)
        self.assertIn("label.hidden = true", keyboard)

        self.assertIn("justify-content: flex-end", style)
        self.assertIn("var(--acp-theme-surface", style)
        self.assertIn("var(--acp-theme-control", style)
        self.assertIn('.touch-key[aria-pressed="true"]', style)
        self.assertIn("background: var(--accent)", style)
        self.assertIn("color: var(--acp-theme-contrast", style)

    def test_touch_keyboard_is_shared_and_plexamp_search_aware(self):
        base = BASE.read_text(encoding="utf-8")
        keyboard = KEYBOARD_CLIENT.read_text(encoding="utf-8")
        style = SHARED_KEYBOARD_STYLE.read_text(encoding="utf-8")

        self.assertIn("touch-keyboard.css", base)
        self.assertIn("settings-keyboard.js", base)
        self.assertIn("__aClockworkPlexTouchKeyboardLoaded", keyboard)
        self.assertIn("ensureKeyboardMarkup", keyboard)
        self.assertIn("acp-plexamp-search-focus-v1", keyboard)
        self.assertIn("acp-plexamp-search-edit-v1", keyboard)
        self.assertIn("submit: 'Search'", keyboard)
        self.assertIn("postRemote('submit')", keyboard)
        self.assertIn("notifyRemote: isRemoteSearch()", keyboard)
        self.assertIn("plexamp-search-keyboard-open", keyboard)
        self.assertIn("body.plexamp-search-keyboard-open .touch-keyboard", style)
        self.assertIn("z-index: 160", style)

    def test_plexamp_search_bridge_is_permission_free_loopback_only_and_loaded_by_kiosk(self):
        manifest = json.loads(PLEXAMP_SEARCH_MANIFEST.read_text(encoding="utf-8"))
        launcher = KIOSK_LAUNCHER.read_text(encoding="utf-8")

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertNotIn("permissions", manifest)
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("background", manifest)
        scripts = manifest["content_scripts"]
        self.assertEqual(len(scripts), 1)
        self.assertEqual(
            set(scripts[0]["matches"]),
            {"http://localhost:32500/*", "http://127.0.0.1:32500/*"},
        )
        self.assertEqual(scripts[0]["js"], ["content.js"])
        self.assertTrue(scripts[0]["all_frames"])
        self.assertIn("browser/plexamp-search-bridge", launcher)
        self.assertIn("extension_dirs", launcher)
        self.assertIn('browser_args+=(--load-extension="$extension_arg")', launcher)
        self.assertNotIn("--remote-debugging-port", launcher)

    def test_plexamp_search_bridge_accepts_only_narrow_search_edit_contract(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        bridge_source = PLEXAMP_BRIDGE.read_text(encoding="utf-8")
        script = r"""
const bridge = require(process.argv[1]);
function input(attrs = {}) {
  return {
    tagName: 'INPUT',
    type: attrs.type || 'text',
    disabled: false,
    readOnly: false,
    getAttribute(name) { return attrs[name] || ''; },
    closest() { return null; },
  };
}
const payload = {
  eligibleByType: bridge.isEligibleSearchTarget(input({ type: 'search' })),
  eligibleByPlaceholder: bridge.isEligibleSearchTarget(input({ placeholder: 'Search' })),
  rejectsOrdinaryText: bridge.isEligibleSearchTarget(input({ placeholder: 'Username' })),
  insertPlan: bridge.planSearchEdit('Miles Davis', 5, 5, 'insert', '!'),
  emojiBackspace: bridge.planSearchEdit('A😀B', 3, 3, 'backspace'),
  acceptsInsert: bridge.validateSearchEditRequest({
    type: 'acp-plexamp-search-edit-v1',
    session_id: '1234567890abcdef',
    command: 'insert',
    text: 'Q',
  }),
  rejectsLongInsert: bridge.validateSearchEditRequest({
    type: 'acp-plexamp-search-edit-v1',
    session_id: '1234567890abcdef',
    command: 'insert',
    text: 'DROP',
  }),
  rejectsArbitraryCommand: bridge.validateSearchEditRequest({
    type: 'acp-plexamp-search-edit-v1',
    session_id: '1234567890abcdef',
    command: 'selector',
  }),
};
process.stdout.write(JSON.stringify(payload));
"""
        result = subprocess.run(
            [node, "-e", script, str(PLEXAMP_BRIDGE)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["eligibleByType"])
        self.assertTrue(payload["eligibleByPlaceholder"])
        self.assertFalse(payload["rejectsOrdinaryText"])
        self.assertEqual(payload["insertPlan"]["value"], "Miles! Davis")
        self.assertEqual(payload["emojiBackspace"]["value"], "AB")
        self.assertIsNotNone(payload["acceptsInsert"])
        self.assertIsNone(payload["rejectsLongInsert"])
        self.assertIsNone(payload["rejectsArbitraryCommand"])

        self.assertIn("ALLOWED_COMMANDS", bridge_source)
        self.assertIn("doc.activeElement !== activeTarget", bridge_source)
        self.assertIn("Array.from(text).length !== 1", bridge_source)
        self.assertIn("event.source !== win.parent", bridge_source)
        self.assertIn("DASHBOARD_ORIGINS.has(event.origin)", bridge_source)
        self.assertIn("typeof win?.crypto?.getRandomValues !== 'function'", bridge_source)
        for forbidden in (
            "request.selector",
            "value: activeTarget.value",
            "text: activeTarget.value",
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "document.cookie",
            "localStorage",
            "chrome.storage",
        ):
            self.assertNotIn(forbidden, bridge_source)

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
        self.assertIn("error.restoreBlocked", restore_client)
        self.assertIn("'Restore blocked'", restore_client)
        self.assertIn("data-configuration-restore-result-status", restore_client)
        self.assertIn("20260831-home-restore-feedback-v2", settings_template)

    def test_guided_restore_target_selection_and_single_confirmation_are_guarded(self):
        restore_client = RESTORE_CLIENT.read_text(encoding="utf-8")
        restore_style = RESTORE_STYLE.read_text(encoding="utf-8")

        self.assertIn('data-configuration-restore-target="acp"', restore_client)
        self.assertIn('data-configuration-restore-target="plexamp"', restore_client)
        self.assertIn("buildSelectedServerBackup", restore_client)
        self.assertIn("review-selected-restore", restore_client)
        self.assertIn("Review selected restore", restore_client)
        self.assertIn("Ready to confirm", restore_client)
        self.assertIn("Confirm &amp; restore", restore_client)
        self.assertIn("Plexamp Home first, then ACP/Headless", restore_client)
        self.assertNotIn("Review Plexamp Home restore", restore_client)
        self.assertNotIn("Confirm Home restore", restore_client)
        self.assertIn('.settings-restore-target[aria-pressed="true"]', restore_style)
        self.assertIn("data-configuration-restore-review-status", restore_client)
        self.assertIn("data-configuration-restore-result-status", restore_client)

    def test_home_restore_success_feedback_and_confirmation_spacing_are_guarded(self):
        base = BASE.read_text(encoding="utf-8")
        restore_client = RESTORE_CLIENT.read_text(encoding="utf-8")
        restore_style = RESTORE_STYLE.read_text(encoding="utf-8")

        self.assertIn("20260831-home-restore-feedback-v2", base)
        self.assertIn("The live Home layout now matches this backup.", restore_client)
        self.assertIn("restoreMessage.classList.remove('is-conflict')", restore_client)
        self.assertIn("[data-configuration-restore-review-status]:not([hidden])", restore_style)
        self.assertIn("[data-configuration-restore-result-status]:not([hidden])", restore_style)
        self.assertIn("margin-top: 14px", restore_style)

    def test_guided_restore_physical_followup_layout_is_guarded(self):
        restore_style = RESTORE_STYLE.read_text(encoding="utf-8")

        self.assertIn(
            '.settings-action-row:has([data-action="preview-configuration-restore"])',
            restore_style,
        )
        self.assertIn("margin-bottom: 12px", restore_style)
        self.assertIn(
            '[data-configuration-restore-apply-zone]:not([hidden])::before',
            restore_style,
        )
        self.assertIn('content: "Review restore"', restore_style)
        self.assertIn("grid-template-columns: auto minmax(0, 1fr)", restore_style)
        self.assertIn('[data-action="review-selected-restore"]', restore_style)
        self.assertIn("[data-configuration-restore-review-status]:not([hidden])", restore_style)
        self.assertIn("[data-configuration-restore-confirm][hidden]", restore_style)
        self.assertIn("display: none !important", restore_style)
        self.assertIn(
            '.settings-card:has(> [data-configuration-restore-result-status]:not([hidden]))',
            restore_style,
        )
        self.assertIn("flex-direction: column", restore_style)
        self.assertIn("order: -2", restore_style)
        self.assertIn("order: -1", restore_style)
        self.assertIn("margin: 12px 0 14px", restore_style)

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
        self.assertIn("touch-keyboard.css", base)
        self.assertIn("20260831-shared-plexamp-search-v1", base)

    def test_external_navigation_is_forbidden_from_the_kiosk_client(self):
        client = SAFE_LINKS.read_text(encoding="utf-8")
        self.assertNotIn("window.open", client)
        self.assertIn("showExternalAddress", client)
        self.assertIn("Copy address", client)
        self.assertIn("The kiosk never leaves the dashboard", client)


if __name__ == "__main__":
    unittest.main()
