from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.approval_store import APPROVAL_NAME, ApprovalStore, decode_record, encode_record  # noqa: E402
from stage_c_runtime_authority.model import ActivationApprovalRecord, HardwareContract, RuntimeAuthorityError  # noqa: E402


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def record() -> ActivationApprovalRecord:
    contract = HardwareContract(
        package_fingerprint=digest("package"),
        split_route_sha256=digest("split"),
        direct_route_sha256=digest("direct"),
        camilladsp_config_sha256=digest("config"),
        camilladsp_binary_version="4.1.3",
        camilladsp_binary_sha256=digest("binary"),
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
    return ActivationApprovalRecord.temporary(
        transaction_id="stage-c21-transaction",
        lock_lease_id="stage-c21-lease",
        contract=contract,
        created_at="2026-08-05T19:30:00Z",
    )


class StageCRuntimeAuthorityApprovalStoreTests(unittest.TestCase):
    def test_record_round_trip_is_canonical_and_checksummed(self):
        original = record()
        encoded = encode_record(original)
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(decode_record(encoded), original)
        envelope = json.loads(encoded)
        self.assertEqual(envelope["record_sha256"], original.record_sha256)
        self.assertEqual(encoded, encode_record(original))

    def test_checksum_and_unknown_fields_fail_closed(self):
        original = record()
        envelope = json.loads(encode_record(original))
        envelope["record_sha256"] = digest("wrong")
        with self.assertRaises(RuntimeAuthorityError):
            decode_record(json.dumps(envelope).encode())
        envelope = json.loads(encode_record(original))
        envelope["record"]["unexpected"] = True
        with self.assertRaises(RuntimeAuthorityError):
            decode_record(json.dumps(envelope).encode())

    def test_publish_new_is_no_overwrite_and_no_follow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ApprovalStore(root)
            original = record()
            with self.assertRaises(RuntimeAuthorityError):
                store.publish_new(original, lock_held=False)
            store.publish_new(original, lock_held=True)
            self.assertEqual(store.read(), original)
            with self.assertRaises(RuntimeAuthorityError):
                store.publish_new(original, lock_held=True)
            approval = root / APPROVAL_NAME
            approval.unlink()
            approval.symlink_to(root / "elsewhere")
            with self.assertRaises((RuntimeAuthorityError, OSError)):
                store.read()

    def test_exact_exchange_promotion_and_rollback_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ApprovalStore(root)
            temporary = record()
            committed = temporary.promote(commit_manifest_sha256=digest("commit"), committed_at="2026-08-05T19:31:00Z")
            store.publish_new(temporary, lock_held=True)
            store.replace_exact(temporary, committed, lock_held=True)
            self.assertEqual(store.read(), committed)
            with self.assertRaises(RuntimeAuthorityError):
                store.remove_exact(temporary, lock_held=True)
            store.remove_exact(committed, lock_held=True)
            self.assertFalse((root / APPROVAL_NAME).exists())

    def test_interruption_after_exchange_restores_exact_temporary_record(self):
        points: list[str] = []

        def fail(point: str) -> None:
            points.append(point)
            if point == "replacement-exchanged":
                raise RuntimeError("injected interruption")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temporary = record()
            committed = temporary.promote(commit_manifest_sha256=digest("commit"), committed_at="2026-08-05T19:31:00Z")
            ApprovalStore(root).publish_new(temporary, lock_held=True)
            with self.assertRaisesRegex(RuntimeError, "injected interruption"):
                ApprovalStore(root, fault_hook=fail).replace_exact(temporary, committed, lock_held=True)
            self.assertEqual(ApprovalStore(root).read(), temporary)
            self.assertIn("replacement-exchanged", points)
            self.assertEqual([path.name for path in root.iterdir()], [APPROVAL_NAME])

    def test_interruption_after_new_link_keeps_public_record_and_cleans_private_name(self):
        def fail(point: str) -> None:
            if point == "new-linked":
                raise RuntimeError("injected interruption")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = record()
            with self.assertRaisesRegex(RuntimeError, "injected interruption"):
                ApprovalStore(root, fault_hook=fail).publish_new(original, lock_held=True)
            self.assertEqual(ApprovalStore(root).read(), original)
            self.assertEqual([path.name for path in root.iterdir()], [APPROVAL_NAME])


if __name__ == "__main__":
    unittest.main()
