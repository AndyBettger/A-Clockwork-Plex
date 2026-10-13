"""Offline-only Stage C2 UK Squeekboard YAML / GTK3 theme sample contract tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/stage-squeekboard-uk-theme.py"
spec = importlib.util.spec_from_file_location("acp_uk_keyboard_stage", FILE)
assert spec and spec.loader
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


NORMAL = '''---
outlines:
    default: { width: 35.33, height: 52 }
views:
    numbers:
        - "1 2 3 4 5 6 7 8 9 0"
        - "@ # $ % & - _ + ( )"
        - "show_symbols   , \\" ' colon ; ! ?  BackSpace"
    symbols:
        - "© ® £ € ¥ ^ ° * { }"
buttons:
    colon:
        text: ":"
'''
NUMBER = '''---
views:
    base:
        - "1 2 3 parenleft parenright"
        - "7 8 9 plus minus"
buttons:
    minus:
        text: "-"
'''


class StageSqueekboardUkThemeTests(unittest.TestCase):
    def test_uk_currency_position_and_dollar_not_lost(self):
        candidate = stage.layout(NORMAL, "us.yaml")
        self.assertIn('@ # £ % & - _ + ( )', candidate)
        self.assertIn('© ® $ € ¥ ^ ° * { }', candidate)
        self.assertIn(chr(92) + chr(34), candidate)
        self.assertIn('colon:', candidate)
        self.assertNotIn('@ # $ % &', candidate)

    def test_vendor_colon_keysym_need_not_have_explicit_button_override(self):
        # A Pi vendor keyboard can render the colon keysym directly without
        # defining a redundant `buttons: colon:` mapping.
        without_button = NORMAL.replace('    colon:\n        text: ":"\n', '')
        self.assertNotIn('    colon:', without_button)
        result = stage.layout(without_button, "us.yaml")
        self.assertIn("@ # £ % & - _ + ( )", result)
        self.assertIn("show_symbols", result)
        self.assertIn("colon", result)

    def test_symbol_row_must_keep_apostrophe_quote_and_colon(self):
        without_button = NORMAL.replace('    colon:\n        text: ":"\n', '')
        quote = chr(92) + chr(34)
        for before, after, expected in (
            (" ' colon ;", " ' semicolon ;", "Colon key"),
            (f" {quote} ' colon", f" {quote} colon", "Apostrophe key"),
            (f" {quote} ' colon", " quotedbl_removed ' colon", "Double-quote key"),
        ):
            with self.subTest(key=expected):
                invalid = without_button.replace(before, after)
                self.assertNotEqual(invalid, without_button)
                with self.assertRaisesRegex(stage.StagingError, expected):
                    stage.layout(invalid, "us.yaml")

    def test_number_layout_provides_decimal_and_time_without_losing_minus(self):
        candidate = stage.layout(NUMBER, "number/us.yaml")
        self.assertIn("1 2 3 period colon", candidate)
        self.assertIn('period:\n        text: "."', candidate)
        self.assertIn('colon:\n        text: ":"', candidate)
        self.assertIn('7 8 9 plus minus', candidate)

    def test_refuses_unknown_vendor_schema(self):
        with self.assertRaises(stage.StagingError):
            stage.layout("views:\nbuttons:\n", "us.yaml")

    def test_acp_day_palette_definitions_are_authoritative(self):
        colours = stage.palette_tokens()
        self.assertEqual(set(colours), set(stage.THEMES))
        self.assertEqual(colours["classic_dark"]["--accent"].lower(), "#8fd3ff")
        self.assertEqual(colours["amber_terminal"]["--accent"].lower(), "#ffbc4d")
        examples = stage.styles()
        self.assertIn("sq_view sq_button", examples["midnight_blue"])
        self.assertIn("#ffbc4d", examples["amber_terminal"])
        self.assertIn("#050000", examples["astronomy_night_idle"])
        self.assertIn("astronomy_night_active", examples)
        self.assertIn("classic_dark_night_classic_idle", examples)

    def test_stage_stays_in_private_new_folder_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            final = Path(temporary) / "sandbox" / "candidate"
            with mock.patch.object(stage, "DEST", final):
                stage.stage({"gb.yaml": NORMAL, "number/gb.yaml": NUMBER},
                            {"classic_dark": stage.gtk_style("#000000", "#111111",
                                                             "#eeeeee", "#888888")})
                self.assertTrue((final / "keyboards/gb.yaml").is_file())
                self.assertTrue((final / "keyboards/number/gb.yaml").is_file())
                self.assertTrue((final / "themes/classic_dark/gtk-3.0/gtk.css").is_file())
                self.assertIn("OFFLINE", (final / "README.txt").read_text())
                with self.assertRaises(stage.StagingError):
                    stage.stage({"gb.yaml": NORMAL}, {"classic_dark": "x"})

    def test_never_starts_keyboard_or_changes_global_configuration(self):
        raw = FILE.read_text(encoding="utf-8")
        for forbidden in ("systemctl", "systemd-run", "os.kill(", "pkill", "gsettings set",
                          "/etc/gtk", "sudo ", "subprocess.Popen"):
            self.assertNotIn(forbidden, raw)
        self.assertIn("SQUEEKBOARD_KEYBOARDSDIR", raw)
        self.assertIn("XDG_CONFIG_HOME", raw)


if __name__ == "__main__":
    unittest.main()
