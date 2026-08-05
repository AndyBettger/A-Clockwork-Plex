from __future__ import annotations

import ast
import json
import stat
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = ROOT / "scripts/stage_c_transaction/approval_record_plan_v7.py"

from stage_c_runtime_authority.approval_store import (
    APPROVAL_NAME,
    ApprovalStore,
    decode_record,
    encode_record,
)
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    canonical_json_bytes,
)
from scripts.stage_c_transaction.approval_authority_binding_v7 import (
    ApprovalAuthorityBindingV7,
    ApprovalHardwareContractV7,
    ApprovalPublicationKnowledgeV7,
)
from scripts.stage_c_transaction.approval_record_plan_v7 import (
    ApprovalObservedStateV7,
    CommittedApprovalRecordPlanV7,
    IndeterminateResolutionActionV7,
    TemporaryApprovalRecordPlanV7,
    classify_approval_record_v7,
    plan_committed_approval_v7,
    plan_temporary_approval_v7,
    resolve_indeterminate_approval_v7,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionIdentity,
)
from scripts.stage_c_transaction.snapshot_core import CURRENT_ALSA_DESTINATION


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


class StageCApprovalRecordPlanV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction = TransactionIdentity("stage-c21-record-plan")
        self.snapshot = SnapshotIdentity("stage-c21-record-plan-snapshot")
        self.package = PackageFingerprint(HASH_A)
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
        self.binding = ApprovalAuthorityBindingV7(
            transaction=self.transaction,
            snapshot=self.snapshot,
            package=self.package,
            production_lock_path=PRODUCTION_LOCK_PATH,
            lock_lease_id="stage-c21-record-plan-lease",
            lock_device=101,
            lock_inode=102,
            authoritative_transaction_path=str(
                Path(AUTHORITATIVE_TRANSACTION_ROOT) / self.transaction.value
            ),
            transaction_device=201,
            transaction_inode=202,
            selected_route_path=CURRENT_ALSA_DESTINATION,
            selected_route_device=301,
            selected_route_inode=302,
            selected_route_sha256=HASH_B,
            hardware=self.hardware,
            source_snapshot_complete=True,
            source_split_route_selected=True,
            source_exact_lock_owned=True,
            source_exact_transaction_verified=True,
        )
        self.temporary = plan_temporary_approval_v7(
            self.binding,
            created_at="2026-08-05T23:00:00Z",
        )
        self.committed = plan_committed_approval_v7(
            self.temporary,
            commit_manifest_sha256=HASH_F,
            committed_at="2026-08-05T23:01:00Z",
        )

    def test_temporary_plan_uses_the_canonical_runtime_schema_and_bytes(self) -> None:
        plan = self.temporary
        self.assertIsInstance(plan, TemporaryApprovalRecordPlanV7)
        self.assertIsInstance(plan.record, ActivationApprovalRecord)
        self.assertIs(plan.record.phase, ApprovalPhase.TEMPORARY)
        self.assertEqual(plan.record.transaction_id, self.transaction.value)
        self.assertEqual(plan.record.lock_lease_id, self.binding.lock_lease_id)
        self.assertEqual(plan.record.package_fingerprint, self.package.sha256)
        self.assertEqual(plan.record.active_route_sha256, HASH_B)
        self.assertIsNone(plan.record.commit_manifest_sha256)
        self.assertIsNone(plan.record.committed_at)
        self.assertEqual(plan.encoded_bytes, encode_record(plan.record))
        self.assertEqual(decode_record(plan.encoded_bytes), plan.record)
        self.assertEqual(plan.record_sha256, plan.record.record_sha256)
        self.assertEqual(len(plan.encoded_sha256), 64)

    def test_committed_plan_derives_only_from_the_exact_temporary_plan(self) -> None:
        plan = self.committed
        self.assertIsInstance(plan, CommittedApprovalRecordPlanV7)
        self.assertIs(plan.record.phase, ApprovalPhase.COMMITTED)
        self.assertEqual(plan.binding_sha256, self.temporary.binding_sha256)
        self.assertEqual(
            plan.temporary_record_sha256,
            self.temporary.record_sha256,
        )
        self.assertEqual(plan.record.created_at, self.temporary.record.created_at)
        self.assertEqual(plan.record.commit_manifest_sha256, HASH_F)
        self.assertEqual(plan.record.committed_at, "2026-08-05T23:01:00Z")
        self.assertNotEqual(plan.record_sha256, self.temporary.record_sha256)
        self.assertNotEqual(plan.encoded_bytes, self.temporary.encoded_bytes)
        self.assertEqual(decode_record(plan.encoded_bytes), plan.record)

    def test_invalid_timestamps_manifest_and_types_are_rejected(self) -> None:
        with self.assertRaises(Exception):
            plan_temporary_approval_v7(
                self.binding,
                created_at="not-a-timestamp",
            )
        with self.assertRaises(ValueError):
            plan_committed_approval_v7(
                self.temporary,
                commit_manifest_sha256="bad",
                committed_at="2026-08-05T23:01:00Z",
            )
        with self.assertRaises(Exception):
            plan_committed_approval_v7(
                self.temporary,
                commit_manifest_sha256=HASH_F,
                committed_at="not-a-timestamp",
            )
        with self.assertRaises(TypeError):
            plan_temporary_approval_v7(  # type: ignore[arg-type]
                object(),
                created_at="2026-08-05T23:00:00Z",
            )
        with self.assertRaises(TypeError):
            plan_committed_approval_v7(  # type: ignore[arg-type]
                object(),
                commit_manifest_sha256=HASH_F,
                committed_at="2026-08-05T23:01:00Z",
            )

    def test_exact_absent_temporary_and_committed_classification(self) -> None:
        absent = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=None,
        )
        self.assertIs(absent.state, ApprovalObservedStateV7.ABSENT)
        self.assertIsNone(absent.observed_record_sha256)

        temporary = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=self.temporary.encoded_bytes,
        )
        self.assertIs(
            temporary.state,
            ApprovalObservedStateV7.EXACT_TEMPORARY,
        )
        self.assertEqual(
            temporary.observed_record_sha256,
            self.temporary.record_sha256,
        )

        committed = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=self.committed.encoded_bytes,
        )
        self.assertIs(
            committed.state,
            ApprovalObservedStateV7.EXACT_COMMITTED,
        )
        self.assertEqual(
            committed.observed_record_sha256,
            self.committed.record_sha256,
        )

    def test_valid_but_noncanonical_or_different_record_is_mismatched(self) -> None:
        envelope = json.loads(self.temporary.encoded_bytes.decode("utf-8"))
        noncanonical = (
            json.dumps(envelope, indent=2, sort_keys=False).encode("utf-8")
            + b"\n"
        )
        self.assertEqual(decode_record(noncanonical), self.temporary.record)
        result = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=noncanonical,
        )
        self.assertIs(result.state, ApprovalObservedStateV7.MISMATCHED)
        self.assertEqual(
            result.observed_record_sha256,
            self.temporary.record_sha256,
        )
        self.assertNotEqual(
            result.observed_encoded_sha256,
            self.temporary.encoded_sha256,
        )

        other = self.temporary.record.promote(
            commit_manifest_sha256="0" * 64,
            committed_at="2026-08-05T23:02:00Z",
        )
        result = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=encode_record(other),
        )
        self.assertIs(result.state, ApprovalObservedStateV7.MISMATCHED)
        self.assertEqual(result.observed_record_sha256, other.record_sha256)

    def test_invalid_bytes_and_observation_error_are_distinct(self) -> None:
        invalid = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=b"not-json\n",
        )
        self.assertIs(invalid.state, ApprovalObservedStateV7.MISMATCHED)
        self.assertIsNone(invalid.observed_record_sha256)
        self.assertIsNotNone(invalid.observed_encoded_sha256)

        failure = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=None,
            observation_error="approval root unavailable",
        )
        self.assertIs(
            failure.state,
            ApprovalObservedStateV7.OBSERVATION_FAILURE,
        )
        self.assertEqual(failure.detail, "approval root unavailable")
        with self.assertRaises(ValueError):
            classify_approval_record_v7(
                self.temporary,
                self.committed,
                observed_raw=b"bytes",
                observation_error="also failed",
            )

    def test_disposable_store_bytes_classify_exactly_through_publish_and_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            root.chmod(0o700)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            store = ApprovalStore(root)
            approval_path = root / APPROVAL_NAME

            self.assertIs(
                classify_approval_record_v7(
                    self.temporary,
                    self.committed,
                    observed_raw=None,
                ).state,
                ApprovalObservedStateV7.ABSENT,
            )
            store.publish_new(self.temporary.record, lock_held=True)
            raw = approval_path.read_bytes()
            self.assertEqual(raw, self.temporary.encoded_bytes)
            self.assertIs(
                classify_approval_record_v7(
                    self.temporary,
                    self.committed,
                    observed_raw=raw,
                ).state,
                ApprovalObservedStateV7.EXACT_TEMPORARY,
            )

            store.replace_exact(
                self.temporary.record,
                self.committed.record,
                lock_held=True,
            )
            raw = approval_path.read_bytes()
            self.assertEqual(raw, self.committed.encoded_bytes)
            self.assertIs(
                classify_approval_record_v7(
                    self.temporary,
                    self.committed,
                    observed_raw=raw,
                ).state,
                ApprovalObservedStateV7.EXACT_COMMITTED,
            )

    def test_temporary_publication_uncertainty_resolves_only_absent_or_exact_temp(self) -> None:
        absent = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=None,
        )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            TEMPORARY_PUBLICATION_INDETERMINATE,
            absent,
        )
        self.assertIs(
            resolution.action,
            IndeterminateResolutionActionV7.
            EXACT_ROLLBACK_APPROVAL_ABSENT,
        )
        self.assertTrue(resolution.exact_rollback_permitted)
        self.assertFalse(resolution.forward_recovery_permitted)

        exact_temp = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=self.temporary.encoded_bytes,
        )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            TEMPORARY_PUBLICATION_INDETERMINATE,
            exact_temp,
        )
        self.assertIs(
            resolution.action,
            IndeterminateResolutionActionV7.CONTINUE_TEMPORARY_INSTALL,
        )
        self.assertFalse(resolution.exact_rollback_permitted)
        self.assertFalse(resolution.forward_recovery_permitted)

        exact_commit = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=self.committed.encoded_bytes,
        )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            TEMPORARY_PUBLICATION_INDETERMINATE,
            exact_commit,
        )
        self.assertIs(
            resolution.action,
            IndeterminateResolutionActionV7.
            RETAIN_LOCK_MANUAL_RECONCILIATION,
        )

    def test_commit_promotion_uncertainty_resolves_exact_temp_or_exact_commit(self) -> None:
        exact_temp = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=self.temporary.encoded_bytes,
        )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            COMMITTED_PROMOTION_INDETERMINATE,
            exact_temp,
        )
        self.assertIs(
            resolution.action,
            IndeterminateResolutionActionV7.
            EXACT_ROLLBACK_REMOVE_TEMPORARY,
        )
        self.assertTrue(resolution.exact_rollback_permitted)

        exact_commit = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=self.committed.encoded_bytes,
        )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            COMMITTED_PROMOTION_INDETERMINATE,
            exact_commit,
        )
        self.assertIs(
            resolution.action,
            IndeterminateResolutionActionV7.FORWARD_RECOVERY_ONLY,
        )
        self.assertFalse(resolution.exact_rollback_permitted)
        self.assertTrue(resolution.forward_recovery_permitted)

        absent = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=None,
        )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            COMMITTED_PROMOTION_INDETERMINATE,
            absent,
        )
        self.assertIs(
            resolution.action,
            IndeterminateResolutionActionV7.
            RETAIN_LOCK_MANUAL_RECONCILIATION,
        )

    def test_mismatch_or_observation_failure_never_pre_authorises_recovery(self) -> None:
        mismatched = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=canonical_json_bytes({"wrong": True}) + b"\n",
        )
        failure = classify_approval_record_v7(
            self.temporary,
            self.committed,
            observed_raw=None,
            observation_error="unreadable",
        )
        for knowledge in (
            ApprovalPublicationKnowledgeV7.
            TEMPORARY_PUBLICATION_INDETERMINATE,
            ApprovalPublicationKnowledgeV7.
            COMMITTED_PROMOTION_INDETERMINATE,
        ):
            for classification in (mismatched, failure):
                with self.subTest(
                    knowledge=knowledge.value,
                    state=classification.state.value,
                ):
                    resolution = resolve_indeterminate_approval_v7(
                        knowledge,
                        classification,
                    )
                    self.assertIs(
                        resolution.action,
                        IndeterminateResolutionActionV7.
                        RETAIN_LOCK_MANUAL_RECONCILIATION,
                    )
                    self.assertTrue(resolution.lock_must_remain_held)
                    self.assertFalse(resolution.exact_rollback_permitted)
                    self.assertFalse(resolution.forward_recovery_permitted)

    def test_plans_and_resolutions_are_frozen_and_use_one_module_identity(self) -> None:
        self.assertIs(
            self.temporary.record.__class__,
            ActivationApprovalRecord,
        )
        self.assertIs(
            self.committed.record.__class__,
            ActivationApprovalRecord,
        )
        with self.assertRaises(FrozenInstanceError):
            self.temporary.record_sha256 = "0" * 64  # type: ignore[misc]
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.
            COMMITTED_PROMOTION_INDETERMINATE,
            classify_approval_record_v7(
                self.temporary,
                self.committed,
                observed_raw=self.committed.encoded_bytes,
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            resolution.lock_must_remain_held = False  # type: ignore[misc]

    def test_module_has_no_store_write_cli_or_generic_dispatch_boundary(self) -> None:
        forbidden_imports = {
            "argparse",
            "ctypes",
            "fcntl",
            "os",
            "pathlib",
            "secrets",
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
            "replace_exact",
            "publish_new",
            "remove_exact",
            "rename",
            "mkdir",
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
            "ACTIVATION_APPROVAL_PATH",
        ):
            self.assertNotIn(forbidden_text, self.source)


if __name__ == "__main__":
    unittest.main()
