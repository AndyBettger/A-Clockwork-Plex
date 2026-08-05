#!/usr/bin/python3
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_SCRIPTS = SCRIPT_DIR.parent
if str(REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REPO_SCRIPTS))

from stage_c_transaction.host_review import (
    EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    capture_mixer_states,
    capture_module_and_dac,
    capture_service_states,
    create_review_root,
    snapshot_paths,
    validate_current_host,
    validate_service_boundary,
)
from stage_c_transaction.package_review import (
    EXPECTED_PACKAGE_FILES,
    parse_manifest,
    sha256,
    validate_stage_c1_evidence,
    write_destination_state,
)
from stage_c_transaction.plans import write_command_plans, write_rollback_obligations

PLANNER_VERSION = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay a validated Stage C1 package against the current host and prepare an "
            "installation/snapshot/rollback review. There is no activation mode."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path, help="Validated Stage C1 laboratory root")
    parser.add_argument("--transaction-root", type=Path, help="New or existing empty Stage C2 review directory")
    return parser.parse_args()


def append_result(results: Path, check: str, detail: str) -> None:
    with results.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def main() -> int:
    args = parse_args()
    for command in ("systemctl", "amixer", "fuser"):
        if shutil.which(command) is None:
            raise SystemExit(f"Required read-only inspection command not found: {command}")

    package_root = args.package_root.expanduser().resolve()
    entries = parse_manifest(package_root)
    validate_stage_c1_evidence(package_root)
    validate_current_host()

    review_root = create_review_root(args.transaction_root)
    results = review_root / "results.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")

    append_result(results, "stage-c1-package-evidence", "all Stage C1 checks replayed as PASS")
    append_result(
        results,
        "manifest-replay",
        f"{EXPECTED_PACKAGE_FILES} files and required directories match manifest checksums/modes",
    )
    append_result(results, "current-audio-graph", "physically validated pre-Stage-C route is still exact")
    append_result(results, "package-inertness", "helper mutations blocked; units gated by absent approval marker")

    destination_state = review_root / "destination-state.tsv"
    destination_review = write_destination_state(entries, package_root, destination_state)
    if destination_review.conflicts:
        raise SystemExit(
            f"Destination conflict gate failed: {destination_review.conflicts} managed destination conflict(s). "
            f"See {destination_state}"
        )
    privileged_paths = set(destination_review.privileged_checks)
    append_result(
        results,
        "destination-conflict-gate",
        f"{destination_review.verified_absent_files} file destinations verified absent; "
        f"{len(privileged_paths)} protected destination(s) require activation-time privileged verification",
    )

    snapshot_root = snapshot_paths(entries, review_root, privileged_paths)
    append_result(
        results,
        "review-snapshot",
        f"filesystem content/absence/protected-path evidence recorded under {snapshot_root}",
    )

    service_state = review_root / "service-state.tsv"
    service_states = capture_service_states(service_state)
    validate_service_boundary(service_states)
    append_result(
        results,
        "service-state-boundary",
        "application services active/enabled; proposed Stage C services absent",
    )

    mixer_state = review_root / "mixer-state.tsv"
    capture_mixer_states(mixer_state, review_root / "mixer-raw")
    append_result(results, "mixer-state-capture", "four live ALSA control percentages captured read-only")

    module_dac = review_root / "module-dac-state.tsv"
    capture_module_and_dac(module_dac, review_root)
    append_result(results, "module-dac-capture", "snd_aloop parameters, DAC owner and hw_params captured")

    rollback = review_root / "rollback-obligations.tsv"
    write_rollback_obligations(entries, rollback)
    append_result(
        results,
        "rollback-contract",
        "exact file/absence/protected-path/service/module/mixer verification obligations generated",
    )

    write_command_plans(review_root, destination_review.privileged_checks)
    append_result(results, "activation-interface", "absent by design; command plans are review text only")

    (review_root / "package-fingerprint.tsv").write_text(
        "item\tsha256\n"
        f"manifest.tsv\t{sha256(package_root / 'manifest.tsv')}\n"
        f"results.tsv\t{sha256(package_root / 'results.tsv')}\n"
        f"report.txt\t{sha256(package_root / 'report.txt')}\n",
        encoding="utf-8",
    )

    protected_lines = "\n".join(f"- {path}" for path in destination_review.privileged_checks) or "- none"
    report = review_root / "report.txt"
    report.write_text(
        f"""A Clockwork Plex Stage C2 prepare-only installation transaction review
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Planner version: {PLANNER_VERSION}
Host: {platform.node()}
Architecture: {platform.machine()}
Stage C1 package: {package_root}
Stage C2 review: {review_root}
Verified pre-Stage-C ALSA SHA-256: {EXPECTED_PRE_STAGE_C_ALSA_SHA256}
Managed package files: {EXPECTED_PACKAGE_FILES}
Verified absent managed files: {destination_review.verified_absent_files}
Existing managed destination conflicts: {destination_review.conflicts}
Privileged destination checks required: {len(destination_review.privileged_checks)}

Protected destinations requiring a fresh privileged activation-time snapshot:
{protected_lines}

Evidence:
- Stage C1 package checksums, modes, directory contract and PASS results were replayed
- current production ALSA remains the exact physically validated rollback graph
- snd_aloop remains index 7 / ACP_Loopback / 2 substreams / pcm_notify 1
- no CamillaDSP process or activation-approved marker exists
- every unprivilegedly verifiable managed file destination is absent
- protected destinations are recorded as unverified, never falsely recorded as absent
- a review snapshot records the current ALSA file, true absence markers and protected-path markers
- service, mixer, module, DAC owner and DAC hw_params state were captured read-only
- exact rollback obligations and future command ordering were generated

Safety state:
- no --activate or --confirm option exists
- no sudo command was invoked
- no production path was written
- no service was started, stopped, restarted, enabled or disabled
- no module was loaded or unloaded
- no PCM was opened
- no mixer value was changed
- no approval marker was created
- protected destinations must be resolved by a fresh root-owned activation-time snapshot before any write
- this review snapshot is evidence only and must be repeated immediately at activation time
- persistent activation remains blocked by activation-blockers.txt
""",
        encoding="utf-8",
    )

    print(
        f"""
A Clockwork Plex Stage C2 transaction review prepared.

  Directory:          {review_root}
  Results:            {results}
  Destination state:  {destination_state}
  Review snapshot:    {snapshot_root}
  Service state:      {service_state}
  Mixer state:        {mixer_state}
  Module/DAC state:   {module_dac}
  Rollback contract:  {rollback}
  Install plan:       {review_root / 'install-command-plan.txt'}
  Rollback plan:      {review_root / 'rollback-command-plan.txt'}
  Blockers:           {review_root / 'activation-blockers.txt'}
  Report:             {report}

No activation path exists. Nothing outside the Stage C2 review directory was
written or changed. Protected destinations remain explicitly unverified, and a
future approved installer must repeat a root-owned snapshot immediately before
any privileged write.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
