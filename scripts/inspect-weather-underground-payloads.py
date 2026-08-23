#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.weather_observations import (  # noqa: E402
    build_weather_underground_current_url,
    build_weather_underground_recent_history_url,
    fetch_json,
    normalise_observation_config,
    weather_underground_current_to_dashboard,
)

MAX_EXAMPLES = 4


def read_secret_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise ValueError("API-key file must be a readable regular file, not a symlink.")
    raw = path.read_bytes().rstrip(b"\r\n")
    if not raw or b"\x00" in raw or b"\n" in raw or b"\r" in raw:
        raise ValueError("API-key file must contain one non-empty line without NUL bytes.")
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("API-key file must contain UTF-8 text.") from exc
    if not value.strip():
        raise ValueError("API-key file must not be blank.")
    return value.strip()


def _observation_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    observations = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(observations, list):
        return []
    return [row for row in observations if isinstance(row, dict)]


def _field_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(_field_paths(child, path))
    elif isinstance(value, list):
        for child in value[:MAX_EXAMPLES]:
            paths.update(_field_paths(child, prefix))
    return paths


def _pressure_paths(rows: list[dict[str, Any]]) -> list[str]:
    discovered: set[str] = set()
    for row in rows:
        for path in _field_paths(row):
            if "pressure" in path.lower():
                discovered.add(path)
    return sorted(discovered)


def _timestamp_evidence(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    candidates = ("obsTimeUtc", "obsTimeLocal", "epoch", "validTimeUtc")
    evidence: dict[str, list[str]] = {}
    for field in candidates:
        values: list[str] = []
        for row in rows:
            value = row.get(field)
            if value is None:
                continue
            text = str(value)
            if text not in values:
                values.append(text)
            if len(values) >= MAX_EXAMPLES:
                break
        if values:
            evidence[field] = values
    return evidence


def _nested_key_union(rows: list[dict[str, Any]], name: str) -> list[str]:
    keys: set[str] = set()
    for row in rows:
        block = row.get(name)
        if isinstance(block, dict):
            keys.update(str(key) for key in block)
    return sorted(keys)


def assess_like_for_like_pressure_history(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _observation_rows(payload)
    if not rows:
        return {
            "candidate": False,
            "rows": 0,
            "matching_rows": 0,
            "reason": "No observation rows were present.",
        }

    matching = 0
    for row in rows:
        timestamp = row.get("obsTimeUtc")
        imperial = row.get("imperial")
        pressure = imperial.get("pressure") if isinstance(imperial, dict) else None
        if timestamp not in (None, "") and isinstance(pressure, (int, float)) and not isinstance(pressure, bool):
            matching += 1

    pressure_paths = _pressure_paths(rows)
    aggregate_paths = [
        path
        for path in pressure_paths
        if any(token in path.lower() for token in ("avg", "average", "min", "max", "trend", "range"))
    ]
    candidate = matching == len(rows)
    if candidate:
        reason = (
            "Every history row has obsTimeUtc plus numeric imperial.pressure, matching the "
            "current-observation pressure vocabulary. This is evidence for review, not automatic ingestion approval."
        )
    elif matching:
        reason = (
            f"Only {matching} of {len(rows)} history rows have obsTimeUtc plus numeric imperial.pressure; "
            "the payload is not uniformly like-for-like."
        )
    else:
        reason = (
            "History rows do not expose obsTimeUtc plus numeric imperial.pressure as the same pair used by current observations."
        )
    if aggregate_paths:
        reason += " Aggregate/range pressure fields are also present and must not be treated as instantaneous samples."

    return {
        "candidate": candidate,
        "rows": len(rows),
        "matching_rows": matching,
        "aggregate_pressure_paths": aggregate_paths,
        "reason": reason,
    }


def summarise_payload(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    rows = _observation_rows(payload)
    top_keys = sorted(str(key) for key in payload)
    row_keys = sorted({str(key) for row in rows for key in row})
    return {
        "label": label,
        "top_level_keys": top_keys,
        "observation_count": len(rows),
        "observation_keys": row_keys,
        "imperial_keys": _nested_key_union(rows, "imperial"),
        "metric_keys": _nested_key_union(rows, "metric"),
        "metric_si_keys": _nested_key_union(rows, "metric_si"),
        "timestamp_evidence": _timestamp_evidence(rows),
        "pressure_paths": _pressure_paths(rows),
    }


def inspect_payloads(
    station_id: str,
    api_key: str,
    *,
    timeout: float,
    fetcher=fetch_json,
) -> dict[str, Any]:
    config = {
        "weather": {
            "provider": "weather_underground",
            "weather_underground": {
                "station_id": station_id,
                "request_timeout_seconds": int(max(2, min(60, timeout))),
            },
        }
    }
    settings = normalise_observation_config(config)
    current_url = build_weather_underground_current_url(settings, api_key)
    history_url = build_weather_underground_recent_history_url(settings, api_key)

    current = fetcher(current_url, timeout)
    history = fetcher(history_url, timeout)

    mapped_current: dict[str, Any] | None = None
    mapping_error: str | None = None
    try:
        mapped_current = weather_underground_current_to_dashboard(current)
    except ValueError as exc:
        mapping_error = str(exc)

    report = {
        "station_id": station_id.upper(),
        "current": summarise_payload("current", current),
        "history": summarise_payload("recent-history", history),
        "current_dashboard_mapping": {
            "ok": mapped_current is not None,
            "mapped_fields": sorted(mapped_current) if mapped_current else [],
            "error": mapping_error,
        },
        "history_pressure_assessment": assess_like_for_like_pressure_history(history),
    }
    return report


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "A Clockwork Plex Weather Underground payload inspection",
        "",
        f"Station: {report['station_id']}",
        "Credential: key-file value hidden; request URLs not displayed",
        "State mutation: none",
    ]

    for key in ("current", "history"):
        section = report[key]
        lines.extend(
            [
                "",
                f"{section['label'].upper()} PAYLOAD",
                f"  Top-level keys: {', '.join(section['top_level_keys']) or '(none)'}",
                f"  Observation rows: {section['observation_count']}",
                f"  Observation keys: {', '.join(section['observation_keys']) or '(none)'}",
                f"  Imperial keys: {', '.join(section['imperial_keys']) or '(none)'}",
                f"  Metric keys: {', '.join(section['metric_keys']) or '(none)'}",
                f"  Metric-SI keys: {', '.join(section['metric_si_keys']) or '(none)'}",
                f"  Pressure-related paths: {', '.join(section['pressure_paths']) or '(none)'}",
            ]
        )
        timestamp_evidence = section["timestamp_evidence"]
        if timestamp_evidence:
            lines.append("  Timestamp evidence:")
            for field, examples in timestamp_evidence.items():
                lines.append(f"    {field}: {', '.join(examples)}")
        else:
            lines.append("  Timestamp evidence: (none recognised)")

    mapping = report["current_dashboard_mapping"]
    lines.extend(
        [
            "",
            "CURRENT MAPPING",
            f"  Existing dashboard mapper: {'PASS' if mapping['ok'] else 'FAIL'}",
            f"  Mapped dashboard fields: {', '.join(mapping['mapped_fields']) or '(none)'}",
        ]
    )
    if mapping["error"]:
        lines.append(f"  Mapping error: {mapping['error']}")

    assessment = report["history_pressure_assessment"]
    lines.extend(
        [
            "",
            "HISTORY PRESSURE ASSESSMENT",
            f"  Rows with obsTimeUtc + numeric imperial.pressure: {assessment['matching_rows']}/{assessment['rows']}",
            "  Like-for-like history candidate: " + ("YES — REVIEW REQUIRED" if assessment["candidate"] else "NO"),
        ]
    )
    aggregate_paths = assessment.get("aggregate_pressure_paths") or []
    if aggregate_paths:
        lines.append(f"  Aggregate/range pressure paths: {', '.join(aggregate_paths)}")
    lines.append(f"  Reason: {assessment['reason']}")
    lines.extend(
        [
            "",
            "This command is diagnostic only. It does not write dashboard state, config,",
            "weather history, services or credentials. Do not promote history fields into",
            "runtime pressure samples until the captured evidence has been reviewed.",
            "WU_PAYLOAD_INSPECTION=PASS",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Weather Underground current/recent-history payload inspector."
    )
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--api-key-file", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    station_id = str(args.station_id or "").strip().upper()
    if not station_id or not all(character.isalnum() or character in "_-" for character in station_id):
        parser.error("--station-id must contain only letters, digits, underscore or hyphen.")
    if not (2 <= args.timeout <= 60):
        parser.error("--timeout must be between 2 and 60 seconds.")

    try:
        api_key = read_secret_file(args.api_key_file)
        report = inspect_payloads(station_id, api_key, timeout=args.timeout)
    except (ValueError, RuntimeError) as exc:
        print(f"WU_PAYLOAD_INSPECTION=FAIL: {exc}", file=sys.stderr)
        return 1

    print(render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
