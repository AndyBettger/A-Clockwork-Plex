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

    def test_c3_midnight_blue_is_visibly_distinct_but_c2_unchanged(self):
        """C3-only stronger blue keys; retain exact upstream resource import."""
        raw = (
            COM + "sq_view { background-color: #06101f; color: #eef7ff; }\n"
            + "sq_view sq_button { background: rgba(20, 49, 77, 0.82); }\n"
        ).encode()
        palette_samples = {f"other_{i}": "immutable" for i in range(21)}
        palette_samples.update({
            "classic_dark": (COM + "sq_view { color: #ffffff; }\n"),
            "midnight_blue": raw.decode(),
        })
        validator = mock.Mock()
        validator.samples.return_value = palette_samples
        with mock.patch.object(stage, "source_module", return_value=validator):
            c3 = stage.palettes()
        validator.verify_stage.assert_called_once_with(palette_samples)
        self.assertEqual(len(c3), 23)
        self.assertEqual(c3["classic_dark"], palette_samples["classic_dark"].encode())
        for name, original in palette_samples.items():
            if name != "midnight_blue":
                self.assertEqual(c3[name], original.encode())
        vivid = c3["midnight_blue"]
        self.assertTrue(vivid.startswith(raw))  # never edits accepted C2 bytes
        self.assertIn(b"background: #2864a0;", vivid)
        self.assertIn(b"background-color: #0b2345;", vivid)
        self.assertIn(b"border: 1px solid #78bfff;", vivid)
        self.assertIn(b"sq_view #Return { background: #78bfff;", vivid)
        self.assertEqual(vivid.count(b"resource:///sm/puri/squeekboard/common.css"), 1)
        # The new fill must be MUCH more blue/bright than the former muted key.
        old = (20, 49, 77)
        new = (0x28, 0x64, 0xa0)
        self.assertGreater(sum(abs(a - b) for a, b in zip(old, new)), 130)
        self.assertNotIn(b"ACP C3 candidate-only", raw)

    def test_c3_midnight_blue_fails_closed_on_changed_source(self):
        good = (
            COM + "sq_view { background-color: #06101f; color: #eef7ff; }\n"
        ).encode()
        for bad in (
            good.replace(b"#06101f", b"#000000"),
            good.replace(b"common.css", b"other.css"),
            good + good,
            stage.c3_midnight_blue(good),
        ):
            with self.subTest(bad=bad[:70]), \
                 self.assertRaisesRegex(stage.CSSStageError, "source changed"):
                stage.c3_midnight_blue(bad)

    def test_c3_vivid_palette_matches_accepted_acp_midnight_tokens(self):
        daytime = (ROOT / "app/static/css/daytime-themes.css").read_text()
        self.assertIn('html[data-daytime-theme="midnight_blue"]', daytime)
        self.assertIn("--accent: #78bfff;", daytime)
        self.assertIn("--acp-theme-bg-start: #16385f;", daytime)
        self.assertIn("--text: #eef7ff;", daytime)
        self.assertIn(b"#78bfff", stage.MIDNIGHT_BLUE_C3_TUNING)
        self.assertIn(b"#16385f", stage.MIDNIGHT_BLUE_C3_TUNING)


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
