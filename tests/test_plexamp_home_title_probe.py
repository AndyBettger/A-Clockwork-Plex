from __future__ import annotations

import importlib.util
import sys
import unittest
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect-plexamp-home-title.py"


def load_module():
    spec = importlib.util.spec_from_file_location("acp_home_title_probe_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Home title probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlexampHomeTitleProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.template = cls.module.RUNTIME_TEMPLATE

    def test_source_compiles_without_syntax_warnings(self):
        source = SCRIPT.read_text(encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            compile(source, str(SCRIPT), "exec")

    def test_expected_title_validation_is_bounded(self):
        self.assertEqual(self.module.require_expected_title("ACP Test Section"), "ACP Test Section")
        with self.assertRaises(ValueError):
            self.module.require_expected_title("")
        with self.assertRaises(ValueError):
            self.module.require_expected_title("x" * 241)
        with self.assertRaises(ValueError):
            self.module.require_expected_title("bad\nname")

    def test_expected_title_is_json_encoded_not_inserted_as_code(self):
        expression = self.module.build_runtime_expression('ACP "quoted" \\ title')
        self.assertNotIn("__EXPECTED_TITLE__", expression)
        self.assertIn('const EXPECTED_TITLE = "ACP \\"quoted\\" \\\\ title";', expression)

    def test_probe_reads_only_bounded_view_settings_and_never_mutates_storage(self):
        self.assertIn("suffix.match(VIEW_RE)", self.template)
        self.assertIn("storage.getItem(key)", self.template)
        self.assertIn("decodeTitle(raw)", self.template)
        self.assertNotIn("setItem(", self.template)
        self.assertNotIn("removeItem(", self.template)
        self.assertNotIn(".clear(", self.template)
        self.assertIn("MAX_STORAGE_KEYS = 2048", self.template)
        self.assertIn("MAX_VIEW_RECORDS = 256", self.template)
        self.assertIn("MAX_VIEW_BYTES = 16384", self.template)
        self.assertIn("MAX_TITLE_CHARS = 240", self.template)

    def test_probe_does_not_emit_stored_titles_values_or_keys(self):
        self.assertIn("titles_emitted: false", self.template)
        self.assertIn("raw_values_emitted: false", self.template)
        self.assertIn("raw_keys_emitted: false", self.template)
        self.assertIn("expected_title_emitted: false", self.template)
        self.assertIn("expected_title_match_count: expectedMatches", self.template)
        self.assertNotIn("title_values", self.template)
        self.assertNotIn("raw_values:", self.template)
        self.assertNotIn("raw_keys:", self.template)

    def test_probe_uses_same_title_and_view_settings_envelope_as_reset_owner(self):
        self.assertIn(
            "const VIEW_RE = /^discovery:customizations:([A-Za-z0-9_.:/%+@~=\\-]{1,600})",
            self.template,
        )
        self.assertIn("function safeTitle(value)", self.template)
        self.assertIn("Object.prototype.hasOwnProperty.call(value, 'title')", self.template)
        self.assertIn("outerKeys.length === 1", self.template)
        self.assertIn("outerKeys[0].length <= 32", self.template)

    def test_probe_reuses_disposable_loopback_transport_and_exposes_no_javascript_argument(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', source)
        self.assertIn("transport.plexamp_target", source)
        self.assertIn("transport.connect_devtools", source)
        self.assertIn('"--expected-title"', source)
        self.assertNotIn("--expression", source)
        self.assertNotIn("--javascript", source)
        self.assertNotIn("--url", source)


if __name__ == "__main__":
    unittest.main()
