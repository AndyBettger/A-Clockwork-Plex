from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_transaction import stage_c23_evidence_identity as identity


class StageC23EvidenceIdentityTests(unittest.TestCase):
    def test_expected_contract_contains_exactly_47_checks(self) -> None:
        self.assertEqual(len(identity.STAGE_C23_EXPECTED_CHECKS), 47)
        self.assertEqual(identity.STAGE_C23_EXPECTED_CHECKS[0], "root-scope")
        self.assertEqual(
            identity.STAGE_C23_EXPECTED_CHECKS[-1], "activation-interface"
        )

    def test_results_require_exact_order_and_pass_state(self) -> None:
        rows = [
            {"check": check, "result": "PASS", "detail": "accepted"}
            for check in identity.STAGE_C23_EXPECTED_CHECKS
        ]
        identity.validate_results(rows)

        with self.assertRaisesRegex(SystemExit, "exact 47 checks"):
            identity.validate_results(list(reversed(rows)))

        rows[29] = {**rows[29], "result": "FAIL"}
        with self.assertRaisesRegex(SystemExit, "non-PASS"):
            identity.validate_results(rows)

    def test_input_binding_is_exact(self) -> None:
        binding = {
            "package_root": str(identity.ACCEPTED_PACKAGE_ROOT),
            "package_fingerprint": identity.ACCEPTED_PACKAGE_FINGERPRINT,
            "baseline_root": str(identity.ACCEPTED_BASELINE_ROOT),
            "stage_c21_root": str(identity.ACCEPTED_STAGE_C21_ROOT),
            "stage_c22_root": str(identity.ACCEPTED_STAGE_C22_ROOT),
            "stage_c22_manifest_sha256": (
                identity.ACCEPTED_STAGE_C22_MANIFEST_SHA256
            ),
            "stage_c22_manifest_rows": "140",
            "stage_c22_manifest_entries": "139",
            "package_files": "28",
            "package_payload_files": "27",
        }
        identity.validate_input_binding(binding)
        binding["stage_c22_manifest_entries"] = "138"
        with self.assertRaisesRegex(SystemExit, "stage_c22_manifest_entries"):
            identity.validate_input_binding(binding)

    def test_exact_rollback_identity_is_required(self) -> None:
        restored = {
            "transaction": (
                "stage-c23-managed-file-rollback-install-0123456789abcdef"
            ),
            "snapshot": (
                "stage-c23-managed-file-rollback-snapshot-0123456789abcdef"
            ),
            "action": "install",
            "package_sha256": identity.ACCEPTED_PACKAGE_FINGERPRINT,
            "lease_id": "stage-c14-lock-0123456789abcdef",
            "host": "plexamp-bedroom",
            "architecture": "aarch64",
            "invoking_user": "andy",
            "caller_supplied": "false",
            "mutation_started": "true",
            "managed_files_installed": "true",
            "filesystem_restored": "true",
            "services_restored": "true",
            "systemd_reloaded": "false",
            "route_selected": "false",
            "committed": "false",
            "reusable_for_activation": "false",
            "reusable_for_rollback": "false",
        }
        identity.validate_identity(restored)
        restored["filesystem_restored"] = "false"
        with self.assertRaisesRegex(SystemExit, "filesystem_restored"):
            identity.validate_identity(restored)

    def test_report_requires_closed_state_and_blocked_activation(self) -> None:
        report = "\n".join(identity.REPORT_MARKERS)
        identity.validate_report(report)
        with self.assertRaisesRegex(SystemExit, "report contract"):
            identity.validate_report(
                report.replace(identity.REPORT_MARKERS[-1], "")
            )

    def test_frozen_manifest_digest_and_rows_are_exact(self) -> None:
        self.assertEqual(
            identity.ACCEPTED_STAGE_C23_MANIFEST_SHA256,
            "e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a",
        )
        self.assertEqual(identity.ACCEPTED_STAGE_C23_MANIFEST_ROWS, 144)

    def test_only_exact_accepted_path_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(SystemExit, "exact retained evidence root"):
                identity.inspect_stage_c23_evidence(Path(temporary))

    def test_python_inspector_contains_no_mutation_interface(self) -> None:
        source = Path(identity.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "systemctl",
            "os.system",
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
            / "inspect-stage-c23-evidence-identity.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("if (($#)); then", wrapper)
        self.assertIn("stage_c23_evidence_identity", wrapper)
        self.assertNotIn("sudo", wrapper)
        self.assertNotIn("systemctl", wrapper)
        self.assertNotIn("amixer", wrapper)
        self.assertNotIn("fuser", wrapper)


if __name__ == "__main__":
    unittest.main()
