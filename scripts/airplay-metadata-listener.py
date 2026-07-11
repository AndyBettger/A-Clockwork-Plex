#!/usr/bin/env python3
"""Read Shairport Sync metadata from a FIFO and store it for the dashboard.

Shairport Sync writes metadata packets as:

    4 byte namespace, 4 byte code, 4 byte big-endian payload length, payload

Common examples are ``core/minm`` for title, ``core/asar`` for artist and
``ssnc/pvol`` for volume. This listener keeps the state file small by storing
text metadata in ``state.json`` and cover art as a generated static file.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PIPE_PATH = Path(os.environ.get("SHAIRPORT_METADATA_PIPE", "/tmp/shairport-sync-metadata"))
BASE_DIR = Path(os.environ.get("ACP_BASE_DIR", Path(__file__).resolve().parent.parent))
STATE_PATH = Path(os.environ.get("ACP_STATE_PATH", BASE_DIR / "state.json"))
ARTWORK_DIR = Path(os.environ.get("ACP_ARTWORK_DIR", BASE_DIR / "app" / "static" / "generated"))
ARTWORK_URL_PREFIX = os.environ.get("ACP_ARTWORK_URL_PREFIX", "/static/generated").rstrip("/")
MAX_FRAME_BYTES = int(os.environ.get("ACP_METADATA_MAX_FRAME_BYTES", str(8 * 1024 * 1024)))

TEXT_FIELDS = {
    "minm": "title",
    "asar": "artist",
    "asal": "album",
    "asgn": "genre",
    "ascp": "composer",
    "asaa": "album_artist",
    "assn": "sort_title",
    "assa": "sort_artist",
    "assl": "sort_album",
    "asdk": "disc_kind",
    "asdt": "date",
    "asct": "category",
    "ascm": "comment",
    "asfm": "format",
    "clip": "client_ip",
}

SESSION_CODES = {
    "pbeg": "play_start",
    "pend": "play_end",
    "pfls": "play_flush",
    "prsm": "play_resume",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"{now_iso()} {message}", flush=True)


def ensure_fifo(path: Path) -> None:
    """Ensure the metadata path is a FIFO without crashing on ownership quirks.

    Shairport Sync and this listener may run as different users. If Shairport
    created the FIFO first, this listener may be able to read it but not chmod
    it. That should be a warning, not a service-killing error.
    """
    if path.exists():
        mode = path.stat().st_mode
        if not stat.S_ISFIFO(mode):
            raise RuntimeError(f"Metadata path exists but is not a FIFO: {path}")
        try:
            os.chmod(path, 0o666)
        except PermissionError:
            log(f"Metadata FIFO already exists but chmod was not permitted: {path}")
            log("Continuing; rerun scripts/install-airplay-metadata-listener.sh if opening the pipe fails.")
        return

    os.mkfifo(path, 0o666)
    try:
        os.chmod(path, 0o666)
    except PermissionError:
        log(f"Metadata FIFO created but chmod was not permitted: {path}")


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log(f"Could not read state file: {exc}")
        return {}


def save_state(state: dict[str, Any]) -> None:
    tmp_path = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(STATE_PATH)


def default_metadata() -> dict[str, Any]:
    return {
        "available": False,
        "title": None,
        "artist": None,
        "album": None,
        "album_artist": None,
        "genre": None,
        "composer": None,
        "format": None,
        "volume": None,
        "volume_db": None,
        "client_ip": None,
        "artwork_url": None,
        "updated_at": None,
        "last_event": None,
    }


def airplay_state(state: dict[str, Any]) -> dict[str, Any]:
    airplay = state.setdefault("airplay", {})
    if not isinstance(airplay, dict):
        airplay = {}
        state["airplay"] = airplay
    metadata = airplay.setdefault("metadata", default_metadata())
    if not isinstance(metadata, dict):
        metadata = default_metadata()
        airplay["metadata"] = metadata
    merged = default_metadata()
    merged.update(metadata)
    airplay["metadata"] = merged
    return airplay


def decode_text(payload: bytes) -> str:
    payload = payload.rstrip(b"\x00")
    for encoding in ("utf-8", "latin-1"):
        try:
            return payload.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace").strip()


def read_exact(handle, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining > 0:
        chunk = handle.read(remaining)
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def parse_header(header: bytes) -> tuple[str, str, int]:
    namespace = header[:4].decode("latin-1", errors="replace")
    code = header[4:8].decode("latin-1", errors="replace")
    length = int.from_bytes(header[8:12], "big")
    if length > MAX_FRAME_BYTES:
        little = int.from_bytes(header[8:12], "little")
        if little <= MAX_FRAME_BYTES:
            length = little
    return namespace, code, length


def artwork_extension(payload: bytes) -> str | None:
    if payload.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
        return "gif"
    return None


def store_artwork(payload: bytes) -> str | None:
    extension = artwork_extension(payload)
    if not extension:
        return None
    ARTWORK_DIR.mkdir(parents=True, exist_ok=True)
    # Remove older generated artwork so the directory does not become a tiny album-art attic.
    for old_file in ARTWORK_DIR.glob("airplay-cover.*"):
        try:
            old_file.unlink()
        except OSError:
            pass
    artwork_path = ARTWORK_DIR / f"airplay-cover.{extension}"
    artwork_path.write_bytes(payload)
    cache_buster = int(time.time())
    return f"{ARTWORK_URL_PREFIX}/airplay-cover.{extension}?v={cache_buster}"


def parse_volume(payload: bytes) -> tuple[str | None, float | None]:
    text = decode_text(payload)
    first = text.split(",", 1)[0].strip()
    try:
        db_value = float(first)
    except ValueError:
        return text or None, None
    if db_value <= -143:
        return "Muted", db_value
    # AirPlay volume is normally in dB below full scale. Keep the raw dB; it is
    # more honest than pretending it is a hardware-volume percentage.
    return f"{db_value:.1f} dB", db_value


def update_metadata(namespace: str, code: str, payload: bytes) -> None:
    state = load_state()
    airplay = airplay_state(state)
    metadata = airplay["metadata"]
    changed = False
    now = now_iso()

    if code in SESSION_CODES:
        metadata["last_event"] = SESSION_CODES[code]
        metadata["updated_at"] = now
        changed = True
        if code == "pbeg":
            # Clear stale title/artist data at the beginning of a new play run.
            artwork_url = metadata.get("artwork_url")
            metadata.clear()
            metadata.update(default_metadata())
            metadata["artwork_url"] = artwork_url
            metadata["last_event"] = "play_start"
            metadata["updated_at"] = now
        elif code in {"pend", "pfls"}:
            metadata["last_event"] = SESSION_CODES[code]

    if code in TEXT_FIELDS:
        value = decode_text(payload)
        if value:
            key = TEXT_FIELDS[code]
            metadata[key] = value
            if key == "client_ip":
                airplay["source"] = value
            metadata["available"] = True
            metadata["updated_at"] = now
            changed = True
            log(f"metadata {key}: {value}")

    elif code == "pvol":
        volume_label, volume_db = parse_volume(payload)
        metadata["volume"] = volume_label
        metadata["volume_db"] = volume_db
        metadata["updated_at"] = now
        changed = True
        if volume_label:
            log(f"metadata volume: {volume_label}")

    elif code == "PICT":
        artwork_url = store_artwork(payload)
        if artwork_url:
            metadata["artwork_url"] = artwork_url
            metadata["available"] = True
            metadata["updated_at"] = now
            changed = True
            log("metadata artwork updated")

    if changed:
        state["airplay"] = airplay
        save_state(state)


def listen_forever() -> None:
    ensure_fifo(PIPE_PATH)
    log(f"Listening for Shairport Sync metadata on {PIPE_PATH}")
    while True:
        try:
            with PIPE_PATH.open("rb", buffering=0) as handle:
                while True:
                    header = read_exact(handle, 12)
                    namespace, code, length = parse_header(header)
                    if length < 0 or length > MAX_FRAME_BYTES:
                        log(f"Skipping suspicious metadata frame {namespace}/{code} length={length}")
                        continue
                    payload = read_exact(handle, length) if length else b""
                    update_metadata(namespace, code, payload)
        except EOFError:
            time.sleep(0.25)
        except Exception as exc:
            log(f"metadata listener error: {exc}")
            time.sleep(2)


if __name__ == "__main__":
    try:
        listen_forever()
    except KeyboardInterrupt:
        sys.exit(0)
