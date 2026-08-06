from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_transaction import stage_c22_evidence_identity as identity


class StageC22EvidenceIdentityTests(unittest.TestCase):
    def test_expected_contract_contains_exactly_41_checks(self) -> None:
        self.assertEqual(len(identity.STAGE_C22_EXPECTED_CHECKS), 41)
        self.assertEqual(identity.STAGE_C22_EXPECTED_CHECKS[0], "root-scope")
        self.assertEqual(
            identity.STAGE_C22_EXPECTED_CHECKS[-1], "activation-interface"
        )

    def test_results_require_exact_order_and_pass_state(self) -> None:
        rows = [
            {"check": check, "result": "PASS", "detail": "accepted"}
            for check in identity.STAGE_C22_EXPECTED_CHECKS
        ]
        identity.validate_results(rows)

        reversed_rows = list(reversed(rows))
        with self.assertRaisesRegex(SystemExit, "exact 41 checks"):
            identity.validate_results(reversed_rows)

        rows[10] = {**rows[10], "result": "FAIL"}
        with self.assertRaisesRegex(SystemExit, "non-PASS"):
            identity.validate_results(rows)

    def test_input_binding_is_exact(self) -> None:
        binding = {
            "package_root": str(identity.ACCEPTED_PACKAGE_ROOT),
            "package_fingerprint": identity.ACCEPTED_PACKAGE_FINGERPRINT,
            "baseline_root": str(identity.ACCEPTED_BASELINE_ROOT),
            "stage_c21_root": str(identity.ACCEPTED_STAGE_C21_ROOT),
            "stage_c21_manifest_sha256": (
                identity.ACCEPTED_STAGE_C21_MANIFEST_SHA256
            ),
            "package_files": "28",
            "package_payload_files": "27",
        }
        identity.validate_input_binding(binding)
        binding["package_files"] = "27"
        with self.assertRaisesRegex(SystemExit, "package_files"):
            identity.validate_input_binding(binding)

    def test_restored_identity_is_required(self) -> None:
        restored = {
            "transaction": "stage-c22-service-rehearsal-install-0123456789abcdef",
            "snapshot": "stage-c22-service-rehearsal-snapshot-0123456789abcdef",
            "action": "install",
            "package_sha256": identity.ACCEPTED_PACKAGE_FINGERPRINT,
            "lease_id": "stage-c14-lock-0123456789abcdef",
            "caller_supplied": "false",
            "candidate_production_authoritative": "false",
            "mutation_started": "true",
            "restored": "true",
            "committed": "false",
            "reusable_for_activation": "false",
            "reusable_for_rollback": "false",
        }
        identity.validate_identity(restored)
        restored["restored"] = "false"
        with self.assertRaisesRegex(SystemExit, "restored"):
            identity.validate_identity(restored)

    def test_report_requires_restored_closed_state_and_no_interface(self) -> None:
        report = "\n".join(identity.REPORT_MARKERS)
        identity.validate_report(report)
        with self.assertRaisesRegex(SystemExit, "report contract"):
            identity.validate_report(
                report.replace(identity.REPORT_MARKERS[-1], "")
            )

    def test_only_exact_accepted_path_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(SystemExit, "exact retained evidence root"):
                identity.inspect_stage_c22_evidence(Path(temporary))

    def test_python_inspector_contains_no_mutation_interface(self) -> None:
        source = Path(identity.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "systemctl",
            "sudo",
            "os.chmod",
            "os.chown",
            "os.unlink",
            "os.remove",
            "os.rename",
            "os.replace",
            "mkdir(",
            "write_text(",
            "write_bytes(",
            "install-master-eq.sh",
        ):
            self.assertNotIn(forbidden, source)

    def test_shell_wrapper_is_argumentless_and_unprivileged(self) -> None:
        wrapper = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "inspect-stage-c22-evidence-identity.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("if (($#)); then", wrapper)
        self.assertIn("stage_c22_evidence_identity", wrapper)
        self.assertNotIn("sudo", wrapper)
        self.assertNotIn("systemctl", wrapper)
        self.assertNotIn("amixer", wrapper)
        self.assertNotIn("fuser", wrapper)


if __name__ == "__main__":
    unittest.main()
