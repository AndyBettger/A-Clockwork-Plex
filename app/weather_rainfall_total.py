from __future__ import annotations

"""Calculated Rainy Day Fund total from the fully backfilled dashboard history."""

from typing import Any


def register_calculated_rain_total(dashboard: Any, service: Any) -> None:
    """Replace the unreliable station lifetime counter with a history-derived total.

    The Rainy Day Fund always backfills the complete previous calendar year plus
    the current year to date. Summing those two non-overlapping windows gives a
    deterministic recorded total without depending on a station lifetime counter
    that may be absent, reset or zeroed.
    """

    projection_target = getattr(dashboard, "core", dashboard)
    current_detail = getattr(projection_target, "weather_detail_data")
    if getattr(current_detail, "_acp_calculated_rain_total", False):
        return

    base_weather_detail = current_detail

    def weather_detail_with_calculated_total(
        config: dict[str, Any],
        weather: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        detail = base_weather_detail(config, weather, state)
        gauges = [
            gauge
            for gauge in detail.get("rain_longer_gauges", [])
            if isinstance(gauge, dict) and gauge.get("label") != "Total rain"
        ]

        calculations = {
            item.get("period"): item
            for item in service.dashboard_calculations(weather)
            if isinstance(item, dict)
        }
        previous = calculations.get("previous_year", {})
        current = calculations.get("current_year", {})
        previous_total = previous.get("total_in")
        current_total = current.get("total_in")

        if (
            previous.get("complete")
            and current.get("complete")
            and isinstance(previous_total, (int, float))
            and isinstance(current_total, (int, float))
        ):
            total_in = float(previous_total) + float(current_total)
            amount_mm = total_in * 25.4
            max_mm = projection_target.dynamic_rain_max_mm(amount_mm)
            missing_days = int(previous.get("missing_days") or 0) + int(current.get("missing_days") or 0)
            note = "Last year + this year"
            if missing_days:
                note += f" · {missing_days} day{'s' if missing_days != 1 else ''} not recorded"
            gauges.append(
                {
                    "label": "Rain total",
                    "value": projection_target.format_rain_mm(amount_mm, config),
                    "percent": round(max(0, min(100, amount_mm / max_mm * 100)) if max_mm else 0, 1),
                    "max_label": projection_target.format_rain_mm(max_mm, config),
                    "note": note,
                }
            )

        detail["rain_longer_gauges"] = gauges
        return detail

    weather_detail_with_calculated_total._acp_calculated_rain_total = True  # type: ignore[attr-defined]
    projection_target.weather_detail_data = weather_detail_with_calculated_total
    dashboard.weather_detail_data = weather_detail_with_calculated_total
