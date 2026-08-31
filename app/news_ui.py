from __future__ import annotations

from typing import Any

from flask import render_template

try:
    from . import screen_projection as _screen_projection
except ImportError:  # Supports direct execution imports.
    import screen_projection as _screen_projection


def register_news_ui(app: Any, dashboard: Any) -> None:
    """Register News as a first-class manually leasable appliance surface.

    The long-lived dashboard and screen-projection modules own the canonical
    mode sets. Mutating those shared set objects here keeps the News feature
    additive while avoiding a second screen authority or a parallel mode path.
    News deliberately remains outside IDLE_RETURN_SCREENS for checkpoint #92;
    it is a user-opened information surface, not a new automatic destination.
    """

    dashboard.VALID_MODES.add("news")
    _screen_projection.VALID_SCREENS.add("news")
    _screen_projection.MANUAL_LEASE_SCREENS.add("news")

    if "news_page" in app.view_functions:
        return

    @app.get("/news")
    def news_page():
        dashboard.set_mode("news")
        return render_template("news.html", active_page="news")
