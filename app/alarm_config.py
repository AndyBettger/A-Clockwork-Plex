from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

DAY_OPTIONS = [
    {"id": "mon", "label": "Mon"},
    {"id": "tue", "label": "Tue"},
    {"id": "wed", "label": "Wed"},
    {"id": "thu", "label": "Thu"},
    {"id": "fri", "label": "Fri"},
    {"id": "sat", "label": "Sat"},
    {"id": "sun", "label": "Sun"},
]
DAY_IDS = [option["id"] for option in DAY_OPTIONS]
DAY_SET = set(DAY_IDS)
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")

DEFAULT_ALARM_DEFAULTS: dict[str, Any] = {
    "snooze_minutes": 8,
    "ring_minutes": 3,
    "occurrence_expiry_minutes": 120,
    "tone_id": "classic-klaxon",
    "fallback_tone_id": "emergency-buzzer",
    "source_type": "tone",
}


def load_tone_manifest(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        payload = {}

    tones = payload.get("tones") if isinstance(payload, dict) else None
    if not isinstance(tones, list):
        tones = []

    clean_tones: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tone in tones:
        if not isinstance(tone, dict):
            continue
        tone_id = str(tone.get("id", "")).strip().lower()
        if not tone_id or tone_id in seen:
            continue
        seen.add(tone_id)
        clean_tones.append(deepcopy(tone))

    default_tone_id = str(payload.get("default_tone_id", "classic-klaxon")).strip().lower()
    fallback_tone_id = str(payload.get("fallback_tone_id", "emergency-buzzer")).strip().lower()
    valid_ids = {str(tone.get("id")) for tone in clean_tones}
    if default_tone_id not in valid_ids and clean_tones:
        default_tone_id = str(clean_tones[0]["id"])
    if fallback_tone_id not in valid_ids:
        fallback_tone_id = default_tone_id

    return {
        "schema_version": int(payload.get("schema_version", 1) or 1),
        "default_tone_id": default_tone_id,
        "fallback_tone_id": fallback_tone_id,
        "preview_seconds": max(1, min(30, _coerce_int(payload.get("preview_seconds"), 10))),
        "tones": clean_tones,
    }


def tone_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        str(tone.get("id", "")).strip().lower()
        for tone in manifest.get("tones", [])
        if isinstance(tone, dict) and str(tone.get("id", "")).strip()
    }


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def _clamp_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, _coerce_int(value, fallback)))


def _normalise_time(value: Any, fallback: str = "11:00", *, strict: bool = False) -> str:
    text = str(value or "").strip()
    if TIME_RE.fullmatch(text):
        return text
    if strict:
        raise ValueError(f"Invalid alarm time: {text or '(blank)'}. Use HH:MM in 24-hour time.")
    return fallback if TIME_RE.fullmatch(fallback) else "11:00"


def _slugify(value: Any, fallback: str = "alarm") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    text = text[:48].strip("-")
    return text or fallback


def _unique_id(candidate: str, used_ids: set[str]) -> str:
    base = candidate[:48].strip("-") or "alarm"
    alarm_id = base
    suffix = 2
    while alarm_id in used_ids:
        tail = f"-{suffix}"
        alarm_id = f"{base[:48 - len(tail)].rstrip('-')}{tail}"
        suffix += 1
    used_ids.add(alarm_id)
    return alarm_id


def _normalise_days(value: Any, *, strict: bool = False) -> list[str]:
    values = value if isinstance(value, list) else []
    days = [day for day in DAY_IDS if day in {str(item).strip().lower() for item in values}]
    if days:
        return days
    if strict:
        raise ValueError("Each alarm must have at least one selected day.")
    return list(DAY_IDS)


def _normalise_defaults(raw: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    valid_tones = tone_ids(manifest)
    default_tone = str(source.get("tone_id", manifest.get("default_tone_id", "classic-klaxon"))).strip().lower()
    fallback_tone = str(source.get("fallback_tone_id", manifest.get("fallback_tone_id", "emergency-buzzer"))).strip().lower()
    if default_tone not in valid_tones:
        default_tone = str(manifest.get("default_tone_id", "classic-klaxon"))
    if fallback_tone not in valid_tones:
        fallback_tone = str(manifest.get("fallback_tone_id", default_tone))

    return {
        "snooze_minutes": _clamp_int(source.get("snooze_minutes"), 8, 1, 60),
        "ring_minutes": _clamp_int(source.get("ring_minutes"), 3, 1, 10),
        "occurrence_expiry_minutes": _clamp_int(source.get("occurrence_expiry_minutes"), 120, 15, 1440),
        "tone_id": default_tone,
        "fallback_tone_id": fallback_tone,
        "source_type": "tone",
    }


def _normalise_alarm(
    raw: Any,
    index: int,
    defaults: dict[str, Any],
    manifest: dict[str, Any],
    used_ids: set[str],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    label = str(source.get("label", f"Alarm {index + 1}")).strip()
    if not label:
        if strict:
            raise ValueError(f"Alarm {index + 1} needs a label.")
        label = f"Alarm {index + 1}"
    label = label[:80]

    requested_id = str(source.get("id", "")).strip().lower()
    if strict:
        if not ID_RE.fullmatch(requested_id):
            raise ValueError(f"Alarm '{label}' has an invalid ID.")
        if requested_id in used_ids:
            raise ValueError(f"Duplicate alarm ID: {requested_id}.")
        used_ids.add(requested_id)
        alarm_id = requested_id
    else:
        alarm_id = _unique_id(_slugify(requested_id or label, f"alarm-{index + 1}"), used_ids)

    valid_tones = tone_ids(manifest)
    source_data = source.get("source") if isinstance(source.get("source"), dict) else {}
    tone_id = str(source_data.get("tone_id", defaults["tone_id"])).strip().lower()
    fallback_tone_id = str(source_data.get("fallback_tone_id", defaults["fallback_tone_id"])).strip().lower()
    if tone_id not in valid_tones:
        if strict:
            raise ValueError(f"Alarm '{label}' uses an unknown tone: {tone_id}.")
        tone_id = defaults["tone_id"]
    if fallback_tone_id not in valid_tones:
        if strict:
            raise ValueError(f"Alarm '{label}' uses an unknown fallback tone: {fallback_tone_id}.")
        fallback_tone_id = defaults["fallback_tone_id"]

    volume = source.get("volume") if isinstance(source.get("volume"), dict) else {}
    return {
        "id": alarm_id,
        "enabled": bool(source.get("enabled", False)),
        "label": label,
        "time": _normalise_time(source.get("time"), "11:00", strict=strict),
        "days": _normalise_days(source.get("days"), strict=strict),
        "snooze_minutes": _clamp_int(source.get("snooze_minutes"), defaults["snooze_minutes"], 1, 60),
        "ring_minutes": _clamp_int(source.get("ring_minutes"), defaults["ring_minutes"], 1, 10),
        "occurrence_expiry_minutes": _clamp_int(
            source.get("occurrence_expiry_minutes"), defaults["occurrence_expiry_minutes"], 15, 1440
        ),
        "source": {
            "type": "tone",
            "tone_id": tone_id,
            "fallback_tone_id": fallback_tone_id,
        },
        "volume": {
            "start_percent": _clamp_int(volume.get("start_percent"), 60, 0, 100),
            "target_percent": _clamp_int(volume.get("target_percent"), 85, 0, 100),
            "fade_seconds": _clamp_int(volume.get("fade_seconds"), 10, 0, 300),
        },
    }


def normalise_alarm_config(raw: Any, manifest: dict[str, Any], *, prefer_legacy: bool = False) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    defaults_source = source.get("defaults") if isinstance(source.get("defaults"), dict) else {}
    defaults_source = {**DEFAULT_ALARM_DEFAULTS, **defaults_source}
    defaults_source["snooze_minutes"] = source.get("snooze_minutes", defaults_source["snooze_minutes"])
    defaults = _normalise_defaults(defaults_source, manifest)

    configured = source.get("alarms") if isinstance(source.get("alarms"), list) else []
    if prefer_legacy or not configured:
        configured = [
            {
                "id": "default-alarm",
                "enabled": bool(source.get("enabled", False)),
                "label": "Default alarm",
                "time": source.get("default_time", "11:00"),
                "days": list(DAY_IDS),
                "snooze_minutes": source.get("snooze_minutes", defaults["snooze_minutes"]),
                "ring_minutes": defaults["ring_minutes"],
                "occurrence_expiry_minutes": defaults["occurrence_expiry_minutes"],
                "source": {
                    "type": "tone",
                    "tone_id": defaults["tone_id"],
                    "fallback_tone_id": defaults["fallback_tone_id"],
                },
                "volume": {"start_percent": 60, "target_percent": 85, "fade_seconds": 10},
            }
        ]

    alarms: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, item in enumerate(configured[:32]):
        alarms.append(_normalise_alarm(item, index, defaults, manifest, used_ids))

    first = alarms[0] if alarms else None
    return {
        "schema_version": 2,
        "enabled": bool(first and first["enabled"]),
        "default_time": first["time"] if first else "11:00",
        "snooze_minutes": first["snooze_minutes"] if first else defaults["snooze_minutes"],
        "defaults": defaults,
        "alarms": alarms,
    }


def validate_submitted_alarm_config(payload: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Alarm configuration must be a JSON object.")

    defaults = _normalise_defaults(payload.get("defaults"), manifest)
    configured = payload.get("alarms")
    if not isinstance(configured, list):
        raise ValueError("Alarm configuration is missing its alarm list.")
    if len(configured) > 32:
        raise ValueError("A maximum of 32 alarms is supported.")

    alarms: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, item in enumerate(configured):
        alarms.append(_normalise_alarm(item, index, defaults, manifest, used_ids, strict=True))

    first = alarms[0] if alarms else None
    return {
        "schema_version": 2,
        "enabled": bool(first and first["enabled"]),
        "default_time": first["time"] if first else "11:00",
        "snooze_minutes": first["snooze_minutes"] if first else defaults["snooze_minutes"],
        "defaults": defaults,
        "alarms": alarms,
    }
