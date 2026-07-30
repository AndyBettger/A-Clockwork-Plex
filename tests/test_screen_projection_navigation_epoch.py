from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "screen-projection.js"


class ScreenProjectionNavigationEpochTests(unittest.TestCase):
    def test_manual_navigation_invalidates_an_in_flight_projection_response(self):
        harness = f"""
const fs = require('fs');

(async () => {{
  const listeners = {{}};
  let intervalCallback = null;
  let overlayVisible = true;
  let holdState = false;
  let releaseState = null;
  let ensureVisibleCalls = 0;
  let showCalls = 0;

  const response = (screen = {{}}) => ({{
    ok: true,
    json: async () => ({{ screen }}),
  }});

  global.fetch = (_url, options = {{}}) => {{
    const body = JSON.parse(options.body || '{{}}');
    if (holdState && body.action === 'state') {{
      return new Promise((resolve) => {{
        releaseState = () => resolve(response({{
          current_screen: 'plexamp',
          visible_surface: 'plexamp',
          recommended_screen: 'plexamp',
          decision_reason: 'plexamp-owns-audio',
          should_apply: false,
          should_present: false,
          lease: {{ active: false }},
          input_activity: {{}},
        }}));
      }});
    }}
    return Promise.resolve(response({{
      current_screen: overlayVisible ? 'plexamp' : 'settings',
      visible_surface: overlayVisible ? 'plexamp' : 'settings',
      recommended_screen: overlayVisible ? 'plexamp' : 'settings',
      should_apply: false,
      should_present: false,
      lease: {{ active: false }},
      input_activity: {{}},
    }}));
  }};

  global.window = {{
    location: {{ pathname: '/settings', assign: () => {{}} }},
    addEventListener: (name, callback) => {{
      (listeners[name] ||= []).push(callback);
    }},
    setInterval: (callback) => {{ intervalCallback = callback; return 1; }},
    setTimeout: (callback) => {{ callback(); return 1; }},
    ACPPlexamp: {{
      isOpen: () => overlayVisible,
      isVisiblyOpen: () => overlayVisible,
      ensureVisible: () => {{ ensureVisibleCalls += 1; overlayVisible = true; }},
      show: () => {{ showCalls += 1; overlayVisible = true; }},
    }},
    ACPDashboardPreferences: {{ read: () => ({{ idleReturnMode: 'clock' }}) }},
    ACPNavigationState: {{
      consumeExplicitNavigation: () => null,
      isLeaving: () => false,
      isPresenting: () => false,
    }},
  }};

  const navLink = {{
    closest: (selector) => selector.includes('.main-nav') ? navLink : null,
  }};

  global.document = {{
    getElementById: () => null,
    body: {{ dataset: {{ activePage: 'settings', defaultMode: 'clock' }} }},
    documentElement: {{ dataset: {{}} }},
    activeElement: null,
  }};

  eval(fs.readFileSync({json.dumps(str(CLIENT))}, 'utf8'));
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  if (typeof intervalCallback !== 'function') throw new Error('Projection interval was not registered.');

  holdState = true;
  intervalCallback();
  await new Promise((resolve) => setImmediate(resolve));
  if (!releaseState) throw new Error('The state request was not held.');

  for (const callback of listeners.pointerdown || []) {{
    callback({{ target: navLink }});
  }}
  overlayVisible = false;
  releaseState();
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  console.log(JSON.stringify({{
    ensureVisibleCalls,
    showCalls,
    navigationEpoch: window.ACPScreenProjection.navigationEpoch(),
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
        self.assertEqual(values["ensureVisibleCalls"], 0)
        self.assertEqual(values["showCalls"], 0)
        self.assertGreater(values["navigationEpoch"], 0)

    def test_projection_rechecks_navigation_after_each_await(self):
        text = CLIENT.read_text(encoding="utf-8")

        self.assertIn("let navigationEpoch = 0", text)
        self.assertIn("function invalidateProjectionResponses", text)
        self.assertIn("epoch !== navigationEpoch || navigationBusy()", text)
        self.assertIn("navigationEpoch: () => navigationEpoch", text)


if __name__ == "__main__":
    unittest.main()
