from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect-plexamp-home-customizations.py"


def load_module():
    spec = importlib.util.spec_from_file_location("acp_home_customization_probe_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Home customisation probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlexampHomeCustomizationProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.expression = cls.module.RUNTIME_EXPRESSION

    def test_probe_is_key_names_only_and_never_reads_values(self):
        self.assertIn("storage.key(index)", self.expression)
        self.assertNotIn("getItem(", self.expression)
        self.assertNotIn("setItem(", self.expression)
        self.assertNotIn("removeItem(", self.expression)
        self.assertNotIn(".clear(", self.expression)
        self.assertIn("storage_values_read: false", self.expression)

    def test_probe_is_bounded_to_home_customisation_namespace(self):
        self.assertIn("mmkv.default\\\\", self.expression)
        self.assertIn("discovery:customizations:", self.expression)
        self.assertIn("MAX_STORAGE_KEYS = 2048", self.expression)
        self.assertIn("MAX_MATCHES = 512", self.expression)
        self.assertIn("key.startsWith(MMKV_PREFIX + CUSTOM_PREFIX)", self.expression)

    def test_probe_reports_only_classified_families_not_raw_keys(self):
        for family in ("order", "hidden", "viewSettings", "editing", "customHubs", "other"):
            with self.subTest(family=family):
                self.assertIn(f"{family}: 0", self.expression)
        self.assertIn("family_counts: families", self.expression)
        self.assertNotIn("raw_keys", self.expression)
        self.assertNotIn("rawKeys", self.expression)
        self.assertNotIn("key_list", self.expression)
        self.assertNotIn("keyList", self.expression)
        self.assertNotIn(".push(key)", self.expression)

    def test_probe_reuses_disposable_loopback_transport_and_has_no_expression_argument(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', source)
        self.assertIn("transport.plexamp_target", source)
        self.assertIn("transport.connect_devtools", source)
        self.assertNotIn("--expression", source)
        self.assertNotIn("--javascript", source)
        self.assertNotIn("--url", source)


if __name__ == "__main__":
    unittest.main()
