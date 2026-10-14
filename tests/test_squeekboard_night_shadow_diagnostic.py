"""C3 diagnostics: local-only one-shot browser/server comparison, never OSK writes."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
SOURCE = ROOT / "app/squeekboard_night_shadow_diagnostic.py"
spec = importlib.util.spec_from_file_location("acp_c3_shadow_diagnostic_test", SOURCE)
assert spec and spec.loader
diagnostic = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = diagnostic
spec.loader.exec_module(diagnostic)


def observation():
    return {
        "browserStatus": {
            "enabled": True,
            "start": "09:31",
            "end": "09:31",  # all-day as in ACP's JS
            "style": "classic",
            "activeStyle": "same",
            "wakeSeconds": 5,
            "scheduled": True,
            "active": True,
            "previewing": False,
            "interacting": False,
            "effectiveStyle": "classic",
        },
        "browserAlarmVisible": False,
        "priorSequence": None,
    }


class C3NightShadowDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.config = mock.Mock(return_value={
            "dashboard": {
                "night_dim_enabled": True,
                "night_dim_start": "09:31",
                "night_dim_end": "09:31",
                "night_dim_style": "classic",
                "night_dim_active_style": "same",
                "night_dim_wake_seconds": 5,
            }
        })
        self.alarm = mock.Mock(return_value={"screen_required": False})
        self.input = mock.Mock(return_value={"sequence": 44})
        diagnostic.register_c3_shadow_diagnostic_api(
            self.app, config_loader=self.config, alarm_status=self.alarm,
            input_snapshot=self.input,
        )
        self.client = self.app.test_client()

    def post(self, data=None, *, origin="http://localhost",
             addr="127.0.0.1", host="localhost", extra_headers=None):
        headers={"Origin": origin, "Content-Type": "application/json"}
        headers.update(extra_headers or {})
        return self.client.post(
            "/api/osk/c3/night-shadow/compare",
            data=json.dumps(data if data is not None else observation(),
                            separators=(",", ":")),
            headers=headers, environ_overrides={"REMOTE_ADDR": addr},
            base_url="http://" + host,
        )

    def test_manual_local_comparison_returns_no_writes_or_retention(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["retained"] is False)
        self.assertTrue(data["cssWritten"] is False)
        self.assertEqual(data["authority"],
                         "diagnostic-only; browser continues to own C3 CSS")
        self.assertEqual(data["inputSequence"], 44)
        self.assertEqual(data["comparisons"]["scheduled"], "match")
        self.assertEqual(data["comparisons"]["alarm_presentation"], "agree")
        self.assertEqual(data["comparisons"]["linux_input"], "initial-baseline")
        self.assertEqual(self.config.call_count, 1)
        self.assertEqual(self.alarm.call_count, 1)
        self.assertEqual(self.input.call_count, 1)

    def test_second_click_is_a_diagnostic_sequence_change_not_a_wake(self):
        status = observation()
        status["priorSequence"] = 42
        data = self.post(status).get_json()
        self.assertEqual(data["comparisons"]["linux_input"], "activity-observed")
        self.assertTrue(any("no wake scheduled" in x for x in data["limitations"]))

    def test_lan_origin_proxy_and_bad_content_are_denied_before_all_readers(self):
        attempts = (
            dict(addr="192.168.1.14"),
            dict(origin="http://evil.example"),
            dict(host="evil.example", origin="http://evil.example"),
            dict(extra_headers={"X-Forwarded-For": "192.168.0.1"}),
            dict(extra_headers={"Sec-Fetch-Site": "cross-site"}),
        )
        for attempt in attempts:
            with self.subTest(attempt=attempt):
                response = self.post(**attempt)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.config.call_count, 0)
        self.assertEqual(self.alarm.call_count, 0)
        self.assertEqual(self.input.call_count, 0)
        self.assertEqual(self.client.get(
            "/api/osk/c3/night-shadow/compare").status_code, 405)

    def test_json_envelope_strict_and_oversize_denied(self):
        cases=(
            {"other": True},
            dict(observation(), cssPalette="red"),
            dict(observation(), browserAlarmVisible="false"),
            dict(observation(), priorSequence=True),
            dict(observation(), priorSequence=-1),
            dict(observation(), browserStatus={"active": True}),
        )
        for item in cases:
            with self.subTest(item=item):
                response=self.post(item)
                self.assertEqual(response.status_code, 400, response.get_json())
        over=self.post(dict(observation(), extra="x"*500))
        self.assertEqual(over.status_code, 403)
        self.assertEqual(self.config.call_count, 0)

    def test_malformed_server_observations_are_safe_and_not_logged_as_config(self):
        self.alarm.return_value={"screen_required": "yes"}
        r=self.post()
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("yes", json.dumps(r.get_json()))
        self.alarm.return_value={"screen_required": False}
        self.input.return_value={"sequence": -1}
        self.assertEqual(self.post().status_code, 400)

    def test_registration_idempotent_and_only_explicit_post(self):
        diagnostic.register_c3_shadow_diagnostic_api(
            self.app, config_loader=self.config, alarm_status=self.alarm,
            input_snapshot=self.input,
        )
        routes=[r for r in self.app.url_map.iter_rules()
                if r.rule=="/api/osk/c3/night-shadow/compare"]
        self.assertEqual(len(routes), 1)
        self.assertNotIn("GET", routes[0].methods)

    def test_client_is_opt_in_and_has_no_auto_poll_or_css_write(self):
        script=(ROOT/"app/static/js/osk-night-shadow-diagnostic.js").read_text()
        template=(ROOT/"app/templates/base.html").read_text()
        runner=(ROOT/"app/runner.py").read_text()
        self.assertIn("new URLSearchParams(window.location.search).has('c3-shadow')", script)
        self.assertIn("button.addEventListener('click'", script)
        self.assertIn("'/api/osk/c3/night-shadow/compare'", script)
        self.assertIn("document.body?.dataset?.activePage !== 'settings'", script)
        self.assertIn("osk-night-shadow-diagnostic.js", template)
        self.assertIn("register_c3_shadow_diagnostic_api(", runner)
        for bad in ("window.setInterval", "setTimeout(", "systemctl",
                    "/api/osk/c3/theme-sync'", "style.css", "localStorage",
                    "sessionStorage", "window.location.reload"):
            self.assertNotIn(bad, script)

    def test_guard_payload_fits_original_strict_384_byte_ceiling(self):
        compact=json.dumps(observation(), separators=(",", ":")).encode()
        self.assertLessEqual(len(compact), 384)


if __name__=="__main__":
    unittest.main()
