#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

ENV_NAME = "WEATHER_UNDERGROUND_API_KEY"
PRODUCTION_PATH = Path("/etc/default/a-clockwork-plex-weather")
MAX_SECRET_BYTES = 4096


def _target_path() -> Path:
    """Return the fixed production path; allow a non-root test path only."""
    test_path = os.environ.get("ACP_WEATHER_SECRET_TEST_FILE", "").strip()
    if test_path:
        if os.geteuid() == 0:
            raise RuntimeError("Weather secret test path is forbidden while running as root.")
        return Path(test_path)
    return PRODUCTION_PATH


def _validated_secret(raw: bytes) -> str:
    if len(raw) > MAX_SECRET_BYTES:
        raise ValueError("Weather Underground API key is too long.")
    raw = raw.rstrip(b"\r\n")
    if not raw:
        raise ValueError("Weather Underground API key is empty.")
    if b"\x00" in raw or b"\n" in raw or b"\r" in raw:
        raise ValueError("Weather Underground API key must be a single line without NUL bytes.")
    try:
        secret = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Weather Underground API key must be UTF-8 text.") from exc
    if not secret.strip():
        raise ValueError("Weather Underground API key is blank.")
    return secret


def _encoded_line(secret: str) -> str:
    escaped = secret.replace("\\", "\\\\").replace('"', '\\"')
    return f'{ENV_NAME}="{escaped}"\n'


def _existing_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Managed weather environment path is not a regular file.")
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _without_secret(lines: list[str]) -> list[str]:
    prefix = f"{ENV_NAME}="
    return [line for line in lines if not line.lstrip().startswith(prefix)]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        if os.geteuid() == 0:
            os.chown(temporary, 0, 0)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _status_file_exists_and_is_safe(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("Managed weather environment path is not a regular file.")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError("Managed weather environment file mode verification failed.")
    if path == PRODUCTION_PATH and (metadata.st_uid != 0 or metadata.st_gid != 0):
        raise RuntimeError("Managed weather environment ownership verification failed.")
    return True


def _decoded_managed_secret(line: str) -> str | None:
    candidate = line.lstrip().rstrip("\r\n")
    prefix = f"{ENV_NAME}="
    if not candidate.startswith(prefix):
        return None
    encoded = candidate[len(prefix) :]
    if len(encoded) < 2 or encoded[0] != '"' or encoded[-1] != '"':
        return None

    payload = encoded[1:-1]
    decoded: list[str] = []
    escaped = False
    for character in payload:
        if escaped:
            if character not in {'"', "\\"}:
                return None
            decoded.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            return None
        else:
            decoded.append(character)
    if escaped:
        return None

    secret = "".join(decoded)
    try:
        return _validated_secret(secret.encode("utf-8"))
    except ValueError:
        return None


def credential_configured(path: Path) -> bool:
    """Return only whether one structurally valid managed credential exists."""
    if not _status_file_exists_and_is_safe(path):
        return False
    lines = _existing_lines(path)
    prefix = f"{ENV_NAME}="
    assignments = [line for line in lines if line.lstrip().startswith(prefix)]
    if len(assignments) != 1:
        return False
    return _decoded_managed_secret(assignments[0]) is not None


def set_secret(path: Path, raw: bytes) -> None:
    secret = _validated_secret(raw)
    lines = _without_secret(_existing_lines(path))
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.append(_encoded_line(secret))
    _atomic_write(path, "".join(lines))


def remove_secret(path: Path) -> None:
    lines = _without_secret(_existing_lines(path))
    if lines:
        _atomic_write(path, "".join(lines))
    elif path.exists():
        path.unlink()


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"set", "remove", "status"}:
        print("Usage: a-clockwork-plex-weather-secret set|remove|status", file=sys.stderr)
        return 64
    try:
        path = _target_path()
        if argv[1] == "status":
            configured = credential_configured(path)
            print(f"WEATHER_SECRET_CONFIGURED={1 if configured else 0}")
            return 0
        if argv[1] == "set":
            set_secret(path, sys.stdin.buffer.read(MAX_SECRET_BYTES + 1))
            print("Weather Underground credential stored.")
        else:
            remove_secret(path)
            print("Weather Underground credential removed.")
        if path.exists() and stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise RuntimeError("Managed weather environment file mode verification failed.")
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
