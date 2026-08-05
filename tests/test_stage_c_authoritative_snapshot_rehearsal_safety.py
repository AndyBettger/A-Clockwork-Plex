from __future__ import annotations

import ast
import inspect
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.stage_c_transaction import authoritative_snapshot_rehearsal as rehearsal
from scripts.stage_c_transaction import authoritative_snapshot_rehearsal_adapter as adapter_module
from scripts.stage_c_transaction import production_adapter_contract as contract
from scripts.stage_c_transaction.production_lock_rehearsal_adapter import (
    ProductionLockRehearsalAdapter,
)


class StageCAuthoritativeSnapshotRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.adapter_path = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "authoritative_snapshot_rehearsal_adapter.py"
        )
        self.engine_path = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "authoritative_snapshot_rehearsal.py"
        )
        self.wrapper_path = (
            self.repo
            / "scripts"
            / "test-stage-c-authoritative-snapshot-rehearsal.sh"
        )
        self.adapter_source = self.adapter_path.read_text(encoding="utf-8")
        self.engine_source = self.engine_path.read_text(encoding="utf-8")
        self.wrapper_source = self.wrapper_path.read_text(encoding="utf-8")
        self.adapter_tree = ast.parse(self.adapter_source)
        self.engine_tree = ast.parse(self.engine_source)

    @staticmethod
    def fake_adapter() -> adapter_module.AuthoritativeSnapshotRehearsalAdapter:
        package = contract.PackageFingerprint("1" * 64)
        with (
            patch.object(adapter_module, "package_tree_fingerprint", return_value=package),
            patch.object(adapter_module, "parse_manifest", return_value=[]),
        ):
            return adapter_module.AuthoritativeSnapshotRehearsalAdapter(
                Path("/var/tmp/a-clockwork-plex-stage-c1-review-test"),
                "andy",
            )

    @staticmethod
    def service_snapshot() -> contract.ServiceSnapshot:
        states = []
        for unit in contract.ServiceUnit:
            application = unit in {
                contract.ServiceUnit.PLEXAMP,
                contract.ServiceUnit.SHAIRPORT_SYNC,
                contract.ServiceUnit.DASHBOARD,
            }
            states.append(
                contract.ServiceState(
                    unit=unit,
                    load=(
                        contract.ServiceLoadState.LOADED
                        if application
                        else contract.ServiceLoadState.NOT_FOUND
                    ),
                    active=(
                        contract.ServiceActiveState.ACTIVE
                        if application
                        else contract.ServiceActiveState.INACTIVE
                    ),
                    enabled=(
                        contract.ServiceEnableState.ENABLED
                        if application
                        else contract.ServiceEnableState.NOT_FOUND
                    ),
                )
            )
        return contract.ServiceSnapshot(tuple(states))

    def test_exact_ten_core_operations_and_twenty_three_blocked(self) -> None:
        self.assertEqual(
            adapter_module.PERMITTED_OPERATIONS,
            (
                contract.AdapterOperation.INSPECT_HOST_CONTRACT,
                contract.AdapterOperation.INSPECT_PRODUCTION_LOCK,
                contract.AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
                contract.AdapterOperation.RELEASE_PRODUCTION_LOCK,
                contract.AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
                contract.AdapterOperation.CAPTURE_FILESYSTEM_STATE,
                contract.AdapterOperation.CAPTURE_SERVICE_STATE,
                contract.AdapterOperation.CAPTURE_MIXER_STATE,
                contract.AdapterOperation.CAPTURE_LOOPBACK_STATE,
                contract.AdapterOperation.CAPTURE_DAC_STATE,
            ),
        )
        self.assertEqual(len(adapter_module.PERMITTED_OPERATIONS), 10)
        self.assertEqual(
            len(
                set(contract.AdapterOperation).difference(
                    adapter_module.PERMITTED_OPERATIONS
                )
            ),
            23,
        )

    def test_adapter_extends_lock_adapter_and_abort_is_explicit(self) -> None:
        adapter = self.fake_adapter()
        self.assertIsInstance(adapter, ProductionLockRehearsalAdapter)
        self.assertIsInstance(adapter, contract.ProductionAdapter)
        overrides = {
            name
            for name, value in adapter_module.AuthoritativeSnapshotRehearsalAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            overrides,
            {
                "create_authoritative_transaction",
                "capture_filesystem_state",
                "capture_service_state",
                "capture_mixer_state",
                "capture_loopback_state",
                "capture_dac_state",
                "release_production_lock",
                "abort_uncommitted_transaction",
            },
        )
        self.assertNotIn("execute", overrides)
        self.assertNotIn("dispatch", overrides)

    def test_fixed_transaction_root_prefix_and_parent_contract(self) -> None:
        self.assertEqual(
            str(adapter_module.TRANSACTION_ROOT),
            "/var/lib/a-clockwork-plex/split-bus/transactions",
        )
        self.assertEqual(adapter_module.TRANSACTION_PREFIX, "stage-c15-install-")
        self.assertEqual(adapter_module.SNAPSHOT_PREFIX, "stage-c15-snapshot-")
        self.assertEqual(
            adapter_module.PARENT_CONTRACT,
            (
                (Path("/var/lib/a-clockwork-plex"), 0o750),
                (Path("/var/lib/a-clockwork-plex/split-bus"), 0o750),
                (
                    Path("/var/lib/a-clockwork-plex/split-bus/transactions"),
                    0o700,
                ),
            ),
        )
        parameters = tuple(
            inspect.signature(
                adapter_module.AuthoritativeSnapshotRehearsalAdapter.create_authoritative_transaction
            ).parameters
        )
        self.assertEqual(parameters, ("self", "action", "package"))

    def test_adapter_has_no_cli_generic_command_or_audio_mutation(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.adapter_tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {
                "argparse",
                "requests",
                "shlex",
                "socket",
                "subprocess",
                "urllib",
            }.isdisjoint(imported)
        )
        for marker in (
            "shell=true",
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
            "camilladsp ",
            "stage_candidate_files(",
            "install_managed_files(",
            "select_split_bus_route(",
        ):
            self.assertNotIn(marker, self.adapter_source.lower())

    def test_release_refuses_while_uncommitted_transaction_exists(self) -> None:
        adapter = self.fake_adapter()
        transaction = contract.AuthoritativeTransaction(
            transaction=contract.TransactionIdentity("stage-c15-install-test"),
            snapshot=contract.SnapshotIdentity("stage-c15-snapshot-test"),
            action=contract.TransactionAction.INSTALL,
            package=adapter.package,
        )
        adapter._transaction = transaction
        adapter._transaction_path = Path("/var/lib/example")
        with patch.object(
            ProductionLockRehearsalAdapter,
            "release_production_lock",
        ) as parent_release:
            result = adapter.release_production_lock()
        self.assertIs(result.status, contract.AdapterStatus.FAIL)
        self.assertIn("uncommitted transaction", result.detail)
        parent_release.assert_not_called()

    def test_abort_result_is_typed_and_fail_closed(self) -> None:
        transaction = contract.TransactionIdentity("stage-c15-install-test")
        receipt = adapter_module.AbortTransactionReceipt(
            transaction=transaction,
            state="aborted-before-mutation",
            evidence_copy="/var/tmp/copy",
            transaction_path_absent=True,
            parents_restored=True,
        )
        result = adapter_module.AbortTransactionResult(
            status=contract.AdapterStatus.PASS,
            detail="complete",
            payload=receipt,
        )
        self.assertEqual(result.payload, receipt)
        with self.assertRaises(ValueError):
            adapter_module.AbortTransactionResult(
                status=contract.AdapterStatus.FAIL,
                detail="failed",
                payload=receipt,
            )

    def test_abort_requires_complete_snapshot_before_copy_or_cleanup(self) -> None:
        adapter = self.fake_adapter()
        adapter._lock_fd = 10
        adapter._lease = contract.ProductionLockLease(
            path=contract.PRODUCTION_LOCK_PATH,
            lease_id="stage-c14-lock-test",
        )
        adapter._transaction = contract.AuthoritativeTransaction(
            transaction=contract.TransactionIdentity("stage-c15-install-test"),
            snapshot=contract.SnapshotIdentity("stage-c15-snapshot-test"),
            action=contract.TransactionAction.INSTALL,
            package=adapter.package,
        )
        adapter._transaction_path = Path("/var/lib/example")
        with patch.object(adapter_module.shutil, "copytree") as copied:
            result = adapter.abort_uncommitted_transaction(Path("/var/tmp/copy"))
        self.assertIs(result.status, contract.AdapterStatus.FAIL)
        self.assertIn("complete snapshot", result.detail)
        copied.assert_not_called()

    def test_transaction_path_substitution_is_rejected_before_copy(self) -> None:
        adapter = self.fake_adapter()
        adapter._lock_fd = 10
        adapter._lease = contract.ProductionLockLease(
            path=contract.PRODUCTION_LOCK_PATH,
            lease_id="stage-c14-lock-test",
        )
        adapter._transaction = contract.AuthoritativeTransaction(
            transaction=contract.TransactionIdentity("stage-c15-install-test"),
            snapshot=contract.SnapshotIdentity("stage-c15-snapshot-test"),
            action=contract.TransactionAction.INSTALL,
            package=adapter.package,
        )
        adapter._transaction_path = Mock()
        adapter._transaction_path.lstat.return_value = SimpleNamespace(
            st_dev=1,
            st_ino=22,
            st_mode=stat.S_IFDIR | 0o700,
        )
        adapter._transaction_device = 1
        adapter._transaction_inode = 11
        adapter._filesystem_captured = True
        adapter._service_captured = True
        adapter._mixer_captured = True
        adapter._loopback_captured = True
        adapter._dac_captured = True
        with patch.object(adapter_module.shutil, "copytree") as copied:
            result = adapter.abort_uncommitted_transaction(Path("/var/tmp/copy"))
        self.assertIs(result.status, contract.AdapterStatus.FAIL)
        self.assertIn("substitution", result.detail)
        copied.assert_not_called()

    def test_package_fingerprint_is_ordered_and_deterministic(self) -> None:
        rows = [
            ("manifest.tsv", "file", "644", "a" * 64),
            ("system-root", "directory", "755", "-"),
        ]
        with (
            patch.object(adapter_module, "validate_stage_c1_evidence"),
            patch.object(adapter_module, "tree_fingerprint", return_value=rows),
        ):
            first = adapter_module.package_tree_fingerprint(Path("/tmp/package"))
            second = adapter_module.package_tree_fingerprint(Path("/tmp/package"))
        self.assertEqual(first, second)
        self.assertEqual(len(first.sha256), 64)

    def test_all_twenty_three_later_operations_remain_blocked(self) -> None:
        adapter = self.fake_adapter()
        transaction = contract.TransactionIdentity("stage-c15-install-test")
        snapshot = contract.SnapshotIdentity("stage-c15-snapshot-test")
        services = self.service_snapshot()
        mixer = contract.MixerSnapshot(94, 100, 100, 100)
        rows = rehearsal.prove_blocked_operations(
            adapter,
            transaction=transaction,
            package=adapter.package,
            services=services,
            mixer=mixer,
            snapshot=snapshot,
        )
        expected = set(contract.AdapterOperation).difference(
            adapter_module.PERMITTED_OPERATIONS
        )
        self.assertEqual(len(rows), 23)
        self.assertEqual(
            {
                contract.AdapterOperation(operation)
                for operation, state in rows
                if state == "blocked"
            },
            expected,
        )

    def test_engine_contract_has_exact_twenty_three_checks(self) -> None:
        self.assertEqual(len(rehearsal.EXPECTED_CHECKS), 23)
        self.assertEqual(
            rehearsal.EXPECTED_CHECKS,
            (
                "root-scope",
                "input-replay",
                "protocol-conformance",
                "pre-lock-host-contract",
                "pre-lock-boundary",
                "production-lock-acquired",
                "transaction-parent-boundary",
                "authoritative-transaction-created",
                "transaction-identity-binding",
                "filesystem-snapshot",
                "service-snapshot",
                "mixer-snapshot",
                "loopback-snapshot",
                "dac-snapshot",
                "snapshot-integrity",
                "blocked-operation-boundary",
                "pre-mutation-abort",
                "transaction-evidence-copy",
                "exact-transaction-cleanup",
                "production-lock-released",
                "input-integrity",
                "evidence-integrity",
                "activation-interface",
            ),
        )

    def test_engine_has_no_direct_audio_or_generic_command_boundary(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.engine_tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {
                "fcntl",
                "requests",
                "shlex",
                "socket",
                "subprocess",
                "urllib",
            }.isdisjoint(imported)
        )
        for marker in (
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
            "subprocess.run",
            "os.open(",
            "flock(",
            "install_managed_files(",
            "select_split_bus_route(",
        ):
            self.assertNotIn(marker, self.engine_source.lower())

    def test_wrapper_is_prepare_only_and_has_one_constrained_sudo(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(self.wrapper_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        prepare = self.wrapper_source.index('if [[ "$MODE" == "prepare" ]]')
        sudo = self.wrapper_source.index("exec sudo env")
        self.assertLess(prepare, sudo)
        self.assertEqual(self.wrapper_source.count("\nexec sudo env"), 1)
        self.assertIn(
            'REQUIRED_CONFIRMATION="STAGE-C15-AUTHORITATIVE-SNAPSHOT-ABORT"',
            self.wrapper_source,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.wrapper_source)
        self.assertIn(
            "-m stage_c_transaction.authoritative_snapshot_rehearsal",
            self.wrapper_source,
        )
        self.assertNotIn("--activate", self.wrapper_source)
        self.assertNotIn("--install", self.wrapper_source)
        self.assertNotIn("--rollback", self.wrapper_source)


if __name__ == "__main__":
    unittest.main()
