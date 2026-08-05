#!/usr/bin/python3
from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from .templates import HostContract

CURRENT_ALSA = Path("/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf")
EXPECTED_FILES = 12
PUBLIC_PCMS = ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def validate_name(label: str, value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", value):
        raise SystemExit(f"Invalid {label}: {value}")
    return value


def first_parameter(name: str) -> str:
    path = Path("/sys/module/snd_aloop/parameters") / name
    try:
        return path.read_text(encoding="utf-8").strip().split(",", 1)[0]
    except OSError as exc:
        raise SystemExit(f"Cannot read snd_aloop {name}: {exc}") from exc


def validate_host(binary: Path, contract: HostContract) -> str:
    if os.geteuid() == 0:
        raise SystemExit(f"Run as {contract.project_user}, not as root.")
    if platform.machine() != "aarch64":
        raise SystemExit(f"Expected aarch64; found {platform.machine()}.")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f"CamillaDSP binary is not executable: {binary}")
    version_result = run([str(binary), "--version"])
    version_lines = (version_result.stdout or version_result.stderr).splitlines()
    version = version_lines[0] if version_lines else "<no version output>"
    if version_result.returncode != 0 or contract.camilladsp_version not in version:
        raise SystemExit(f"Unexpected CamillaDSP version: {version}")
    if sha256(binary) != contract.camilladsp_sha256:
        raise SystemExit(f"Unexpected CamillaDSP SHA-256: {sha256(binary)}")
    if not CURRENT_ALSA.is_file():
        raise SystemExit(f"Current ALSA route is unreadable: {CURRENT_ALSA}")
    observed_alsa = sha256(CURRENT_ALSA)
    if observed_alsa != contract.pre_stage_c_alsa_sha256:
        raise SystemExit(
            "Current ALSA checksum differs from the physically validated pre-Stage-C route.\n"
            f"Expected: {contract.pre_stage_c_alsa_sha256}\nObserved: {observed_alsa}"
        )
    current_text = CURRENT_ALSA.read_text(encoding="utf-8")
    start = current_text.index("pcm.acp_alarm_volume")
    end = current_text.index("pcm.acp_alarm {", start)
    if 'slave.pcm "acp_master"' not in current_text[start:end]:
        raise SystemExit("Current route is not the expected pre-Stage-C alarm-under-Master graph.")
    expected_parameters = {
        "index": str(contract.loopback_index),
        "id": contract.loopback_id,
        "pcm_substreams": "2",
        "pcm_notify": "1",
    }
    for name, expected in expected_parameters.items():
        observed = first_parameter(name)
        if observed != expected:
            raise SystemExit(f"Unexpected snd_aloop {name}: {observed}")
    cards = Path("/proc/asound/cards").read_text(encoding="utf-8")
    if not re.search(rf"^\s*{contract.loopback_index}\s+\[ACPLoopback\s*\]", cards, re.MULTILINE):
        raise SystemExit("Expected ACP loopback card was not found.")
    if not re.search(r"^\s*\d+\s+\[Pro\s*\]", cards, re.MULTILINE):
        raise SystemExit("Physical DAC card Pro was not found.")
    return version


def create_lab_root(requested: Path | None) -> Path:
    if requested is None:
        root = Path(tempfile.mkdtemp(prefix="a-clockwork-plex-stage-c1-package.", dir="/var/tmp"))
    else:
        root = requested.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise SystemExit(f"--lab-root must be empty: {root}")
    root.chmod(0o700)
    return root


def write_text(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def build_validation_root(fragment: Path, output: Path) -> None:
    base_path = Path("/usr/share/alsa/alsa.conf")
    lines = base_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    skipping = False
    depth = 0
    removed = False
    for line in lines:
        stripped = line.strip()
        if not removed and not skipping and stripped.startswith("@hooks") and "[" in stripped:
            skipping = True
            depth = line.count("[") - line.count("]")
            if depth == 0:
                skipping = False
                removed = True
            continue
        if skipping:
            depth += line.count("[") - line.count("]")
            if depth == 0:
                skipping = False
                removed = True
            continue
        out.append(line)
    if not removed:
        raise SystemExit("Could not remove the global ALSA preload hook.")
    out.extend(("", fragment.read_text(encoding="utf-8")))
    output.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def result(results: Path, check: str, status_text: str, detail: str) -> None:
    line = f"{check}\t{status_text}\t{detail}\n"
    with results.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(line.rstrip())


def validate_package(rootfs: Path, lab: Path, paths: dict[str, Path], version: str, contract: HostContract) -> None:
    results = lab / "results.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")
    for name in ("split", "direct"):
        fragment = paths[name]
        validation = lab / f"alsa-{name}-validation.conf"
        build_validation_root(fragment, validation)
        env = os.environ.copy()
        env["ALSA_CONFIG_PATH"] = str(validation)
        probe = run(["aplay", "-L"], env=env)
        (lab / f"aplay-{name}.txt").write_text(probe.stdout, encoding="utf-8")
        (lab / f"aplay-{name}.err").write_text(probe.stderr, encoding="utf-8")
        if probe.returncode != 0:
            raise SystemExit(f"ALSA {name} candidate did not parse; see aplay-{name}.err")
        for pcm in PUBLIC_PCMS:
            if pcm not in probe.stdout.splitlines():
                raise SystemExit(f"{name} route is missing {pcm}")
        result(results, f"alsa-{name}-parse", "PASS", "candidate parsed")
    result(results, "public-pcm-contract", "PASS", "all five public PCMs exist in both routes")

    if sha256(paths["binary"]) != contract.camilladsp_sha256:
        raise SystemExit("Staged CamillaDSP checksum changed during copy.")
    camilla = run([str(paths["binary"]), "--check", str(paths["camilla_config"])])
    (lab / "camilladsp-check.txt").write_text(camilla.stdout + camilla.stderr, encoding="utf-8")
    if camilla.returncode != 0:
        raise SystemExit("CamillaDSP configuration failed validation; see camilladsp-check.txt")
    result(results, "camilladsp-config", "PASS", version)

    source = paths["route_helper"].read_text(encoding="utf-8")
    compile(source, str(paths["route_helper"]), "exec")
    result(results, "route-helper-syntax", "PASS", "Python candidate compiled in memory")

    visudo = shutil.which("visudo")
    if visudo:
        checked = run([visudo, "-cf", str(paths["sudoers"])])
        (lab / "visudo.txt").write_text(checked.stdout + checked.stderr, encoding="utf-8")
        if checked.returncode != 0:
            raise SystemExit("Sudoers candidate failed validation; see visudo.txt")
        result(results, "sudoers-candidate", "PASS", "visudo accepted read-only rules")
    else:
        result(results, "sudoers-candidate", "SKIP", "visudo unavailable")

    entries = list(rootfs.rglob("*"))
    invalid = [
        p
        for p in entries
        if p.is_symlink() or p.name == "__pycache__" or p.suffix == ".pyc" or not (p.is_dir() or p.is_file())
    ]
    if invalid:
        raise SystemExit(f"Package purity failure: unsupported artifact {invalid[0]}")
    files = [p for p in entries if p.is_file()]
    if len(files) != EXPECTED_FILES:
        raise SystemExit(f"Package file count mismatch: expected {EXPECTED_FILES}, found {len(files)}")
    result(results, "package-purity", "PASS", f"{len(files)} regular files; no cache, symlink or special objects")

    route_unit = paths["route_unit"].read_text(encoding="utf-8")
    camilla_unit = paths["camilla_unit"].read_text(encoding="utf-8")
    required_fragments = (
        "Before=a-clockwork-plex-camilladsp.service plexamp.service shairport-sync.service a-clockwork-plex.service",
        "Requires=a-clockwork-plex-audio-route.service sound.target",
        "Before=plexamp.service shairport-sync.service a-clockwork-plex.service",
        "OnFailure=a-clockwork-plex-audio-failback.service",
    )
    combined = route_unit + "\n" + camilla_unit
    for fragment in required_fragments:
        if fragment not in combined:
            raise SystemExit(f"Systemd ordering contract is missing: {fragment}")
    result(results, "systemd-ordering-contract", "PASS", "route authority precedes DSP and source services")


def write_manifest(rootfs: Path, manifest: Path, results: Path) -> None:
    rows = ["type\tdestination\tmode\towner\tsha256"]
    for directory in sorted((p for p in rootfs.rglob("*") if p.is_dir()), key=lambda p: str(p)):
        destination = "/" + str(directory.relative_to(rootfs))
        rows.append(f"directory\t{destination}\t{stat.S_IMODE(directory.stat().st_mode):o}\troot:root\t-")
    for file in sorted((p for p in rootfs.rglob("*") if p.is_file()), key=lambda p: str(p)):
        destination = "/" + str(file.relative_to(rootfs))
        rows.append(f"file\t{destination}\t{stat.S_IMODE(file.stat().st_mode):o}\troot:root\t{sha256(file)}")
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    state_row = "directory\t/var/lib/a-clockwork-plex/split-bus\t755\troot:root\t-"
    if state_row not in rows:
        raise SystemExit("Manifest omitted the required empty Stage C state directory.")
    result(results, "manifest-contract", "PASS", "directories and files recorded; empty state directory retained")
