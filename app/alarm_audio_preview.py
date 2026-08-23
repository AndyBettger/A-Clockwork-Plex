from __future__ import annotations

from typing import Any

from flask import jsonify, request


def register_alarm_audio_preview_api(app: Any, dashboard: Any) -> None:
    """Expose the fixed-volume appliance tone preview after audio promotion."""
    if "api_alarm_audio_preview" in app.view_functions:
        return

    @app.route("/api/alarms/audio/preview", methods=["POST"])
    def api_alarm_audio_preview():
        payload = request.get_json(silent=True) or {}
        tone_id = str(payload.get("tone_id") or "").strip()
        if not tone_id:
            return jsonify({"ok": False, "error": "tone_id is required."}), 400

        try:
            preview = dashboard.alarm_audio.preview_tone(tone_id)
        except ValueError as exc:
            message = str(exc)
            status_code = (
                409
                if "locked" in message.lower() or "safety switch" in message.lower()
                else 400
            )
            return jsonify({"ok": False, "error": message}), status_code

        duration = int(preview.get("preview_duration_seconds") or 8)
        volume = int(preview.get("preview_volume_percent") or 15)
        labels = dashboard.tone_labels()
        return jsonify(
            {
                "ok": True,
                "preview": {
                    "tone_id": tone_id,
                    "duration_seconds": duration,
                    "volume_percent": volume,
                },
                "audio": dashboard.alarm_audio.status(),
                "message": (
                    f"Previewing {labels.get(tone_id, tone_id)} at a fixed "
                    f"{volume}% for {duration} seconds."
                ),
            }
        )
