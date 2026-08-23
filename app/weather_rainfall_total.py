from __future__ import annotations

"""Rainy Day Fund lifetime total projection."""

from datetime import date
from typing import Any


def _display_start(value: Any) -> str | None:
    try:
        parsed = date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None
    return parsed.strftime("%d/%m/%Y")


def register_calculated_rain_total(dashboard: Any, service: Any, lifetime: Any | None = None) -> None:
    """Replace the unreliable live station total with WU-backed history.

    ``service`` owns the previous/current-year comparison windows.  When the
    optional lifetime archive service is supplied it walks farther backwards and
    this projection becomes a true first-WU-record-to-today total.  While that
    one-time backfill is still progressing the gauge remains useful but says so
    explicitly instead of pretending the partial archive is complete.
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
            if isinstance(gauge, dict) and gauge.get("label") not in {"Total rain", "Rain total", "Rain lifetime"}
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
            older_total = 0.0
            older_missing = 0
            lifetime_snapshot: dict[str, Any] = {}
            if lifetime is not None:
                lifetime_snapshot = lifetime.snapshot()
                candidate = lifetime_snapshot.get("total_in")
                if isinstance(candidate, (int, float)):
                    older_total = float(candidate)
                older_missing = int(lifetime_snapshot.get("missing_days") or 0)

            total_in = older_total + float(previous_total) + float(current_total)
            amount_mm = total_in * 25.4
            max_mm = projection_target.dynamic_rain_max_mm(amount_mm)
            missing_days = (
                older_missing
                + int(previous.get("missing_days") or 0)
                + int(current.get("missing_days") or 0)
            )

            if lifetime is None:
                label = "Rain total"
                note = "Last year + this year"
            else:
                label = "Rain lifetime"
                lifetime_status = str(lifetime_snapshot.get("status") or "pending")
                ready = bool(
                    lifetime_snapshot.get("discovery_complete")
                    and lifetime_snapshot.get("coverage_complete")
                )
                start = _display_start(lifetime_snapshot.get("first_record_date"))
                if ready:
                    note = f"Since first WU record {start}" if start else "All discovered WU history"
                elif lifetime_status == "error":
                    note = "Older WU history unavailable"
                else:
                    note = "Backfilling earlier WU history"

            if missing_days:
                note += f" · {missing_days} day{'s' if missing_days != 1 else ''} not recorded"

            gauges.append(
                {
                    "label": label,
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
