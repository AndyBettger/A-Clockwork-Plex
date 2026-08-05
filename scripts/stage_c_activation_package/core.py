from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

from stage_c_package.core import PUBLIC_PCMS, build_validation_root, result, run, sha256
from stage_c_package.templates import HostContract

from .runtime_templates import PACKAGE_PHASE


EXPECTED_FILES = 28
RUNTIME_MODULES = (
    "__init__.py",
    "model.py",
    "approval_store.py",
    "state_machine.py",
    "supervisor_model.py",
    "runtime_executor.py",
    "linux_runtime_filesystem.py",
    "linux_runtime_process.py",
    "linux_runtime_adapter.py",
    "install_runtime_filesystem.py",
    "install_runtime_process.py",
    "install_runtime_adapter.py",
    "install_runtime_executor.py",
    "supervisor_service.py",
    "package_entry.py",
)


def create_lab_root(requested: Path | None) -> Path:
    if requested is None:
        root = Path(
            tempfile.mkdtemp(
                prefix="a-clockwork-plex-stage-c21-activation-package-v2.",
                dir="/var/tmp",
            )
        )
    else:
        root = requested.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise SystemExit(f"--lab-root must be empty: {root}")
    root.chmod(0o700)
    return root


def package_rows(rootfs: Path, *, exclude: set[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((p for p in rootfs.rglob("*") if p.is_file()), key=lambda p: str(p)):
        if path in exclude:
            continue
        rows.append(
            {
                "path": "/" + str(path.relative_to(rootfs)),
                "sha256": sha256(path),
            }
        )
    return rows


def package_fingerprint(rows: list[dict[str, str]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_package(
    rootfs: Path,
    lab: Path,
    paths: dict[str, Path],
    version: str,
    contract: HostContract,
) -> None:
    results = lab / "results.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")

    for name in ("split", "direct"):
        validation = lab / f"alsa-{name}-validation.conf"
        build_validation_root(paths[name], validation)
        env = os.environ.copy()
        env["ALSA_CONFIG_PATH"] = str(validation)
        probe = run(["aplay", "-L"], env=env)
        (lab / f"aplay-{name}.txt").write_text(probe.stdout, encoding="utf-8")
        (lab / f"aplay-{name}.err").write_text(probe.stderr, encoding="utf-8")
        if probe.returncode != 0:
            raise SystemExit(f"ALSA {name} candidate did not parse; see aplay-{name}.err")
        names = set(probe.stdout.splitlines())
        for pcm in PUBLIC_PCMS:
            if pcm not in names:
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

    python_candidates = [paths["route_helper"]]
    python_candidates.extend(sorted(paths["runtime_package"].glob("*.py")))
    for source_path in python_candidates:
        source = source_path.read_text(encoding="utf-8")
        compile(source, str(source_path), "exec")
    result(
        results,
        "runtime-python-syntax",
        "PASS",
        f"{len(python_candidates)} runtime Python candidates compiled in memory",
    )

    visudo = shutil.which("visudo")
    if visudo:
        checked = run([visudo, "-cf", str(paths["sudoers"])])
        (lab / "visudo.txt").write_text(checked.stdout + checked.stderr, encoding="utf-8")
        if checked.returncode != 0:
            raise SystemExit("Sudoers candidate failed validation; see visudo.txt")
        result(results, "sudoers-candidate", "PASS", "visudo accepted read-only user rules")
    else:
        result(results, "sudoers-candidate", "SKIP", "visudo unavailable")

    entries = list(rootfs.rglob("*"))
    invalid = [
        path
        for path in entries
        if path.is_symlink()
        or path.name == "__pycache__"
        or path.suffix == ".pyc"
        or not (path.is_dir() or path.is_file())
    ]
    if invalid:
        raise SystemExit(f"Package purity failure: unsupported artifact {invalid[0]}")
    files = [path for path in entries if path.is_file()]
    if len(files) != EXPECTED_FILES:
        raise SystemExit(
            f"Package file count mismatch: expected {EXPECTED_FILES}, found {len(files)}"
        )
    if (paths["runtime_package"] / "recording_runtime_adapter.py").exists():
        raise SystemExit("Production package unexpectedly contains the recording test adapter")
    result(
        results,
        "package-purity",
        "PASS",
        f"{len(files)} regular files; no cache, symlink, special object or recording adapter",
    )

    unit_text = "\n".join(
        paths[name].read_text(encoding="utf-8")
        for name in ("route_unit", "camilla_unit", "failback_unit")
    )
    required_fragments = (
        "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route boot-prepare",
        "Type=notify",
        "NotifyAccess=main",
        "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route supervise",
        "Before=plexamp.service shairport-sync.service a-clockwork-plex.service",
        "OnFailure=a-clockwork-plex-audio-failback.service",
        "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route emergency-direct-failback",
    )
    for fragment in required_fragments:
        if fragment not in unit_text:
            raise SystemExit(f"Runtime unit contract is missing: {fragment}")
    result(
        results,
        "systemd-readiness-contract",
        "PASS",
        "oneshot preparation precedes Type=notify supervisor and applications",
    )

    entry = paths["package_entry"].read_text(encoding="utf-8")
    for action in (
        "status",
        "validate-runtime",
        "accept-install-handoff",
        "promote-committed-approval",
        "boot-prepare",
        "supervise",
        "emergency-direct-failback",
    ):
        if action not in entry:
            raise SystemExit(f"Package entry is missing fixed action identity: {action}")
    for required in (
        "INSTALLED_PACKAGE_ROOT",
        PACKAGE_PHASE,
        'contract.get("host_mutation_available") is not True',
        "transaction-only approval operation is not exposed through the service helper",
        "runtime mutation requires root",
    ):
        if required not in entry:
            raise SystemExit(f"Activation-capable package entry is missing guard: {required}")
    for forbidden in (
        "subprocess.Popen",
        "shell=True",
        "systemctl",
        "os.system",
        "os.exec",
        "def dispatch",
    ):
        if forbidden in entry:
            raise SystemExit(f"Package entry contains a forbidden direct boundary: {forbidden}")
    result(
        results,
        "runtime-entry-boundary",
        "PASS",
        "fixed installed actions are package-bound; transaction-only approval operations remain unexposed",
    )

    contract_payload = json.loads(paths["package_contract"].read_text(encoding="utf-8"))
    if contract_payload.get("schema_version") != 1:
        raise SystemExit("Package contract schema mismatch")
    if contract_payload.get("package_phase") != PACKAGE_PHASE:
        raise SystemExit("Package contract phase mismatch")
    if contract_payload.get("host_mutation_available") is not True:
        raise SystemExit("Package contract does not identify the reviewed runtime authority")
    rows = contract_payload.get("files")
    if not isinstance(rows, list) or len(rows) != EXPECTED_FILES - 1:
        raise SystemExit("Package contract file set mismatch")
    if contract_payload.get("package_fingerprint") != package_fingerprint(rows):
        raise SystemExit("Package fingerprint mismatch")
    result(
        results,
        "package-fingerprint",
        "PASS",
        f"{len(rows)} payload files bound by one deterministic fingerprint",
    )


def write_manifest(rootfs: Path, manifest: Path, results: Path) -> None:
    rows = ["type\tdestination\tmode\towner\tsha256"]
    for directory in sorted((p for p in rootfs.rglob("*") if p.is_dir()), key=lambda p: str(p)):
        destination = "/" + str(directory.relative_to(rootfs))
        rows.append(
            f"directory\t{destination}\t{stat.S_IMODE(directory.stat().st_mode):o}\troot:root\t-"
        )
    for file in sorted((p for p in rootfs.rglob("*") if p.is_file()), key=lambda p: str(p)):
        destination = "/" + str(file.relative_to(rootfs))
        rows.append(
            f"file\t{destination}\t{stat.S_IMODE(file.stat().st_mode):o}\troot:root\t{sha256(file)}"
        )
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    state_row = "directory\t/var/lib/a-clockwork-plex/split-bus\t755\troot:root\t-"
    if state_row not in rows:
        raise SystemExit("Manifest omitted the required empty Stage C state directory.")
    result(
        results,
        "manifest-contract",
        "PASS",
        "directories and all versioned package files recorded",
    )
