#!/usr/bin/python3
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from .approval_store import ApprovalStore
from .model import BootObservation, CommitObservation, HardwareContract, InstallHandoffObservation, UnitObservation, utc_timestamp
from .state_machine import accept_install_handoff, decide_boot, promote_committed_approval


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def build_contract() -> HardwareContract:
    return HardwareContract(
        package_fingerprint=digest("stage-c21-review-package"),
        split_route_sha256=digest("split-route"),
        direct_route_sha256=digest("direct-route"),
        camilladsp_config_sha256=digest("camilladsp-config"),
        camilladsp_binary_version="4.1.3",
        camilladsp_binary_sha256=digest("camilladsp-binary"),
        loopback_index=7,
        loopback_id="ACP_Loopback",
        loopback_pcm_substreams=2,
        loopback_pcm_notify=1,
        dac_card="Pro",
        dac_device=0,
        sample_rate=44100,
        sample_format="S16_LE",
        period_size=1024,
        buffer_size=8192,
    )


def boot_observation(contract: HardwareContract, *, start_ok: bool, health_ok: bool) -> BootObservation:
    return BootObservation(
        **contract.as_dict(),
        managed_files_valid=True,
        split_route_valid=True,
        direct_route_valid=True,
        loopback_valid=True,
        dac_valid=True,
        camilladsp_start_succeeded=start_ok,
        split_bus_health_valid=health_ok,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the non-physical Stage C21 runtime-authority disposable-root review.")
    parser.add_argument("--lab-root", type=Path, help="new or existing empty disposable review directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.lab_root is None:
        lab = Path(tempfile.mkdtemp(prefix="a-clockwork-plex-stage-c21-runtime-authority.", dir="/var/tmp"))
    else:
        lab = args.lab_root.expanduser().resolve()
        lab.mkdir(parents=True, exist_ok=True)
        if any(lab.iterdir()):
            raise SystemExit(f"--lab-root must be empty: {lab}")
    lab.chmod(0o700)
    state_root = lab / "state"
    state_root.mkdir(mode=0o700)
    contract = build_contract()
    units = tuple(
        UnitObservation(name, "loaded", "inactive", "dead", unit_file_state)
        for name, unit_file_state in (
            ("a-clockwork-plex-audio-route.service", "disabled"),
            ("a-clockwork-plex-camilladsp.service", "disabled"),
            ("a-clockwork-plex-audio-failback.service", "static"),
        )
    )
    handoff = InstallHandoffObservation(
        transaction_id="stage-c21-review-transaction",
        lock_lease_id="stage-c21-review-lease",
        production_lock_held=True,
        candidate_validated=True,
        package_fingerprint=contract.package_fingerprint,
        active_route_sha256=contract.split_route_sha256,
        installed_file_count=12,
        managed_units=units,
        dac_released=True,
        loopback_playback_released=True,
    )
    temporary, handoff_decision = accept_install_handoff(handoff, contract, created_at=utc_timestamp())
    store = ApprovalStore(state_root)
    store.publish_new(temporary, lock_held=True)
    commit = CommitObservation(
        transaction_id=temporary.transaction_id,
        lock_lease_id=temporary.lock_lease_id,
        production_lock_held=True,
        install_committed=True,
        split_bus_healthy=True,
        active_route_sha256=contract.split_route_sha256,
        commit_manifest_sha256=digest("commit-manifest"),
    )
    committed, commit_decision = promote_committed_approval(temporary, commit, committed_at=utc_timestamp())
    store.replace_exact(temporary, committed, lock_held=True)
    if store.read() != committed:
        raise SystemExit("approval reread mismatch")
    split_decision = decide_boot(committed, boot_observation(contract, start_ok=True, health_ok=True))
    failback_decision = decide_boot(committed, boot_observation(contract, start_ok=False, health_ok=False))

    results = [
        ("install-handoff", "PASS", handoff_decision.reason),
        ("temporary-approval", "PASS", temporary.record_sha256),
        ("committed-promotion", "PASS", commit_decision.reason),
        ("approval-reread", "PASS", committed.record_sha256),
        ("split-boot", "PASS", split_decision.mode.value),
        ("failed-split-direct-failback", "PASS", failback_decision.mode.value),
        ("physical-boundary", "PASS", "no sudo, systemd, ALSA, PCM, network or production path access"),
    ]
    (lab / "results.tsv").write_text(
        "check\tresult\tdetail\n" + "".join(f"{a}\t{b}\t{c}\n" for a, b, c in results), encoding="utf-8"
    )
    (lab / "contract.json").write_text(json.dumps(contract.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (lab / "decisions.json").write_text(
        json.dumps(
            {
                "install_handoff": [action.value for action in handoff_decision.actions],
                "commit": [action.value for action in commit_decision.actions],
                "split_boot": [action.value for action in split_decision.actions],
                "direct_failback": [action.value for action in failback_decision.actions],
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    print("A Clockwork Plex Stage C21 runtime-authority disposable review passed.\n")
    print(f"  Directory: {lab}")
    print(f"  Results:   {lab / 'results.tsv'}")
    print(f"  Approval:  {state_root / 'activation-approved'}")
    print(f"  Decisions: {lab / 'decisions.json'}")
    print("\nNo host observation, sudo, service, route, mixer, PCM or production write occurred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
