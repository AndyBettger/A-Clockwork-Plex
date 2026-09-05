from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect-plexamp-browser-storage.py"


def load_module():
    spec = importlib.util.spec_from_file_location("acp_plexamp_browser_storage_probe_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Plexamp browser-storage probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlexampBrowserStorageProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.expression = cls.module.RUNTIME_EXPRESSION

    def test_web_storage_inventory_never_reads_or_mutates_values(self):
        self.assertIn("storage.key(index)", self.expression)
        self.assertNotIn("getItem(", self.expression)
        self.assertNotIn("setItem(", self.expression)
        self.assertNotIn("removeItem(", self.expression)
        self.assertNotIn(".clear(", self.expression)
        self.assertIn("web_storage_values_read: false", self.expression)

    def test_indexeddb_inventory_reads_metadata_not_records(self):
        self.assertIn("indexedDB.databases()", self.expression)
        self.assertIn("indexedDB.open(rawName)", self.expression)
        self.assertIn("db.objectStoreNames", self.expression)
        self.assertNotIn(".transaction(", self.expression)
        self.assertNotIn(".objectStore(", self.expression)
        self.assertNotIn("openCursor(", self.expression)
        self.assertNotIn("getAll(", self.expression)
        self.assertNotIn("records.push", self.expression)
        self.assertIn("indexeddb_records_read: false", self.expression)
        self.assertIn("indexeddb_transactions_opened: false", self.expression)

    def test_probe_is_bounded_and_redacts_sensitive_metadata_names(self):
        self.assertIn("MAX_STORAGE_KEYS = 2048", self.expression)
        self.assertIn("MAX_FAMILIES = 64", self.expression)
        self.assertIn("MAX_DATABASES = 32", self.expression)
        self.assertIn("MAX_OBJECT_STORES = 64", self.expression)
        self.assertIn("SENSITIVE_NAME", self.expression)
        self.assertIn("redacted: true", self.expression)

    def test_probe_reuses_disposable_loopback_transport_and_has_no_code_argument(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', source)
        self.assertIn("transport.plexamp_target", source)
        self.assertIn("transport.connect_devtools", source)
        self.assertNotIn("--expression", source)
        self.assertNotIn("--javascript", source)
        self.assertNotIn("--url", source)
        self.assertIn('"awaitPromise": True', source)


if __name__ == "__main__":
    unittest.main()
