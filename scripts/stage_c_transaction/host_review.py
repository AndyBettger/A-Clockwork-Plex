#!/usr/bin/python3
from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from .package_review import (
    ManifestEntry,
    mode_from_stat,
    mode_string,
    owner_from_stat,
    owner_string,
    sha256,
)

EXPECTED_PRE_STAGE_C_ALSA_SHA256 = "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"
CURRENT_ALSA = Path("/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf")
APPROVAL_MARKER = Path("/var/lib/a-clockwork-plex/split-bus/activation-approved")
APPLICATION_SERVICES = (
    "plexamp.service",
    "shairport-sync.service",
    "a-clockwork-plex.service",
)
STAGE_C_SERVICES = (
    "a-clockwork-plex-audio-route.service",
    "a-clockwork-plex-camilladsp.service",
    "a-clockwork-plex-audio-failback.service",
)
MIXER_CONTROLS = (
    "A Clockwork Master",
    "A Clockwork Plexamp",
    "A Clockwork AirPlay",
    "A Clockwork Alarm",
)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def create_review_root(requested: Path | None) -> Path:
    if requested is None:
        root = Path(tempfile.mkdtemp(prefix="a-clockwork-plex-stage-c2-transaction.", dir="/var/tmp"))
    else:
        root = requested.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise SystemExit(f"--transaction-root must be empty: {root}")
    root.chmod(0o700)
    return root


def _first_module_parameter(name: str) -> str:
    path = Path("/sys/module/snd_aloop/parameters") / name
    try:
        return path.read_text(encoding="utf-8").strip().split(",", 1)[0]
    except OSError as exc:
        raise SystemExit(f"Cannot read snd_aloop {name}: {exc}") from exc


def running_camilladsp_pids() -> list[int]:
    pids: list[int] = []
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text(encoding="utf-8").strip() == "camilladsp":
                pids.append(int(comm.parent.name))
        except (OSError, ValueError):
            continue
    return sorted(pids)


def validate_current_host() -> None:
    if os.geteuid() == 0:
        raise SystemExit("Run Stage C2 as the normal project user, not as root.")
    if platform.machine() != "aarch64":
        raise SystemExit(f"Expected aarch64; found {platform.machine()}.")
    if not CURRENT_ALSA.is_file():
        raise SystemExit(f"Current ALSA route is missing: {CURRENT_ALSA}")
    if sha256(CURRENT_ALSA) != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise SystemExit("Current ALSA checksum is not the physically validated pre-Stage-C route.")
    if mode_string(CURRENT_ALSA) != "644" or owner_string(CURRENT_ALSA) != "root:root":
        raise SystemExit("Current ALSA owner/mode differs from the validated pre-Stage-C state.")
    text = CURRENT_ALSA.read_text(encoding="utf-8")
    start = text.index("pcm.acp_alarm_volume")
    end = text.index("pcm.acp_alarm {", start)
    if 'slave.pcm "acp_master"' not in text[start:end]:
        raise SystemExit("Current route is not the expected alarm-under-Master rollback graph.")

    expected = {"index": "7", "id": "ACP_Loopback", "pcm_substreams": "2", "pcm_notify": "1"}
    for name, value in expected.items():
        observed = _first_module_parameter(name)
        if observed != value:
            raise SystemExit(f"Unexpected snd_aloop {name}: {observed}")
    if APPROVAL_MARKER.exists():
        raise SystemExit(f"Unexpected Stage C approval marker already exists: {APPROVAL_MARKER}")
    pids = running_camilladsp_pids()
    if pids:
        raise SystemExit(f"Unexpected running CamillaDSP process: {pids}")


def snapshot_paths(
    entries: list[ManifestEntry], review_root: Path, privileged_paths: set[str]
) -> Path:
    snapshot_root = review_root / "review-snapshot"
    files_root = snapshot_root / "rootfs"
    marker_root = snapshot_root / "absence-markers"
    files_root.mkdir(parents=True)
    marker_root.mkdir(parents=True)
    metadata = ["kind\tdestination\tpreinstall_state\tmode\towner\tsha256\tsnapshot"]

    managed_files = [Path(entry.destination) for entry in entries if entry.kind == "file"]
    for destination in [CURRENT_ALSA, *managed_files]:
        relative = destination.relative_to("/")
        if str(destination) in privileged_paths:
            marker = marker_root / (str(relative).replace("/", "__") + ".privileged-check-required")
            marker.write_text(
                "UNVERIFIED\t"
                f"{destination}\tprivileged activation-time snapshot required before any write\n",
                encoding="utf-8",
            )
            metadata.append(
                f"file\t{destination}\tprivileged-check-required\t-\t-\t-\t{marker}"
            )
            continue

        try:
            info = destination.lstat()
        except FileNotFoundError:
            info = None
        except PermissionError as exc:
            raise SystemExit(
                f"New protected destination appeared after conflict review: {destination} ({exc})."
            ) from exc

        if info is not None and stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Refusing to snapshot symlinked managed path: {destination}")
        if info is not None and stat.S_ISREG(info.st_mode):
            snapshot = files_root / relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, snapshot)
            metadata.append(
                f"file\t{destination}\tpresent\t{mode_from_stat(info)}\t"
                f"{owner_from_stat(info)}\t{sha256(destination)}\t{snapshot}"
            )
        elif info is not None:
            raise SystemExit(f"Managed file destination is not a regular file: {destination}")
        else:
            marker = marker_root / (str(relative).replace("/", "__") + ".absent")
            marker.write_text(f"ABSENT\t{destination}\n", encoding="utf-8")
            metadata.append(f"file\t{destination}\tabsent\t-\t-\t-\t{marker}")

    for entry in entries:
        if entry.kind != "directory":
            continue
        destination = Path(entry.destination)
        try:
            info = destination.lstat()
        except FileNotFoundError:
            info = None
        except PermissionError as exc:
            raise SystemExit(f"Cannot inspect managed directory {destination}: {exc}") from exc
        if info is not None and stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Refusing symlinked managed directory: {destination}")
        if info is not None and stat.S_ISDIR(info.st_mode):
            metadata.append(
                f"directory\t{destination}\tpresent\t{mode_from_stat(info)}\t"
                f"{owner_from_stat(info)}\t-\t-"
            )
        elif info is not None:
            raise SystemExit(f"Managed directory destination has a conflicting type: {destination}")
        else:
            metadata.append(f"directory\t{destination}\tabsent\t-\t-\t-\t-")

    (snapshot_root / "filesystem-state.tsv").write_text("\n".join(metadata) + "\n", encoding="utf-8")
    return snapshot_root


def capture_service_states(output: Path) -> dict[str, tuple[str, str, str]]:
    rows = ["service\tload_state\tactive_state\tenabled_state"]
    states: dict[str, tuple[str, str, str]] = {}
    for service in (*APPLICATION_SERVICES, *STAGE_C_SERVICES):
        show = run(["systemctl", "show", service, "--property=LoadState", "--value"])
        load_state = (show.stdout.strip() or "unknown").replace("\t", " ")
        active = run(["systemctl", "is-active", service]).stdout.strip() or "unknown"
        enabled_result = run(["systemctl", "is-enabled", service])
        enabled = (enabled_result.stdout.strip() or "unknown").replace("\t", " ")
        states[service] = (load_state, active, enabled)
        rows.append(f"{service}\t{load_state}\t{active}\t{enabled}")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return states


def validate_service_boundary(states: dict[str, tuple[str, str, str]]) -> None:
    for service in APPLICATION_SERVICES:
        load_state, active, enabled = states[service]
        if (load_state, active, enabled) != ("loaded", "active", "enabled"):
            raise SystemExit(
                f"Application service differs from the discovered Stage C boundary: "
                f"{service} load={load_state} active={active} enabled={enabled}"
            )
    for service in STAGE_C_SERVICES:
        load_state, _active, enabled = states[service]
        if load_state != "not-found" or enabled != "not-found":
            raise SystemExit(
                f"Unexpected pre-existing Stage C service: {service} load={load_state} enabled={enabled}"
            )


def capture_mixer_states(output: Path, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True)
    rows = ["control\tpercent\traw_output"]
    for control in MIXER_CONTROLS:
        result = run(["amixer", "-c", "Pro", "sget", control])
        raw_path = raw_dir / (control.lower().replace(" ", "-") + ".txt")
        raw_path.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise SystemExit(f"Could not read mixer control: {control}")
        matches = re.findall(r"\[(\d+)%\]", result.stdout)
        if not matches:
            raise SystemExit(f"Could not parse mixer percentage: {control}")
        rows.append(f"{control}\t{matches[0]}\t{raw_path}")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def capture_module_and_dac(output: Path, review_root: Path) -> None:
    params = {
        name: _first_module_parameter(name)
        for name in ("index", "id", "pcm_substreams", "pcm_notify", "enable")
    }
    device = Path("/dev/snd/pcmC2D0p")
    hw_params_path = Path("/proc/asound/Pro/pcm0p/sub0/hw_params")
    hw_copy = review_root / "dac-hw-params.txt"
    hw_copy.write_text(
        hw_params_path.read_text(encoding="utf-8") if hw_params_path.is_file() else "<unavailable>\n",
        encoding="utf-8",
    )
    fuser = run(["fuser", str(device)])
    owners = (fuser.stdout + fuser.stderr).strip().replace("\t", " ")
    rows = [
        "item\tvalue",
        "snd_aloop.loaded\ttrue",
        *(f"snd_aloop.{name}\t{value}" for name, value in params.items()),
        f"dac.device\t{device}",
        f"dac.exists\t{str(device.exists()).lower()}",
        f"dac.owners\t{owners or 'none'}",
        f"dac.hw_params\t{hw_copy}",
    ]
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
