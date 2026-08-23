from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
CATALOGUE = ROOT / "docs" / "development" / "testing" / "test-catalogue.md"
ENTRY_RE = re.compile(
    r"^- `(?P<path>tests/test_[A-Za-z0-9_]+\.py)` — .+$",
    re.MULTILINE,
)


class TestCatalogueTests(unittest.TestCase):
    def catalogue_entries(self) -> list[str]:
        text = CATALOGUE.read_text(encoding="utf-8")
        return [match.group("path") for match in ENTRY_RE.finditer(text)]

    def test_every_live_test_module_is_catalogued_exactly_once(self):
        live = {
            path.relative_to(ROOT).as_posix()
            for path in TESTS.glob("test_*.py")
            if path.is_file()
        }
        entries = self.catalogue_entries()
        counts = Counter(entries)
        duplicates = sorted(path for path, count in counts.items() if count != 1)

        self.assertFalse(
            duplicates,
            f"test catalogue contains duplicate module entries: {duplicates}",
        )
        self.assertEqual(
            set(entries),
            live,
            "test catalogue must exactly match the live tests/test_*.py module set",
        )

    def test_catalogue_documents_supported_run_and_result_contract(self):
        text = CATALOGUE.read_text(encoding="utf-8")

        required = (
            "bash scripts/run-tests.sh",
            "venv/bin/python -m unittest discover -s tests -v",
            "venv/bin/python -m unittest discover -s tests -p 'test_alarm_audio.py' -v",
            "<module>.<TestCaseClass>.<test_method>",
            "process exit status `0`",
            "`unittest` finishes with `OK`",
            "test count is not a release invariant",
            "fresh-appliance-acceptance-runbook.md",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
