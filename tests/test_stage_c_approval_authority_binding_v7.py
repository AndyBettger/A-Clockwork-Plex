from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/approval_authority_binding_v7.py"

from scripts.stage_c_transaction.approval_authority_binding_v7 import (
    RECONCILIATION_POLICY_V7,
    ApprovalAuthorityBindingResultV7,
    ApprovalAuthorityBindingV7,
    ApprovalHardwareContractV7,
    ApprovalPublicationKnowledgeV7,
    ApprovalRecoveryActionV7,
    bind_approval_authority_v7,
    reconciliation_policy_v7,
)
from scripts.stage_c_transaction.borrowed_authority_view_v7 import (
    BorrowedAuthorityViewV7,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    AdapterStatus,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
)
from scripts.stage_c_transaction.snapshot_core import CURRENT_ALSA_DESTINATION


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64


class StageCApprovalAuthorityBindingV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction = TransactionIdentity("stage-c21-binding-test")
        self.snapshot = SnapshotIdentity("stage-c21-binding-snapshot")
        self.package = PackageFingerprint(HASH_A)
        self.authority = BorrowedAuthorityViewV7(
            production_lock_path=PRODUCTION_LOCK_PATH,
            lock_lease_id="stage-c21-binding-lease",
            lock_device=101,
            lock_inode=102,
            transaction=self.transaction,
            snapshot=self.snapshot,
            package=self.package,
            authoritative_transaction_path=str(
                Path(AUTHORITATIVE_TRANSACTION_ROOT) / self.transaction.value
            ),
            transaction_device=201,
            transaction_inode=202,
            selected_route_path=CURRENT_ALSA_DESTINATION,
            selected_route_device=301,
            selected_route_inode=302,
            selected_route_sha256=HASH_B,
            snapshot_complete=True,
            split_bus_route_selected=True,
            exact_lock_owned=True,
            exact_transaction_verified=True,
        )
        self.hardware = ApprovalHardwareContractV7(
            package=self.package,
            split_route_sha256=HASH_B,
            direct_route_sha256=HASH_C,
            camilladsp_config_sha256=HASH_D,
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=HASH_E,
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

    def test_success_binds_exact_authority_and_hardware_without_host_receipt(self) -> None:
        result = bind_approval_authority_v7(self.authority, self.hardware)
        self.assertIs(result.status, AdapterStatus.PASS)
        self.assertIsInstance(result.payload, ApprovalAuthorityBindingV7)
        binding = result.payload
        assert binding is not None
        self.assertEqual(binding.transaction, self.transaction)
        self.assertEqual(binding.snapshot, self.snapshot)
        self.assertEqual(binding.package, self.package)
        self.assertEqual(binding.production_lock_path, PRODUCTION_LOCK_PATH)
        self.assertEqual(binding.lock_lease_id, "stage-c21-binding-lease")
        self.assertEqual(binding.lock_device, 101)
        self.assertEqual(binding.lock_inode, 102)
        self.assertEqual(binding.selected_route_sha256, HASH_B)
        self.assertEqual(binding.hardware, self.hardware)
        self.assertEqual(len(binding.binding_sha256), 64)
        self.assertTrue(
            all(character in "0123456789abcdef" for character in binding.binding_sha256)
        )
        self.assertNotIn("fd", ApprovalAuthorityBindingV7.__dataclass_fields__)
        self.assertNotIn("descriptor", ApprovalAuthorityBindingV7.__dataclass_fields__)
        self.assertNotIn("adapter", ApprovalAuthorityBindingV7.__dataclass_fields__)

    def test_binding_digest_is_canonical_deterministic_and_identity_sensitive(self) -> None:
        first = bind_approval_authority_v7(self.authority, self.hardware).payload
        second = bind_approval_authority_v7(self.authority, self.hardware).payload
        assert first is not None and second is not None
        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(first.binding_sha256, second.binding_sha256)
        self.assertEqual(first.as_dict()["schema_version"], 1)
        self.assertEqual(
            set(first.as_dict()["hardware"]),
            {
                "package_fingerprint",
                "split_route_sha256",
                "direct_route_sha256",
                "camilladsp_config_sha256",
                "camilladsp_binary_version",
                "camilladsp_binary_sha256",
                "loopback_index",
                "loopback_id",
                "loopback_pcm_substreams",
                "loopback_pcm_notify",
                "dac_card",
                "dac_device",
                "sample_rate",
                "sample_format",
                "period_size",
                "buffer_size",
            },
        )

        changed_hardware = ApprovalHardwareContractV7(
            package=self.package,
            split_route_sha256=HASH_B,
            direct_route_sha256="f" * 64,
            camilladsp_config_sha256=HASH_D,
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=HASH_E,
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
        changed = bind_approval_authority_v7(
            self.authority,
            changed_hardware,
        ).payload
        assert changed is not None
        self.assertNotEqual(first.binding_sha256, changed.binding_sha256)

    def test_package_or_selected_route_mismatch_returns_typed_failure(self) -> None:
        wrong_package_hardware = ApprovalHardwareContractV7(
            package=PackageFingerprint("f" * 64),
            split_route_sha256=HASH_B,
            direct_route_sha256=HASH_C,
            camilladsp_config_sha256=HASH_D,
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=HASH_E,
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
        result = bind_approval_authority_v7(
            self.authority,
            wrong_package_hardware,
        )
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIsNone(result.payload)
        self.assertIn("package differs", result.detail)

        wrong_route_hardware = ApprovalHardwareContractV7(
            package=self.package,
            split_route_sha256="f" * 64,
            direct_route_sha256=HASH_C,
            camilladsp_config_sha256=HASH_D,
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=HASH_E,
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
        result = bind_approval_authority_v7(
            self.authority,
            wrong_route_hardware,
        )
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIsNone(result.payload)
        self.assertIn("split-route digest differs", result.detail)

    def test_hardware_contract_rejects_invalid_digests_tokens_and_geometry(self) -> None:
        values = self.hardware.__dict__.copy()
        values["direct_route_sha256"] = "not-a-digest"
        with self.assertRaises(ValueError):
            ApprovalHardwareContractV7(**values)

        values = self.hardware.__dict__.copy()
        values["camilladsp_binary_version"] = "bad version"
        with self.assertRaises(ValueError):
            ApprovalHardwareContractV7(**values)

        values = self.hardware.__dict__.copy()
        values["loopback_pcm_substreams"] = 0
        with self.assertRaises(ValueError):
            ApprovalHardwareContractV7(**values)

        values = self.hardware.__dict__.copy()
        values["period_size"] = 8193
        with self.assertRaises(ValueError):
            ApprovalHardwareContractV7(**values)

        values = self.hardware.__dict__.copy()
        values["dac_device"] = True
        with self.assertRaises(ValueError):
            ApprovalHardwareContractV7(**values)

    def test_binding_requires_exact_types_and_result_payload_invariants(self) -> None:
        with self.assertRaises(TypeError):
            bind_approval_authority_v7(object(), self.hardware)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            bind_approval_authority_v7(self.authority, object())  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ApprovalAuthorityBindingResultV7(
                status=AdapterStatus.PASS,
                detail="missing payload",
            )
        binding = bind_approval_authority_v7(
            self.authority,
            self.hardware,
        ).payload
        assert binding is not None
        with self.assertRaises(ValueError):
            ApprovalAuthorityBindingResultV7(
                status=AdapterStatus.FAIL,
                detail="invented payload",
                payload=binding,
            )

    def test_binding_and_hardware_records_are_frozen(self) -> None:
        binding = bind_approval_authority_v7(
            self.authority,
            self.hardware,
        ).payload
        assert binding is not None
        with self.assertRaises(FrozenInstanceError):
            binding.lock_inode = 999  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.hardware.sample_rate = 48000  # type: ignore[misc]

    def test_reconciliation_policy_covers_every_knowledge_state_once(self) -> None:
        self.assertEqual(
            set(RECONCILIATION_POLICY_V7),
            set(ApprovalPublicationKnowledgeV7),
        )
        for knowledge in ApprovalPublicationKnowledgeV7:
            policy = reconciliation_policy_v7(knowledge)
            self.assertIs(policy.knowledge, knowledge)
            self.assertTrue(policy.lock_must_remain_held)
            self.assertFalse(policy.blind_rollback_permitted)
            self.assertTrue(policy.permitted_actions)
        with self.assertRaises(TypeError):
            reconciliation_policy_v7("temporary-confirmed")  # type: ignore[arg-type]

    def test_confirmed_absent_temporary_and_committed_states_are_distinct(self) -> None:
        absent = reconciliation_policy_v7(
            ApprovalPublicationKnowledgeV7.ABSENT_CONFIRMED
        )
        self.assertEqual(
            absent.permitted_actions,
            (ApprovalRecoveryActionV7.PUBLISH_TEMPORARY,),
        )
        self.assertFalse(absent.forward_recovery_permitted)
        self.assertFalse(absent.exact_record_reconciliation_required)

        temporary = reconciliation_policy_v7(
            ApprovalPublicationKnowledgeV7.TEMPORARY_CONFIRMED
        )
        self.assertEqual(
            temporary.permitted_actions,
            (
                ApprovalRecoveryActionV7.CONTINUE_TEMPORARY_INSTALL,
                ApprovalRecoveryActionV7.
                REMOVE_EXACT_TEMPORARY_DURING_ROLLBACK,
            ),
        )
        self.assertFalse(temporary.forward_recovery_permitted)
        self.assertFalse(temporary.exact_record_reconciliation_required)

        committed = reconciliation_policy_v7(
            ApprovalPublicationKnowledgeV7.COMMITTED_CONFIRMED
        )
        self.assertEqual(
            committed.permitted_actions,
            (ApprovalRecoveryActionV7.FORWARD_RECOVERY_ONLY,),
        )
        self.assertTrue(committed.forward_recovery_permitted)
        self.assertFalse(committed.exact_record_reconciliation_required)

    def test_both_indeterminate_states_have_one_fail_closed_action(self) -> None:
        for knowledge in (
            ApprovalPublicationKnowledgeV7.
            TEMPORARY_PUBLICATION_INDETERMINATE,
            ApprovalPublicationKnowledgeV7.
            COMMITTED_PROMOTION_INDETERMINATE,
        ):
            with self.subTest(knowledge=knowledge.value):
                policy = reconciliation_policy_v7(knowledge)
                self.assertEqual(
                    policy.permitted_actions,
                    (
                        ApprovalRecoveryActionV7.
                        RECONCILE_EXACT_RECORD_RETAIN_LOCK,
                    ),
                )
                self.assertTrue(policy.lock_must_remain_held)
                self.assertFalse(policy.blind_rollback_permitted)
                self.assertFalse(policy.forward_recovery_permitted)
                self.assertTrue(policy.exact_record_reconciliation_required)

    def test_binding_adds_no_operation_receipt_or_activation_entrypoint(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        self.assertNotIn("ProductionLockLeaseBindingReceipt", self.source)
        self.assertNotIn("TemporaryActivationApprovalReceipt", self.source)
        self.assertNotIn("CommittedActivationApprovalReceipt", self.source)
        self.assertNotIn("ActivationApprovalRecord", self.source)
        self.assertNotIn("ACTIVATION_APPROVAL_PATH", self.source)

    def test_module_has_no_host_write_cli_or_generic_dispatch_boundary(self) -> None:
        forbidden_imports = {
            "argparse",
            "ctypes",
            "fcntl",
            "os",
            "pathlib",
            "socket",
            "subprocess",
            "sys",
        }
        imported = {
            alias.name.split(".")[0]
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint(forbidden_imports))
        forbidden_attributes = {
            "open",
            "unlink",
            "replace",
            "rename",
            "mkdir",
            "rmdir",
            "write_text",
            "write_bytes",
            "chmod",
            "chown",
            "flock",
            "system",
            "run",
            "popen",
            "dispatch",
        }
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id,
                        {"eval", "exec", "open", "getattr", "setattr"},
                    )
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden_attributes)
        for forbidden_text in (
            "systemctl",
            "aplay",
            "amixer",
            "/dev/snd",
            "/etc/alsa",
            "shell=True",
        ):
            self.assertNotIn(forbidden_text, self.source)


if __name__ == "__main__":
    unittest.main()
