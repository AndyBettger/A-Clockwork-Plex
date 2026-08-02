from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


ConfigProvider = Callable[[], dict[str, Any]]


def _clock_format(config: dict[str, Any]) -> str:
    dashboard = config.get("dashboard") if isinstance(config.get("dashboard"), dict) else {}
    return "12h" if str(dashboard.get("clock_format", "24h")).lower() == "12h" else "24h"


def format_datetime(parsed: datetime, clock_format: str) -> str:
    if clock_format == "12h":
        hour = parsed.strftime("%I").lstrip("0") or "12"
        return f"{parsed.strftime('%d/%m/%Y')} {hour}:{parsed.strftime('%M:%S %p')}"
    return parsed.strftime("%d/%m/%Y %H:%M:%S")


def promote_server_time_formatting(dashboard: Any) -> None:
    """Make server-rendered timestamps follow the dashboard clock setting.

    dashboard_core's weather formatter is intentionally retained as the single
    formatting hook; this promotion only replaces its implementation so every
    existing caller picks up the configured 12/24-hour choice.
    """

    core = getattr(dashboard, "core", dashboard)
    parse_datetime = getattr(core, "parse_datetime")
    load_config: ConfigProvider = getattr(dashboard, "load_config")

    def format_display_datetime(value: Any) -> str:
        parsed = parse_datetime(value)
        if parsed is None:
            return str(value) if value else ""
        return format_datetime(parsed, _clock_format(load_config()))

    core.format_display_datetime = format_display_datetime
    dashboard.format_display_datetime = format_display_datetime


__all__ = ["format_datetime", "promote_server_time_formatting"]
