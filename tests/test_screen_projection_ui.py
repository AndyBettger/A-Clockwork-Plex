from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "screen-projection.js"
MODE_WATCH = ROOT / "app" / "static" / "js" / "mode-watch.js"
PAGE_TRANSITIONS = ROOT / "app" / "static" / "js" / "page-transitions.js"
PLEXAMP_PERSISTENT = ROOT / "app" / "static" / "js" / "plexamp-persistent.js"
BASE = ROOT / "app" / "templates" / "base.html"
RUNNER = ROOT / "app" / "runner.py"


class ScreenProjectionUiTests(unittest.TestCase):
    def test_navigation_clients_have_valid_javascript_syntax(self):
        for path in (CLIENT, PAGE_TRANSITIONS, MODE_WATCH, PLEXAMP_PERSISTENT):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["node", "--check", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_client_uses_screen_authority_and_never_controls_audio(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("fetch('/api/screen/state'", text)
        self.assertIn("post('apply'", text)
        self.assertIn("recommended_screen", text)
        self.assertNotIn("/api/airplay/control", text)
        self.assertNotIn("/player/playback/", text)
        self.assertNotIn("systemctl", text)

    def test_deliberate_page_arrival_opens_one_explicit_screen_lease(self):
        client = CLIENT.read_text(encoding="utf-8")
        transitions = PAGE_TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("consumeExplicitNavigation", transitions)
        self.assertIn("leasableRoutes", transitions)
        self.assertIn("window.ACPNavigationState?.consumeExplicitNavigation", client)
        self.assertIn("Boolean(explicitNavigation) || surface === 'settings'", client)
        self.assertIn("explicit-navigation-arrival", client)
        self.assertIn("await post('open'", client)

    def test_explicit_open_is_never_dropped_behind_pointer_activity(self):
        text = CLIENT.read_text(encoding="utf-8")

        self.assertIn("let postTail = Promise.resolve();", text)
        self.assertIn("const guaranteed = action === 'open'", text)
        self.assertIn("queuedNonApplyPosts", text)
        self.assertIn("isNavigationGesture", text)
        self.assertIn("initialise().finally", text)
        self.assertNotIn("if (posting && action !== 'apply') return null", text)

    def test_manual_open_is_queued_after_in_flight_activity(self):
        harness = f"""
const fs = require('fs');

(async () => {{
  const listeners = {{}};
  const calls = [];
  let holdInteraction = false;
  let releaseInteraction = null;

  const response = (screen = {{}}) => ({{
    ok: true,
    json: async () => ({{ screen }}),
  }});

  global.fetch = (url, options = {{}}) => {{
    if (options.method === 'POST') {{
      const body = JSON.parse(options.body || '{{}}');
      calls.push(body);
      if (holdInteraction && body.action === 'interaction') {{
        return new Promise((resolve) => {{
          releaseInteraction = () => resolve(response({{}}));
        }});
      }}
      return Promise.resolve(response({{}}));
    }}
    return Promise.resolve(response({{}}));
  }};

  global.window = {{
    location: {{ pathname: '/clock', assign: () => {{}} }},
    addEventListener: (name, callback) => {{
      (listeners[name] ||= []).push(callback);
    }},
    setInterval: () => 0,
    setTimeout: () => 0,
    ACPPlexamp: {{ isOpen: () => false, isVisiblyOpen: () => false }},
    ACPDashboardPreferences: {{ read: () => ({{ idleReturnMode: 'clock' }}) }},
    ACPNavigationState: {{
      consumeExplicitNavigation: () => null,
      isLeaving: () => false,
    }},
  }};

  global.document = {{
    getElementById: () => null,
    body: {{ dataset: {{ activePage: 'clock', defaultMode: 'clock' }} }},
    documentElement: {{ dataset: {{}} }},
    activeElement: null,
  }};

  eval(fs.readFileSync({json.dumps(str(CLIENT))}, 'utf8'));
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  calls.length = 0;

  holdInteraction = true;
  window.ACPScreenProjection.markActivity('outer-pointerdown', {{
    force: true,
    surface: 'plexamp',
  }});
  await new Promise((resolve) => setImmediate(resolve));

  for (const callback of listeners['acp:manual-screen-open'] || []) {{
    callback({{ detail: {{ surface: 'clock', source: 'navigation-link' }} }});
  }}
  await new Promise((resolve) => setImmediate(resolve));

  const beforeRelease = calls.map((call) => [call.action, call.surface]);
  if (!releaseInteraction) throw new Error('The interaction request was not held.');
  releaseInteraction();
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  console.log(JSON.stringify({{
    beforeRelease,
    afterRelease: calls.map((call) => [call.action, call.surface]),
  }}));
}})().catch((error) => {{
  console.error(error.stack || String(error));
  process.exit(1);
}});
"""
        result = subprocess.run(
            ["node", "-e", harness],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        values = json.loads(result.stdout.strip())
        self.assertEqual(values["beforeRelease"], [["interaction", "plexamp"]])
        self.assertEqual(
            values["afterRelease"],
            [["interaction", "plexamp"], ["open", "clock"]],
        )

    def test_projected_plexamp_open_cannot_create_a_manual_lease(self):
        client = CLIENT.read_text(encoding="utf-8")
        persistent = PLEXAMP_PERSISTENT.read_text(encoding="utf-8")

        self.assertIn("manual: false", client)
        self.assertIn("source: 'screen-projection'", client)
        self.assertIn("function announceManualOpen", persistent)
        self.assertIn("options.manual === false || options.updateMode === false", persistent)
        self.assertNotIn("plexamp-surface-opened", client)
        self.assertNotIn("new MutationObserver(observeOpenState)", client)

    def test_projected_navigation_cannot_create_an_explicit_lease(self):
        client = CLIENT.read_text(encoding="utf-8")
        transitions = PAGE_TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("automatic: true", client)
        self.assertIn("source: 'screen-projection'", client)
        self.assertIn("isAutomaticNavigation", transitions)
        self.assertIn("if (isAutomaticNavigation(options)", transitions)
        self.assertIn("rememberNavigation(target, options)", transitions)

    def test_plexamp_iframe_activity_cannot_cancel_another_surface_lease(self):
        text = CLIENT.read_text(encoding="utf-8")

        self.assertIn("function anotherSurfaceOwnsLease", text)
        self.assertIn("function plexampActivityAllowed", text)
        self.assertIn("if (!plexampActivityAllowed()) return", text)
        self.assertIn("document.activeElement === frame && plexampActivityAllowed()", text)
        self.assertNotIn("frame.contentDocument", text)
        self.assertNotIn("frame.contentWindow.document", text)

    def test_logical_plexamp_projection_repairs_an_invisible_overlay(self):
        client = CLIENT.read_text(encoding="utf-8")
        persistent = PLEXAMP_PERSISTENT.read_text(encoding="utf-8")

        self.assertIn("function reconcilePlexampVisual", client)
        self.assertIn("window.ACPPlexamp?.ensureVisible", client)
        self.assertIn("current !== 'plexamp' || recommended !== 'plexamp'", client)
        self.assertIn("function ensureVisible", persistent)
        self.assertIn("function isVisiblyOpen", persistent)
        self.assertIn("lastVisibilityRepair", persistent)

    def test_client_cannot_manufacture_repeating_activity(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertNotIn("IdleDetector", text)
        self.assertNotIn("idleDetector", text)
        self.assertNotIn("frameEngaged", text)
        self.assertNotIn("heartbeatMs", text)
        self.assertNotIn("plexamp-frame-active-heartbeat", text)
        self.assertNotIn("setInterval(() => {\n    if (\n      currentSurface() === 'plexamp'", text)

    def test_stationary_mouse_hover_is_one_interaction_only(self):
        text = CLIENT.read_text(encoding="utf-8")
        pointer_enter = text.split("frame.addEventListener('pointerenter'", 1)[1].split(
            "frame.addEventListener('focus'", 1
        )[0]

        self.assertIn("markActivity('plexamp-frame-pointerenter'", pointer_enter)
        self.assertNotIn("setInterval", pointer_enter)
        self.assertNotIn("frameEngaged", pointer_enter)

    def test_legacy_idle_return_is_not_loaded(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("js/screen-projection.js", text)
        self.assertIn("20260729-plexamp-visual-lease-authority", text)
        self.assertNotIn("js/idle-return.js", text)

    def test_navigation_ownership_is_split_once_by_intent(self):
        projection = CLIENT.read_text(encoding="utf-8")
        recovery = MODE_WATCH.read_text(encoding="utf-8")
        transitions = PAGE_TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("recommended_screen", projection)
        self.assertIn("window.ACPNavigate", projection)
        self.assertIn("window.ACPNavigate = navigate", transitions)
        self.assertIn("document.addEventListener('click'", transitions)
        self.assertNotIn("ACPNavigate", recovery)
        self.assertNotIn("window.location.assign", recovery)
        self.assertNotIn("requestedMode", recovery)
        self.assertNotIn("ACPPlexamp.show", recovery)
        self.assertNotIn("ACPPlexamp.hide", recovery)

    def test_real_runner_registers_screen_projection_before_state_apis(self):
        text = RUNNER.read_text(encoding="utf-8")
        projection = text.index("register_screen_projection(app, application_state_hub, dashboard)")
        state_api = text.index("register_application_state_api(app, application_state_hub)")
        self.assertLess(projection, state_api)


if __name__ == "__main__":
    unittest.main()
