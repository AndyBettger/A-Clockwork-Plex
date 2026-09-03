from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.plexamp_commissioning import (
    MANAGED_AUDIO_DEVICE_LABEL,
    PlexampCommissioningConflict,
    PlexampCommissioningError,
    PlexampCommissioningManager,
)


class FakePlexampApi:
    def __init__(self) -> None:
        self.settings = {
            "playerName": "Bedroom Plexamp",
            "audioDeviceUuid": "",
        }
        self.audio_choices = [
            ["", "Follows system output"],
            ["hw:7,0", MANAGED_AUDIO_DEVICE_LABEL],
        ]
        self.calls: list[tuple[str, str]] = []
        self.fail_put_name: str | None = None
        self.ignore_put_name: str | None = None

    def __call__(self, method: str, path: str, timeout: int):
        del timeout
        self.calls.append((method, path))
        parsed = urlparse(path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if method == "GET" and parsed.path == "/settings" and not parsed.query:
            return {
                **self.settings,
                "authenticationToken": "not-exposed-by-manager",
                "unrelatedSetting": "ignored",
            }
        if method == "GET" and parsed.path == "/settings/values":
            if query.get("name") == ["audioDeviceUuid"]:
                return list(self.audio_choices)
            raise AssertionError(path)
        if method == "PUT" and parsed.path == "/settings":
            name = query.get("name", [None])[0]
            value = query.get("value", [None])[0]
            if name == self.fail_put_name:
                raise PlexampCommissioningError(f"injected failure for {name}")
            if name not in {"playerName", "audioDeviceUuid"} or not isinstance(value, str):
                raise AssertionError(path)
            if name != self.ignore_put_name:
                self.settings[name] = value
            return {"ok": True}
        raise AssertionError((method, path))


class PlexampCommissioningTests(unittest.TestCase):
    def manager(self, root: Path, api: FakePlexampApi) -> PlexampCommissioningManager:
        home = root / "home" / "clockuser"
        home.mkdir(parents=True)
        return PlexampCommissioningManager(home=home, requester=api)

    def test_first_commission_accepts_unset_audio_and_selects_managed_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)

            result = manager.commission()

            self.assertTrue(result["verified"])
            self.assertTrue(result["baseline_captured"])
            self.assertEqual(result["changed_count"], 1)
            self.assertEqual(api.settings["playerName"], "Bedroom Plexamp")
            self.assertEqual(api.settings["audioDeviceUuid"], "hw:7,0")
            baseline = json.loads(manager.baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(baseline, {"schema_version": 1, "player_name": "Bedroom Plexamp"})
            self.assertEqual(manager.baseline_path.stat().st_mode & 0o777, 0o600)

    def test_repeat_commission_never_recaptures_changed_player_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)
            manager.commission()
            api.settings["playerName"] = "Temporary renamed player"
            api.settings["audioDeviceUuid"] = ""

            result = manager.commission()

            self.assertFalse(result["baseline_captured"])
            self.assertEqual(result["changed_count"], 2)
            self.assertEqual(api.settings["playerName"], "Bedroom Plexamp")
            self.assertEqual(api.settings["audioDeviceUuid"], "hw:7,0")
            baseline = json.loads(manager.baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(baseline["player_name"], "Bedroom Plexamp")

    def test_public_plan_exposes_only_change_shape_not_player_name_or_device_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)
            manager.commission()
            api.settings["playerName"] = "Secret-ish room label"
            api.settings["audioDeviceUuid"] = ""

            plan = manager.plan()
            encoded = json.dumps(plan, sort_keys=True)

            self.assertTrue(plan["ready"])
            self.assertEqual(plan["change_count"], 2)
            self.assertTrue(plan["player_name_changed"])
            self.assertTrue(plan["audio_output_changed"])
            self.assertNotIn("Secret-ish room label", encoded)
            self.assertNotIn("Bedroom Plexamp", encoded)
            self.assertNotIn("hw:7,0", encoded)
            self.assertNotIn("default", encoded)
            self.assertEqual(plan["audio_output_label"], MANAGED_AUDIO_DEVICE_LABEL)

    def test_missing_baseline_plan_is_inspection_only_and_does_not_read_plexamp_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)

            plan = manager.plan()

            self.assertFalse(plan["ready"])
            self.assertFalse(plan["baseline_present"])
            self.assertEqual(plan["reason"], "baseline-missing")
            self.assertEqual(api.calls, [])

    def test_stale_fingerprint_refuses_before_any_put(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)
            manager.commission()
            api.settings["playerName"] = "Needs reset"
            plan = manager.plan()
            api.settings["playerName"] = "Changed after preview"
            call_count = len(api.calls)

            with self.assertRaises(PlexampCommissioningConflict):
                manager.apply(fingerprint=plan["fingerprint"])

            later = api.calls[call_count:]
            self.assertFalse(any(method == "PUT" for method, _path in later))
            self.assertEqual(api.settings["playerName"], "Changed after preview")

    def test_second_write_failure_rolls_first_write_back_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)
            manager.commission()
            api.settings["playerName"] = "Temporary name"
            api.settings["audioDeviceUuid"] = ""
            before = dict(api.settings)
            plan = manager.plan()
            api.fail_put_name = "audioDeviceUuid"

            with self.assertRaises(PlexampCommissioningError) as context:
                manager.apply(fingerprint=plan["fingerprint"])

            self.assertTrue(context.exception.rolled_back)
            self.assertEqual(context.exception.rollback_failures, [])
            self.assertEqual(api.settings, before)

    def test_verification_failure_can_roll_audio_back_to_exact_unset_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)
            manager.commission()
            api.settings["audioDeviceUuid"] = ""
            plan = manager.plan()
            api.ignore_put_name = "audioDeviceUuid"
            call_count = len(api.calls)

            with self.assertRaises(PlexampCommissioningError) as context:
                manager.apply(fingerprint=plan["fingerprint"])

            self.assertTrue(context.exception.rolled_back)
            self.assertEqual(context.exception.rollback_failures, [])
            self.assertEqual(api.settings["audioDeviceUuid"], "")
            later_puts = [
                path for method, path in api.calls[call_count:] if method == "PUT"
            ]
            self.assertTrue(any("name=audioDeviceUuid&value=" in path for path in later_puts))

    def test_missing_or_ambiguous_managed_audio_route_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = FakePlexampApi()
            manager = self.manager(root, api)

            api.audio_choices = [["", "Follows system output"]]
            with self.assertRaises(PlexampCommissioningError):
                manager.commission()

            # A failed first attempt may have captured the stable claimed player name;
            # it must still refuse audio mutation until the route is unambiguous.
            api.audio_choices = [
                ["route-a", MANAGED_AUDIO_DEVICE_LABEL],
                ["route-b", MANAGED_AUDIO_DEVICE_LABEL],
            ]
            with self.assertRaises(PlexampCommissioningError):
                manager.commission()
            self.assertEqual(api.settings["audioDeviceUuid"], "")

    def test_non_loopback_commissioning_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                PlexampCommissioningManager(
                    home=Path(directory),
                    base_url="https://example.com:32500",
                    requester=FakePlexampApi(),
                )


if __name__ == "__main__":
    unittest.main()
