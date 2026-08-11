from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect-weather-underground-payloads.py"
SPEC = importlib.util.spec_from_file_location("acp_wu_payload_inspector", SCRIPT)
INSPECTOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(INSPECTOR)


CURRENT = {
    "observations": [
        {
            "stationID": "ITEST1",
            "obsTimeUtc": "2026-08-11T01:30:00Z",
            "humidity": 77,
            "imperial": {
                "temp": 61.2,
                "pressure": 29.91,
                "windSpeed": 3.1,
            },
        }
    ]
}

AGGREGATE_HISTORY = {
    "observations": [
        {
            "stationID": "ITEST1",
            "obsTimeUtc": "2026-08-11T00:00:00Z",
            "imperial": {
                "pressureAvg": 29.90,
                "pressureMin": 29.88,
                "pressureMax": 29.92,
            },
        },
        {
            "stationID": "ITEST1",
            "obsTimeUtc": "2026-08-11T01:00:00Z",
            "imperial": {
                "pressureAvg": 29.91,
                "pressureMin": 29.89,
                "pressureMax": 29.93,
            },
        },
    ]
}

LIKE_FOR_LIKE_HISTORY = {
    "observations": [
        {
            "stationID": "ITEST1",
            "obsTimeUtc": "2026-08-11T00:00:00Z",
            "imperial": {"pressure": 29.90},
        },
        {
            "stationID": "ITEST1",
            "obsTimeUtc": "2026-08-11T01:00:00Z",
            "imperial": {"pressure": 29.91},
        },
    ]
}


class WeatherUndergroundPayloadInspectorTests(unittest.TestCase):
    def test_aggregate_history_is_not_promoted_as_like_for_like_pressure(self) -> None:
        assessment = INSPECTOR.assess_like_for_like_pressure_history(AGGREGATE_HISTORY)
        self.assertFalse(assessment["candidate"])
        self.assertEqual(assessment["matching_rows"], 0)
        self.assertIn("imperial.pressureAvg", assessment["aggregate_pressure_paths"])
        self.assertIn("must not be treated as instantaneous samples", assessment["reason"])

    def test_like_for_like_history_is_only_reported_as_review_candidate(self) -> None:
        assessment = INSPECTOR.assess_like_for_like_pressure_history(LIKE_FOR_LIKE_HISTORY)
        self.assertTrue(assessment["candidate"])
        self.assertEqual(assessment["matching_rows"], 2)
        self.assertIn("evidence for review", assessment["reason"])

    def test_inspection_uses_both_existing_wu_url_builders_without_exposing_urls(self) -> None:
        seen: list[str] = []

        def fetcher(url: str, timeout: float):
            self.assertEqual(timeout, 7.0)
            seen.append(url)
            return CURRENT if "/observations/current" in url else AGGREGATE_HISTORY

        report = INSPECTOR.inspect_payloads(
            "ITEST1",
            "secret-that-must-not-render",
            timeout=7.0,
            fetcher=fetcher,
        )
        rendered = INSPECTOR.render_report(report)

        self.assertEqual(len(seen), 2)
        self.assertTrue(any("/observations/current" in url for url in seen))
        self.assertTrue(any("/observations/all/1day" in url for url in seen))
        self.assertTrue(all("apiKey=secret-that-must-not-render" in url for url in seen))
        self.assertNotIn("secret-that-must-not-render", rendered)
        self.assertNotIn("api.weather.com", rendered)
        self.assertIn("State mutation: none", rendered)
        self.assertIn("WU_PAYLOAD_INSPECTION=PASS", rendered)
        self.assertIn("Like-for-like history candidate: NO", rendered)

    def test_current_mapper_contract_is_included_in_report(self) -> None:
        def fetcher(url: str, _timeout: float):
            return CURRENT if "/observations/current" in url else LIKE_FOR_LIKE_HISTORY

        report = INSPECTOR.inspect_payloads("ITEST1", "secret", timeout=5.0, fetcher=fetcher)
        mapping = report["current_dashboard_mapping"]
        self.assertTrue(mapping["ok"])
        self.assertIn("baromrelin", mapping["mapped_fields"])
        self.assertIn("dateutc", mapping["mapped_fields"])

    def test_secret_file_validation_rejects_multiline_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            multiline = root / "multiline"
            multiline.write_text("one\ntwo\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "one non-empty line"):
                INSPECTOR.read_secret_file(multiline)

            real = root / "real"
            real.write_text("secret\n", encoding="utf-8")
            link = root / "link"
            link.symlink_to(real)
            with self.assertRaisesRegex(ValueError, "not a symlink"):
                INSPECTOR.read_secret_file(link)

    def test_source_is_diagnostic_only_and_has_no_state_write_path(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("diagnostic only", source)
        self.assertIn("build_weather_underground_recent_history_url", source)
        self.assertIn("weather_underground_current_to_dashboard", source)
        self.assertNotIn("WeatherObservationStore", source)
        self.assertNotIn("write_observation", source)
        self.assertNotIn("state.json", source)
        self.assertNotIn("config.json", source)
        self.assertNotIn("apiKey=", source)


if __name__ == "__main__":
    unittest.main()
