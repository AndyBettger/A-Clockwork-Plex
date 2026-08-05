from __future__ import annotations

import ast
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "prepare-stage-c-install-transaction.sh"
MODULES = (
    ROOT / "scripts" / "stage_c_transaction" / "package_review.py",
    ROOT / "scripts" / "stage_c_transaction" / "host_review.py",
    ROOT / "scripts" / "stage_c_transaction" / "plans.py",
    ROOT / "scripts" / "stage_c_transaction" / "prepare.py",
)


def source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in MODULES)


class StageCInstallTransactionSafetyTests(unittest.TestCase):
    def test_wrapper_has_valid_shell_syntax_and_disables_bytecode(self):
        result = subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", text)
        self.assertIn("python3 -B", text)

    def test_python_modules_compile(self):
        for path in MODULES:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_no_activation_interface_or_confirmation_token_exists(self):
        combined = WRAPPER.read_text(encoding="utf-8") + source()
        self.assertNotIn('add_argument("--activate"', combined)
        self.assertNotIn('add_argument("--confirm"', combined)
        self.assertNotIn("STAGE-C2-", combined)
        self.assertIn("There is no activation mode", combined)
        self.assertIn("No activation path exists", combined)

    def test_executable_paths_are_read_only(self):
        text = source()
        self.assertNotIn('run(["sudo"', text)
        self.assertNotIn('run(["modprobe"', text)
        self.assertNotIn('run(["aplay"', text)
        self.assertNotIn('"systemctl", "start"', text)
        self.assertNotIn('"systemctl", "stop"', text)
        self.assertNotIn('"systemctl", "restart"', text)
        self.assertNotIn('"systemctl", "enable"', text)
        self.assertNotIn('"systemctl", "disable"', text)
        self.assertNotIn('"amixer", "-c", "Pro", "sset"', text)
        self.assertNotIn('"amixer", "-c", "Pro", "set"', text)
        for allowed in (
            'run(["systemctl", "show"',
            'run(["systemctl", "is-active"',
            'run(["systemctl", "is-enabled"',
            'run(["amixer", "-c", "Pro", "sget"',
            'run(["fuser"',
        ):
            self.assertIn(allowed, text)

    def test_current_host_contract_is_exact(self):
        text = source()
        self.assertIn(
            'EXPECTED_PRE_STAGE_C_ALSA_SHA256 = "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"',
            text,
        )
        for expected in ('"index": "7"', '"id": "ACP_Loopback"', '"pcm_substreams": "2"', '"pcm_notify": "1"'):
            self.assertIn(expected, text)
        self.assertIn('slave.pcm "acp_master"', text)
        self.assertIn("Unexpected Stage C approval marker", text)
        self.assertIn("Unexpected running CamillaDSP process", text)

    def test_stage_c1_package_is_replayed_not_blindly_trusted(self):
        text = source()
        for expected in (
            "parse_manifest",
            "validate_stage_c1_evidence",
            "Package checksum mismatch",
            "Package mode mismatch",
            "Stage C1 package file count mismatch",
            "Stage C1 manifest omitted the empty split-bus state directory",
            "Stage C1 manifest contains Python cache material",
            "Generated route helper is not the inert Stage C1 candidate",
            "Generated unit lacks the approval-marker gate",
            "Package version: 2",
        ):
            self.assertIn(expected, text)

    def test_destination_conflicts_are_a_hard_gate(self):
        text = source()
        self.assertIn("write_destination_state", text)
        self.assertIn("Destination conflict gate failed", text)
        self.assertIn("managed file destinations absent", text)
        self.assertNotIn("overwrite existing", text.lower())

    def test_service_boundary_is_pinned_to_discovery(self):
        text = source()
        self.assertIn('("loaded", "active", "enabled")', text)
        self.assertIn('load_state != "not-found" or enabled != "not-found"', text)
        self.assertIn("Unexpected pre-existing Stage C service", text)

    def test_review_snapshot_records_all_state_domains(self):
        text = source()
        for expected in (
            "review-snapshot",
            "absence-markers",
            "filesystem-state.tsv",
            "service-state.tsv",
            "mixer-state.tsv",
            "module-dac-state.tsv",
            "dac-hw-params.txt",
            "package-fingerprint.tsv",
        ):
            self.assertIn(expected, text)
        for control in (
            "A Clockwork Master",
            "A Clockwork Plexamp",
            "A Clockwork AirPlay",
            "A Clockwork Alarm",
        ):
            self.assertIn(control, text)

    def test_exact_rollback_contract_is_explicit(self):
        text = source()
        for expected in (
            "rollback-obligations.tsv",
            "restore original file or exact absence marker",
            "restore exact enabled states",
            "restore loaded and persistence state exactly",
            "restore all four captured control percentages",
            "zero rollback mismatches",
            "Report rollback success only when the mismatch count is zero",
        ):
            self.assertIn(expected, text)

    def test_review_snapshot_is_never_activation_authoritative(self):
        text = source()
        self.assertIn("never reuse this Stage C2 review snapshot", text)
        self.assertIn("must be repeated immediately at activation time", text)
        self.assertIn("review only", text.lower())

    def test_activation_blockers_cover_runtime_eq_health_and_failure_proof(self):
        text = source()
        for expected in (
            "transactional mutation logic",
            "activation-time snapshot/rollback",
            "automatic direct failback",
            "migrate the EQ helper",
            "dashboard diagnostics",
            "deliberate CamillaDSP failure",
            "explicit user authorisation",
        ):
            self.assertIn(expected, text)

    def test_source_has_no_hidden_dynamic_execution(self):
        for path in MODULES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"eval", "exec", "compile"}
            ]
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
