#!/usr/bin/python3
from __future__ import annotations

"""Final terminal adapter correction.

The v15 adapter supplies the complete fixed terminal runtime. This narrow
layer replaces only terminal publication so every known pre-publication failure
returns FAIL after reversing enablement and persistent-path preparation, while
an indeterminate approval exchange fails closed with authority retained for
inspection.
"""

import os

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.model import utc_timestamp

from .approval_record_plan_v7 import plan_committed_approval_v7
from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .current_package_terminal_install_adapter_v15 import (
    ACTIVE_ROUTE,
    APPROVAL_PATH,
    COMMIT_MANIFEST_NAME,
    COMMITTED_INSTALL_ROOT,
    ENABLE_UNITS,
    ORIGINAL_ROUTE_NAME,
    RUNTIME_HELPER,
    SPLIT_ROUTE,
    STATE_ROOT,
    TRANSACTION_ROOT,
    ActivationApprovalAdapterResult,
    ActivationApprovalLifecycleOperation,
    AdapterStatus,
    CommittedActivationApprovalReceipt,
    COMMITTED_APPROVAL_PHASE,
    CurrentPackageTerminalInstallAdapterV15,
    TerminalInstallFailure,
    _atomic_json,
    _fsync_directory,
    _require_identity,
    _run_fixed,
    sha256,
)
from .production_adapter_contract import TransactionIdentity


class IndeterminateCommitPublication(TerminalInstallFailure):
    """The committed approval may have been published; rollback is forbidden."""


class CurrentPackageTerminalInstallAdapterV16(
    CurrentPackageTerminalInstallAdapterV15
):
    """v15 host implementation with deterministic terminal publication recovery."""

    def promote_committed_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        operation = (
            ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL
        )
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, ActivationApprovalAdapterResult)
            return invalid
        if self._temporary_plan is None or self._approval_binding is None:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="temporary approval or authority binding is unavailable",
            )
        if not all(
            (
                self._managed_services_started,
                self._services_restored,
                self._dashboard_verified,
                self._route_selected,
                self._route_selected_once,
                self._route_exchange_completed,
            )
        ):
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "runtime, applications, dashboard and selected route must "
                    "be healthy before commit"
                ),
            )
        if COMMITTED_INSTALL_ROOT.exists() or COMMITTED_INSTALL_ROOT.is_symlink():
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="a committed Stage C installation already exists",
            )

        assert self.transaction_path is not None
        assert self._route_rollback_name is not None
        assert self._route_original is not None
        assert self._route_candidate is not None
        assert self.authoritative_transaction is not None
        assert self.lease is not None

        transaction_path = self.transaction_path
        parked_route = ACTIVE_ROUTE.parent / self._route_rollback_name
        uninstall_root = transaction_path / "uninstall"
        original_destination = uninstall_root / ORIGINAL_ROUTE_NAME
        route_moved = False
        transaction_moved = False
        store = ApprovalStore(STATE_ROOT)
        committed_plan = None

        try:
            uninstall_root.mkdir(mode=0o700, exist_ok=False)
            os.chown(uninstall_root, 0, 0)
            uninstall_root.chmod(0o700)
            _require_identity(
                parked_route,
                self._route_original,
                "parked pre-EQ route",
            )
            os.rename(parked_route, original_destination)
            route_moved = True
            _fsync_directory(ACTIVE_ROUTE.parent)
            _fsync_directory(uninstall_root)
            _require_identity(
                original_destination,
                self._route_original,
                "committed pre-EQ uninstall route",
            )

            _run_fixed(
                "systemctl",
                "enable",
                *tuple(unit.value for unit in ENABLE_UNITS),
            )
            self._managed_enablement_started = True
            for unit in ENABLE_UNITS:
                if _run_fixed("systemctl", "is-enabled", unit.value) != "enabled":
                    raise TerminalInstallFailure(
                        f"managed unit did not become enabled: {unit.value}"
                    )

            manifest_path = transaction_path / COMMIT_MANIFEST_NAME
            _atomic_json(
                manifest_path,
                {
                    "schema_version": 1,
                    "state": "committed-stage-c-eq-install",
                    "committed_at": utc_timestamp(),
                    "transaction_id": transaction.value,
                    "snapshot_id": self.authoritative_transaction.snapshot.value,
                    "package_fingerprint": self.package.sha256,
                    "active_route_path": str(ACTIVE_ROUTE),
                    "active_route_sha256": self._route_candidate.digest,
                    "pre_eq_route_path": f"uninstall/{ORIGINAL_ROUTE_NAME}",
                    "pre_eq_route_sha256": self._route_original.digest,
                    "managed_file_count": 28,
                    "payload_file_count": 27,
                    "enabled_units": [unit.value for unit in ENABLE_UNITS],
                    "accepted_c25_evidence": str(self._accepted_c25_evidence),
                    "temporary_approval_sha256": self._temporary_plan.record_sha256,
                    "reboot_verification": "pending",
                    "pr_ready_or_merged": False,
                },
            )
            manifest_sha256 = sha256(manifest_path)
            committed_plan = plan_committed_approval_v7(
                self._temporary_plan,
                commit_manifest_sha256=manifest_sha256,
                committed_at=utc_timestamp(),
            )
            _atomic_text(
                transaction_path / "committed-approval-sha256.txt",
                committed_plan.record_sha256 + "\n",
            )
            _fsync_directory(transaction_path)

            os.rename(transaction_path, COMMITTED_INSTALL_ROOT)
            transaction_moved = True
            _fsync_directory(STATE_ROOT)

            try:
                store.replace_exact(
                    self._temporary_plan.record,
                    committed_plan.record,
                    lock_held=True,
                )
            except BaseException as publication_exc:
                try:
                    observed = store.read()
                except BaseException as observation_exc:
                    raise IndeterminateCommitPublication(
                        "committed approval publication became indeterminate"
                    ) from observation_exc
                if observed == committed_plan.record:
                    pass
                elif observed == self._temporary_plan.record:
                    self._revert_commit_preparation(
                        transaction_path=transaction_path,
                        committed_root=COMMITTED_INSTALL_ROOT,
                        parked_route=parked_route,
                        original_destination=original_destination,
                        transaction_moved=transaction_moved,
                        route_moved=route_moved,
                    )
                    self._record_runtime_action(
                        "promote-committed-approval",
                        "FAIL",
                        str(publication_exc),
                    )
                    return ActivationApprovalAdapterResult(
                        operation=operation,
                        status=AdapterStatus.FAIL,
                        detail=(
                            "committed approval was not published: "
                            f"{publication_exc}"
                        ),
                    )
                else:
                    raise IndeterminateCommitPublication(
                        "approval store contains neither exact temporary nor "
                        "exact committed record"
                    ) from publication_exc

            try:
                observed_after = store.read()
            except BaseException as verification_exc:
                raise IndeterminateCommitPublication(
                    "committed approval cannot be verified after publication"
                ) from verification_exc
            if observed_after == self._temporary_plan.record:
                raise TerminalInstallFailure(
                    "approval remained temporary after committed publication"
                )
            if observed_after != committed_plan.record:
                raise IndeterminateCommitPublication(
                    "approval identity changed after committed publication"
                )

        except IndeterminateCommitPublication as exc:
            self._record_runtime_action(
                "promote-committed-approval",
                "INDETERMINATE",
                str(exc),
            )
            raise
        except BaseException as exc:
            try:
                observed = store.read()
            except BaseException:
                observed = None
            if committed_plan is not None and observed == committed_plan.record:
                raise IndeterminateCommitPublication(
                    "committed approval exists after a terminal publication error"
                ) from exc
            try:
                if transaction_moved or route_moved or self._managed_enablement_started:
                    self._revert_commit_preparation(
                        transaction_path=transaction_path,
                        committed_root=COMMITTED_INSTALL_ROOT,
                        parked_route=parked_route,
                        original_destination=original_destination,
                        transaction_moved=transaction_moved,
                        route_moved=route_moved,
                    )
            except BaseException as revert_exc:
                raise TerminalInstallFailure(
                    f"commit preparation failed: {exc}; preparation reversal "
                    f"failed: {revert_exc}"
                ) from exc
            self._record_runtime_action(
                "promote-committed-approval",
                "FAIL",
                str(exc),
            )
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )

        assert committed_plan is not None
        self._committed_plan = committed_plan
        self._commit_manifest_sha256 = committed_plan.commit_manifest_sha256
        self._committed_install_root = COMMITTED_INSTALL_ROOT
        self._terminal_committed = True
        self._route_exchange_completed = False
        self._route_rollback_name = None
        self.transaction_path = None
        if TRANSACTION_ROOT.exists():
            try:
                TRANSACTION_ROOT.rmdir()
            except OSError:
                pass
        self._record_runtime_action(
            "promote-committed-approval",
            "PASS",
            committed_plan.record_sha256,
        )
        return ActivationApprovalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "durable uninstall snapshot and manifest prepared, managed boot "
                "units enabled and committed approval atomically published"
            ),
            payload=CommittedActivationApprovalReceipt(
                transaction=transaction,
                approval_path=str(APPROVAL_PATH),
                phase=COMMITTED_APPROVAL_PHASE,
                package=self.package,
                lock_lease_id=self.lease.lease_id,
                temporary_record_sha256=self._temporary_plan.record_sha256,
                committed_record_sha256=committed_plan.record_sha256,
                commit_manifest_sha256=committed_plan.commit_manifest_sha256,
                boot_eligible=True,
                atomically_promoted=True,
                exact_record_verified=True,
            ),
        )
