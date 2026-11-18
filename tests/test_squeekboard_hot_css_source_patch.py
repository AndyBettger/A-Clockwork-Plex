"""Source-only C2/C3 candidate CSS reload hook: isolated and failure-closed."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts/ci/patch-squeekboard-hot-css.py"
SPEC = importlib.util.spec_from_file_location("acp_c3_hot_css_patch", PATCH)
assert SPEC and SPEC.loader
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def sample_vendor() -> str:
    # Minimal representative shape for the exact upstream anchors.
    # Real disposable ARM64 CI must independently validate Debian source.
    return (
        '#include "eek-renderer.h"\n'
        '#include "eek-gtk-keyboard.h"\n'
        'typedef struct _EekGtkKeyboardPrivate {\n'
        '    EekRenderer *renderer; // owned, nullable\n'
        '    gulong kb_signal;\n'
        '} EekGtkKeyboardPrivate;\n'
        'G_DEFINE_TYPE_WITH_PRIVATE (EekGtkKeyboard, eek_gtk_keyboard, GTK_TYPE_DRAWING_AREA)\n'
        'static gboolean eek_gtk_keyboard_real_draw (GtkWidget *self, cairo_t *cr) {\n'
        '    priv->renderer = eek_renderer_new (keyboard, context);\n'
        '    return FALSE;\n}\n'
        'static void\neek_gtk_keyboard_dispose (GObject *object)\n'
        '{\n'
        '    EekGtkKeyboard *self = EEK_GTK_KEYBOARD (object);\n'
        '    EekGtkKeyboardPrivate *priv = eek_gtk_keyboard_get_instance_private (self);\n'
        '    if (priv->kb_signal != 0) {\n'
        '        g_signal_handler_disconnect(priv->eekboard_context, priv->kb_signal);\n'
        '    }\n}\n'
        'static void on_notify_keyboard (GObject *obj, GParamSpec *spec, EekGtkKeyboard *self) {\n'
        '    gtk_widget_queue_draw(GTK_WIDGET(self));\n'
        '}\n'
        'GtkWidget *eek_gtk_keyboard_new (void) {\n'
        '    g_signal_connect (eekservice, "notify::keyboard", G_CALLBACK(on_notify_keyboard), ret);\n'
        '    on_notify_keyboard(G_OBJECT(eekservice), NULL, ret);\n'
        '    return GTK_WIDGET(ret);\n}\n'
        '/* vendor placeholder to meet source-length safety gate */\n'
        + ("/* unchanged vendor C contents */\n" * 20)
    )


class SourceOnlyHotCSSPatchTests(unittest.TestCase):
    def test_known_vendor_shape_gains_monitor_without_changing_existing_bytes(self):
        before = sample_vendor()
        result = patch.patch_keyboard_source(before)
        self.assertNotEqual(result, before)
        self.assertIn("g_file_monitor_directory", result)
        self.assertIn("G_FILE_MONITOR_WATCH_MOVES", result)
        self.assertIn("G_FILE_MONITOR_EVENT_RENAMED", result)
        self.assertIn("g_file_monitor_cancel", result)
        self.assertIn("gtk_css_provider_load_from_resource", result)
        self.assertIn("gtk_widget_queue_draw (GTK_WIDGET (self))", result)
        self.assertIn("ACP_SQUEEKBOARD_CSS_DIR", result)
        self.assertIn('"/sm/puri/squeekboard/style.css"', result)
        self.assertIn("g_signal_handlers_disconnect_by_data", result)
        self.assertEqual(result.count("acp_squeekboard_start_css_watch (ret);"), 1)
        restored = (
            result.replace(patch.INCLUDE, "")
            .replace(patch.PRIVATE, "")
            .replace(patch.HELPERS, "")
            .replace(patch.DISPOSE_CLEANUP, "")
            .replace(patch.NEW_WATCH, "")
        )
        self.assertEqual(restored, before)

    def test_fail_closed_on_changed_upstream_layout(self):
        with self.assertRaisesRegex(patch.SourcePatchError, "unique vendor structure"):
            patch.patch_keyboard_source(sample_vendor().replace(
                "priv->renderer = eek_renderer_new (", "priv->renderer = changed ("
            ))

    def test_fail_closed_on_duplicated_anchor(self):
        with self.assertRaisesRegex(patch.SourcePatchError, "unique vendor structure"):
            patch.patch_keyboard_source(sample_vendor() + "\n" +
                'gtk_widget_queue_draw(GTK_WIDGET(self));\n'
            )

    def test_never_double_patches(self):
        once = patch.patch_keyboard_source(sample_vendor())
        with self.assertRaisesRegex(patch.SourcePatchError, "Already contains"):
            patch.patch_keyboard_source(once)

    def test_rejects_short_or_absent_source(self):
        for source in ("", "short", "/* empty */", None):
            with self.subTest(source=source), self.assertRaises(patch.SourcePatchError):
                patch.patch_keyboard_source(source)

    def test_existing_binary_and_ci_build_not_touched(self):
        text = PATCH.read_text(encoding="utf-8")
        for forbidden in (
            "os.kill(", "systemctl", "systemd-run", "pkill", "gsettings set",
            "subprocess.run", "subprocess.Popen", "dpkg -i",
            ".write_text(", ".write_bytes(", ".unlink(", "/usr/bin/squeekboard",
        ):
            self.assertNotIn(forbidden, text)
        ci = (ROOT / "scripts/ci/prepare-squeekboard-overlay-source.py").read_text()
        self.assertNotIn("patch-squeekboard-hot-css", ci)
        old_trial = (ROOT / "scripts/try-squeekboard-overlay.py").read_text()
        self.assertNotIn("ACP_SQUEEKBOARD_CSS_DIR", old_trial)

    def test_gfile_monitor_not_gtk_global_theme_or_keyboard_restart(self):
        code = patch.HELPERS
        self.assertIn('g_getenv ("ACP_SQUEEKBOARD_CSS_DIR")', code)
        self.assertIn("gtk_widget_queue_draw", code)
        self.assertNotIn("gtk-theme-name", code)
        self.assertNotIn("g_settings_set", code)
        self.assertNotIn("eek_renderer_free", code)
        self.assertNotIn("squeek_layout_free", code)
        self.assertNotIn("gtk_widget_hide", code)
        self.assertNotIn("gtk_style_context_invalidate", code)
        self.assertIn('g_strcmp0 (basename, "style.css")', code)
        self.assertIn('g_strcmp0 (other_name, "style.css")', code)


if __name__ == "__main__":
    unittest.main()
