#!/usr/bin/env python3
"""Restricted transactional owner for portable Plexamp Headless preferences.

This helper is installed root-owned and invoked through an exact sudoers policy.
It can read/write only the eight non-authentication preference keys physically
classified by A Clockwork Plex. Preference values are accepted on stdin, never
argv, and status/output never exposes stored values.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote


CONFIG_PATH = Path("/etc/default/a-clockwork-plex-plexamp-preferences")
LOCK_PATH = Path("/run/lock/a-clockwork-plex-plexamp-preferences.lock")
PLEXAMP_SETTINGS_PREFIX = "@Plexamp:settings:"
PLEXAMP_HEADLESS_SPECS = {
    "audioConversionBitrate": "integer",
    "autoPlayEnabled": "boolean",
    "cacheSize": "integer",
    "cachingWiFi": "integer",
    "loudnessLeveling": "boolean",
    "precacheNetworkSpeed": "integer",
    "sampleRateConversionQuality": "integer",
    "sampleRateMatching": "integer",
}
MAX_STDIN_BYTES = 4096
PROJECT_USER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@-]+\.service$")

Runner = Callable[..., subprocess.CompletedProcess[str]]
Connector = Callable[..., Any]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class HelperConfig:
    project_user: str
    project_home: Path
    service: str = "plexamp.service"
    port: int = 32500


@dataclass(frozen=True)
class PreferenceSnapshot:
    key: str
    path: Path
    data: bytes
    mode: int
    uid: int
    gid: int
    atime_ns: int
    mtime_ns: int


class PreferenceTransactionError(RuntimeError):
    def __init__(self, stage: str, rollback_failures: list[str] | None = None) -> None:
        self.stage = stage
        self.rollback_failures = list(rollback_failures or [])
        super().__init__(f"Plexamp preference restore failed during {stage}.")


def _decode_scalar(raw: bytes, expected: str) -> bool | int:
    if len(raw) > 64:
        raise ValueError("stored value exceeds the 64-byte preference limit")
    try:
        text = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("stored value is not UTF-8") from exc
    if expected == "boolean":
        if text == "Btrue":
            return True
        if text == "Bfalse":
            return False
        raise ValueError("stored boolean uses an unsupported encoding")
    if expected == "integer":
        if not text.startswith("N"):
            raise ValueError("stored integer uses an unsupported encoding")
        number = text[1:]
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,15})", number):
            raise ValueError("stored integer uses an unsupported encoding")
        value = int(number)
        if not -(2**31) <= value <= 2**31 - 1:
            raise ValueError("stored integer is outside the supported range")
        return value
    raise ValueError("unsupported preference type")


def _validate_value(key: str, value: Any) -> bool | int:
    expected = PLEXAMP_HEADLESS_SPECS[key]
    if expected == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"Plexamp preference {key} must be boolean.")
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Plexamp preference {key} must be an integer.")
    if not -(2**31) <= value <= 2**31 - 1:
        raise ValueError(f"Plexamp preference {key} is outside the supported integer range.")
    return value


def _encode_scalar(key: str, value: Any) -> bytes:
    checked = _validate_value(key, value)
    if PLEXAMP_HEADLESS_SPECS[key] == "boolean":
        return b"Btrue" if checked else b"Bfalse"
    return f"N{checked}".encode("ascii")


def load_config(path: Path = CONFIG_PATH) -> HelperConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"Plexamp preference helper configuration is unavailable: {exc}") from exc

    values: dict[str, str] = {}
    allowed = {"PROJECT_USER", "PROJECT_HOME", "PLEXAMP_SERVICE", "PLEXAMP_PORT"}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise RuntimeError("Plexamp preference helper configuration contains an invalid line.")
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in allowed or key in values:
            raise RuntimeError("Plexamp preference helper configuration contains an unsupported field.")
        values[key] = value

    user = values.get("PROJECT_USER", "")
    home_text = values.get("PROJECT_HOME", "")
    service = values.get("PLEXAMP_SERVICE", "plexamp.service")
    port_text = values.get("PLEXAMP_PORT", "32500")
    if not PROJECT_USER_RE.fullmatch(user):
        raise RuntimeError("Plexamp preference helper configuration has an invalid project user.")
    home = Path(home_text)
    if not home.is_absolute() or home == Path("/") or ".." in home.parts:
        raise RuntimeError("Plexamp preference helper configuration has an invalid project home.")
    if not SERVICE_RE.fullmatch(service) or service != "plexamp.service":
        raise RuntimeError("Plexamp preference helper configuration has an invalid service.")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError("Plexamp preference helper configuration has an invalid port.") from exc
    if port != 32500:
        raise RuntimeError("Plexamp preference helper configuration has an unsupported Plexamp port.")
    return HelperConfig(user, home, service, port)


class PlexampPreferenceTransaction:
    """Transactional writer with service quiescence, verification and rollback."""

    def __init__(
        self,
        config: HelperConfig,
        *,
        runner: Runner | None = None,
        connector: Connector | None = None,
        sleeper: Sleeper | None = None,
        lock_path: Path = LOCK_PATH,
    ) -> None:
        self.config = config
        self.runner = runner or subprocess.run
        self.connector = connector or socket.create_connection
        self.sleeper = sleeper or time.sleep
        self.lock_path = Path(lock_path)
        self.settings_dir = config.project_home / ".local" / "share" / "Plexamp" / "Settings"
        self.package_path = config.project_home / "plexamp" / "package.json"

    def _run(self, *arguments: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(
                list(arguments),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Could not coordinate Plexamp service state: {exc}") from exc

    def _service_active(self) -> bool:
        result = self._run("systemctl", "is-active", "--quiet", self.config.service, timeout=5)
        return result.returncode == 0

    def _stop_service(self) -> None:
        result = self._run("systemctl", "stop", self.config.service)
        if result.returncode != 0 or self._service_active():
            raise RuntimeError("Plexamp service could not be stopped safely.")

    def _start_service(self) -> None:
        result = self._run("systemctl", "start", self.config.service)
        if result.returncode != 0:
            raise RuntimeError("Plexamp service could not be started.")

    def _wait_ready(self) -> None:
        for _attempt in range(50):
            if self._service_active():
                try:
                    connection = self.connector(("127.0.0.1", self.config.port), timeout=0.25)
                except OSError:
                    pass
                else:
                    try:
                        connection.close()
                    except Exception:
                        pass
                    return
            self.sleeper(0.2)
        raise RuntimeError("Plexamp did not become ready on its managed local port.")

    def installed_version(self) -> str | None:
        try:
            if not self.package_path.is_file() or self.package_path.is_symlink():
                return None
            if self.package_path.stat().st_size > 1_000_000:
                return None
            payload = json.loads(self.package_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        version = str(payload.get("version") or "").strip()
        return version[:80] or None

    def _preference_paths(self) -> tuple[dict[str, Path], list[str], list[str]]:
        if not self.settings_dir.is_dir() or self.settings_dir.is_symlink():
            return {}, sorted(PLEXAMP_HEADLESS_SPECS), []
        paths: dict[str, Path] = {}
        invalid: set[str] = set()
        try:
            entries = list(self.settings_dir.iterdir())
        except OSError:
            return {}, sorted(PLEXAMP_HEADLESS_SPECS), []
        for entry in entries:
            decoded = unquote(entry.name)
            if not decoded.startswith(PLEXAMP_SETTINGS_PREFIX):
                continue
            key = decoded[len(PLEXAMP_SETTINGS_PREFIX) :]
            if key not in PLEXAMP_HEADLESS_SPECS:
                continue
            if key in paths or entry.is_symlink() or not entry.is_file():
                invalid.add(key)
                continue
            paths[key] = entry
        for key in invalid:
            paths.pop(key, None)
        missing = sorted(set(PLEXAMP_HEADLESS_SPECS) - set(paths))
        return paths, missing, sorted(invalid)

    def status(self) -> dict[str, Any]:
        version = self.installed_version()
        paths, missing, invalid = self._preference_paths()
        valid_count = 0
        invalid_names = set(invalid)
        for key, path in paths.items():
            try:
                raw = path.read_bytes()
                _decode_scalar(raw, PLEXAMP_HEADLESS_SPECS[key])
            except (OSError, ValueError):
                invalid_names.add(key)
            else:
                valid_count += 1
        missing_names = sorted(set(missing) | invalid_names)
        service_active = False
        try:
            service_active = self._service_active()
        except RuntimeError:
            service_active = False
        ready = bool(
            version
            and self.settings_dir.is_dir()
            and not self.settings_dir.is_symlink()
            and valid_count == len(PLEXAMP_HEADLESS_SPECS)
            and not missing_names
            and service_active
        )
        return {
            "ok": True,
            "available": ready,
            "restore_ready": ready,
            "installed_version": version,
            "service": self.config.service,
            "service_active": service_active,
            "settings_directory_present": self.settings_dir.is_dir() and not self.settings_dir.is_symlink(),
            "allowlisted_preferences_present": valid_count,
            "allowlisted_preferences_expected": len(PLEXAMP_HEADLESS_SPECS),
            "missing_or_invalid_preferences": missing_names,
        }

    def _snapshot(self, key: str, path: Path) -> PreferenceSnapshot:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"Plexamp preference {key} is not a safe existing file.")
        try:
            info = path.stat()
            raw = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"Plexamp preference {key} could not be read safely.") from exc
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError(f"Plexamp preference {key} is not a regular file.")
        _decode_scalar(raw, PLEXAMP_HEADLESS_SPECS[key])
        return PreferenceSnapshot(
            key=key,
            path=path,
            data=raw,
            mode=stat.S_IMODE(info.st_mode),
            uid=info.st_uid,
            gid=info.st_gid,
            atime_ns=info.st_atime_ns,
            mtime_ns=info.st_mtime_ns,
        )

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _replace_bytes(
        self,
        snapshot: PreferenceSnapshot,
        data: bytes,
        *,
        restore_times: bool = False,
    ) -> None:
        parent = snapshot.path.parent
        descriptor, temporary_name = tempfile.mkstemp(prefix=".acp-plexamp-pref.", dir=parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), snapshot.mode)
                current = os.fstat(stream.fileno())
                if os.geteuid() == 0 or current.st_uid != snapshot.uid or current.st_gid != snapshot.gid:
                    os.fchown(stream.fileno(), snapshot.uid, snapshot.gid)
            os.replace(temporary, snapshot.path)
            if restore_times:
                os.utime(
                    snapshot.path,
                    ns=(snapshot.atime_ns, snapshot.mtime_ns),
                    follow_symlinks=False,
                )
            self._fsync_directory(parent)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def apply(self, *, source_version: str, preferences: dict[str, Any]) -> dict[str, Any]:
        source_version = str(source_version or "").strip()
        if not source_version or len(source_version) > 80:
            raise ValueError("Backup Plexamp version is required for Headless preference restore.")
        if not isinstance(preferences, dict) or not preferences:
            raise ValueError("At least one Plexamp Headless preference is required.")
        unknown = sorted(set(preferences) - set(PLEXAMP_HEADLESS_SPECS))
        if unknown:
            raise ValueError(f"Unsupported Plexamp Headless preference: {unknown[0]}")
        targets = {key: _validate_value(key, value) for key, value in preferences.items()}

        installed = self.installed_version()
        if not installed:
            raise RuntimeError("Installed Plexamp version could not be verified.")
        if source_version != installed:
            raise RuntimeError("Backup Plexamp version is not compatible with the installed Plexamp version.")

        paths, _missing, invalid = self._preference_paths()
        if invalid:
            raise RuntimeError(f"Plexamp preference {invalid[0]} has an unsafe or duplicate storage entry.")
        absent = sorted(set(targets) - set(paths))
        if absent:
            raise RuntimeError(
                f"Plexamp preference {absent[0]} is not present on the commissioned target; it will not be created implicitly."
            )

        snapshots: dict[str, PreferenceSnapshot] = {}
        changed: list[str] = []
        for key in sorted(targets):
            snapshot = self._snapshot(key, paths[key])
            current = _decode_scalar(snapshot.data, PLEXAMP_HEADLESS_SPECS[key])
            if current != targets[key]:
                snapshots[key] = snapshot
                changed.append(key)
        if not changed:
            return {
                "ok": True,
                "applied": True,
                "changed_count": 0,
                "verified": True,
                "installed_version": installed,
                "service_restarted": False,
            }

        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_stream = self.lock_path.open("a+", encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("Plexamp preference transaction lock is unavailable.") from exc

        with lock_stream:
            try:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                raise RuntimeError("Plexamp preference transaction lock could not be acquired.") from exc

            service_was_active = False
            service_stopped = False
            writes_started = False
            stage = "preflight"
            try:
                service_was_active = self._service_active()
                if not service_was_active:
                    raise RuntimeError("Plexamp service is not active; no preferences were changed.")

                stage = "service stop"
                self._stop_service()
                service_stopped = True

                stage = "preference write"
                for key in changed:
                    writes_started = True
                    self._replace_bytes(snapshots[key], _encode_scalar(key, targets[key]))

                stage = "preference verification"
                for key in changed:
                    observed = _decode_scalar(
                        snapshots[key].path.read_bytes(),
                        PLEXAMP_HEADLESS_SPECS[key],
                    )
                    if observed != targets[key]:
                        raise RuntimeError(f"Plexamp preference {key} did not verify after write.")

                stage = "service restart"
                self._start_service()
                service_stopped = False
                self._wait_ready()

                stage = "post-restart verification"
                for key in changed:
                    observed = _decode_scalar(
                        snapshots[key].path.read_bytes(),
                        PLEXAMP_HEADLESS_SPECS[key],
                    )
                    if observed != targets[key]:
                        raise RuntimeError(f"Plexamp preference {key} did not survive service restart.")
            except Exception as exc:
                rollback_failures: list[str] = []
                if writes_started:
                    try:
                        if self._service_active():
                            self._stop_service()
                            service_stopped = True
                    except Exception:
                        rollback_failures.append("service stop")
                    for key in reversed(changed):
                        snapshot = snapshots[key]
                        try:
                            self._replace_bytes(snapshot, snapshot.data, restore_times=True)
                            if snapshot.path.read_bytes() != snapshot.data:
                                raise RuntimeError("rollback bytes did not verify")
                        except Exception:
                            rollback_failures.append(f"preference:{key}")
                if service_was_active:
                    try:
                        if not self._service_active():
                            self._start_service()
                        service_stopped = False
                        self._wait_ready()
                    except Exception:
                        rollback_failures.append("service restart")
                elif service_stopped:
                    rollback_failures.append("service state")
                raise PreferenceTransactionError(stage, rollback_failures) from exc

        return {
            "ok": True,
            "applied": True,
            "changed_count": len(changed),
            "verified": True,
            "installed_version": installed,
            "service_restarted": True,
        }


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    if len(raw) > MAX_STDIN_BYTES:
        raise ValueError("Plexamp preference restore request is too large.")
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Plexamp preference restore request must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Plexamp preference restore request must be a JSON object.")
    if set(payload) != {"source_version", "preferences"}:
        raise ValueError("Plexamp preference restore request contains unsupported fields.")
    if not isinstance(payload.get("preferences"), dict):
        raise ValueError("Plexamp preference restore preferences must be a JSON object.")
    return payload


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv: list[str]) -> int:
    if os.geteuid() != 0:
        _emit({"ok": False, "error": "This restricted helper must run as root through its managed sudo policy."})
        return 1
    if len(argv) != 2 or argv[1] not in {"status", "apply"}:
        _emit({"ok": False, "error": "Usage: a-clockwork-plex-plexamp-preferences status|apply"})
        return 64
    try:
        owner = PlexampPreferenceTransaction(load_config())
        if argv[1] == "status":
            _emit(owner.status())
            return 0
        request = _read_request()
        result = owner.apply(
            source_version=str(request.get("source_version") or ""),
            preferences=request["preferences"],
        )
        _emit(result)
        return 0
    except PreferenceTransactionError as exc:
        _emit(
            {
                "ok": False,
                "error": str(exc),
                "failed_stage": exc.stage,
                "rolled_back": not exc.rollback_failures,
                "rollback_failures": exc.rollback_failures,
            }
        )
        return 1
    except (ValueError, RuntimeError, OSError) as exc:
        _emit({"ok": False, "error": str(exc), "rolled_back": True, "rollback_failures": []})
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
