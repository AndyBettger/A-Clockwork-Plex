#!/usr/bin/python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path, PurePosixPath

from . import sandbox_transaction as base
from .package_review import ManifestEntry

REQUIRED_CONFIRMATION = base.REQUIRED_CONFIRMATION
SANDBOX_PREFIX = base.SANDBOX_PREFIX
CURRENT_ALSA_DESTINATION = base.CURRENT_ALSA_DESTINATION
SPLIT_ROUTE_DESTINATION = base.SPLIT_ROUTE_DESTINATION
EXPECTED_PRE_STAGE_C_ALSA_SHA256 = base.EXPECTED_PRE_STAGE_C_ALSA_SHA256
EXPECTED_STAGE_C3_CHECKS = base.EXPECTED_STAGE_C3_CHECKS
APPLICATION_SERVICES = base.APPLICATION_SERVICES
STAGE_C_SERVICES = base.STAGE_C_SERVICES
MIXER_CONTROLS = base.MIXER_CONTROLS
FAILURE_POINTS = base.FAILURE_POINTS
InjectedFailure = base.InjectedFailure
StageC3Evidence = base.StageC3Evidence
ScenarioResult = base.ScenarioResult

_read_tsv = base._read_tsv
_write_tsv = base._write_tsv
_assert_regular_tree = base._assert_regular_tree
tree_fingerprint = base.tree_fingerprint
combined_scenario_fingerprint = base.combined_scenario_fingerprint
write_fingerprint = base.write_fingerprint
validate_inputs = base.validate_inputs
validate_sandbox_root = base.validate_sandbox_root
mapped_path = base.mapped_path
_atomic_copy = base._atomic_copy
_journal = base._journal
_set_application_active_state = base._set_application_active_state
verify_install = base.verify_install
apply_sandbox_install = base.apply_sandbox_install
result = base.result
write_file_plan = base.write_file_plan
write_evidence_manifest = base.write_evidence_manifest
parse_manifest = base.parse_manifest
sha256 = base.sha256


def _captured_present_directory_modes(
    entries: list[ManifestEntry], evidence: StageC3Evidence
) -> dict[str, int]:
    managed = {entry.destination for entry in entries if entry.kind == "directory"}
    captured: dict[str, int] = {}
    for row in evidence.filesystem_rows:
        destination = row.get("destination", "")
        if (
            row.get("kind") != "directory"
            or row.get("preinstall_state") != "present"
            or destination not in managed
        ):
            continue
        mode_text = row.get("mode", "")
        try:
            mode = int(mode_text, 8)
        except ValueError as exc:
            raise SystemExit(
                f"Invalid captured managed-directory mode: {destination} {mode_text}"
            ) from exc
        captured[destination] = mode
    return captured


def seed_scenario(
    scenario_root: Path,
    package_root: Path,
    stage_c3_root: Path,
    entries: list[ManifestEntry],
    evidence: StageC3Evidence,
) -> tuple[
    tuple[tuple[str, str, str, str], ...],
    set[str],
    dict[str, int],
]:
    baseline, absent_directories = base.seed_scenario(
        scenario_root, package_root, stage_c3_root, entries, evidence
    )
    present_directory_modes = _captured_present_directory_modes(entries, evidence)
    rows = ["destination\tmode"]
    rows.extend(
        f"{destination}\t{mode:o}"
        for destination, mode in sorted(present_directory_modes.items())
    )
    (scenario_root / "baseline/present-directory-modes.tsv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
    return baseline, absent_directories, present_directory_modes


def rollback_sandbox(
    scenario_root: Path,
    entries: list[ManifestEntry],
    absent_directories: set[str],
    present_directory_modes: dict[str, int],
    baseline: tuple[tuple[str, str, str, str], ...],
    reason: str,
) -> int:
    system_root = scenario_root / "system-root"
    state_root = scenario_root / "simulated-state"
    baseline_root = scenario_root / "baseline"
    journal = scenario_root / "journal.tsv"
    _journal(journal, "rollback-start", reason)

    for entry in reversed([item for item in entries if item.kind == "file"]):
        destination = mapped_path(system_root, entry.destination)
        if destination.is_symlink():
            raise SystemExit(f"Refusing symlink during sandbox rollback: {entry.destination}")
        if destination.exists():
            if not destination.is_file():
                raise SystemExit(
                    f"Sandbox rollback file has conflicting type: {entry.destination}"
                )
            destination.unlink()

    baseline_current = baseline_root / "rootfs" / CURRENT_ALSA_DESTINATION.lstrip("/")
    active_current = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    _atomic_copy(baseline_current, active_current, 0o644)

    shutil.rmtree(state_root)
    shutil.copytree(baseline_root / "simulated-state", state_root)
    committed = scenario_root / "transaction-committed.sandbox-only"
    if committed.exists() or committed.is_symlink():
        committed.unlink()

    for destination in sorted(
        absent_directories,
        key=lambda item: len(PurePosixPath(item).parts),
        reverse=True,
    ):
        path = mapped_path(system_root, destination)
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(
                f"Sandbox rollback directory has conflicting type: {destination}"
            )
        try:
            path.rmdir()
        except OSError as exc:
            raise SystemExit(
                f"Sandbox rollback would remove a non-empty directory: {destination}"
            ) from exc

    for destination, mode in sorted(
        present_directory_modes.items(),
        key=lambda item: len(PurePosixPath(item[0]).parts),
    ):
        path = mapped_path(system_root, destination)
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(
                f"Captured existing sandbox directory is missing or unsafe: {destination}"
            )
        path.chmod(mode)
    _journal(
        journal,
        "directory-modes",
        f"restored {len(present_directory_modes)} captured existing managed-directory modes",
    )

    observed = combined_scenario_fingerprint(scenario_root)
    mismatches = 0 if observed == baseline else 1
    write_fingerprint(scenario_root / "post-rollback-fingerprint.tsv", observed)
    _journal(journal, "rollback-finish", f"baseline mismatches={mismatches}")
    return mismatches


def run_scenario(
    sandbox_root: Path,
    name: str,
    fail_after: str | None,
    package_root: Path,
    stage_c3_root: Path,
    entries: list[ManifestEntry],
    evidence: StageC3Evidence,
) -> ScenarioResult:
    scenario_root = sandbox_root / "scenarios" / name
    scenario_root.mkdir(parents=True)
    baseline, absent_directories, present_directory_modes = seed_scenario(
        scenario_root, package_root, stage_c3_root, entries, evidence
    )
    install_verified = False
    rollback_reason = "explicit-uninstall"
    try:
        apply_sandbox_install(scenario_root, package_root, entries, fail_after)
        if fail_after is not None:
            raise SystemExit(f"Failure injection did not trigger: {fail_after}")
        install_verified = True
    except InjectedFailure as exc:
        if str(exc) != fail_after:
            raise
        rollback_reason = f"automatic:{fail_after}"
        _journal(scenario_root / "journal.tsv", "injected-failure", str(exc))

    mismatches = rollback_sandbox(
        scenario_root,
        entries,
        absent_directories,
        present_directory_modes,
        baseline,
        rollback_reason,
    )
    if mismatches:
        raise SystemExit(f"Sandbox rollback did not restore exact baseline: {name}")
    return ScenarioResult(
        name=name,
        injected_failure=fail_after or "none",
        install_verified=install_verified,
        rollback_reason=rollback_reason,
        rollback_mismatches=mismatches,
    )


def run_rehearsal(
    package_root: Path, stage_c3_root: Path, sandbox_root: Path
) -> list[ScenarioResult]:
    entries, evidence = validate_inputs(package_root, stage_c3_root)
    sandbox_root = validate_sandbox_root(sandbox_root, package_root, stage_c3_root)
    package_before = tree_fingerprint(package_root)
    stage_c3_before = tree_fingerprint(stage_c3_root)

    results = sandbox_root / "results.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")
    result(results, "input-replay", "Stage C1 package and complete Stage C3 evidence replayed")
    result(results, "sandbox-scope", f"all mutation paths constrained beneath {sandbox_root}")
    result(results, "first-install-boundary", "all twelve managed files begin absent in every scenario")
    write_file_plan(sandbox_root / "file-plan.tsv", entries, evidence)

    scenarios = [
        run_scenario(
            sandbox_root,
            "success-explicit-uninstall",
            None,
            package_root,
            stage_c3_root,
            entries,
            evidence,
        )
    ]
    result(results, "install-success", "twelve files and synthetic split route verified before uninstall")
    result(
        results,
        "explicit-uninstall-rollback",
        "successful sandbox install restored files, state and captured directory modes",
    )

    for failure in FAILURE_POINTS:
        scenarios.append(
            run_scenario(
                sandbox_root,
                f"failure-{failure}",
                failure,
                package_root,
                stage_c3_root,
                entries,
                evidence,
            )
        )
    result(results, "failure-injection", "three independent transaction failure points exercised")
    result(results, "automatic-rollback", "all injected failures invoked the exact rollback implementation")
    if any(item.rollback_mismatches for item in scenarios):
        raise SystemExit("One or more Stage C4 scenarios reported rollback mismatches.")
    result(results, "exact-state-verification", "all four scenarios ended with zero baseline mismatches")

    scenario_rows = [
        "scenario\tinjected_failure\tinstall_verified\trollback_reason\trollback_mismatches"
    ]
    scenario_rows.extend(
        f"{item.name}\t{item.injected_failure}\t{str(item.install_verified).lower()}\t"
        f"{item.rollback_reason}\t{item.rollback_mismatches}"
        for item in scenarios
    )
    (sandbox_root / "scenario-state.tsv").write_text(
        "\n".join(scenario_rows) + "\n", encoding="utf-8"
    )

    if tree_fingerprint(package_root) != package_before:
        raise SystemExit("Stage C1 package changed during sandbox rehearsal.")
    if tree_fingerprint(stage_c3_root) != stage_c3_before:
        raise SystemExit("Stage C3 evidence changed during sandbox rehearsal.")
    result(
        results,
        "production-boundary",
        "input trees unchanged; no production path or command was used",
    )

    report = f"""A Clockwork Plex Stage C4 sandbox transaction and exact-rollback rehearsal
Sandbox version: 2
Stage C1 package: {package_root.resolve()}
Stage C3 evidence: {stage_c3_root.resolve()}
Stage C4 sandbox: {sandbox_root}
Managed package files: 12
Scenarios: 4
Injected failure points: 3
Final rollback mismatches: 0

Proved in synthetic filesystems:
- exact Stage C1 and Stage C3 evidence replay
- first-install absence boundary for all twelve managed files
- atomic sandbox installation of all package files
- synthetic active ALSA selection from the installed split-bus route
- successful install verification followed by explicit exact uninstall
- automatic exact rollback after files installed, route selected and services restored
- restoration of captured modes for pre-existing managed directories
- unchanged Stage C1 package and Stage C3 evidence trees

Not proved by Stage C4:
- real ALSA parsing or PCM availability
- CamillaDSP startup, DSP health or DAC ownership
- real service-manager ordering or service behaviour
- real music/alarm lane probes
- runtime direct alarm-bypass failback
- EQ migration or dashboard health

Safety state:
- no sudo or root execution
- no production path opened for writing
- no service-manager, mixer, module, PCM-owner or CamillaDSP command execution
- no device or PCM opened
- no activation marker created
- no production activation/install/rollback/uninstall interface exists
- persistent Stage C activation remains blocked
"""
    (sandbox_root / "report.txt").write_text(report, encoding="utf-8")
    write_evidence_manifest(sandbox_root)
    print("A Clockwork Plex Stage C4 sandbox transaction rehearsal passed.")
    print(f"  Directory: {sandbox_root}")
    print(f"  Results:   {results}")
    print(f"  Scenarios: {sandbox_root / 'scenario-state.tsv'}")
    print(f"  Report:    {sandbox_root / 'report.txt'}")
    print("No production path was written or changed. Persistent activation remains blocked.")
    return scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Stage C4 transaction and rollback only inside a synthetic root."
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c3-root", required=True, type=Path)
    parser.add_argument("--sandbox-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit("Exact Stage C4 sandbox confirmation token was not supplied.")
    run_rehearsal(args.package_root, args.stage_c3_root, args.sandbox_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
