"""Static, no-OSK tests for the staged Stage C2 keyboard/theme validator."""
from __future__ import annotations
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate-squeekboard-uk-theme-stage.py"
spec = importlib.util.spec_from_file_location("acp_c2_validator", SCRIPT)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class StageValidationTests(unittest.TestCase):
    def test_readonly_verified_contents_and_separate_parser_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = "---\nviews:\n    base:\n        - \"1 2 3\"\nbuttons:\n    1:\n        text: \"1\"\n"
            css = "sq_view { background: #070b14; }"
            (root / "keyboards").mkdir()
            (root / "keyboards/gb.yaml").write_text(layout)
            (root / "themes/classic_dark/gtk-3.0").mkdir(parents=True)
            (root / "themes/classic_dark/gtk-3.0/gtk.css").write_text(css)
            (root / "README.txt").write_text(
                "ACP Stage C2 OFFLINE candidate; no keyboard/theme service activated.\n")
            fake = mock.Mock(DEST=root, stock=lambda: {"gb.yaml": layout},
                             styles=lambda: {"classic_dark": css})
            out = io.StringIO()
            with mock.patch.object(validator, "generator", return_value=fake), \
                 mock.patch.object(validator, "validate_yaml", return_value=(0, 0)), \
                 redirect_stdout(out):
                validator.validate()
            self.assertIn("UK LAYOUT CONTENT: PASS (1", out.getvalue())
            self.assertIn("ACP GTK3 PALETTE CONTENT: PASS (1", out.getvalue())
            self.assertIn("Physical key output", out.getvalue())

    def test_rejects_modified_staged_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keyboards").mkdir()
            (root / "keyboards/gb.yaml").write_text("changed")
            (root / "README.txt").write_text(
                "ACP Stage C2 OFFLINE candidate; no keyboard/theme service activated.\n")
            fake = mock.Mock(DEST=root, stock=lambda: {"gb.yaml": "original"},
                             styles=lambda: {})
            with mock.patch.object(validator, "generator", return_value=fake), \
                 self.assertRaisesRegex(validator.CheckError, "differs"):
                validator.validate()

    def test_does_not_follow_staged_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keyboards").mkdir()
            (root / "keyboards/gb.yaml").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(validator.CheckError, "Symlinked"):
                validator.staged_files(root)

    def test_never_installs_or_restarts_keyboard(self):
        raw = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("systemctl", "systemd-run", "apt install", "sudo ", "os.kill(",
                          "subprocess.Popen", "gsettings set", "dpkg -i"):
            self.assertNotIn(forbidden, raw)
        self.assertIn("squeekboard-test-layout", raw)
        self.assertIn("YAML SYNTAX: NOT CHECKED", raw)


if __name__ == "__main__":
    unittest.main()
