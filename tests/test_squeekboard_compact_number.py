"""Offline Stage C2 compact-number layout: isolated and key-preserving."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "scripts/stage-squeekboard-compact-number.py"
SPEC = importlib.util.spec_from_file_location("acp_c2_compact_numeric", SRC)
assert SPEC and SPEC.loader
compact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compact)

try:
    import yaml  # noqa: F401
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

NUMBER = """---
outlines:
    default: { width: 37.46341, height: 52 }
    altline: { width: 48.39024, height: 52 }
    outline7: { width: 88.97561, height: 52 }
    spaceline: { width: 120.5853, height: 52 }
views:
    base:
        - ". 1 2 3 :"
        - "# 4 5 6 +"
        - "* 7 8 9 -"
        - "BackSpace 0 space Return"
buttons:
    BackSpace:
        outline: altline
        action: erase
    space:
        outline: spaceline
        text: " "
    Return:
        outline: outline7
        keysym: Return
    0:
        text: "0"
"""


class CompactNumberStageTests(unittest.TestCase):
    @unittest.skipUnless(YAML_AVAILABLE, "PyYAML required for vendor YAML parsing")
    def test_numeric_margins_are_symmetric_and_keys_unmodified(self):
        candidate, original_width, side = compact.compact_numeric(NUMBER)
        self.assertIn("margins: { top: 0, side: ", candidate)
        self.assertEqual(candidate.split("\n", 2)[2], NUMBER.split("\n", 1)[1])
        self.assertGreater(original_width, 100)
        self.assertAlmostEqual(side, original_width * compact.MARGIN_FRACTION, places=3)
        parsed = yaml.safe_load(candidate)
        self.assertEqual(parsed["views"], yaml.safe_load(NUMBER)["views"])
        self.assertEqual(parsed["buttons"], yaml.safe_load(NUMBER)["buttons"])
        self.assertEqual(parsed["outlines"], yaml.safe_load(NUMBER)["outlines"])
        self.assertEqual(parsed["margins"]["top"], 0)
        self.assertEqual(parsed["margins"]["bottom"], 0)

    @unittest.skipUnless(YAML_AVAILABLE, "PyYAML required for vendor YAML parsing")
    def test_only_number_keymap_changes(self):
        layouts = {"gb.yaml": "---\nviews:\n  base: [\"q w e\"]\n",
                   "number/gb.yaml": NUMBER,
                   "email/gb.yaml": "---\nviews:\n  base: [\"email\"]\n"}
        out, _, _ = compact.expected_layouts(layouts)
        self.assertEqual(layouts["gb.yaml"], out["gb.yaml"])
        self.assertEqual(layouts["email/gb.yaml"], out["email/gb.yaml"])
        self.assertEqual(layouts["number/gb.yaml"], NUMBER)
        self.assertNotEqual(out["number/gb.yaml"], NUMBER)

    @unittest.skipUnless(YAML_AVAILABLE, "PyYAML required for vendor YAML parsing")
    def test_fail_closed_on_preexisting_margins_or_new_schema(self):
        bad = NUMBER.replace("---\n", "---\nmargins: { top: 0, side: 10, bottom: 0 }\n")
        with self.assertRaisesRegex(compact.CompactError, "already defines margins"):
            compact.compact_numeric(bad)
        with self.assertRaisesRegex(compact.CompactError, "Unexpected numeric view"):
            compact.compact_numeric(NUMBER.replace("views:\n    base:", "views:\n    symbols:"))

    def test_non_overwriting_private_stage_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(compact, "ROOT", Path(tmp) / "compact"):
            keys = {"gb.yaml": "untouched full QWERTY",
                    "number/gb.yaml": "new numeric YAML"}
            compact.stage(keys)
            compact.verify(keys)
            self.assertEqual(
                (compact.ROOT / "keyboards/gb.yaml").read_text(), "untouched full QWERTY"
            )
            with self.assertRaisesRegex(compact.CompactError, "overwrite"):
                compact.stage(keys)
            (compact.ROOT / "keyboards/number/gb.yaml").write_text("tampered")
            with self.assertRaisesRegex(compact.CompactError, "changed"):
                compact.verify(keys)

    def test_stage_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(compact, "ROOT", Path(tmp) / "compact"):
            compact.stage({"number/gb.yaml": "new YAML"})
            (compact.ROOT / "keyboards" / "evil").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(compact.CompactError, "Symlink"):
                compact.verify({"number/gb.yaml": "new YAML"})

    def test_source_contains_no_runtime_changes(self):
        body = SRC.read_text(encoding="utf-8")
        for forbidden in ("os.kill(", "pkill", "systemctl", "systemd-run",
                          "gsettings set", "dpkg -i", "sudo apt", "subprocess.Popen"):
            self.assertNotIn(forbidden, body)
        self.assertIn("MARGIN_FRACTION = 0.45", body)
        self.assertIn("validator.validate()", body)
        self.assertIn("Refusing to overwrite", body)


if __name__ == "__main__":
    unittest.main()
