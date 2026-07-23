from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_IDS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_INDEX = {day_id: index for index, day_id in enumerate(DAY_IDS)}

RUNTIME_SCHEMA_VERSION = 1
DEFAULT_POLL_SECONDS = 15
DEFAULT_PERSIST_SECONDS = 60
DEFAULT_MISSED_GRACE_MINUTES = 10
HISTORY_RETENTION_DAYS = 14


def resolve_local_timezone() -> Any:
    """Resolve the Pi's real local timezone, retaining future DST transitions."""
    candidates: list[str] = []
    env_timezone = str(os.environ.get("TZ", "")).strip()
    if env_timezone:
        candidates.append(env_timezone)

    try:
        timezone_name = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if timezone_name:
            candidates.append(timezone_name)
    except OSError:
        pass

    try:
        localtime = Path("/etc/localtime").resolve()
        parts = localtime.parts
        if "zoneinfo" in parts:
            index = parts.index("zoneinfo")
            candidates.append("/".join(parts[index + 1 :]))
    except OSError:
        pass

    for candidate in candidates:
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue

    return datetime.now().astimezone().tzinfo or timezone.utc


def timezone_name(timezone_info: Any) -> str:
    return str(getattr(timezone_info, "key", None) or timezone_info or "UTC")


def ensure_aware(value: datetime, timezone_info: Any) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone_info)
    return value.astimezone(timezone_info)


def parse_iso_datetime(value: Any, timezone_info: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return ensure_aware(parsed, timezone_info)


def parse_alarm_time(value: Any) -> time | None:
    try:
        parsed = time.fromisoformat(str(value).strip())
    except ValueError:
        return None
    return parsed.replace(second=0, microsecond=0)


def resolve_wall_datetime(day: date, alarm_time: time, timezone_info: Any) -> datetime:
    """
    Resolve a local wall-clock alarm time.

    Ambiguous fall-back times use the first occurrence. Non-existent spring-forward
    times are moved forward by the timezone transition while preserving minutes.
    """
    naive = datetime.combine(day, alarm_time)
    candidate = naive.replace(tzinfo=timezone_info, fold=0)
    round_trip = candidate.astimezone(timezone.utc).astimezone(timezone_info)
    if round_trip.replace(tzinfo=None) != naive:
        return round_trip
    return candidate


def occurrence_key(alarm_id: str, wall_date: date, wall_time: str) -> str:
    return f"{alarm_id}|{wall_date.isoformat()}|{wall_time}"


def build_occurrence(alarm: dict[str, Any], wall_date: date, timezone_info: Any) -> dict[str, Any] | None:
    alarm_time = parse_alarm_time(alarm.get("time"))
    if alarm_time is None:
        return None

    wall_time = alarm_time.strftime("%H:%M")
    scheduled = resolve_wall_datetime(wall_date, alarm_time, timezone_info)
    source = alarm.get("source") if isinstance(alarm.get("source"), dict) else {}
    volume = alarm.get("volume") if isinstance(alarm.get("volume"), dict) else {}

    return {
        "occurrence_key": occurrence_key(str(alarm.get("id", "alarm")), wall_date, wall_time),
        "alarm_id": str(alarm.get("id", "alarm")),
        "label": str(alarm.get("label", "Alarm")),
        "scheduled_for": scheduled.isoformat(timespec="seconds"),
        "scheduled_utc": scheduled.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "wall_date": wall_date.isoformat(),
        "wall_time": wall_time,
        "timezone": timezone_name(timezone_info),
        "snooze_minutes": int(alarm.get("snooze_minutes", 8)),
        "ring_minutes": int(alarm.get("ring_minutes", 3)),
        "occurrence_expiry_minutes": int(alarm.get("occurrence_expiry_minutes", 120)),
        "source": deepcopy(source),
        "volume": deepcopy(volume),
    }


def enabled_alarm_count(alarm_config: dict[str, Any]) -> int:
    alarms = alarm_config.get("alarms") if isinstance(alarm_config, dict) else []
    return sum(1 for alarm in alarms if isinstance(alarm, dict) and bool(alarm.get("enabled")))


def occurrences_between(
    alarm_config: dict[str, Any],
    start: datetime,
    end: datetime,
    timezone_info: Any,
) -> list[dict[str, Any]]:
    start = ensure_aware(start, timezone_info)
    end = ensure_aware(end, timezone_info)
    if end < start:
        start, end = end, start

    alarms = alarm_config.get("alarms") if isinstance(alarm_config, dict) else []
    results: list[dict[str, Any]] = []
    current_date = start.date()
    final_date = end.date()

    while current_date <= final_date:
        day_id = DAY_IDS[current_date.weekday()]
        for alarm in alarms:
            if not isinstance(alarm, dict) or not bool(alarm.get("enabled")):
                continue
            days = alarm.get("days") if isinstance(alarm.get("days"), list) else []
            if day_id not in days:
                continue
            occurrence = build_occurrence(alarm, current_date, timezone_info)
            if occurrence is None:
                continue
            scheduled = parse_iso_datetime(occurrence["scheduled_for"], timezone_info)
            if scheduled is not None and start <= scheduled <= end:
                results.append(occurrence)
        current_date += timedelta(days=1)

    results.sort(key=lambda item: item["scheduled_utc"])
    return results


def next_alarm_occurrence(
    alarm_config: dict[str, Any],
    now: datetime,
    timezone_info: Any,
) -> dict[str, Any] | None:
    now = ensure_aware(now, timezone_info)
    alarms = alarm_config.get("alarms") if isinstance(alarm_config, dict) else []
    candidates: list[dict[str, Any]] = []

    for day_offset in range(8):
        candidate_date = now.date() + timedelta(days=day_offset)
        day_id = DAY_IDS[candidate_date.weekday()]
        for alarm in alarms:
            if not isinstance(alarm, dict) or not bool(alarm.get("enabled")):
                continue
            days = alarm.get("days") if isinstance(alarm.get("days"), list) else []
            if day_id not in days:
                continue
            occurrence = build_occurrence(alarm, candidate_date, timezone_info)
            if occurrence is None:
                continue
            scheduled = parse_iso_datetime(occurrence["scheduled_for"], timezone_info)
            if scheduled is not None and scheduled > now:
                candidates.append(occurrence)

    if not candidates:
        return None
    return min(candidates, key=lambda item: item["scheduled_utc"])


class SilentAlarmScheduler:
    """Persistent alarm scheduler foundation with playback deliberately disabled."""

    def __init__(
        self,
        config_loader: Callable[[], dict[str, Any]],
        runtime_path: Path,
        *,
        timezone_info: Any | None = None,
        now_provider: Callable[[], datetime] | None = None,
        poll_seconds: int = DEFAULT_POLL_SECONDS,
        persist_seconds: int = DEFAULT_PERSIST_SECONDS,
        missed_grace_minutes: int = DEFAULT_MISSED_GRACE_MINUTES,
    ) -> None:
        self._config_loader = config_loader
        self._runtime_path = Path(runtime_path)
        self._timezone = timezone_info or resolve_local_timezone()
        self._now_provider = now_provider or (lambda: datetime.now(self._timezone))
        self._poll_seconds = max(5, int(poll_seconds))
        self._persist_seconds = max(15, int(persist_seconds))
        self._missed_grace_minutes = max(1, min(120, int(missed_grace_minutes)))

        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._startup_tick_pending = True
        self._state = self._load_runtime_state()

    def _now(self) -> datetime:
        return ensure_aware(self._now_provider(), self._timezone)

    def _default_runtime_state(self) -> dict[str, Any]:
        return {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "mode": "silent-foundation",
            "playback_enabled": False,
            "scheduler_started_at": None,
            "last_check_at": None,
            "last_persisted_at": None,
            "timezone": timezone_name(self._timezone),
            "poll_seconds": self._poll_seconds,
            "missed_alarm_grace_minutes": self._missed_grace_minutes,
            "enabled_alarm_count": 0,
            "config_fingerprint": None,
            "last_config_reload_at": None,
            "next_occurrence": None,
            "last_observed_occurrence": None,
            "observed_occurrences": [],
            "active_occurrence": None,
            "snoozed_until": None,
            "last_error": None,
        }

    def _load_runtime_state(self) -> dict[str, Any]:
        state = self._default_runtime_state()
        try:
            loaded = json.loads(self._runtime_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return state
        except (OSError, json.JSONDecodeError) as exc:
            state["last_error"] = f"Could not load alarm runtime state: {exc}"
            return state

        if not isinstance(loaded, dict):
            return state
        state.update(loaded)
        if not isinstance(state.get("observed_occurrences"), list):
            state["observed_occurrences"] = []
        state["schema_version"] = RUNTIME_SCHEMA_VERSION
        state["mode"] = "silent-foundation"
        state["playback_enabled"] = False
        state["timezone"] = timezone_name(self._timezone)
        state["poll_seconds"] = self._poll_seconds
        state["missed_alarm_grace_minutes"] = self._missed_grace_minutes
        state["active_occurrence"] = None
        state["snoozed_until"] = None
        return state

    @staticmethod
    def _fingerprint(alarm_config: dict[str, Any]) -> str:
        import hashlib

        encoded = json.dumps(alarm_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def _persist_locked(self, now: datetime, *, force: bool = False) -> None:
        last_persisted = parse_iso_datetime(self._state.get("last_persisted_at"), self._timezone)
        due = last_persisted is None or (now - last_persisted).total_seconds() >= self._persist_seconds
        if not force and not due:
            return

        self._state["last_persisted_at"] = now.isoformat(timespec="seconds")
        self._runtime_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._runtime_path.with_suffix(self._runtime_path.suffix + ".tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2, sort_keys=True)
                handle.write("\n")
            temporary_path.replace(self._runtime_path)
        except OSError as exc:
            self._state["last_error"] = f"Could not persist alarm runtime state: {exc}"
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _clean_history_locked(self, now: datetime) -> None:
        cutoff = now - timedelta(days=HISTORY_RETENTION_DAYS)
        cleaned: list[dict[str, Any]] = []
        for record in self._state.get("observed_occurrences", []):
            if not isinstance(record, dict):
                continue
            scheduled = parse_iso_datetime(record.get("scheduled_for"), self._timezone)
            if scheduled is None or scheduled >= cutoff:
                cleaned.append(record)
        self._state["observed_occurrences"] = cleaned[-256:]

    def tick(
        self,
        *,
        now: datetime | None = None,
        startup: bool | None = None,
        force_persist: bool = False,
    ) -> dict[str, Any]:
        current = ensure_aware(now, self._timezone) if now is not None else self._now()
        if startup is None:
            startup = self._startup_tick_pending

        try:
            config = self._config_loader()
            alarm_config = config.get("alarm", {}) if isinstance(config, dict) else {}
            if not isinstance(alarm_config, dict):
                alarm_config = {}
        except Exception as exc:
            with self._lock:
                self._state["last_error"] = f"Could not load alarm configuration: {exc}"
                self._state["last_check_at"] = current.isoformat(timespec="seconds")
                self._persist_locked(current, force=True)
                self._startup_tick_pending = False
                return self.status()

        with self._lock:
            fingerprint = self._fingerprint(alarm_config)
            if fingerprint != self._state.get("config_fingerprint"):
                self._state["config_fingerprint"] = fingerprint
                self._state["last_config_reload_at"] = current.isoformat(timespec="seconds")

            last_check = parse_iso_datetime(self._state.get("last_check_at"), self._timezone)
            grace_start = current - timedelta(minutes=self._missed_grace_minutes)
            if last_check is None or last_check > current:
                window_start = grace_start
            else:
                window_start = max(last_check, grace_start)

            due_occurrences = occurrences_between(alarm_config, window_start, current, self._timezone)
            observed_records = [
                record
                for record in self._state.get("observed_occurrences", [])
                if isinstance(record, dict)
            ]
            handled_keys = {
                str(record.get("occurrence_key"))
                for record in observed_records
                if record.get("occurrence_key")
            }

            new_records: list[dict[str, Any]] = []
            for occurrence in due_occurrences:
                key = occurrence["occurrence_key"]
                if key in handled_keys:
                    continue
                scheduled = parse_iso_datetime(occurrence["scheduled_for"], self._timezone)
                recovered = bool(startup and scheduled is not None and scheduled < current)
                record = {
                    **occurrence,
                    "observed_at": current.isoformat(timespec="seconds"),
                    "status": "observed-silently",
                    "playback_attempted": False,
                    "recovered_after_restart": recovered,
                }
                observed_records.append(record)
                handled_keys.add(key)
                new_records.append(record)
                print(
                    "A Clockwork Plex scheduler: observed "
                    f"{record['label']} at {record['scheduled_for']} "
                    "(silent foundation; no playback attempted).",
                    flush=True,
                )

            self._state["observed_occurrences"] = observed_records
            self._state["last_observed_occurrence"] = (
                observed_records[-1] if observed_records else None
            )
            self._state["next_occurrence"] = next_alarm_occurrence(
                alarm_config,
                current,
                self._timezone,
            )
            self._state["enabled_alarm_count"] = enabled_alarm_count(alarm_config)
            self._state["last_check_at"] = current.isoformat(timespec="seconds")
            self._state["timezone"] = timezone_name(self._timezone)
            self._state["last_error"] = None
            self._clean_history_locked(current)
            self._persist_locked(current, force=force_persist or bool(new_records) or startup)
            self._startup_tick_pending = False
            return self.status()

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._wake_event.clear()
            now = self._now()
            self._state["scheduler_started_at"] = now.isoformat(timespec="seconds")
            self._state["mode"] = "silent-foundation"
            self._state["playback_enabled"] = False

        self.tick(now=now, startup=True, force_persist=True)
        self._thread = threading.Thread(
            target=self._thread_main,
            name="a-clockwork-plex-alarm-scheduler",
            daemon=True,
        )
        self._thread.start()
        print(
            "A Clockwork Plex scheduler: running silently "
            f"in {timezone_name(self._timezone)}; playback is disabled.",
            flush=True,
        )

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=max(2, self._poll_seconds + 1))
        with self._lock:
            self._running = False
            now = self._now()
            self._persist_locked(now, force=True)

    def wake(self) -> None:
        self._wake_event.set()

    def recalculate(self) -> dict[str, Any]:
        return self.tick(force_persist=True)

    def _thread_main(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.wait(self._poll_seconds)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            try:
                self.tick()
            except Exception as exc:
                with self._lock:
                    now = self._now()
                    self._state["last_error"] = f"Scheduler tick failed: {exc}"
                    self._state["last_check_at"] = now.isoformat(timespec="seconds")
                    self._persist_locked(now, force=True)

    def status(self) -> dict[str, Any]:
        with self._lock:
            status = deepcopy(self._state)
            thread_alive = bool(self._thread and self._thread.is_alive())
            status["running"] = bool(self._running and thread_alive)
            status["thread_alive"] = thread_alive
            status["silent_mode"] = True
            status["playback_enabled"] = False
            status["health"] = (
                "running-silently"
                if status["running"] and not status.get("last_error")
                else "error"
                if status.get("last_error")
                else "stopped"
            )
            status["observed_occurrence_count"] = len(status.get("observed_occurrences", []))
            status["duplicate_protection_count"] = status["observed_occurrence_count"]

            now = self._now()
            next_occurrence = status.get("next_occurrence")
            next_time = (
                parse_iso_datetime(next_occurrence.get("scheduled_for"), self._timezone)
                if isinstance(next_occurrence, dict)
                else None
            )
            status["seconds_until_next"] = (
                max(0, round((next_time - now).total_seconds()))
                if next_time is not None
                else None
            )
            status["playback_lockout_reason"] = (
                "Alarm scheduling is active, but audio playback is deliberately disabled "
                "during the scheduler-foundation pass."
            )
            return status
