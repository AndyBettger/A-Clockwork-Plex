#!/usr/bin/python3
from __future__ import annotations

"""Corrected Stage C17 post-restoration readiness verifier.

The original physical rehearsal proved service restoration but sampled the
strict DAC contract immediately after systemd reported Plexamp active. This
subclass changes only that final readiness boundary: the dashboard is awaited,
then the known-good DAC contract and owner are polled for a bounded interval.
All transaction, service mutation, restoration and cleanup behaviour remains in
the physically exercised Stage C17 adapter.
"""

import os
import time
from pathlib import Path

from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    TransactionIdentity,
)
from .read_only_host_adapter import (
    ObservationFailure,
    _fail,
    _observe_dac_snapshot,
    _observe_host_contract,
    _observe_loopback_snapshot,
    _observe_mixer_snapshot,
    _observe_service_snapshot,
)
from .service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceFailure,
    ServiceQuiescenceRehearsalAdapter,
)


RESTORATION_READINESS_NAME = "restoration-readiness.tsv"
DAC_READY_TIMEOUT_SECONDS = 30.0
DAC_READY_POLL_SECONDS = 0.25


class ServiceQuiescenceRehearsalAdapterV2(
    ServiceQuiescenceRehearsalAdapter
):
    """Stage C17 with bounded post-start DAC readiness observation."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._restoration_readiness = (
            self._evidence_root / RESTORATION_READINESS_NAME
        )
        self._restoration_readiness.write_text(
            "attempt\tmonotonic_ns\tstate\tdetail\n",
            encoding="utf-8",
        )
        os.chown(self._restoration_readiness, 0, 0)
        self._restoration_readiness.chmod(0o600)
        self._readiness_attempt = 0

    def _record_readiness(self, state: str, detail: str) -> None:
        self._readiness_attempt += 1
        clean = detail.replace("\t", " ").replace("\n", " ").strip()
        with self._restoration_readiness.open("a", encoding="utf-8") as output:
            output.write(
                f"{self._readiness_attempt}\t{time.monotonic_ns()}\t"
                f"{state}\t{clean}\n"
            )

    def _wait_for_restored_dac(
        self,
        timeout_seconds: float = DAC_READY_TIMEOUT_SECONDS,
    ):
        deadline = time.monotonic() + timeout_seconds
        last = "no DAC observation attempted"
        while time.monotonic() < deadline:
            try:
                observed = _observe_dac_snapshot()
            except ObservationFailure as exc:
                last = str(exc)
                self._record_readiness("not-ready", last)
            else:
                if observed.released or not observed.owners:
                    last = "strict DAC contract is visible but no owner has returned"
                    self._record_readiness("not-ready", last)
                else:
                    self._record_readiness(
                        "ready",
                        f"owner_count={len(observed.owners)}",
                    )
                    return observed
            time.sleep(DAC_READY_POLL_SECONDS)
        raise ServiceQuiescenceFailure(
            "physical DAC did not regain the full known-good runtime contract "
            f"within {timeout_seconds:.1f}s; last observation: {last}; "
            f"retained {self._restoration_readiness}"
        )

    def verify_dashboard_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_DASHBOARD_HEALTH
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._services_restored:
            return _fail(
                operation,
                "captured application services are not restored",
            )
        if self._dashboard_verified:
            return _fail(
                operation,
                "dashboard restoration was already verified",
            )
        try:
            if _observe_service_snapshot() != self._captured_services_exact:
                raise ServiceQuiescenceFailure(
                    "six-service state differs from the authoritative snapshot"
                )
            _observe_host_contract()
            if _observe_mixer_snapshot() != self._captured_mixer_exact:
                raise ServiceQuiescenceFailure(
                    "mixer state changed during service quiescence"
                )
            if _observe_loopback_snapshot() != self._captured_loopback_exact:
                raise ServiceQuiescenceFailure(
                    "loopback state changed during service quiescence"
                )

            # systemd 'active' is a process-lifecycle observation, not proof that
            # Plexamp has finished opening ALSA. Wait for the dashboard first,
            # then poll the strict DAC observer rather than sleeping blindly.
            status, content_type = self._wait_for_dashboard()
            restored_dac = self._wait_for_restored_dac()
        except (
            ObservationFailure,
            ServiceQuiescenceFailure,
            OSError,
        ) as exc:
            return _fail(operation, str(exc))

        self._dashboard_verified = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "service, route, mixer, loopback, bounded DAC readiness and "
                "dashboard health restored"
            ),
            evidence=(
                ("dashboard_url", "http://127.0.0.1:8088/"),
                ("http_status", str(status)),
                ("content_type", content_type),
                ("dac_owner_count", str(len(restored_dac.owners))),
                ("dac_readiness_attempts", str(self._readiness_attempt)),
                ("readiness_evidence", str(self._restoration_readiness)),
            ),
        )
