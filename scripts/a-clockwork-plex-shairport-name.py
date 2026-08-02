#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("/etc/shairport-sync.conf")
SERVICE_NAME = "shairport-sync.service"
SHAIRPORT_BINARY = Path("/usr/bin/shairport-sync")
SYSTEMCTL_BINARY = Path("/usr/bin/systemctl")
MAX_RECEIVER_NAME_LENGTH = 50
DISPLAY_CONFIG_END_MARKER = ">> Display Config End."
VALIDATION_TIMEOUT_SECONDS = 5.0
GENERAL_BLOCK_RE = re.compile(r"(?P<prefix>\bgeneral\s*=\s*\{)(?P<body>.*?)(?P<suffix>\}\s*;)", re.DOTALL)
NAME_RE = re.compile(r'(?m)^(?P<indent>\s*)name\s*=\s*"(?:\\.|[^"\\])*"\s*;')


def emit(payload: dict[str, Any], return_code: int = 0) -> None:
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(return_code)


def run(command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def validate_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("AirPlay receiver name cannot be blank.")
    if len(name) > MAX_RECEIVER_NAME_LENGTH:
        raise ValueError(
            f"AirPlay receiver name must be {MAX_RECEIVER_NAME_LENGTH} characters or fewer."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("AirPlay receiver name cannot contain control characters.")
    return name


def quote_libconfig(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def receiver_name_from_config(text: str) -> str | None:
    block = GENERAL_BLOCK_RE.search(text)
    if not block:
        return None
    match = NAME_RE.search(block.group("body"))
    if not match:
        return None
    statement = match.group(0)
    literal_match = re.search(r'"((?:\\.|[^"\\])*)"', statement)
    if not literal_match:
        return None
    try:
        return json.loads(f'"{literal_match.group(1)}"')
    except json.JSONDecodeError:
        return literal_match.group(1)


def update_receiver_name(text: str, receiver_name: str) -> str:
    quoted = quote_libconfig(receiver_name)
    block = GENERAL_BLOCK_RE.search(text)
    if not block:
        prefix = f"general =\n{{\n    name = {quoted};\n}};\n\n"
        return prefix + text.lstrip("\n")

    body = block.group("body")
    replacement = f"    name = {quoted};"
    if NAME_RE.search(body):
        body = NAME_RE.sub(replacement, body, count=1)
    else:
        if body and not body.startswith("\n"):
            body = "\n" + body
        body = f"\n{replacement}{body}"
        if not body.endswith("\n"):
            body += "\n"
    return text[: block.start("body")] + body + text[block.end("body") :]


def service_active() -> bool:
    result = run([str(SYSTEMCTL_BINARY), "is-active", "--quiet", SERVICE_NAME], timeout=8)
    return result.returncode == 0


def validation_command(path: Path) -> list[str]:
    # Shairport Sync exits after --displayConfig only when that is the sole option.
    # A custom candidate path therefore needs a supervised process. Port zero and
    # a temporary identity keep the short-lived validator separate from the live
    # receiver while the configuration parser runs.
    return [
        str(SHAIRPORT_BINARY),
        "--displayConfig",
        "--configfile",
        str(path),
        "--port",
        "0",
        "--name",
        f"ACP-config-check-{os.getpid()}",
    ]


def _stop_validation_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=1)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=1)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass


def _concise_validation_detail(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-8:])


def validate_config(path: Path) -> tuple[bool, str | None]:
    if not SHAIRPORT_BINARY.exists():
        return False, f"Shairport Sync binary not found at {SHAIRPORT_BINARY}."

    command = validation_command(path)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        return False, f"Could not start Shairport Sync configuration validation: {exc}"

    output: list[str] = []
    selector = selectors.DefaultSelector()
    marker_seen = False
    deadline = time.monotonic() + VALIDATION_TIMEOUT_SECONDS
    try:
        if process.stdout is None:
            return False, "Shairport Sync configuration validation produced no output stream."
        selector.register(process.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            events = selector.select(timeout=min(0.1, remaining))
            if events:
                for key, _mask in events:
                    line = key.fileobj.readline()
                    if line:
                        output.append(line)
                        if DISPLAY_CONFIG_END_MARKER in line:
                            marker_seen = True
                            break
                if marker_seen:
                    break
            elif process.poll() is not None:
                remainder = process.stdout.read()
                if remainder:
                    output.append(remainder)
                break
    finally:
        selector.close()
        _stop_validation_process(process)

    combined = "".join(output)
    if marker_seen or DISPLAY_CONFIG_END_MARKER in combined:
        return True, None

    detail = _concise_validation_detail(combined)
    if detail:
        return False, detail
    return False, "Shairport Sync did not finish reading the generated configuration."


def restart_service() -> tuple[bool, str | None]:
    result = run([str(SYSTEMCTL_BINARY), "restart", SERVICE_NAME], timeout=20)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail or "Could not restart Shairport Sync."
    if not service_active():
        return False, "Shairport Sync did not return to the active state."
    return True, None


def read_config() -> str:
    try:
        return CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read {CONFIG_PATH}: {exc}") from exc


def write_atomic(text: str, original_stat: os.stat_result) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".shairport-sync.conf.",
        dir=str(CONFIG_PATH.parent),
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, original_stat.st_mode & 0o7777)
        try:
            os.chown(temporary_path, original_stat.st_uid, original_stat.st_gid)
        except PermissionError:
            pass
        os.replace(temporary_path, CONFIG_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)


def status_payload() -> dict[str, Any]:
    text = read_config()
    return {
        "ok": True,
        "available": True,
        "config_path": str(CONFIG_PATH),
        "receiver_name": receiver_name_from_config(text),
        "service": SERVICE_NAME,
        "service_active": service_active(),
    }


def set_receiver_name(receiver_name: str) -> dict[str, Any]:
    name = validate_name(receiver_name)
    original = read_config()
    current_name = receiver_name_from_config(original)
    if current_name == name:
        payload = status_payload()
        payload.update({"changed": False, "restarted": False, "message": "Receiver name is already current."})
        return payload

    try:
        original_stat = CONFIG_PATH.stat()
    except OSError as exc:
        raise RuntimeError(f"Could not inspect {CONFIG_PATH}: {exc}") from exc

    updated = update_receiver_name(original, name)
    descriptor, candidate_name = tempfile.mkstemp(prefix="shairport-sync-candidate-", suffix=".conf")
    candidate = Path(candidate_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(updated)
        valid, validation_error = validate_config(candidate)
    finally:
        candidate.unlink(missing_ok=True)
    if not valid:
        raise RuntimeError(validation_error or "The generated Shairport configuration was invalid.")

    write_atomic(updated, original_stat)
    restarted, restart_error = restart_service()
    if not restarted:
        write_atomic(original, original_stat)
        rollback_ok, rollback_error = restart_service()
        detail = restart_error or "Shairport Sync restart failed."
        if not rollback_ok:
            detail += f" Rollback restart also failed: {rollback_error or 'unknown error'}"
        raise RuntimeError(detail)

    payload = status_payload()
    payload.update(
        {
            "changed": True,
            "restarted": True,
            "previous_receiver_name": current_name,
            "message": "AirPlay receiver name updated and Shairport Sync restarted.",
        }
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Shairport Sync advertised receiver name.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    set_parser = subparsers.add_parser("set")
    set_parser.add_argument("receiver_name")
    arguments = parser.parse_args()

    try:
        payload = status_payload() if arguments.command == "status" else set_receiver_name(arguments.receiver_name)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        emit({"ok": False, "error": str(exc)}, 1)
    emit(payload)


if __name__ == "__main__":
    main()
