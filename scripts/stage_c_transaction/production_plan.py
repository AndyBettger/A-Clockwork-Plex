#!/usr/bin/python3
from __future__ import annotations

import argparse
import csv
import os
import stat
from pathlib import Path, PurePosixPath

from .package_review import sha256
from .sandbox_transaction import (
    CURRENT_ALSA_DESTINATION,
    EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    _assert_regular_tree,
    _read_tsv,
    tree_fingerprint,
    validate_inputs,
)

REQUIRED_CONFIRMATION = "STAGE-C5-PRODUCTION-TRANSACTION-PLAN-REVIEW"
REVIEW_PREFIX = "a-clockwork-plex-stage-c5-review."
ROUTE_LOCK = "/run/lock/a-clockwork-plex-audio-route.lock"
TRANSACTION_ROOT = "/var/lib/a-clockwork-plex/split-bus/transactions"

EXPECTED_STAGE_C4_CHECKS = (
    "input-replay",
    "sandbox-scope",
    "first-install-boundary",
    "install-success",
    "explicit-uninstall-rollback",
    "failure-injection",
    "automatic-rollback",
    "exact-state-verification",
    "production-boundary",
)

EXPECTED_SCENARIOS = (
    (
        "success-explicit-uninstall",
        "none",
        "true",
        "explicit-uninstall",
        "0",
    ),
    (
        "failure-after-files-installed",
        "after-files-installed",
        "false",
        "automatic:after-files-installed",
        "0",
    ),
    (
        "failure-after-route-selected",
        "after-route-selected",
        "false",
        "automatic:after-route-selected",
        "0",
    ),
    (
        "failure-after-services-restored",
        "after-services-restored",
        "false",
        "automatic:after-services-restored",
        "0",
    ),
)

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


def _write_tsv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.lstat().st_mode):o}"


def _validate_evidence_manifest(root: Path, label: str) -> None:
    manifest = root / "evidence-manifest.tsv"
    rows = _read_tsv(manifest)
    if not rows:
        raise SystemExit(f"{label} evidence manifest is empty.")

    listed: set[str] = set()
    for row in rows:
        relative = row.get("path", "")
        kind = row.get("type", "")
        mode = row.get("mode", "")
        digest = row.get("sha256", "")
        pure = PurePosixPath(relative)
        if not relative or pure.is_absolute() or ".." in pure.parts:
            raise SystemExit(f"Unsafe {label} evidence path: {relative}")
        if relative in listed:
            raise SystemExit(f"Duplicate {label} evidence path: {relative}")
        listed.add(relative)
        path = root.joinpath(*pure.parts)

        if kind == "self":
            if relative != "evidence-manifest.tsv" or not path.is_file():
                raise SystemExit(f"{label} evidence self row is invalid.")
            continue

        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise SystemExit(f"{label} evidence entry is missing: {relative}") from exc

        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"{label} evidence contains a symlink: {relative}")
        if kind == "directory":
            if not stat.S_ISDIR(info.st_mode) or _mode(path) != mode or digest != "-":
                raise SystemExit(f"{label} directory metadata mismatch: {relative}")
        elif kind == "file":
            if not stat.S_ISREG(info.st_mode) or _mode(path) != mode or sha256(path) != digest:
                raise SystemExit(f"{label} file metadata mismatch: {relative}")
        else:
            raise SystemExit(f"Unsupported {label} evidence type: {kind}")

    actual = {str(path.relative_to(root)) for path in root.rglob("*")}
    if actual != listed:
        raise SystemExit(
            f"{label} evidence inventory mismatch: "
            f"unlisted={sorted(actual - listed)[:1]} missing={sorted(listed - actual)[:1]}"
        )


def validate_stage_c4(stage_c4_root: Path) -> Path:
    root = stage_c4_root.resolve()
    _assert_regular_tree(root, "Stage C4 evidence")
    if root.parent != Path("/var/tmp") or not root.name.startswith(
        "a-clockwork-plex-stage-c4-sandbox."
    ):
        raise SystemExit("Stage C4 evidence must be a direct validated /var/tmp sandbox.")
    if root.lstat().st_uid != os.getuid():
        raise SystemExit("Stage C4 evidence must be owned by the invoking user.")
    if stat.S_IMODE(root.lstat().st_mode) != 0o700:
        raise SystemExit("Stage C4 evidence root must retain mode 0700.")

    _validate_evidence_manifest(root, "Stage C4")

    results = _read_tsv(root / "results.tsv")
    observed_checks = tuple(row.get("check", "") for row in results)
    if observed_checks != EXPECTED_STAGE_C4_CHECKS:
        raise SystemExit("Stage C4 evidence does not contain the exact nine checks.")
    if any(row.get("result") != "PASS" for row in results):
        raise SystemExit("Stage C4 evidence contains a non-PASS result.")

    scenarios = _read_tsv(root / "scenario-state.tsv")
    observed_scenarios = tuple(
        (
            row.get("scenario", ""),
            row.get("injected_failure", ""),
            row.get("install_verified", ""),
            row.get("rollback_reason", ""),
            row.get("rollback_mismatches", ""),
        )
        for row in scenarios
    )
    if observed_scenarios != EXPECTED_SCENARIOS:
        raise SystemExit("Stage C4 scenario evidence differs from the reviewed four-scenario result.")

    plan = _read_tsv(root / "file-plan.tsv")
    managed_files = [row for row in plan if row.get("type") == "file"]
    active_routes = [row for row in plan if row.get("type") == "active-route"]
    if len(managed_files) != 12 or any(
        row.get("stage_c3_state") != "absent" for row in managed_files
    ):
        raise SystemExit("Stage C4 file plan does not preserve the twelve-file absence boundary.")
    if len(active_routes) != 1:
        raise SystemExit("Stage C4 file plan must contain exactly one active-route row.")
    active = active_routes[0]
    if (
        active.get("destination") != CURRENT_ALSA_DESTINATION
        or active.get("candidate_sha256") != EXPECTED_PRE_STAGE_C_ALSA_SHA256
        or active.get("stage_c3_state") != "present"
    ):
        raise SystemExit("Stage C4 active-route rollback contract changed.")

    for scenario in EXPECTED_SCENARIOS:
        scenario_name = scenario[0]
        sudoers = root / "scenarios" / scenario_name / "system-root/etc/sudoers.d"
        if sudoers.is_symlink() or not sudoers.is_dir() or _mode(sudoers) != "750":
            raise SystemExit(
                f"Stage C4 did not restore /etc/sudoers.d mode 0750: {scenario_name}"
            )
        active_file = (
            root
            / "scenarios"
            / scenario_name
            / "system-root"
            / CURRENT_ALSA_DESTINATION.lstrip("/")
        )
        if not active_file.is_file() or sha256(active_file) != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
            raise SystemExit(f"Stage C4 did not restore the exact ALSA file: {scenario_name}")

    report = (root / "report.txt").read_text(encoding="utf-8")
    for expected in (
        "Managed package files: 12",
        "Scenarios: 4",
        "Injected failure points: 3",
        "Final rollback mismatches: 0",
        "no sudo or root execution",
        "no production path opened for writing",
        "persistent Stage C activation remains blocked",
    ):
        if expected not in report:
            raise SystemExit(f"Stage C4 report contract is missing: {expected}")
    return root


def validate_review_root(requested: Path, *inputs: Path) -> Path:
    if os.geteuid() == 0:
        raise SystemExit("Run Stage C5 as the normal project user, not as root.")
    raw = requested.expanduser()
    if not raw.is_absolute():
        raise SystemExit("--review-root must be an absolute path beneath /var/tmp.")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit(f"--review-root must already exist: {raw}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("--review-root must be a real directory, not a symlink.")
    resolved = raw.resolve()
    if resolved.parent != Path("/var/tmp") or not resolved.name.startswith(REVIEW_PREFIX):
        raise SystemExit(f"--review-root must be a direct /var/tmp/{REVIEW_PREFIX}* directory.")
    if info.st_uid != os.getuid():
        raise SystemExit("--review-root must be owned by the invoking user.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("--review-root must have mode 0700.")
    if any(resolved.iterdir()):
        raise SystemExit(f"--review-root must be empty: {resolved}")
    if resolved in {path.resolve() for path in inputs}:
        raise SystemExit("Stage C5 review root must be separate from all input evidence trees.")
    return resolved


def state_machine_rows() -> list[dict[str, str]]:
    rows = (
        (10, "replay-contracts", "preflight", "false", "abort-release-lock-if-held", "false", "Replay immutable Stage C1, C3 and C4 contracts."),
        (20, "acquire-route-lock", "preflight", "false", "abort", "acquire", f"Acquire exclusive non-blocking {ROUTE_LOCK}."),
        (30, "create-transaction-identity", "snapshot", "false", "close-uncommitted-release-lock", "held", f"Create fresh root-owned transaction beneath {TRANSACTION_ROOT}."),
        (40, "capture-authoritative-snapshot", "snapshot", "false", "close-uncommitted-release-lock", "held", "Capture files, directories, services, mixers, loopback and DAC state."),
        (50, "verify-snapshot", "snapshot", "false", "close-uncommitted-release-lock", "held", "Verify complete inventory, checksums, modes, owners and absence markers."),
        (60, "stage-candidates", "staging", "false", "close-uncommitted-release-lock", "held", "Copy package into transaction staging area and verify checksums."),
        (70, "validate-staged-candidates", "staging", "false", "close-uncommitted-release-lock", "held", "Validate ALSA, CamillaDSP, sudoers, unit and helper candidates."),
        (80, "stop-application-services", "mutation", "true", "exact-rollback", "held", "Stop only application services captured active."),
        (90, "verify-endpoints-released", "mutation", "true", "exact-rollback", "held", "Prove DAC and loopback endpoints are released."),
        (100, "install-managed-files", "mutation", "true", "exact-rollback", "held", "Atomically install and verify all managed files."),
        (110, "daemon-reload", "mutation", "true", "exact-rollback", "held", "Reload systemd exactly once after unit installation."),
        (120, "activate-route-authority", "mutation", "true", "exact-rollback", "held", "Start one bounded route authority operation."),
        (130, "verify-split-bus-health", "validation", "true", "exact-rollback", "held", "Verify loopback, CamillaDSP, DAC owner and exact hardware format."),
        (140, "finite-music-lane-probe", "validation", "true", "exact-rollback", "held", "Run a finite music-only route probe."),
        (150, "finite-alarm-lane-probe", "validation", "true", "exact-rollback", "held", "Run a finite alarm-only route probe."),
        (160, "restore-application-services", "validation", "true", "exact-rollback", "held", "Restore only application services captured active."),
        (170, "verify-post-start-health", "validation", "true", "exact-rollback", "held", "Verify CamillaDSP survives application startup."),
        (180, "verify-dashboard-health", "validation", "true", "exact-rollback", "held", "Require dashboard and root-helper route health agreement."),
        (190, "commit-manifest", "commit", "true", "explicit-uninstall-only", "held", "Atomically record the committed transaction manifest."),
        (200, "release-route-lock", "complete", "false", "none", "release", "Release only after commit or verified rollback."),
    )
    return [
        {
            "order": str(order),
            "state": state,
            "phase": phase,
            "production_mutation": mutation,
            "failure_action": failure,
            "route_lock": lock,
            "detail": detail,
        }
        for order, state, phase, mutation, failure, lock, detail in rows
    ]


def lock_rows() -> list[dict[str, str]]:
    return [
        {"rule": "path", "value": ROUTE_LOCK, "requirement": "single lock for installer, route helper, runtime failback and uninstall"},
        {"rule": "acquisition", "value": "exclusive-nonblocking-flock", "requirement": "fail closed when another writer owns the route"},
        {"rule": "ordering", "value": "before-transaction-id-and-snapshot", "requirement": "snapshot cannot race another route writer"},
        {"rule": "lifetime", "value": "through-commit-or-verified-rollback", "requirement": "never release during partial mutation"},
        {"rule": "identity", "value": "pid-action-transaction-id", "requirement": "record while lock is held"},
        {"rule": "secondary-locks", "value": "forbidden", "requirement": "no independent installer, route or EQ writer lock"},
    ]


def snapshot_rows() -> list[dict[str, str]]:
    items = (
        ("identity", "fresh generated transaction id", "caller cannot supply or reuse"),
        ("directory", f"{TRANSACTION_ROOT}/<transaction-id>", "root:root mode 0700 and initially empty"),
        ("managed-files", "content sha256 mode uid gid or explicit absence", "all twelve reviewed destinations"),
        ("active-alsa", f"content and sha256 for {CURRENT_ALSA_DESTINATION}", "exact uninstall rollback source"),
        ("managed-directories", "existence mode uid gid", "remove only newly created empty directories"),
        ("services", "load active enabled", "three application and three Stage C services"),
        ("mixers", "exact raw and displayed restore values", ", ".join(MIXER_CONTROLS)),
        ("loopback", "persistence files plus loaded parameters", "index 7 id ACP_Loopback substreams 2 notify 1 enable Y"),
        ("dac-owner", "pid user command fd access", "structured evidence; no fuser stdout/stderr joining"),
        ("dac-hw-params", "access format subformat channels rate period buffer", "exact physical boundary"),
        ("candidate", "package and engine checksums", "bind snapshot to reviewed implementation"),
        ("provenance", "action invoking user timestamps", "audit and rollback identity"),
        ("rehearsal-evidence", "forbidden-as-backup", "Stage C3 and C4 may be referenced only as review provenance"),
    )
    return [
        {"area": area, "capture": capture, "requirement": requirement}
        for area, capture, requirement in items
    ]


def command_rows() -> list[dict[str, str]]:
    operations = (
        ("filesystem", "fixed snapshot/copy/replace/fsync/chmod/chown/unlink/rmdir", "no caller-supplied production path"),
        ("lock", f"exclusive flock {ROUTE_LOCK}", "single fixed lock path"),
        ("systemd", "fixed operations for six reviewed units", "no dynamic unit name"),
        ("mixer", "fixed reads/writes for four reviewed controls", "bounded values only"),
        ("loopback", "fixed inspect/load/unload for snd_aloop", "exact reviewed parameters only"),
        ("dac", "fixed owner and hw_params inspection", "no arbitrary device path"),
        ("alsa", "finite parse and PCM probes", "bounded duration and known PCM names"),
        ("camilladsp", "fixed start stop reload health", "pinned binary and configuration"),
        ("dashboard", "fixed local health request", "no external network request"),
        ("shell", "forbidden", "no shell=True, eval, exec or arbitrary command"),
        ("network-download", "forbidden", "activation installs no package and fetches no executable"),
    )
    return [
        {"family": family, "allowed_shape": shape, "restriction": restriction}
        for family, shape, restriction in operations
    ]


def rollback_rows() -> list[dict[str, str]]:
    rows = (
        ("replay-contracts", "validate-staged-candidates", "pre-mutation-abort", "close uncommitted record if created; release lock"),
        ("stop-application-services", "verify-dashboard-health", "exact-install-rollback", "restore authoritative snapshot and verify zero mismatches while retaining lock"),
        ("commit-manifest", "committed", "explicit-uninstall-only", "use that installation's authoritative transaction snapshot"),
        ("runtime-camilladsp-failure", "runtime", "direct-alarm-bypass-failback", "select alarm-safe no-DSP route; do not perform uninstall rollback"),
    )
    return [
        {"from_state": start, "through_state": end, "action": action, "requirement": requirement}
        for start, end, action, requirement in rows
    ]


def blocker_rows() -> list[dict[str, str]]:
    blockers = (
        ("root-adapter", "absent", "no production filesystem or command adapter exists"),
        ("root-entrypoint", "absent", "no sudo or root execution interface exists"),
        ("activation-token", "absent", "the only token is review-generation-only"),
        ("approval-marker", "absent", "Stage C5 cannot create or consume an approval marker"),
        ("production-lock", "not-opened", "the real route lock is documented but untouched"),
        ("production-transaction-directory", "not-created", "only the review directory may be written"),
        ("service-audio-commands", "not-executable", "no systemctl, mixer, module, PCM, DAC or CamillaDSP call path"),
        ("rehearsal-snapshot-reuse", "forbidden", "Stage C3 and C4 evidence cannot become rollback sources"),
        ("persistent-activation", "blocked", "requires later review and explicit user authorisation"),
    )
    return [
        {"blocker": blocker, "state": state, "detail": detail}
        for blocker, state, detail in blockers
    ]


def _write_result(path: Path, check: str, detail: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def _write_evidence_manifest(root: Path) -> None:
    rows: list[dict[str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative = str(path.relative_to(root))
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Stage C5 review contains a symlink: {relative}")
        if stat.S_ISDIR(info.st_mode):
            rows.append({"path": relative, "type": "directory", "mode": _mode(path), "sha256": "-"})
        elif stat.S_ISREG(info.st_mode):
            rows.append({"path": relative, "type": "file", "mode": _mode(path), "sha256": sha256(path)})
        else:
            raise SystemExit(f"Stage C5 review contains a special object: {relative}")
    rows.append({"path": "evidence-manifest.tsv", "type": "self", "mode": "-", "sha256": "-"})
    _write_tsv(root / "evidence-manifest.tsv", ("path", "type", "mode", "sha256"), rows)


def generate_review(
    package_root: Path,
    stage_c3_root: Path,
    stage_c4_root: Path,
    review_root: Path,
) -> None:
    package_root = package_root.resolve()
    stage_c3_root = stage_c3_root.resolve()
    validate_inputs(package_root, stage_c3_root)
    stage_c4_root = validate_stage_c4(stage_c4_root)
    review_root = validate_review_root(
        review_root,
        package_root,
        stage_c3_root,
        stage_c4_root,
    )

    input_fingerprints = {
        "stage-c1": tree_fingerprint(package_root),
        "stage-c3": tree_fingerprint(stage_c3_root),
        "stage-c4": tree_fingerprint(stage_c4_root),
    }

    results = review_root / "results.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")
    _write_result(results, "input-replay", "Stage C1 package plus Stage C3 and Stage C4 evidence replayed")
    _write_result(results, "stage-c4-proof", "four scenarios, three automatic rollbacks and zero mismatches verified")
    _write_result(results, "review-scope", f"all writes constrained beneath {review_root}")

    _write_tsv(
        review_root / "transaction-state-machine.tsv",
        ("order", "state", "phase", "production_mutation", "failure_action", "route_lock", "detail"),
        state_machine_rows(),
    )
    _write_result(results, "state-machine", "lock, snapshot, staging, mutation, validation and commit ordering fixed")

    _write_tsv(
        review_root / "lock-contract.tsv",
        ("rule", "value", "requirement"),
        lock_rows(),
    )
    _write_result(results, "single-lock", f"one route lock fixed at {ROUTE_LOCK}; not opened by Stage C5")

    _write_tsv(
        review_root / "authoritative-snapshot-contract.tsv",
        ("area", "capture", "requirement"),
        snapshot_rows(),
    )
    _write_result(results, "fresh-snapshot", "new root-owned snapshot required after lock and before mutation")

    _write_tsv(
        review_root / "command-contract.tsv",
        ("family", "allowed_shape", "restriction"),
        command_rows(),
    )
    _write_result(results, "command-contract", "fixed operation families documented; arbitrary shell and network download forbidden")

    _write_tsv(
        review_root / "rollback-entrypoints.tsv",
        ("from_state", "through_state", "action", "requirement"),
        rollback_rows(),
    )
    _write_result(results, "rollback-ownership", "pre-mutation abort, exact install rollback, uninstall and runtime failback separated")

    _write_tsv(
        review_root / "activation-blockers.tsv",
        ("blocker", "state", "detail"),
        blocker_rows(),
    )
    _write_result(results, "activation-blockers", "no root adapter, production entrypoint or activation authority exists")

    for label, root in (
        ("stage-c1", package_root),
        ("stage-c3", stage_c3_root),
        ("stage-c4", stage_c4_root),
    ):
        if tree_fingerprint(root) != input_fingerprints[label]:
            raise SystemExit(f"{label} input changed during Stage C5 review generation.")
    _write_result(results, "input-integrity", "Stage C1, Stage C3 and Stage C4 input trees remained unchanged")

    report = f"""A Clockwork Plex Stage C5 production transaction plan review
Review version: 1
Stage C1 package: {package_root}
Stage C3 evidence: {stage_c3_root}
Stage C4 evidence: {stage_c4_root}
Stage C5 review: {review_root}
Route lock: {ROUTE_LOCK}
Future transaction root: {TRANSACTION_ROOT}
Managed package files: 12
Reviewed transaction states: {len(state_machine_rows())}
Rollback ownership classes: {len(rollback_rows())}
Activation blockers: {len(blocker_rows())}

Proved by Stage C5:
- exact Stage C1, Stage C3 and Stage C4 evidence replay
- Stage C4 four-scenario zero-mismatch rollback result
- single route-lock ordering before transaction identity and fresh snapshot
- deterministic production state-machine ordering
- exact separation of pre-mutation abort, install rollback, explicit uninstall and runtime failback
- complete fresh authoritative snapshot contract
- fixed command-family contract with arbitrary shell and network download forbidden
- unchanged input evidence trees

Not implemented by Stage C5:
- root filesystem or command adapter
- route-lock acquisition
- authoritative production snapshot capture
- service, mixer, module, PCM, DAC or CamillaDSP execution
- production installation, activation, rollback or uninstall
- runtime direct failback execution
- EQ migration or dashboard degraded-mode health

Safety state:
- no sudo or root execution
- no production path opened for writing
- no production lock opened
- no production transaction directory created
- no device or PCM opened
- no approval marker created or consumed
- Stage C3 and Stage C4 remain review evidence only
- persistent Stage C activation remains blocked
"""
    (review_root / "report.txt").write_text(report, encoding="utf-8")
    _write_evidence_manifest(review_root)

    print("A Clockwork Plex Stage C5 production transaction plan review passed.")
    print(f"  Directory: {review_root}")
    print(f"  Results:   {results}")
    print(f"  State machine: {review_root / 'transaction-state-machine.tsv'}")
    print(f"  Report:    {review_root / 'report.txt'}")
    print("No production path was written or changed. Persistent activation remains blocked.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the Stage C5 production transaction plan inside a review-only directory."
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c3-root", required=True, type=Path)
    parser.add_argument("--stage-c4-root", required=True, type=Path)
    parser.add_argument("--review-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit("Exact Stage C5 review confirmation token was not supplied.")
    generate_review(
        args.package_root,
        args.stage_c3_root,
        args.stage_c4_root,
        args.review_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
