#!/usr/bin/python3
from __future__ import annotations

import argparse
import csv
import errno
import fcntl
import os
import platform
import secrets
import shutil
import stat
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .host_review import (
    capture_mixer_states,
    capture_module_and_dac,
    capture_service_states,
    validate_service_boundary,
)
from .package_review import EXPECTED_PACKAGE_FILES, sha256, validate_stage_c1_evidence
from .privileged_snapshot import (
    invoking_identity,
    validate_current_host_as_root,
    write_package_fingerprint,
    write_rollback_ledger,
)
from .privileged_snapshot_entry import validate_physical_capture_boundary
from .production_plan import (
    EXPECTED_SCENARIOS,
    EXPECTED_STAGE_C4_CHECKS,
    _validate_evidence_manifest,
    blocker_rows,
    command_rows,
    lock_rows,
    rollback_rows,
    snapshot_rows,
    state_machine_rows,
)
from .sandbox_transaction import (
    CURRENT_ALSA_DESTINATION,
    EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    _assert_regular_tree,
    _read_tsv,
    tree_fingerprint,
    validate_inputs,
)
from .snapshot_core import (
    chown_evidence_tree,
    collect_filesystem_snapshot,
    write_evidence_manifest,
)

REQUIRED_CONFIRMATION = "STAGE-C6-LOCKED-PRIVILEGED-SNAPSHOT-READ-ONLY"
SNAPSHOT_PREFIX = "a-clockwork-plex-stage-c6-snapshot."
PRODUCTION_LOCK = Path("/run/lock/a-clockwork-plex-audio-route.lock")
REHEARSAL_LOCK_RELATIVE = Path("control/a-clockwork-plex-audio-route.lock")
SNAPSHOT_VERSION = 1
EXPECTED_STAGE_C5_CHECKS = (
    "input-replay",
    "stage-c4-proof",
    "review-scope",
    "state-machine",
    "single-lock",
    "fresh-snapshot",
    "command-contract",
    "rollback-ownership",
    "activation-blockers",
    "input-integrity",
)


@dataclass
class RehearsalLock:
    path: Path
    fd: int
    inode: int
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.released = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a root-owned Stage C6 lock-before-snapshot rehearsal. "
            "The production route lock and all production destinations remain read-only."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c3-root", required=True, type=Path)
    parser.add_argument("--stage-c4-root", required=True, type=Path)
    parser.add_argument("--stage-c5-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def _mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.lstat().st_mode):o}"


def _validate_owned_input_root(
    path: Path,
    *,
    prefix: str,
    invoking_uid: int,
    label: str,
) -> Path:
    raw = path.expanduser()
    if not raw.is_absolute():
        raise SystemExit(f"{label} must be an absolute path.")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} does not exist: {raw}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"{label} must be a real directory: {raw}")
    resolved = raw.resolve()
    if resolved.parent != Path("/var/tmp") or not resolved.name.startswith(prefix):
        raise SystemExit(f"Unexpected {label} directory: {resolved}")
    if info.st_uid != invoking_uid:
        raise SystemExit(f"{label} must remain owned by the invoking user.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit(f"{label} root must retain mode 0700.")
    _assert_regular_tree(resolved, label)
    return resolved


def validate_snapshot_root(raw: Path, invoking_uid: int) -> Path:
    if not raw.is_absolute() or raw.parent != Path("/var/tmp"):
        raise SystemExit("--snapshot-root must be directly beneath /var/tmp.")
    if not raw.name.startswith(SNAPSHOT_PREFIX):
        raise SystemExit(f"--snapshot-root name must start with {SNAPSHOT_PREFIX}")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit("--snapshot-root must already exist and be empty.") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("--snapshot-root must be a real directory.")
    if info.st_uid != invoking_uid:
        raise SystemExit("--snapshot-root must be owned by the invoking user before capture.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("--snapshot-root must have mode 0700.")
    if any(raw.iterdir()):
        raise SystemExit("--snapshot-root must be empty.")
    return raw.resolve()


def _rows_equal(observed: list[dict[str, str]], expected: list[dict[str, str]], label: str) -> None:
    if observed != expected:
        raise SystemExit(f"Stage C5 {label} differs from the reviewed contract.")


def validate_stage_c4(stage_c4_root: Path, invoking_uid: int) -> Path:
    root = _validate_owned_input_root(
        stage_c4_root,
        prefix="a-clockwork-plex-stage-c4-sandbox.",
        invoking_uid=invoking_uid,
        label="Stage C4 evidence",
    )
    _validate_evidence_manifest(root, "Stage C4")
    results = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in results) != EXPECTED_STAGE_C4_CHECKS:
        raise SystemExit("Stage C4 evidence does not contain the exact nine checks.")
    if any(row.get("result") != "PASS" for row in results):
        raise SystemExit("Stage C4 evidence contains a non-PASS result.")
    observed_scenarios = tuple(
        (
            row.get("scenario", ""),
            row.get("injected_failure", ""),
            row.get("install_verified", ""),
            row.get("rollback_reason", ""),
            row.get("rollback_mismatches", ""),
        )
        for row in _read_tsv(root / "scenario-state.tsv")
    )
    if observed_scenarios != EXPECTED_SCENARIOS:
        raise SystemExit("Stage C4 scenario evidence differs from the reviewed result.")

    plan = _read_tsv(root / "file-plan.tsv")
    managed = [row for row in plan if row.get("type") == "file"]
    active = [row for row in plan if row.get("type") == "active-route"]
    if len(managed) != EXPECTED_PACKAGE_FILES or any(
        row.get("stage_c3_state") != "absent" for row in managed
    ):
        raise SystemExit("Stage C4 managed-file absence boundary changed.")
    if len(active) != 1 or (
        active[0].get("destination") != CURRENT_ALSA_DESTINATION
        or active[0].get("candidate_sha256") != EXPECTED_PRE_STAGE_C_ALSA_SHA256
        or active[0].get("stage_c3_state") != "present"
    ):
        raise SystemExit("Stage C4 active-route rollback contract changed.")

    for scenario in EXPECTED_SCENARIOS:
        name = scenario[0]
        sudoers = root / "scenarios" / name / "system-root/etc/sudoers.d"
        if sudoers.is_symlink() or not sudoers.is_dir() or _mode(sudoers) != "750":
            raise SystemExit(f"Stage C4 sudoers mode restoration changed: {name}")
        current = (
            root
            / "scenarios"
            / name
            / "system-root"
            / CURRENT_ALSA_DESTINATION.lstrip("/")
        )
        if not current.is_file() or sha256(current) != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
            raise SystemExit(f"Stage C4 exact ALSA restoration changed: {name}")
    return root


def validate_stage_c5(
    stage_c5_root: Path,
    *,
    package_root: Path,
    stage_c3_root: Path,
    stage_c4_root: Path,
    invoking_uid: int,
) -> Path:
    root = _validate_owned_input_root(
        stage_c5_root,
        prefix="a-clockwork-plex-stage-c5-review.",
        invoking_uid=invoking_uid,
        label="Stage C5 evidence",
    )
    _validate_evidence_manifest(root, "Stage C5")
    results = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in results) != EXPECTED_STAGE_C5_CHECKS:
        raise SystemExit("Stage C5 evidence does not contain the exact ten checks.")
    if any(row.get("result") != "PASS" for row in results):
        raise SystemExit("Stage C5 evidence contains a non-PASS result.")

    _rows_equal(
        _read_tsv(root / "transaction-state-machine.tsv"),
        state_machine_rows(),
        "transaction state machine",
    )
    _rows_equal(_read_tsv(root / "lock-contract.tsv"), lock_rows(), "lock contract")
    _rows_equal(
        _read_tsv(root / "authoritative-snapshot-contract.tsv"),
        snapshot_rows(),
        "snapshot contract",
    )
    _rows_equal(
        _read_tsv(root / "command-contract.tsv"),
        command_rows(),
        "command contract",
    )
    _rows_equal(
        _read_tsv(root / "rollback-entrypoints.tsv"),
        rollback_rows(),
        "rollback ownership",
    )
    _rows_equal(
        _read_tsv(root / "activation-blockers.tsv"),
        blocker_rows(),
        "activation blockers",
    )

    report = (root / "report.txt").read_text(encoding="utf-8")
    for expected in (
        f"Stage C1 package: {package_root}",
        f"Stage C3 evidence: {stage_c3_root}",
        f"Stage C4 evidence: {stage_c4_root}",
        "Reviewed transaction states: 20",
        "Rollback ownership classes: 4",
        "Activation blockers: 9",
        "no production lock opened",
        "persistent Stage C activation remains blocked",
    ):
        if expected not in report:
            raise SystemExit(f"Stage C5 report contract is missing: {expected}")
    return root


def inspect_production_lock_boundary() -> tuple[str, str]:
    parent = PRODUCTION_LOCK.parent
    try:
        parent_info = parent.lstat()
    except FileNotFoundError as exc:
        raise SystemExit(f"Production lock parent is missing: {parent}") from exc
    if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
        raise SystemExit(f"Production lock parent is not a real directory: {parent}")
    if parent_info.st_uid != 0 or parent_info.st_gid != 0:
        raise SystemExit(f"Production lock parent is not root-owned: {parent}")
    try:
        lock_info = PRODUCTION_LOCK.lstat()
    except FileNotFoundError:
        return (_mode(parent), "absent")
    if stat.S_ISLNK(lock_info.st_mode):
        raise SystemExit(f"Production lock path is a symlink: {PRODUCTION_LOCK}")
    raise SystemExit(f"Production lock path unexpectedly already exists: {PRODUCTION_LOCK}")


def acquire_rehearsal_lock(snapshot_root: Path) -> RehearsalLock:
    control = snapshot_root / REHEARSAL_LOCK_RELATIVE.parent
    control.mkdir(mode=0o700, parents=False, exist_ok=False)
    lock_path = snapshot_root / REHEARSAL_LOCK_RELATIVE
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        inode = os.fstat(fd).st_ino
    except BaseException:
        os.close(fd)
        raise
    return RehearsalLock(path=lock_path, fd=fd, inode=inode)


def prove_lock_contention(lock: RehearsalLock) -> None:
    flags = os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    second_fd = os.open(lock.path, flags)
    try:
        try:
            fcntl.flock(second_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return
            raise
        else:
            fcntl.flock(second_fd, fcntl.LOCK_UN)
            raise SystemExit("Independent descriptor unexpectedly acquired the rehearsal lock.")
    finally:
        os.close(second_fd)


def append_result(results: Path, check: str, detail: str) -> None:
    with results.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def append_event(events: Path, order: int, event: str, detail: str) -> None:
    now = datetime.now().astimezone().isoformat(timespec="microseconds")
    with events.open("a", encoding="utf-8") as handle:
        handle.write(f"{order}\t{time.monotonic_ns()}\t{now}\t{event}\t{detail}\n")


def write_tree_fingerprint(root: Path, output: Path) -> None:
    rows = ["path\ttype\tmode\tsha256"]
    rows.extend("\t".join(row) for row in tree_fingerprint(root))
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_dac_owner_evidence(module_state: Path, output: Path) -> None:
    rows = _read_tsv(module_state)
    selected = [row for row in rows if row.get("item", "").startswith("dac.owner")]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("item", "value"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(selected)


def write_lock_state(
    output: Path,
    *,
    parent_mode: str,
    lock: RehearsalLock,
    acquired_monotonic_ns: int,
    released_monotonic_ns: int | None,
) -> None:
    rows = [
        ("production.lock_path", str(PRODUCTION_LOCK)),
        ("production.lock_state", "absent"),
        ("production.lock_parent_mode", parent_mode),
        ("production.lock_opened", "false"),
        ("rehearsal.lock_path", str(lock.path)),
        ("rehearsal.lock_mode", _mode(lock.path)),
        ("rehearsal.lock_inode", str(lock.inode)),
        ("rehearsal.lock_acquired", "true"),
        ("rehearsal.lock_acquired_monotonic_ns", str(acquired_monotonic_ns)),
        ("rehearsal.lock_released", str(lock.released).lower()),
        (
            "rehearsal.lock_released_monotonic_ns",
            str(released_monotonic_ns) if released_monotonic_ns is not None else "-",
        ),
    ]
    output.write_text(
        "item\tvalue\n" + "".join(f"{item}\t{value}\n" for item, value in rows),
        encoding="utf-8",
    )


def write_identity(output: Path, invoking_user: str) -> str:
    identity = f"stage-c6-{secrets.token_hex(12)}"
    rows = (
        ("identity", identity),
        ("host", platform.node()),
        ("architecture", platform.machine()),
        ("invoking_user", invoking_user),
        ("root_pid", str(os.getpid())),
        ("generated", datetime.now().astimezone().isoformat(timespec="microseconds")),
        ("caller_supplied", "false"),
        ("activation_authoritative", "false"),
    )
    output.write_text(
        "item\tvalue\n" + "".join(f"{item}\t{value}\n" for item, value in rows),
        encoding="utf-8",
    )
    return identity


def write_report(
    output: Path,
    *,
    package_root: Path,
    stage_c3_root: Path,
    stage_c4_root: Path,
    stage_c5_root: Path,
    snapshot_root: Path,
    identity: str,
    invoking_user: str,
    summary,
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C6 locked privileged snapshot rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Snapshot version: {SNAPSHOT_VERSION}
Host: {platform.node()}
Architecture: {platform.machine()}
Invoking user: {invoking_user}
Stage C1 package: {package_root}
Stage C3 evidence: {stage_c3_root}
Stage C4 evidence: {stage_c4_root}
Stage C5 evidence: {stage_c5_root}
Stage C6 snapshot: {snapshot_root}
Rehearsal identity: {identity}
Future production lock: {PRODUCTION_LOCK}
Production lock state: absent and never opened
Rehearsal lock: {snapshot_root / REHEARSAL_LOCK_RELATIVE}
Verified pre-Stage-C ALSA SHA-256: {EXPECTED_PRE_STAGE_C_ALSA_SHA256}
Managed package files: {EXPECTED_PACKAGE_FILES}
Verified absent managed files: {summary.managed_absent}
Existing managed files: {summary.managed_present}
Managed destination conflicts: {summary.conflicts}

Proved by Stage C6:
- exact Stage C1, Stage C3, Stage C4 and Stage C5 evidence replay
- live pre-Stage-C route and physical host boundary remained exact
- future production lock path was absent and not opened
- exclusive non-blocking rehearsal flock acquired before identity and snapshot
- independent descriptor contention was proved
- fresh rehearsal identity was generated only after lock acquisition
- root-owned filesystem, service, mixer, loopback and DAC snapshot completed while locked
- all input trees remained unchanged
- the rehearsal lock was released after snapshot verification and manifest generation

Safety state:
- one sudo command launched this constrained root-owned engine
- root wrote only inside the Stage C6 evidence directory
- no production path was written
- no production lock or transaction directory was created
- no route or candidate file was installed
- no service was started, stopped, restarted, enabled or disabled
- no systemd daemon-reload was run
- no module was loaded or unloaded
- no PCM or device node was opened
- no mixer value was changed
- no CamillaDSP process was started, stopped or signalled
- no approval marker was created or consumed
- no install, activation, failback, rollback or uninstall action exists
- this rehearsal must never be reused as an activation-authoritative snapshot
- persistent Stage C activation remains blocked
""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            f"Read-only privileged rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )
    for command in ("systemctl", "amixer", "fuser"):
        if shutil.which(command) is None:
            raise SystemExit(f"Required read-only inspection command not found: {command}")

    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = _validate_owned_input_root(
        args.package_root,
        prefix="a-clockwork-plex-stage-c1-review-",
        invoking_uid=invoking_uid,
        label="Stage C1 package",
    )
    stage_c3_root = _validate_owned_input_root(
        args.stage_c3_root,
        prefix="a-clockwork-plex-stage-c3-snapshot.",
        invoking_uid=invoking_uid,
        label="Stage C3 evidence",
    )
    stage_c4_root = validate_stage_c4(args.stage_c4_root, invoking_uid)
    stage_c5_root = validate_stage_c5(
        args.stage_c5_root,
        package_root=package_root,
        stage_c3_root=stage_c3_root,
        stage_c4_root=stage_c4_root,
        invoking_uid=invoking_uid,
    )
    snapshot_root = validate_snapshot_root(args.snapshot_root, invoking_uid)

    input_fingerprints = {
        "stage-c1": tree_fingerprint(package_root),
        "stage-c3": tree_fingerprint(stage_c3_root),
        "stage-c4": tree_fingerprint(stage_c4_root),
        "stage-c5": tree_fingerprint(stage_c5_root),
    }

    entries, _stage_c3 = validate_inputs(package_root, stage_c3_root)
    validate_stage_c1_evidence(package_root)
    validate_current_host_as_root()
    validate_physical_capture_boundary()
    parent_mode, production_state = inspect_production_lock_boundary()
    if production_state != "absent":
        raise SystemExit("Unexpected production lock boundary.")

    os.chown(snapshot_root, 0, 0)
    snapshot_root.chmod(0o700)
    lock: RehearsalLock | None = None
    completed = False
    released_monotonic_ns: int | None = None
    event_order = 0

    try:
        results = snapshot_root / "results.tsv"
        results.write_text("check\tresult\tdetail\n", encoding="utf-8")
        events = snapshot_root / "ordered-events.tsv"
        events.write_text(
            "order\tmonotonic_ns\twall_time\tevent\tdetail\n",
            encoding="utf-8",
        )

        def event(name: str, detail: str) -> None:
            nonlocal event_order
            event_order += 10
            append_event(events, event_order, name, detail)

        append_result(results, "root-scope", f"root writes constrained to {snapshot_root}")
        append_result(results, "input-replay", "Stage C1, C3, C4 and C5 contracts replayed")
        append_result(
            results,
            "current-host-boundary",
            "pre-Stage-C route, loopback, DAC and process boundary remain exact",
        )
        event(
            "production-lock-boundary",
            f"{PRODUCTION_LOCK} absent; parent mode {parent_mode}; path not opened",
        )
        append_result(
            results,
            "production-lock-boundary",
            f"{PRODUCTION_LOCK} absent and not opened; parent mode {parent_mode}",
        )

        lock = acquire_rehearsal_lock(snapshot_root)
        acquired_monotonic_ns = time.monotonic_ns()
        event("rehearsal-lock-acquired", f"inode={lock.inode} path={lock.path}")
        append_result(
            results,
            "rehearsal-lock-acquired",
            "exclusive non-blocking flock held inside Stage C6 evidence",
        )

        prove_lock_contention(lock)
        event("lock-contention-proved", "second independent descriptor failed closed")
        append_result(
            results,
            "lock-contention",
            "second independent descriptor could not acquire the held lock",
        )

        identity = write_identity(snapshot_root / "identity.tsv", invoking_user)
        event("fresh-identity-created", identity)
        append_result(
            results,
            "fresh-identity",
            "new non-caller-supplied rehearsal identity created after lock acquisition",
        )

        write_lock_state(
            snapshot_root / "lock-state.tsv",
            parent_mode=parent_mode,
            lock=lock,
            acquired_monotonic_ns=acquired_monotonic_ns,
            released_monotonic_ns=None,
        )

        event("snapshot-started", "root-owned live snapshot began while rehearsal lock held")
        summary = collect_filesystem_snapshot(entries, Path("/"), snapshot_root)
        if (
            summary.conflicts
            or summary.managed_present
            or summary.managed_absent != EXPECTED_PACKAGE_FILES
        ):
            raise SystemExit(
                "Privileged destination boundary failed: "
                f"absent={summary.managed_absent} present={summary.managed_present} "
                f"conflicts={summary.conflicts}"
            )
        append_result(
            results,
            "privileged-destination-resolution",
            f"all {EXPECTED_PACKAGE_FILES} managed file destinations absent; zero conflicts",
        )
        append_result(
            results,
            "filesystem-snapshot",
            "current ALSA copied and exact managed absence markers recorded",
        )

        states = capture_service_states(snapshot_root / "service-state.tsv")
        validate_service_boundary(states)
        append_result(
            results,
            "service-state-boundary",
            "application services active/enabled; Stage C services absent",
        )

        capture_mixer_states(
            snapshot_root / "mixer-state.tsv",
            snapshot_root / "mixer-raw",
        )
        append_result(
            results,
            "mixer-state-capture",
            "four live ALSA control percentages captured read-only",
        )

        module_state = snapshot_root / "module-dac-state.tsv"
        capture_module_and_dac(module_state, snapshot_root)
        write_dac_owner_evidence(module_state, snapshot_root / "dac-owners.tsv")
        append_result(
            results,
            "module-dac-capture",
            "loopback parameters, structured DAC owner and hw_params captured",
        )

        write_package_fingerprint(package_root, snapshot_root / "package-fingerprint.tsv")
        write_tree_fingerprint(stage_c5_root, snapshot_root / "stage-c5-fingerprint.tsv")
        write_rollback_ledger(entries, snapshot_root / "rollback-ledger.tsv", snapshot_root)
        append_result(
            results,
            "rollback-ledger",
            "fresh rehearsal obligations generated; future activation snapshot still required",
        )

        for label, root in (
            ("stage-c1", package_root),
            ("stage-c3", stage_c3_root),
            ("stage-c4", stage_c4_root),
            ("stage-c5", stage_c5_root),
        ):
            if tree_fingerprint(root) != input_fingerprints[label]:
                raise SystemExit(f"{label} input changed during Stage C6 capture.")
        append_result(
            results,
            "input-integrity",
            "Stage C1, C3, C4 and C5 input trees remained unchanged",
        )

        event("snapshot-verified", "live snapshot and all immutable inputs verified")
        write_report(
            snapshot_root / "report.txt",
            package_root=package_root,
            stage_c3_root=stage_c3_root,
            stage_c4_root=stage_c4_root,
            stage_c5_root=stage_c5_root,
            snapshot_root=snapshot_root,
            identity=identity,
            invoking_user=invoking_user,
            summary=summary,
        )
        write_evidence_manifest(snapshot_root)
        event("manifest-generated", "complete checksummed evidence manifest generated while locked")
        append_result(
            results,
            "snapshot-integrity",
            "evidence inventory generated with no symlink or special object",
        )
        write_evidence_manifest(snapshot_root)

        lock.release()
        released_monotonic_ns = time.monotonic_ns()
        event("rehearsal-lock-released", "exclusive rehearsal flock released after manifest")
        write_lock_state(
            snapshot_root / "lock-state.tsv",
            parent_mode=parent_mode,
            lock=lock,
            acquired_monotonic_ns=acquired_monotonic_ns,
            released_monotonic_ns=released_monotonic_ns,
        )
        append_result(
            results,
            "rehearsal-lock-released",
            "lock released only after snapshot verification and manifest generation",
        )
        append_result(
            results,
            "activation-interface",
            "absent; no production lock, install, activation, failback, rollback or uninstall action",
        )
        write_evidence_manifest(snapshot_root)
        completed = True
    finally:
        if lock is not None and not lock.released:
            lock.release()
        chown_evidence_tree(snapshot_root, invoking_uid, invoking_gid)
        snapshot_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C6 locked snapshot did not complete.")

    print(
        f"""
A Clockwork Plex Stage C6 locked privileged snapshot rehearsal passed.

  Directory:          {snapshot_root}
  Results:            {snapshot_root / 'results.tsv'}
  Ordered events:     {snapshot_root / 'ordered-events.tsv'}
  Lock state:         {snapshot_root / 'lock-state.tsv'}
  Identity:           {snapshot_root / 'identity.tsv'}
  Filesystem state:   {snapshot_root / 'filesystem-state.tsv'}
  Service state:      {snapshot_root / 'service-state.tsv'}
  Mixer state:        {snapshot_root / 'mixer-state.tsv'}
  Module/DAC state:   {snapshot_root / 'module-dac-state.tsv'}
  Rollback ledger:    {snapshot_root / 'rollback-ledger.tsv'}
  Evidence manifest:  {snapshot_root / 'evidence-manifest.tsv'}
  Report:             {snapshot_root / 'report.txt'}

No production path was written or changed. The real route lock was not opened.
This rehearsal must never be reused as an activation-authoritative snapshot.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
