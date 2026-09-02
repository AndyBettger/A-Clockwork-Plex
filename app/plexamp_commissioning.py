from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


SCHEMA_VERSION = 1
MANAGED_AUDIO_DEVICE_LABEL = "A Clockwork Plex - Plexamp"
DEFAULT_BASE_URL = "http://127.0.0.1:32500"
DEFAULT_BASELINE_RELATIVE = Path(".local/share/a-clockwork-plex/plexamp-commissioning.json")
MAX_RESPONSE_BYTES = 1_000_000
MAX_PLAYER_NAME_LENGTH = 120
MAX_DEVICE_VALUE_LENGTH = 500
MAX_DEVICE_LABEL_LENGTH = 500
MAX_AUDIO_CHOICES = 256
ALLOWED_SETTING_NAMES = frozenset({"playerName", "audioDeviceUuid"})
Requester = Callable[[str, str, int], Any]


class PlexampCommissioningError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        rolled_back: bool | None = None,
        rollback_failures: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.rolled_back = rolled_back
        self.rollback_failures = list(rollback_failures or [])


class PlexampCommissioningConflict(PlexampCommissioningError):
    pass


def _safe_text(value: Any, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise PlexampCommissioningError(f"Plexamp {label} is not a string.")
    text = value.strip()
    if not text or len(text) > maximum or any(ord(char) < 32 for char in text):
        raise PlexampCommissioningError(f"Plexamp {label} is outside the supported format.")
    return text


def _validated_base_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port != 32500
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Plexamp commissioning is restricted to the loopback HTTP API on port 32500.")
    host = parsed.hostname
    if host == "::1":
        host = "[::1]"
    return f"http://{host}:32500"


def _default_requester(base_url: str) -> Requester:
    def request(method: str, path: str, timeout: int) -> Any:
        url = f"{base_url}{path}"
        request_object = Request(url, method=method, headers={"Accept": "application/json"})
        try:
            with urlopen(request_object, timeout=timeout) as response:  # nosec B310 - URL is validated loopback-only above.
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise PlexampCommissioningError(f"Plexamp loopback settings request failed: {exc}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise PlexampCommissioningError("Plexamp loopback settings response exceeded the safety limit.")
        if not raw.strip():
            return None
        try:
            return json.loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PlexampCommissioningError("Plexamp loopback settings response was not valid JSON.") from exc

    return request


class PlexampCommissioningManager:
    """Own the non-portable Plexamp label/output commissioning baseline.

    This owner deliberately remains separate from portable backup/restore. It reads
    only the two exact Plexamp Settings fields needed for commissioning and resolves
    the appliance audio target from Plexamp's own loopback device-choice list.
    Authentication, claim/session material and unrelated preferences are never
    returned or persisted by this owner.
    """

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        baseline_path: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        requester: Requester | None = None,
    ) -> None:
        self.home = Path(home).expanduser() if home is not None else Path.home()
        self.baseline_path = (
            Path(baseline_path).expanduser()
            if baseline_path is not None
            else self.home / DEFAULT_BASELINE_RELATIVE
        )
        self.base_url = _validated_base_url(base_url)
        self.requester = requester or _default_requester(self.base_url)

    def _request(self, method: str, path: str, *, timeout: int = 4) -> Any:
        if method not in {"GET", "PUT"}:
            raise ValueError("Unsupported Plexamp commissioning HTTP method.")
        if not path.startswith("/settings") or "\r" in path or "\n" in path:
            raise ValueError("Unsupported Plexamp commissioning API path.")
        return self.requester(method, path, timeout)

    def _settings(self) -> dict[str, str]:
        payload = self._request("GET", "/settings")
        if not isinstance(payload, dict):
            raise PlexampCommissioningError("Plexamp settings endpoint returned an invalid object.")
        return {
            "playerName": _safe_text(
                payload.get("playerName"), "player name", MAX_PLAYER_NAME_LENGTH
            ),
            "audioDeviceUuid": _safe_text(
                payload.get("audioDeviceUuid"),
                "audio-device value",
                MAX_DEVICE_VALUE_LENGTH,
            ),
        }

    def _managed_audio_value(self) -> str:
        query = urlencode({"name": "audioDeviceUuid"})
        payload = self._request("GET", f"/settings/values?{query}")
        if not isinstance(payload, list) or len(payload) > MAX_AUDIO_CHOICES:
            raise PlexampCommissioningError("Plexamp audio-device choices returned an invalid list.")

        matches: list[str] = []
        for item in payload:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            value, label = item[0], item[1]
            if not isinstance(value, str) or not isinstance(label, str):
                continue
            if (
                not value
                or len(value) > MAX_DEVICE_VALUE_LENGTH
                or len(label) > MAX_DEVICE_LABEL_LENGTH
            ):
                continue
            if label == MANAGED_AUDIO_DEVICE_LABEL:
                matches.append(value)

        unique = sorted(set(matches))
        if not unique:
            raise PlexampCommissioningError(
                f'Plexamp does not currently expose the managed audio output "{MANAGED_AUDIO_DEVICE_LABEL}".'
            )
        if len(unique) != 1:
            raise PlexampCommissioningError(
                f'Plexamp exposed more than one audio output named "{MANAGED_AUDIO_DEVICE_LABEL}".'
            )
        return unique[0]

    def _load_baseline(self) -> dict[str, Any] | None:
        path = self.baseline_path
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise PlexampCommissioningError("Plexamp commissioning baseline is not a safe regular file.")
        try:
            if path.stat().st_size > 4096:
                raise PlexampCommissioningError("Plexamp commissioning baseline is unexpectedly large.")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except PlexampCommissioningError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PlexampCommissioningError("Plexamp commissioning baseline could not be read safely.") from exc
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "player_name"}:
            raise PlexampCommissioningError("Plexamp commissioning baseline has an unsupported schema.")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise PlexampCommissioningError("Plexamp commissioning baseline version is unsupported.")
        return {
            "schema_version": SCHEMA_VERSION,
            "player_name": _safe_text(
                payload.get("player_name"), "commissioned player name", MAX_PLAYER_NAME_LENGTH
            ),
        }

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _capture_baseline(self, player_name: str) -> None:
        parent = self.baseline_path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise PlexampCommissioningError("Plexamp commissioning baseline directory is unavailable.") from exc
        if self.baseline_path.exists() or self.baseline_path.is_symlink():
            raise PlexampCommissioningConflict(
                "Plexamp commissioning baseline appeared while it was being captured.",
                rolled_back=True,
            )

        payload = json.dumps(
            {"schema_version": SCHEMA_VERSION, "player_name": player_name},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".plexamp-commissioning.", dir=parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.baseline_path)
            os.chmod(self.baseline_path, 0o600)
            self._fsync_directory(parent)
        except OSError as exc:
            raise PlexampCommissioningError("Plexamp commissioning baseline could not be stored safely.") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _fingerprint(state: dict[str, str]) -> str:
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:32]

    def _state(self, *, capture_if_missing: bool = False) -> tuple[dict[str, str], bool]:
        settings = self._settings()
        baseline = self._load_baseline()
        captured = False
        if baseline is None:
            if not capture_if_missing:
                raise PlexampCommissioningConflict(
                    "Plexamp commissioning baseline has not been captured yet.",
                    rolled_back=True,
                )
            self._capture_baseline(settings["playerName"])
            baseline = self._load_baseline()
            captured = True
        if baseline is None:
            raise PlexampCommissioningError("Plexamp commissioning baseline capture did not verify.")
        target_audio = self._managed_audio_value()
        return (
            {
                "current_player_name": settings["playerName"],
                "current_audio_value": settings["audioDeviceUuid"],
                "target_player_name": str(baseline["player_name"]),
                "target_audio_value": target_audio,
            },
            captured,
        )

    @staticmethod
    def _public_plan(state: dict[str, str], *, baseline_captured: bool = False) -> dict[str, Any]:
        player_changed = state["current_player_name"] != state["target_player_name"]
        audio_changed = state["current_audio_value"] != state["target_audio_value"]
        return {
            "ok": True,
            "ready": True,
            "baseline_present": True,
            "baseline_captured": baseline_captured,
            "change_count": int(player_changed) + int(audio_changed),
            "player_name_changed": player_changed,
            "audio_output_changed": audio_changed,
            "audio_output_label": MANAGED_AUDIO_DEVICE_LABEL,
            "fingerprint": PlexampCommissioningManager._fingerprint(state),
            "reason": None,
        }

    def plan(self) -> dict[str, Any]:
        if self._load_baseline() is None:
            return {
                "ok": True,
                "ready": False,
                "baseline_present": False,
                "baseline_captured": False,
                "change_count": 0,
                "player_name_changed": False,
                "audio_output_changed": False,
                "audio_output_label": MANAGED_AUDIO_DEVICE_LABEL,
                "fingerprint": None,
                "reason": "baseline-missing",
                "error": "Plexamp commissioning baseline has not been captured yet.",
            }
        state, _captured = self._state(capture_if_missing=False)
        return self._public_plan(state)

    def _put_setting(self, name: str, value: str) -> None:
        if name not in ALLOWED_SETTING_NAMES:
            raise ValueError("Unsupported Plexamp commissioning setting.")
        maximum = MAX_PLAYER_NAME_LENGTH if name == "playerName" else MAX_DEVICE_VALUE_LENGTH
        checked = _safe_text(value, name, maximum)
        query = urlencode({"name": name, "value": checked})
        self._request("PUT", f"/settings?{query}")

    def apply(self, *, fingerprint: str) -> dict[str, Any]:
        state, _captured = self._state(capture_if_missing=False)
        expected = str(fingerprint or "").strip()
        current_fingerprint = self._fingerprint(state)
        if not expected or expected != current_fingerprint:
            raise PlexampCommissioningConflict(
                "Plexamp commissioning state changed after Preview. Run Preview reset again.",
                rolled_back=True,
            )

        changes: list[tuple[str, str, str]] = []
        if state["current_player_name"] != state["target_player_name"]:
            changes.append(("playerName", state["current_player_name"], state["target_player_name"]))
        if state["current_audio_value"] != state["target_audio_value"]:
            changes.append(("audioDeviceUuid", state["current_audio_value"], state["target_audio_value"]))
        if not changes:
            return {
                "ok": True,
                "applied": True,
                "verified": True,
                "changed_count": 0,
                "player_name_changed": False,
                "audio_output_changed": False,
                "audio_output_label": MANAGED_AUDIO_DEVICE_LABEL,
            }

        touched: list[tuple[str, str]] = []
        stage = "write"
        try:
            for name, before, target in changes:
                self._put_setting(name, target)
                touched.append((name, before))
            stage = "verification"
            observed = self._settings()
            for name, _before, target in changes:
                if observed.get(name) != target:
                    raise PlexampCommissioningError(
                        f"Plexamp commissioning setting {name} did not verify after write."
                    )
        except Exception as exc:
            rollback_failures: list[str] = []
            for name, before in reversed(touched):
                try:
                    self._put_setting(name, before)
                except Exception:
                    rollback_failures.append(name)
            if touched and not rollback_failures:
                try:
                    restored = self._settings()
                    for name, before in touched:
                        if restored.get(name) != before:
                            rollback_failures.append(name)
                except Exception:
                    rollback_failures.append("verification")
            raise PlexampCommissioningError(
                f"Plexamp commissioning failed during {stage}.",
                rolled_back=not rollback_failures,
                rollback_failures=rollback_failures,
            ) from exc

        names = {name for name, _before, _target in changes}
        return {
            "ok": True,
            "applied": True,
            "verified": True,
            "changed_count": len(changes),
            "player_name_changed": "playerName" in names,
            "audio_output_changed": "audioDeviceUuid" in names,
            "audio_output_label": MANAGED_AUDIO_DEVICE_LABEL,
        }

    def commission(self) -> dict[str, Any]:
        state, captured = self._state(capture_if_missing=True)
        plan = self._public_plan(state, baseline_captured=captured)
        applied = self.apply(fingerprint=str(plan["fingerprint"]))
        return {**applied, "baseline_present": True, "baseline_captured": captured}
