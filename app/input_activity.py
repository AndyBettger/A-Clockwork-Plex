from __future__ import annotations

import glob
import os
import select
import struct
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


NowProvider = Callable[[], datetime]

EV_SYN = 0
EV_KEY = 1
EV_REL = 2
EV_ABS = 3

# struct input_event: struct timeval + type + code + signed value.
_INPUT_EVENT = struct.Struct("@llHHi")


def _default_now() -> datetime:
    return datetime.now().astimezone()


class LinuxInputActivityMonitor:
    """Observe local Linux input events without taking exclusive device ownership."""

    authority = "linux-input-activity-monitor"

    def __init__(
        self,
        *,
        device_glob: str = "/dev/input/event*",
        now_provider: NowProvider | None = None,
        rescan_seconds: float = 10.0,
        debounce_seconds: float = 0.15,
    ) -> None:
        self._device_glob = device_glob
        self._now = now_provider or _default_now
        self._rescan_seconds = max(1.0, float(rescan_seconds))
        self._debounce_seconds = max(0.0, float(debounce_seconds))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._devices: dict[int, dict[str, Any]] = {}
        self._sequence = 0
        self._last_activity_at: datetime | None = None
        self._last_event: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._last_record_monotonic = 0.0

    @staticmethod
    def activity_kind(event_type: int, value: int) -> str | None:
        if event_type == EV_KEY:
            return "key" if value in {1, 2} else None
        if event_type == EV_REL:
            return "relative" if value != 0 else None
        if event_type == EV_ABS:
            return "absolute"
        return None

    @staticmethod
    def _event_capabilities(path: str) -> int | None:
        event_name = Path(path).name
        capability_path = Path("/sys/class/input") / event_name / "device" / "capabilities" / "ev"
        try:
            words = capability_path.read_text(encoding="ascii").strip().split()
            return int(words[-1], 16) if words else None
        except (OSError, ValueError):
            return None

    @classmethod
    def _supports_user_input(cls, path: str) -> bool:
        capabilities = cls._event_capabilities(path)
        if capabilities is None:
            return True
        return bool(capabilities & ((1 << EV_KEY) | (1 << EV_REL)))

    @staticmethod
    def _device_name(path: str) -> str:
        event_name = Path(path).name
        name_path = Path("/sys/class/input") / event_name / "device" / "name"
        try:
            name = name_path.read_text(encoding="utf-8").strip()
            return name or event_name
        except OSError:
            return event_name

    def _close_device(self, fd: int) -> None:
        info = self._devices.pop(fd, None)
        try:
            os.close(fd)
        except OSError:
            pass
        if info is not None:
            info["closed"] = True

    def _discover_devices(self) -> None:
        known_paths = {str(info.get("path")) for info in self._devices.values()}
        errors: list[str] = []
        for path in sorted(glob.glob(self._device_glob)):
            if path in known_paths or not self._supports_user_input(path):
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                continue
            self._devices[fd] = {
                "path": path,
                "name": self._device_name(path),
            }
        with self._lock:
            self._last_error = "; ".join(errors) if errors else None

    def _record_activity(self, info: dict[str, Any], *, kind: str, code: int, value: int) -> None:
        now_monotonic = time.monotonic()
        if now_monotonic - self._last_record_monotonic < self._debounce_seconds:
            return
        self._last_record_monotonic = now_monotonic
        occurred_at = self._now()
        with self._lock:
            self._sequence += 1
            self._last_activity_at = occurred_at
            self._last_event = {
                "sequence": self._sequence,
                "at": occurred_at.isoformat(timespec="milliseconds"),
                "kind": kind,
                "code": int(code),
                "value": int(value),
                "device": str(info.get("name") or Path(str(info.get("path") or "input")).name),
                "path": str(info.get("path") or ""),
            }

    def _consume_device(self, fd: int, info: dict[str, Any]) -> None:
        try:
            data = os.read(fd, _INPUT_EVENT.size * 64)
        except BlockingIOError:
            return
        except OSError:
            self._close_device(fd)
            return
        if not data:
            self._close_device(fd)
            return
        complete = len(data) - (len(data) % _INPUT_EVENT.size)
        for offset in range(0, complete, _INPUT_EVENT.size):
            _seconds, _microseconds, event_type, code, value = _INPUT_EVENT.unpack_from(data, offset)
            kind = self.activity_kind(event_type, value)
            if kind is not None:
                self._record_activity(info, kind=kind, code=code, value=value)

    def _run(self) -> None:
        next_scan = 0.0
        try:
            while not self._stop.is_set():
                now_monotonic = time.monotonic()
                if now_monotonic >= next_scan:
                    self._discover_devices()
                    next_scan = now_monotonic + self._rescan_seconds

                fds = list(self._devices)
                if not fds:
                    self._stop.wait(min(1.0, self._rescan_seconds))
                    continue
                try:
                    ready, _writable, _errors = select.select(fds, [], [], 1.0)
                except (OSError, ValueError):
                    for fd in list(self._devices):
                        self._close_device(fd)
                    continue
                for fd in ready:
                    info = self._devices.get(fd)
                    if info is not None:
                        self._consume_device(fd, info)
        finally:
            for fd in list(self._devices):
                self._close_device(fd)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="a-clockwork-plex-input-activity",
                daemon=True,
            )
            self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            devices = [
                {
                    "path": str(info.get("path") or ""),
                    "name": str(info.get("name") or "input"),
                }
                for info in self._devices.values()
            ]
            return {
                "authority": self.authority,
                "running": bool(thread is not None and thread.is_alive()),
                "available": bool(devices),
                "device_count": len(devices),
                "devices": devices,
                "sequence": self._sequence,
                "last_activity_at": (
                    self._last_activity_at.isoformat(timespec="milliseconds")
                    if self._last_activity_at is not None
                    else None
                ),
                "last_event": dict(self._last_event) if self._last_event is not None else None,
                "last_error": self._last_error,
            }
