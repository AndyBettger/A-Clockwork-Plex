from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare-plexamp-local-storage-keys.py"


def load_module():
    spec = importlib.util.spec_from_file_location("acp_plexamp_local_storage_key_comparison_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Plexamp Local Storage key comparison")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlexampLocalStorageKeyComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.expression = cls.module.RUNTIME_EXPRESSION
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_comparison_reads_key_names_only_and_never_values_or_mutation(self):
        self.assertIn("storage.key(index)", self.expression)
        self.assertNotIn("getItem(", self.expression)
        self.assertNotIn("setItem(", self.expression)
        self.assertNotIn("removeItem(", self.expression)
        self.assertNotIn(".clear(", self.expression)
        self.assertIn("values_read: false", self.expression)
        self.assertIn('"storage_values_read": False', self.source)

    def test_comparison_is_bounded_and_redacts_sensitive_key_names(self):
        self.assertIn("MAX_STORAGE_KEYS = 2048", self.source)
        self.assertIn("MAX_DELTA_KEYS = 64", self.source)
        self.assertIn("SENSITIVE_NAME", self.source)
        self.assertIn("safe_key_metadata", self.source)
        self.assertIn('{"name": None, "name_length": length, "redacted": True}', self.source)
        self.assertNotIn("sha256", self.source.lower())
        self.assertNotIn("fingerprint", self.source.lower())

    def test_comparison_requires_two_distinct_loopback_debug_profiles(self):
        self.assertIn("DEFAULT_TRACER_DEBUG_PORT = 9224", self.source)
        self.assertIn("DEFAULT_CONTROL_DEBUG_PORT = 9225", self.source)
        self.assertIn("Tracer and control debug ports must be different", self.source)
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', self.source)
        self.assertIn("transport.plexamp_target", self.source)
        self.assertIn("transport.connect_devtools", self.source)

    def test_comparison_has_no_arbitrary_code_or_url_input(self):
        self.assertNotIn("--expression", self.source)
        self.assertNotIn("--javascript", self.source)
        self.assertNotIn("--url", self.source)
        self.assertNotIn("indexedDB", self.source)
        self.assertNotIn("sessionStorage", self.source)
        self.assertIn('"awaitPromise": False', self.source)


if __name__ == "__main__":
    unittest.main()
