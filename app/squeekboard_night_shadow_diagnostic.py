"""Explicit, loopback-only one-shot C3 night shadow diagnostics.

NO theme writes, no OSK ownership, no background jobs, no retention.
The only production integration is a same-origin POST which collects the
server's current *read-only* status once, then compares it against an explicitly
reported ACP browser state. Nothing touches the C3 trial controller.

The browser remains the sole C3 palette writer; this endpoint is diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


_BROWSER_KEYS = frozenset({
    "enabled", "start", "end", "style", "activeStyle", "wakeSeconds",
    "scheduled", "active", "previewing", "interacting", "effectiveStyle",
})
_INPUT_KEYS = frozenset({"browserStatus", "browserAlarmVisible", "priorSequence"})


def _validated_request(payload: Any) -> tuple[dict[str, Any], bool, int | None]:
    if not isinstance(payload, dict) or set(payload) != _INPUT_KEYS:
        raise ValueError("Expected exact read-only C3 observation envelope")
    browser = payload["browserStatus"]
    if not isinstance(browser, dict) or set(browser) != _BROWSER_KEYS:
        raise ValueError("Expected exactly the C3 night browser status fields")
    for field in ("enabled", "scheduled", "active", "previewing", "interacting"):
        if type(browser[field]) is not bool:
            raise ValueError(f"Invalid browser flag {field}")
    for field in ("start", "end", "style", "activeStyle", "effectiveStyle"):
        if not isinstance(browser[field], str) or len(browser[field]) > 32:
            raise ValueError(f"Invalid browser field {field}")
    if type(browser["wakeSeconds"]) is not int or not 5 <= browser["wakeSeconds"] <= 300:
        raise ValueError("Invalid browser wake seconds")
    alarm_visible = payload["browserAlarmVisible"]
    if type(alarm_visible) is not bool:
        raise ValueError("Browser alarm presentation must be explicitly boolean")
    prior = payload["priorSequence"]
    if prior is not None and (type(prior) is not int or not 0 <= prior <= 2**53 - 1):
        raise ValueError("Invalid input sequence baseline")
    return browser, alarm_visible, prior


def register_c3_shadow_diagnostic_api(
    app: Any,
    *,
    config_loader: Callable[[], dict[str, Any]],
    alarm_status: Callable[[], dict[str, Any]],
    input_snapshot: Callable[[], dict[str, Any]],
) -> None:
    """Register one local, deliberately *manual* and read-only comparison."""
    try:
        from . import squeekboard_theme_sync as _guard
        from . import squeekboard_night_shadow_compare as _shadow
    except ImportError:
        import squeekboard_theme_sync as _guard
        import squeekboard_night_shadow_compare as _shadow
    from flask import jsonify, request

    if "api_c3_night_shadow_diagnostic" in app.view_functions:
        return

    @app.route("/api/osk/c3/night-shadow/compare", methods=["POST"])
    def api_c3_night_shadow_diagnostic():
        if not _guard.local_browser_request(request, mutation=True):
            return jsonify({"ok": False, "error": "Local same-origin JSON only"}), 403
        try:
            browser, browser_alarm, prior = _validated_request(request.get_json(silent=True))
            config = config_loader()
            if not isinstance(config, dict):
                raise ValueError("Server configuration unavailable")
            settings = config.get("dashboard")
            if not isinstance(settings, dict):
                raise ValueError("Server display settings unavailable")
            alarm = alarm_status()
            if not isinstance(alarm, dict):
                raise ValueError("Server alarm status unavailable")
            activity = input_snapshot()
            if not isinstance(activity, dict):
                raise ValueError("Linux input activity unavailable")
            sequence = activity.get("sequence")
            if type(sequence) is not int or sequence < 0:
                raise ValueError("Linux input sequence unavailable")
            # Server time is captured within the same request. Do not trust a
            # client timestamp when interpreting an authoritative schedule.
            captured = datetime.now(timezone.utc)
            report = _shadow.compare(
                server_settings=settings,
                browser_status=browser,
                browser_alarm_visible=browser_alarm,
                server_alarm_status=alarm,
                observed_at=captured,
                screen_snapshot={"screen": {"input_activity": {"sequence": sequence}}},
                prior_input_sequence=prior,
            )
        except (ValueError, KeyError, TypeError):
            return jsonify({"ok": False, "error": "Incomplete or invalid C3 observation"}), 400
        except Exception:
            # Do not disclose config, paths, alarms, devices or exceptions.
            app.logger.warning("Read-only C3 shadow diagnostic failed")
            return jsonify({"ok": False, "error": "Read-only comparison unavailable"}), 503
        return jsonify({
            "ok": True,
            "sampledAt": captured.isoformat(timespec="seconds"),
            "inputSequence": sequence,
            **report.as_dict(),
            "retained": False,
            "cssWritten": False,
        })
