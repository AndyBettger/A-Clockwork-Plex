from __future__ import annotations

from typing import Any

from flask import render_template

try:
    from . import screen_projection as _screen_projection
    from . import settings_unified as _settings_unified
except ImportError:  # Supports direct execution imports.
    import screen_projection as _screen_projection
    import settings_unified as _settings_unified


def _wrap_news_settings_mode_option(owner: Any) -> None:
    """Add News to one existing Settings destination-context owner once."""

    original = getattr(owner, "settings_page_context", None)
    if not callable(original) or getattr(original, "_acp_news_aware", False):
        return

    def settings_page_context(*args: Any, **kwargs: Any) -> dict[str, Any]:
        context = original(*args, **kwargs)
        options = context.get("mode_options")
        if not isinstance(options, list):
            return context
        if any(isinstance(item, dict) and item.get("id") == "news" for item in options):
            return context

        insert_at = next(
            (
                index
                for index, item in enumerate(options)
                if isinstance(item, dict) and item.get("id") == "plexamp"
            ),
            len(options),
        )
        options.insert(insert_at, {"id": "news", "label": "News"})
        return context

    settings_page_context._acp_news_aware = True  # type: ignore[attr-defined]
    owner.settings_page_context = settings_page_context


def _install_news_settings_mode_option(dashboard: Any) -> None:
    """Extend both the public dashboard copy and canonical Settings owner.

    ``app.main`` re-exports ``dashboard_core.settings_page_context`` by value,
    while Flask's long-lived ``/settings`` route continues to resolve the
    original function from ``dashboard_core``. Patch both owners so the live
    route and compatibility imports see the same destination catalogue.
    """

    _wrap_news_settings_mode_option(dashboard)
    core = getattr(dashboard, "core", None)
    if core is not None and core is not dashboard:
        _wrap_news_settings_mode_option(core)


def register_news_ui(app: Any, dashboard: Any) -> None:
    """Register News with the existing dashboard and screen authorities.

    The long-lived dashboard, unified-settings and screen-projection modules own
    the canonical mode sets. Extending those shared owners here keeps News
    additive: it can be opened manually and selected as either the appliance
    startup destination or the idle-return destination without introducing a
    parallel mode or persistence path.
    """

    dashboard.VALID_MODES.add("news")
    _settings_unified.VALID_MODES.add("news")
    _screen_projection.VALID_SCREENS.add("news")
    _screen_projection.MANUAL_LEASE_SCREENS.add("news")
    _screen_projection.IDLE_RETURN_SCREENS.add("news")
    _install_news_settings_mode_option(dashboard)

    if "news_page" in app.view_functions:
        return

    @app.get("/news")
    def news_page():
        dashboard.set_mode("news")
        return render_template("news.html", active_page="news")
