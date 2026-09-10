from __future__ import annotations

import importlib.util
import sys
import unittest
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rehearse-plexamp-home-scrub.py"


def load_module():
    spec = importlib.util.spec_from_file_location("acp_home_scrub_rehearsal_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Home scrub rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeTransport:
    @staticmethod
    def require_safe_port(port: int) -> int:
        if port < 1024 or port > 65535:
            raise RuntimeError("unsafe port")
        return port


class PlexampHomeScrubRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.template = cls.module.RUNTIME_TEMPLATE

    def test_source_compiles_without_syntax_warnings(self):
        source = SCRIPT.read_text(encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            compile(source, str(SCRIPT), "exec")

    def test_preserved_evidence_ports_are_refused(self):
        for port in range(9224, 9230):
            with self.subTest(port=port):
                with self.assertRaises(self.module.RehearsalError):
                    self.module.require_rehearsal_port(port, FakeTransport)
        self.assertEqual(self.module.require_rehearsal_port(9230, FakeTransport), 9230)

    def test_snapshot_path_is_pinned_to_var_tmp_and_debug_port(self):
        expected = Path("/var/tmp/plexamp-home-scrub-9230.json")
        self.assertEqual(self.module.require_snapshot_path(None, 9230), expected)
        self.assertEqual(self.module.require_snapshot_path(str(expected), 9230), expected)
        for bad in (
            "/tmp/plexamp-home-scrub-9230.json",
            "/var/tmp/other.json",
            "/var/tmp/plexamp-home-scrub-9231.json",
            "plexamp-home-scrub-9230.json",
        ):
            with self.subTest(path=bad):
                with self.assertRaises(self.module.RehearsalError):
                    self.module.require_snapshot_path(bad, 9230)

    def test_snapshot_key_classifier_is_exactly_the_closed_family_set(self):
        prefix = "mmkv.default\\discovery:customizations:ctx::/library/sections/9:"
        self.assertEqual(self.module.classify_snapshot_key(prefix + "order"), "order")
        self.assertEqual(self.module.classify_snapshot_key(prefix + "customHubs"), "customHubs")
        self.assertEqual(self.module.classify_snapshot_key(prefix + "hub:hidden"), "hidden")
        self.assertEqual(self.module.classify_snapshot_key(prefix + "hub:viewSettings"), "viewSettings")
        self.assertEqual(self.module.classify_snapshot_key(prefix + "hub:editing"), "editing")
        self.assertIsNone(self.module.classify_snapshot_key(prefix + "hub:futureThing"))
        self.assertIsNone(self.module.classify_snapshot_key("other.namespace:key"))

    def test_snapshot_validation_refuses_editing_duplicates_and_oversized_values(self):
        prefix = "mmkv.default\\discovery:customizations:ctx::/library/sections/9:"
        valid = [
            {"key": prefix + "order", "raw": "[]", "family": "order"},
            {"key": prefix + "hub:viewSettings", "raw": "{}", "family": "viewSettings"},
        ]
        self.assertEqual(len(self.module.validate_records(valid)), 2)

        with self.assertRaises(self.module.RehearsalError):
            self.module.validate_records([
                {"key": prefix + "hub:editing", "raw": "true", "family": "editing"}
            ])
        with self.assertRaises(self.module.RehearsalError):
            self.module.validate_records(valid + [dict(valid[0])])
        with self.assertRaises(self.module.RehearsalError):
            self.module.validate_records([
                {"key": prefix + "order", "raw": "x" * (self.module.MAX_RECORD_BYTES + 1), "family": "order"}
            ])

    def test_runtime_fails_closed_on_editing_unknown_or_invalid_state(self):
        self.assertIn("families.other > 0", self.template)
        self.assertIn("families.editing > 0", self.template)
        self.assertIn("status = 'unclassified-customization-keys'", self.template)
        self.assertIn("status = 'editing-active'", self.template)
        self.assertIn("MAX_STORAGE_KEYS = 2048", self.template)
        self.assertIn("MAX_RECORDS = 512", self.template)
        self.assertIn("MAX_RECORD_BYTES = 65536", self.template)
        self.assertIn("MAX_TOTAL_BYTES = 524288", self.template)

    def test_scrub_removes_only_individual_classified_records_never_storage_wholesale(self):
        self.assertIn("storage.removeItem(record.key)", self.template)
        self.assertNotIn("storage.clear(", self.template)
        self.assertNotIn("localStorage.clear(", self.template)
        self.assertIn("DURABLE = new Set(['order', 'hidden', 'viewSettings', 'customHubs'])", self.template)
        self.assertIn("if (!classified.valid || !DURABLE.has(classified.family)) continue", self.template)

    def test_scrub_has_stale_check_self_rollback_and_post_scrub_verification(self):
        self.assertIn("inventory.fingerprint !== EXPECTED_FINGERPRINT", self.template)
        self.assertIn("status: 'stale-target'", self.template)
        self.assertIn("storage.setItem(record.key, record.raw)", self.template)
        self.assertIn("status: 'scrub-failed'", self.template)
        self.assertIn("(after.internalRecords || []).length !== 0", self.template)

    def test_restore_requires_empty_target_and_exact_snapshot_fingerprint(self):
        self.assertIn("status: 'target-not-empty'", self.template)
        self.assertIn("restoreFingerprint !== EXPECTED_FINGERPRINT", self.template)
        self.assertIn("after.fingerprint !== EXPECTED_FINGERPRINT", self.template)
        self.assertIn("status: 'restore-failed'", self.template)

    def test_snapshot_file_contract_is_no_overwrite_no_follow_and_mode_0600(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("os.O_EXCL", source)
        self.assertIn('hasattr(os, "O_NOFOLLOW")', source)
        self.assertIn("0o600", source)
        self.assertIn("SNAPSHOT_ROOT = Path(\"/var/tmp\")", source)
        self.assertIn("refuse to overwrite rollback evidence", source)

    def test_runtime_output_never_emits_raw_home_keys_or_values(self):
        self.assertIn("raw_keys_emitted: false", self.template)
        self.assertIn("raw_values_emitted: false", self.template)
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if key != "records"', source)
        self.assertNotIn("print(capture", source)
        self.assertNotIn("print(records", source)

    def test_expression_builder_has_fixed_actions_and_json_encodes_restore_records(self):
        prefix = "mmkv.default\\discovery:customizations:ctx::/library/sections/9:"
        records = [{"key": prefix + "order", "raw": '["quoted\\\\value"]', "family": "order"}]
        expression = self.module.build_runtime_expression(
            "restore",
            expected_fingerprint="1234abcd",
            restore_records=records,
        )
        self.assertNotIn("__ACTION__", expression)
        self.assertNotIn("__EXPECTED_FINGERPRINT__", expression)
        self.assertNotIn("__RESTORE_RECORDS__", expression)
        self.assertIn('const ACTION = "restore";', expression)
        self.assertIn('const EXPECTED_FINGERPRINT = "1234abcd";', expression)
        with self.assertRaises(ValueError):
            self.module.build_runtime_expression("javascript")

    def test_cli_reuses_loopback_transport_and_exposes_no_arbitrary_code_or_url(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', source)
        self.assertIn("transport.plexamp_target", source)
        self.assertIn("transport.connect_devtools", source)
        self.assertNotIn("--expression", source)
        self.assertNotIn("--javascript", source)
        self.assertNotIn("--url", source)
        self.assertIn('"--confirm-scrub"', source)
        self.assertIn('"--confirm-rollback"', source)


if __name__ == "__main__":
    unittest.main()
