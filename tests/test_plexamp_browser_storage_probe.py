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
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_web_storage_inventory_never_reads_or_mutates_values(self):
        self.assertIn("storage.key(index)", self.expression)
        self.assertNotIn("getItem(", self.expression)
        self.assertNotIn("setItem(", self.expression)
        self.assertNotIn("removeItem(", self.expression)
        self.assertNotIn(".clear(", self.expression)
        self.assertIn("web_storage_values_read: false", self.expression)

    def test_indexeddb_inventory_uses_cdp_metadata_not_page_database_open(self):
        self.assertNotIn("indexedDB.open(", self.source)
        self.assertNotIn("indexedDB.databases(", self.source)
        self.assertIn('"IndexedDB.enable"', self.source)
        self.assertIn('"IndexedDB.requestDatabaseNames"', self.source)
        self.assertIn('"IndexedDB.requestDatabase"', self.source)
        self.assertNotIn('"IndexedDB.requestData"', self.source)
        self.assertNotIn('"IndexedDB.clearObjectStore"', self.source)
        self.assertNotIn('"IndexedDB.deleteDatabase"', self.source)
        self.assertNotIn(".transaction(", self.source)
        self.assertNotIn(".objectStore(", self.source)
        self.assertIn('"indexeddb_records_read": False', self.source)
        self.assertIn('"indexeddb_transactions_opened": False', self.source)
        self.assertIn('"indexeddb_page_database_opened": False', self.source)

    def test_probe_is_bounded_redacted_and_origin_scoped(self):
        self.assertIn("MAX_STORAGE_KEYS = 2048", self.expression)
        self.assertIn("MAX_FAMILIES = 64", self.expression)
        self.assertIn("MAX_DATABASES = 32", self.source)
        self.assertIn("MAX_OBJECT_STORES = 64", self.source)
        self.assertIn("SENSITIVE_NAME", self.source)
        self.assertIn("bounded_metadata_name", self.source)
        self.assertIn("target_security_origin", self.source)
        self.assertIn('{"localhost", "127.0.0.1"}', self.source)
        self.assertIn('parsed.port != 32500', self.source)
        self.assertIn('{"securityOrigin": security_origin}', self.source)

    def test_probe_reuses_disposable_loopback_transport_and_has_no_code_argument(self):
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', self.source)
        self.assertIn("transport.plexamp_target", self.source)
        self.assertIn("transport.connect_devtools", self.source)
        self.assertNotIn("--expression", self.source)
        self.assertNotIn("--javascript", self.source)
        self.assertNotIn("--url", self.source)
        self.assertIn('"awaitPromise": False', self.source)


if __name__ == "__main__":
    unittest.main()
