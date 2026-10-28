"""B4.3 Audio: reuse Chromium mixer, yield GTK, preserve existing audio."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GTK = ROOT / "scripts/try-native-navigation-drawer.py"
BRIDGE = ROOT / "app/native_navigation_bridge.py"
BROWSER = ROOT / "app/static/js/native-navigation-bridge.js"
DRAWER = ROOT / "app/static/js/nav-drawer.js"
OWNER = ROOT / "app/static/js/shared-native-nav-owner.js"
BASE = ROOT / "app/templates/base.html"

def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

gtk = load_script("b43_audio_gtk", GTK)
bridge = load_script("b43_audio_bridge", BRIDGE)


class SharedNativeNavigationAudioTests(unittest.TestCase):
    def test_existing_audio_mailbox_and_browser_mixer_are_reused(self):
        self.assertIn("audio", bridge.ALLOWED_DESTINATIONS)
        commands = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"sequence":49}'
        def mocked_urlopen(request, timeout):
            commands.append((request, timeout))
            return Response()
        with mock.patch.object(gtk.urllib.request, "urlopen", mocked_urlopen):
            self.assertEqual(gtk.request_page_handoff("Audio"), 49)
        self.assertEqual(len(commands), 1)
        req, timeout = commands[0]
        self.assertEqual(json.loads(req.data), {"destination": "audio"})
        self.assertEqual(timeout, 2)
        self.assertEqual(req.get_header("X-acp-b3-source"), "native-gtk-b3-dev")
        js = BROWSER.read_text(encoding="utf-8")
        self.assertIn("window.ACPNavDrawer?.ensureAudioPanel?.()", js)
        self.assertIn("if (button && !document.body.classList.contains('nav-audio-open')) button.click()", js)
        self.assertNotIn("Audio remains browser-owned; action deferred",
                         GTK.read_text(encoding="utf-8"))

    def test_native_control_yields_only_to_foreground_acp_audio(self):
        yield_to = gtk.shared_audio_chrome_yields
        self.assertTrue(yield_to(("acp", "Home"), True, False))
        self.assertTrue(yield_to(("acp", "Weather"), False, True))
        self.assertFalse(yield_to(("acp", "Home"), False, False))
        self.assertFalse(yield_to(("plexamp", "Plexamp"), True, False))
        self.assertFalse(yield_to(("plexamp", "Plexamp"), False, True))
        self.assertFalse(yield_to(None, True, True))
        src = GTK.read_text(encoding="utf-8")
        self.assertIn("GLib.timeout_add(900, refresh_audio_visibility)", src)
        self.assertIn("indicator.hide()", src)
        self.assertIn("indicator.show_all()", src)
        self.assertIn('if (audio_chrome_yields() or not overlay_allowed', src)
        self.assertIn('elif audio_chrome_yields() or state["audio_requested"]:', src)

    def test_strict_transient_snapshot_flags_audio_without_audio_api(self):
        # The palette+presentation snapshot is already short-lived and
        # same-origin; no duplicate mixer state or endpoint is introduced.
        expected = {
            "viewport_width": 853, "viewport_height": 480,
            "drawer_width": 839, "drawer_height": 69, "drawer_bottom": 8,
            "drawer_padding": 8, "workspace_gap": 8, "utility_gap": 6,
            "button_height": 56, "utility_size": 56, "font_size": 20,
            "navigation_transition_duration_ms": 1000,
            "navigation_inactivity_seconds": 5,
            "night_brightness": 1.0, "astronomy_night": False,
            "audio_open": False,
        }
        for open_value in (True, False):
            data = {**expected, "audio_open": open_value}
            self.assertTrue(bridge.valid_presentation(data))
            self.assertTrue(gtk.valid_presentation(data))
        for invalid in ({**expected, "audio_open": 1},
                        {**expected, "audio_open": "true"},
                        {k: v for k, v in expected.items() if k != "audio_open"}):
            self.assertFalse(bridge.valid_presentation(invalid))
            self.assertFalse(gtk.valid_presentation(invalid))
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn("audio_open: document.body.classList.contains('nav-audio-open')",
                      browser)

    def test_browser_opens_navigation_for_mixer_dismissal_and_publishes_changes(self):
        source = BROWSER.read_text(encoding="utf-8")
        drawer = DRAWER.read_text(encoding="utf-8")
        owner = OWNER.read_text(encoding="utf-8")
        self.assertIn("if (command.destination === 'audio'", source)
        self.assertIn("|| command.destination === 'audio')", source)
        self.assertIn("window.ACPNavDrawer?.show?.()", source)
        self.assertIn("window.addEventListener('acp:navigation-audio-visibility'", source)
        self.assertIn("lastPaletteAttemptAt = 0;", source)
        self.assertIn("publishAudioOverlayVisibility()", drawer)
        self.assertIn("if (wasOpen) publishAudioOverlayVisibility()", drawer)
        self.assertIn("new Event('acp:navigation-audio-visibility')", drawer)
        self.assertIn("document.body.classList.contains('nav-audio-open')", owner)
        self.assertIn("release();", owner)

    def test_audio_uses_ready_painted_curtain_and_bounds_unconfirmed_mixer(self):
        source = GTK.read_text(encoding="utf-8")
        self.assertIn('if name not in {"Home", "Weather", "News", "AirPlay", "Settings", "Audio"}:', source)
        self.assertIn("arm_audio_request(sequence)", source)
        self.assertIn("state[\"audio_request_sequence\"] = sequence", source)
        self.assertIn("GLib.timeout_add_seconds(12, abort_if_unconfirmed)", source)
        self.assertIn("Audio visibility not confirmed; restoring ACP navigation", source)
        self.assertIn("state[\"audio_seen\"] = True", source)
        self.assertIn("state[\"audio_requested\"] = False", source)
        self.assertIn("start_curtained_focus(name, sequence)", source)
        self.assertIn("if name != \"Audio\":", source)
        self.assertIn('if (overlay_allowed(state["keyboard"])', source)
        self.assertIn('and not state["audio_requested"] and not audio_chrome_yields()', source)
        self.assertNotIn("flatpak kill", source)

    def test_browser_asset_refresh_is_scoped(self):
        self.assertIn("20261028-b43-shared-audio-v1",
                      BASE.read_text(encoding="utf-8"))
        src = GTK.read_text(encoding="utf-8")
        self.assertIn("if navigate_shared:", src)
        self.assertIn("if presentation_from_acp:", src)
        # The protected B3 static per-window route and current C3 OSK
        # integration are not replaced by this Audio bridge.
        self.assertIn("elif route_pages:", src)
        self.assertIn("def refresh_keyboard():", src)


if __name__ == "__main__":
    unittest.main()
