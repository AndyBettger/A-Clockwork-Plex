from __future__ import annotations

import json
import unittest
from copy import deepcopy

from app.configuration_restore import ConfigurationRestorePlanner


class ConfigurationRestoreV2Tests(unittest.TestCase):
    @staticmethod
    def v1_backup() -> dict:
        return {
            "schema_version": 1,
            "source": {
                "application": "A Clockwork Plex",
                "app_version": "0.4.0",
                "release_tag": "v0.4.0",
            },
            "a_clockwork_plex": {
                "settings": {
                    "dashboard": {"idle_timeout_seconds": 180},
                    "display": {},
                    "weather": {},
                    "alarms": {},
                    "airplay": {},
                    "news": {},
                },
                "audio": {},
            },
            "plexamp": {
                "source_version": "4.13.2",
                "headless_preferences": {},
                "browser_preferences": {
                    "schema_version": 1,
                    "home": {
                        "order": ["music.recent.added"],
                        "hidden": [],
                    },
                },
            },
        }

    @classmethod
    def v2_backup(cls) -> dict:
        backup = cls.v1_backup()
        backup["schema_version"] = 2
        backup["plexamp"].pop("headless_preferences", None)
        backup["plexamp"]["portable_settings"] = {
            "schema_version": 1,
            "settings_schema_fingerprint": "deadbeef",
            "settings": {
                "cacheSize": 65536,
                "nestedPortable": {
                    "mode": "source-choice",
                    "levels": [4, 5],
                },
            },
        }
        backup["plexamp"]["browser_preferences"] = {
            "schema_version": 2,
            "home": {
                "schema_version": 2,
                "order": [
                    {"type": "custom", "ref": "custom-1"},
                    {"type": "builtin", "id": "music.recent.added"},
                ],
                "hidden": [
                    {"type": "builtin", "id": "music.recent.plays"},
                ],
                "presentation": [
                    {
                        "target": {"type": "builtin", "id": "music.recent.added"},
                        "settings": {"type": "carousel", "subtype": "block", "size": 180},
                    },
                    {
                        "target": {"type": "custom", "ref": "custom-1"},
                        "settings": {
                            "title": "ACP Portable Artist Section",
                            "type": "carousel",
                            "size": 180,
                        },
                    },
                ],
                "custom_sections": [
                    {
                        "ref": "custom-1",
                        "kind": "artist",
                        "query_suffix": "/all?type=8",
                    },
                ],
            },
        }
        return backup

    def planner(self) -> ConfigurationRestorePlanner:
        current = self.v1_backup()
        return ConfigurationRestorePlanner(current_backup=lambda: deepcopy(current))

    def test_schema_v1_contract_remains_accepted(self):
        result = self.planner().plan(self.v1_backup())
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], 1)
        self.assertTrue(result["plexamp_browser"]["present"])
        self.assertEqual(result["plexamp_browser"]["schema_version"], 1)
        self.assertEqual(result["plexamp_browser"]["order_items"], 1)
        self.assertFalse(result["plexamp_portable_settings"]["present"])

    def test_schema_v2_validates_browser_owned_native_and_home_without_exposing_values(self):
        candidate = self.v2_backup()
        result = self.planner().plan(candidate)

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], 2)
        self.assertFalse(result["restore_available"])
        self.assertEqual(result["change_count"], 0)
        self.assertEqual(
            result["plexamp_portable_settings"],
            {
                "present": True,
                "setting_items": 2,
                "comparison": "deferred-to-live-browser",
            },
        )
        self.assertEqual(result["plexamp_browser"]["schema_version"], 2)
        self.assertEqual(result["plexamp_browser"]["order_items"], 2)
        self.assertEqual(result["plexamp_browser"]["hidden_items"], 1)
        self.assertEqual(result["plexamp_browser"]["presentation_items"], 2)
        self.assertEqual(result["plexamp_browser"]["custom_section_items"], 1)

        encoded = json.dumps(result, sort_keys=True)
        for forbidden_value in (
            "65536",
            "source-choice",
            "music.recent.added",
            "music.recent.plays",
            "ACP Portable Artist Section",
            "/all?type=8",
            "deadbeef",
        ):
            self.assertNotIn(forbidden_value, encoded)

    def test_schema_v2_still_reports_server_owned_acp_changes(self):
        candidate = self.v2_backup()
        candidate["a_clockwork_plex"]["settings"]["dashboard"]["idle_timeout_seconds"] = 321

        result = self.planner().plan(candidate)

        self.assertTrue(result["server_restore_available"])
        self.assertTrue(result["restore_available"])
        self.assertEqual(result["server_change_count"], 1)
        self.assertEqual(
            result["server_changed_paths"],
            ["a_clockwork_plex.settings.dashboard.idle_timeout_seconds"],
        )
        self.assertEqual(result["plexamp_headless_detected_change_count"], 0)

    def test_schema_v2_token_ignores_legacy_headless_observer_but_v1_stays_protected(self):
        current = self.v1_backup()
        current["plexamp"]["headless_preferences"] = {"cacheSize": 32768}
        planner = ConfigurationRestorePlanner(
            current_backup=lambda: deepcopy(current),
            plexamp_preference_status=lambda: {
                "restore_ready": True,
                "installed_version": "4.13.2",
            },
        )

        v2 = self.v2_backup()
        v2["a_clockwork_plex"]["settings"]["dashboard"]["idle_timeout_seconds"] = 321
        v2_before = planner.plan(v2)["preview_token"]
        current["plexamp"]["headless_preferences"]["cacheSize"] = 16384
        v2_after = planner.plan(v2)["preview_token"]
        self.assertEqual(v2_before, v2_after)

        current["plexamp"]["headless_preferences"]["cacheSize"] = 32768
        v1 = self.v1_backup()
        v1["plexamp"]["headless_preferences"] = {"cacheSize": 65536}
        v1_before = planner.plan(v1)["preview_token"]
        current["plexamp"]["headless_preferences"]["cacheSize"] = 16384
        v1_after = planner.plan(v1)["preview_token"]
        self.assertNotEqual(v1_before, v1_after)

    def test_schema_versions_do_not_allow_mixed_plexamp_ownership(self):
        v1 = self.v1_backup()
        v1["plexamp"]["portable_settings"] = {
            "schema_version": 1,
            "settings_schema_fingerprint": "deadbeef",
            "settings": {},
        }
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            self.planner().plan(v1)

        v2 = self.v2_backup()
        v2["plexamp"]["headless_preferences"] = {"cacheSize": 12345}
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            self.planner().plan(v2)

    def test_schema_v2_rejects_invalid_native_fingerprint(self):
        candidate = self.v2_backup()
        candidate["plexamp"]["portable_settings"]["settings_schema_fingerprint"] = "NOT-A-FINGERPRINT"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.planner().plan(candidate)

    def test_schema_v2_rejects_nonportable_or_sensitive_native_setting_names(self):
        cases = {
            "runtime-owned": {"activeTab": "library"},
            "sensitive-top-level": {"sessionToken": "do-not-export"},
            "sensitive-nested": {"safeSetting": {"authToken": "do-not-export"}},
            "identity-owned": {"playerName": "Bedroom"},
        }
        for label, settings in cases.items():
            with self.subTest(label=label):
                candidate = self.v2_backup()
                candidate["plexamp"]["portable_settings"]["settings"] = settings
                with self.assertRaises(ValueError):
                    self.planner().plan(candidate)

    def test_schema_v2_rejects_generated_custom_uuid_as_builtin_reference(self):
        candidate = self.v2_backup()
        candidate["plexamp"]["browser_preferences"]["home"]["order"] = [
            {
                "type": "builtin",
                "id": "custom.hub.artist.88888888-8888-4888-8888-888888888888",
            }
        ]
        with self.assertRaisesRegex(ValueError, "built-in Home identifier"):
            self.planner().plan(candidate)

    def test_schema_v2_rejects_source_library_path_in_custom_query(self):
        candidate = self.v2_backup()
        candidate["plexamp"]["browser_preferences"]["home"]["custom_sections"][0][
            "query_suffix"
        ] = "/library/sections/9/all?type=8"
        with self.assertRaisesRegex(ValueError, "library-relative"):
            self.planner().plan(candidate)

    def test_schema_v2_rejects_raw_custom_source_or_titleless_custom_section(self):
        candidate = self.v2_backup()
        candidate["plexamp"]["browser_preferences"]["home"]["custom_sections"][0][
            "source"
        ] = "srv-source-context"
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            self.planner().plan(candidate)

        candidate = self.v2_backup()
        for row in candidate["plexamp"]["browser_preferences"]["home"]["presentation"]:
            if row["target"] == {"type": "custom", "ref": "custom-1"}:
                row["settings"].pop("title")
        with self.assertRaisesRegex(ValueError, "title-bearing"):
            self.planner().plan(candidate)

    def test_schema_v2_rejects_sensitive_or_traversing_custom_queries(self):
        queries = (
            "/all?authToken=secret",
            "/../all?type=8",
            "/all#fragment",
            "https://example.invalid/all",
        )
        for query in queries:
            with self.subTest(query=query):
                candidate = self.v2_backup()
                candidate["plexamp"]["browser_preferences"]["home"]["custom_sections"][0][
                    "query_suffix"
                ] = query
                with self.assertRaises(ValueError):
                    self.planner().plan(candidate)

    def test_unknown_top_level_schema_still_fails_closed(self):
        candidate = self.v2_backup()
        candidate["schema_version"] = 3
        with self.assertRaisesRegex(ValueError, "supported versions are 1, 2"):
            self.planner().plan(candidate)


if __name__ == "__main__":
    unittest.main()
