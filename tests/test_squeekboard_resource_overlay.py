"""Private GLib GResource CSS substitution is non-overwriting and process-local."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SRC = Path(__file__).resolve().parents[1] / "scripts/probe-squeekboard-resource-overlay.py"
SPEC = importlib.util.spec_from_file_location("acp_c2_resource_probe", SRC)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

PALETTE = "midnight_blue"
STYLE = probe.COMMON_IMPORT + 'sq_view sq_button { color: #eef7ff; }\n'


class ResourceOverlayTests(unittest.TestCase):
    def test_generator_preserves_vendor_common_styles(self):
        mock_gen = mock.Mock(styles=mock.Mock(return_value={PALETTE: "sq_button {color: #ffffff;}"}))
        checker = mock.Mock(generator=mock.Mock(return_value=mock_gen), validate=mock.Mock())
        with mock.patch.object(probe, "stage_validator", return_value=checker):
            sample = probe.samples()
        self.assertTrue(sample[PALETTE].startswith(probe.COMMON_IMPORT))
        self.assertIn("sq_button {color: #ffffff;}", sample[PALETTE])
        checker.validate.assert_called_once()

    def test_private_stage_manifest_and_override(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(probe, "ROOT", Path(tmp) / "private"):
            probe.stage({PALETTE: STYLE})
            probe.verify_stage({PALETTE: STYLE})
            self.assertEqual(
                probe.trial_override(PALETTE),
                probe.RESOURCE_PREFIX + "=" + str(probe.ROOT / "palettes" / PALETTE),
            )
            self.assertEqual(probe.destination(PALETTE).read_text(), STYLE)
            with self.assertRaisesRegex(probe.OverlayError, "overwrite"):
                probe.stage({PALETTE: STYLE})

    def test_stage_refuses_tampering(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(probe, "ROOT", Path(tmp) / "private"):
            probe.stage({PALETTE: STYLE})
            css = probe.ROOT / "palettes" / PALETTE / "style.css"
            css.write_text("tampered")
            with self.assertRaisesRegex(probe.OverlayError, "changed"):
                probe.verify_stage({PALETTE: STYLE})

    def test_stage_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(probe, "ROOT", Path(tmp) / "private"):
            probe.stage({PALETTE: STYLE})
            link = probe.ROOT / "palettes" / PALETTE / "evil"
            link.symlink_to("/etc/passwd")
            with self.assertRaisesRegex(probe.OverlayError, "Symlink"):
                probe.verify_stage({PALETTE: STYLE})

    def test_no_global_environment_or_keyboard_mutation(self):
        body = SRC.read_text()
        for forbidden in ("os.kill(", "pkill", "systemctl", "systemd-run",
                          "gsettings set", "dpkg -i", "sudo apt", "subprocess.Popen"):
            self.assertNotIn(forbidden, body)
        self.assertIn('env["G_RESOURCE_OVERLAYS"] = trial_override(THEME)', body)
        self.assertIn("Gio.resources_lookup_data(", body)
        self.assertIn("Gio.resources_get_info(", body)
        self.assertIn("import url(", probe.COMMON_IMPORT)


if __name__ == "__main__":
    unittest.main()
