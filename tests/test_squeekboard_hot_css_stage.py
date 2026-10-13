"""C3 private, atomically updated native CSS test stage; never alters C2 or OSK."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/stage-squeekboard-hot-css.py"
SPEC = importlib.util.spec_from_file_location("acp_c3_private_hot_css_stage", SRC)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)

COM = '@import url("resource:///sm/puri/squeekboard/common.css");\n'
PALETTES = {
    "classic_dark": (COM + "sq_view { color: #eeeeee; }\n").encode(),
    "midnight_blue": (COM + "sq_view { color: #abcdef; }\n").encode(),
    "astronomy_night_idle": (COM + "sq_view { color: #652323; }\n").encode(),
}


class C3PrivateHotCSSStageTests(unittest.TestCase):
    def test_private_stage_classic_dark_default_and_exact_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cache" / "c3"
            with mock.patch.object(stage, "ROOT", path):
                stage.stage(PALETTES)
                self.assertEqual(stage.inspect(PALETTES), "classic_dark")
                self.assertEqual({f.name for f in path.iterdir()},
                                 {"style.css", "README.txt"})
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((path / "style.css").stat().st_mode), 0o600)
                self.assertEqual((path / "style.css").read_bytes(), PALETTES["classic_dark"])

    def test_selection_only_replaces_c3_css_and_preserves_original_c2(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "c2-css"
            src.mkdir()
            original = src / "style.css"
            original.write_bytes(PALETTES["midnight_blue"])
            path = Path(tmp) / "cache" / "c3"
            with mock.patch.object(stage, "ROOT", path):
                stage.stage(PALETTES)
                initial_inode = (path / "style.css").stat().st_ino
                before, changed = stage.select(PALETTES, "midnight_blue")
                self.assertEqual((before, changed), ("classic_dark", True))
                self.assertEqual(stage.inspect(PALETTES), "midnight_blue")
                self.assertNotEqual((path / "style.css").stat().st_ino, initial_inode)
                self.assertEqual(original.read_bytes(), PALETTES["midnight_blue"])
                self.assertEqual({p.name for p in path.iterdir()},
                                 {"README.txt", "style.css"})
                self.assertEqual(
                    stage.select(PALETTES, "classic_dark"),
                    ("midnight_blue", True),
                )

    def test_same_palette_is_idempotent_without_filesystem_mutation(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            stage.stage(PALETTES)
            before = (stage.ROOT / "style.css").stat()
            self.assertEqual(stage.select(PALETTES, "classic_dark"), ("classic_dark", False))
            after = (stage.ROOT / "style.css").stat()
            self.assertEqual((before.st_ino, before.st_mtime_ns),
                             (after.st_ino, after.st_mtime_ns))

    def test_unknown_palette_refused_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            stage.stage(PALETTES)
            before = (stage.ROOT / "style.css").read_bytes()
            with self.assertRaisesRegex(stage.CSSStageError, "Unknown"):
                stage.select(PALETTES, "../global/gtk.css")
            self.assertEqual((stage.ROOT / "style.css").read_bytes(), before)

    def test_stage_never_overwrites_and_broken_style_refuses_selection(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            stage.stage(PALETTES)
            with self.assertRaisesRegex(stage.CSSStageError, "overwrite"):
                stage.stage(PALETTES)
            (stage.ROOT / "style.css").write_bytes(b"corrupted")
            with self.assertRaisesRegex(stage.CSSStageError, "not an exact"):
                stage.select(PALETTES, "midnight_blue")

    def test_tampered_manifest_or_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            stage.stage(PALETTES)
            (stage.ROOT / "intruder.txt").write_text("untrusted")
            with self.assertRaisesRegex(stage.CSSStageError, "missing/unexpected"):
                stage.inspect(PALETTES)
            (stage.ROOT / "intruder.txt").unlink()
            (stage.ROOT / "README.txt").write_text("tampered")
            with self.assertRaisesRegex(stage.CSSStageError, "manifest"):
                stage.inspect(PALETTES)

    def test_symlinked_css_or_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            stage.stage(PALETTES)
            path = stage.ROOT / "style.css"
            original = path.read_bytes()
            target = Path(tmp) / "external.css"
            target.write_bytes(original)
            path.unlink()
            path.symlink_to(target)
            with self.assertRaisesRegex(stage.CSSStageError, "Expected regular"):
                stage.inspect(PALETTES)
            self.assertEqual(target.read_bytes(), original)

    def test_non_private_mode_or_hardlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            stage.stage(PALETTES)
            stage.ROOT.chmod(0o755)
            with self.assertRaisesRegex(stage.CSSStageError, "0700"):
                stage.inspect(PALETTES)
            stage.ROOT.chmod(0o700)
            extra_hardlink = Path(tmp) / "hardlinked-style.css"
            extra_hardlink.hardlink_to(stage.ROOT / "style.css")
            with self.assertRaisesRegex(stage.CSSStageError, "ownership/link"):
                stage.inspect(PALETTES)

    def test_c2_resource_source_validated_before_palette_selection(self):
        fake_source = mock.Mock()
        fake_source.samples.return_value = {
            "classic_dark": "hi", "midnight_blue": "hello",
        }
        with mock.patch.object(stage, "source_module", return_value=fake_source):
            with self.assertRaisesRegex(stage.CSSStageError, "23 validated"):
                stage.palettes()
        fake_source.verify_stage.assert_called_once()

    def test_only_future_candidate_process_receives_environment_strings(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(stage, "ROOT", Path(tmp) / "cache" / "c3"):
            env = stage.resource_environment()
            self.assertEqual(env["G_RESOURCE_OVERLAYS"],
                             "/sm/puri/squeekboard=" + str(stage.ROOT))
            self.assertEqual(env["ACP_SQUEEKBOARD_CSS_DIR"], str(stage.ROOT))
        source = SRC.read_text(encoding="utf-8")
        for forbidden in (
            "os.environ[", "systemctl", "systemd-run", "pkill", "sudo ",
            "gsettings set", "dpkg -i", "/usr/bin/squeekboard",
            "subprocess.Popen", "subprocess.run", "gtk.css",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        accepted_trial = (ROOT / "scripts/try-squeekboard-overlay.py").read_text()
        self.assertNotIn("squeekboard-c3-hot-css-v1", accepted_trial)
        self.assertNotIn("ACP_SQUEEKBOARD_CSS_DIR", accepted_trial)


if __name__ == "__main__":
    unittest.main()
