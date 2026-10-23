#!/usr/bin/env python3
"""Stage C3 source-only prototype of an opt-in, candidate-local Squeekboard CSS watch.

This module PATCHES NO FILE when executed; it only defines a pure source
transform for the pinned disposable ARM64 CI build. Deliberately NOT wired
into the existing accepted builder/ELF/OSK trial.

The candidate-only ACP_SQUEEKBOARD_CSS_DIR environment variable would point
to a disposable writable directory mapped (only in that candidate's environment)
as G_RESOURCE_OVERLAYS=/sm/puri/squeekboard=<that directory>.

Directory monitoring (not file-inode monitoring) detects atomic style.css
renames. GTK runs the callback on its own main loop; the same provider
is reloaded and the same GtkDrawingArea queued for redraw. No keyboard
layout, text input purpose, focus, or vendor/GTK theme setting is changed.
"""
from __future__ import annotations


class SourcePatchError(RuntimeError):
    pass


INCLUDE_ANCHOR = '#include "eek-renderer.h"\n'
PRIVATE_ANCHOR = '    EekRenderer *renderer; // owned, nullable\n'
DISPOSE_ANCHOR = 'static void\neek_gtk_keyboard_dispose (GObject *object)\n'
DISPOSE_BODY_ANCHOR = '    if (priv->kb_signal != 0) {\n'
NEW_ANCHOR = '    on_notify_keyboard(G_OBJECT(eekservice), NULL, ret);\n'
SOURCE_ANCHORS = (
    '#include "eek-gtk-keyboard.h"',
    'G_DEFINE_TYPE_WITH_PRIVATE (EekGtkKeyboard, eek_gtk_keyboard, GTK_TYPE_DRAWING_AREA)',
    'eek_gtk_keyboard_real_draw (GtkWidget *self,',
    'priv->renderer = eek_renderer_new (',
    'g_signal_connect (eekservice,',
    'gtk_widget_queue_draw(GTK_WIDGET(self));',
)

INCLUDE = '#include <gio/gio.h> /* ACP candidate-only CSS directory monitor */\n'

PRIVATE = '    GFileMonitor *acp_css_monitor; // ACP candidate-only, nullable, owned\n'

HELPERS = r"""/* ACP experimental candidate only: never alter system GTK or the stock OSK.
 * The only styling input is the private GLib resource overlay chosen at start.
 * Monitoring the DIRECTORY survives atomic replacement of style.css.
 */
static void
acp_squeekboard_css_changed (GFileMonitor *monitor,
                             GFile *file,
                             GFile *other,
                             GFileMonitorEvent event_type,
                             gpointer data)
{
    EekGtkKeyboard *self = EEK_GTK_KEYBOARD (data);
    EekGtkKeyboardPrivate *priv = eek_gtk_keyboard_get_instance_private (self);
    g_autofree gchar *basename = NULL;
    g_autofree gchar *other_name = NULL;
    (void)monitor;

    switch (event_type) {
    case G_FILE_MONITOR_EVENT_CREATED:
    case G_FILE_MONITOR_EVENT_CHANGED:
    case G_FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
    case G_FILE_MONITOR_EVENT_MOVED_IN:
    case G_FILE_MONITOR_EVENT_RENAMED:
        break;
    default:
        return;
    }

    basename = file ? g_file_get_basename (file) : NULL;
    other_name = other ? g_file_get_basename (other) : NULL;
    if (g_strcmp0 (basename, "style.css") != 0 &&
        g_strcmp0 (other_name, "style.css") != 0)
        return;

    if (priv->renderer && priv->renderer->css_provider) {
        /* On the SAME GTK main loop, reparse the already verified private
         * GResource path; GTK3 invalidates provider styles automatically.
         * Do not replace the active renderer/layout or its input state.
         */
        gtk_css_provider_load_from_resource (priv->renderer->css_provider,
                                              "/sm/puri/squeekboard/style.css");
    }
    gtk_widget_queue_draw (GTK_WIDGET (self));
}

static void
acp_squeekboard_start_css_watch (EekGtkKeyboard *self)
{
    EekGtkKeyboardPrivate *priv = eek_gtk_keyboard_get_instance_private (self);
    const gchar *directory = g_getenv ("ACP_SQUEEKBOARD_CSS_DIR");
    g_autoptr(GFile) folder = NULL;
    g_autoptr(GError) error = NULL;
    if (!directory || !*directory)
        return; /* Stock-like candidate behaviour when not explicitly opted in. */
    if (!g_path_is_absolute (directory) ||
        !g_file_test (directory, G_FILE_TEST_IS_DIR)) {
        g_warning ("ACP private Squeekboard CSS directory is invalid");
        return;
    }
    folder = g_file_new_for_path (directory);
    priv->acp_css_monitor = g_file_monitor_directory (
        folder, G_FILE_MONITOR_WATCH_MOVES, NULL, &error);
    if (!priv->acp_css_monitor) {
        g_warning ("ACP CSS monitor unavailable: %s",
                   error ? error->message : "unknown error");
        return;
    }
    g_signal_connect (priv->acp_css_monitor, "changed",
                      G_CALLBACK (acp_squeekboard_css_changed), self);
}

"""

DISPOSE_CLEANUP = r"""    /* Disconnect first; no callback may access the widget during dispose. */
    if (priv->acp_css_monitor) {
        g_signal_handlers_disconnect_by_data (priv->acp_css_monitor, self);
        g_file_monitor_cancel (priv->acp_css_monitor);
        g_clear_object (&priv->acp_css_monitor);
    }

"""

NEW_WATCH = '    acp_squeekboard_start_css_watch (ret);\n'


def once(source: str, needle: str, replacement: str) -> str:
    if source.count(needle) != 1:
        raise SourcePatchError(f"Unexpected or duplicate vendor C anchor: {needle[:72]}")
    return source.replace(needle, replacement, 1)


def patch_keyboard_source(source: str) -> str:
    """Return an amended C source without side effects; unknown source fails closed."""
    if not isinstance(source, str) or len(source) < 1000:
        raise SourcePatchError("Vendor keyboard source missing or too short")
    if "acp_squeekboard_css_changed" in source or "ACP_SQUEEKBOARD_CSS_DIR" in source:
        raise SourcePatchError("Already contains an experimental CSS hook")
    for anchor in SOURCE_ANCHORS:
        if source.count(anchor) != 1:
            raise SourcePatchError(f"Source lacks expected unique vendor structure: {anchor[:65]}")
    altered = once(source, INCLUDE_ANCHOR, INCLUDE_ANCHOR + INCLUDE)
    altered = once(altered, PRIVATE_ANCHOR, PRIVATE_ANCHOR + PRIVATE)
    altered = once(altered, DISPOSE_ANCHOR, HELPERS + DISPOSE_ANCHOR)
    altered = once(altered, DISPOSE_BODY_ANCHOR, DISPOSE_CLEANUP + DISPOSE_BODY_ANCHOR)
    altered = once(altered, NEW_ANCHOR, NEW_ANCHOR + NEW_WATCH)
    # The transformed code has the existing GTK draw/input functions intact.
    # No other byte is removed or replaced by this prototype.
    if altered.count("acp_squeekboard_start_css_watch (ret);") != 1:
        raise SourcePatchError("Unexpected CSS watch installation count")
    return altered


if __name__ == "__main__":
    raise SystemExit(
        "Source-only prototype: import patch_keyboard_source() in disposable CI. "
        "No Pi/vendor keyboard or global GTK changes are permitted."
    )
