from __future__ import annotations

import ast
import inspect
import subprocess
import unittest
from pathlib import Path

from scripts.stage_c_transaction import candidate_validation_rehearsal as engine
from scripts.stage_c_transaction import candidate_validation_rehearsal_adapter as adapter
from scripts.stage_c_transaction import production_adapter_contract as v1
from scripts.stage_c_transaction import production_adapter_lifecycle_v2 as v2


class StageCCandidateValidationRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.adapter_path = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "candidate_validation_rehearsal_adapter.py"
        )
        self.engine_path = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "candidate_validation_rehearsal.py"
        )
        self.wrapper_path = (
            self.repo
            / "scripts"
            / "test-stage-c-candidate-validation-rehearsal.sh"
        )
        self.adapter_source = self.adapter_path.read_text(encoding="utf-8")
        self.engine_source = self.engine_path.read_text(encoding="utf-8")
        self.wrapper_source = self.wrapper_path.read_text(encoding="utf-8")
        self.adapter_tree = ast.parse(self.adapter_source)
        self.engine_tree = ast.parse(self.engine_source)

    @staticmethod
    def function_node(tree: ast.AST, name: str) -> ast.FunctionDef:
        matches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if len(matches) != 1:
            raise AssertionError(f"expected one function named {name}; found {len(matches)}")
        return matches[0]

    @staticmethod
    def called_names(node: ast.AST) -> tuple[str, ...]:
        names: list[str] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            function = child.func
            if isinstance(function, ast.Name):
                names.append(function.id)
            elif isinstance(function, ast.Attribute):
                names.append(function.attr)
        return tuple(names)

    def test_exact_fifteen_v1_plus_abort_and_eighteen_blocked(self) -> None:
        expected = (
            v1.AdapterOperation.INSPECT_HOST_CONTRACT,
            v1.AdapterOperation.INSPECT_PRODUCTION_LOCK,
            v1.AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            v1.AdapterOperation.RELEASE_PRODUCTION_LOCK,
            v1.AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            v1.AdapterOperation.CAPTURE_FILESYSTEM_STATE,
            v1.AdapterOperation.CAPTURE_SERVICE_STATE,
            v1.AdapterOperation.CAPTURE_MIXER_STATE,
            v1.AdapterOperation.CAPTURE_LOOPBACK_STATE,
            v1.AdapterOperation.CAPTURE_DAC_STATE,
            v1.AdapterOperation.STAGE_CANDIDATE_FILES,
            v1.AdapterOperation.VALIDATE_CANDIDATE_ALSA,
            v1.AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
            v1.AdapterOperation.VALIDATE_CANDIDATE_UNITS,
            v1.AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
        )
        self.assertEqual(adapter.PERMITTED_V1_OPERATIONS, expected)
        self.assertEqual(len(adapter.PERMITTED_V1_OPERATIONS), 15)
        self.assertEqual(adapter.PERMITTED_V2_COUNT, 16)
        self.assertEqual(adapter.BLOCKED_V2_COUNT, 18)
        self.assertEqual(len(v2.ALL_OPERATIONS_V2), 34)
        self.assertEqual(
            len(set(v1.AdapterOperation).difference(expected)),
            18,
        )

    def test_adapter_extends_c15_and_v2_protocol(self) -> None:
        mro = adapter.CandidateValidationRehearsalAdapter.__mro__
        from scripts.stage_c_transaction.authoritative_snapshot_rehearsal_adapter import (
            AuthoritativeSnapshotRehearsalAdapter,
        )

        self.assertIn(AuthoritativeSnapshotRehearsalAdapter, mro)
        self.assertIn(v2.ProductionAdapterV2, mro)
        overrides = {
            name
            for name, value in adapter.CandidateValidationRehearsalAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            overrides,
            {
                "stage_candidate_files",
                "validate_candidate_alsa",
                "validate_candidate_sudoers",
                "validate_candidate_units",
                "validate_candidate_camilladsp",
                "abort_uncommitted_transaction",
            },
        )
        self.assertNotIn("execute", overrides)
        self.assertNotIn("dispatch", overrides)

    def test_candidate_and_validation_roots_are_fixed_and_not_caller_inputs(self) -> None:
        self.assertEqual(adapter.CANDIDATE_ROOT_NAME, "candidate-rootfs")
        self.assertEqual(adapter.VALIDATION_ROOT_NAME, "candidate-validation")
        signatures = {
            name: inspect.signature(
                getattr(adapter.CandidateValidationRehearsalAdapter, name)
            )
            for name in (
                "stage_candidate_files",
                "validate_candidate_alsa",
                "validate_candidate_sudoers",
                "validate_candidate_units",
                "validate_candidate_camilladsp",
                "abort_uncommitted_transaction",
            )
        }
        self.assertEqual(
            tuple(signatures["stage_candidate_files"].parameters),
            ("self", "transaction", "package"),
        )
        for name in (
            "validate_candidate_alsa",
            "validate_candidate_sudoers",
            "validate_candidate_units",
            "validate_candidate_camilladsp",
            "abort_uncommitted_transaction",
        ):
            self.assertEqual(
                tuple(signatures[name].parameters),
                ("self", "transaction"),
            )
        forbidden = {"path", "root", "destination", "command", "argv", "evidence_copy"}
        for signature in signatures.values():
            self.assertTrue(forbidden.isdisjoint(signature.parameters))

    def test_atomic_copy_is_double_hashed_root_owned_and_nonfollowing(self) -> None:
        node = self.function_node(self.adapter_tree, "_atomic_copy")
        source = ast.get_source_segment(self.adapter_source, node) or ""
        self.assertGreaterEqual(source.count("sha256(source)"), 2)
        self.assertIn("sha256(temporary)", source)
        self.assertIn("source_info.st_nlink != 1", source)
        self.assertIn("os.O_EXCL", source)
        self.assertIn("os.O_NOFOLLOW", source)
        self.assertIn("os.fchmod", source)
        self.assertIn("os.fchown", source)
        self.assertIn("os.fsync", source)
        self.assertIn("os.replace", source)
        self.assertIn("info.st_uid != 0", source)
        self.assertIn("info.st_gid != 0", source)
        self.assertIn("info.st_nlink != 1", source)

    def test_staging_is_transaction_confined_and_never_maps_production(self) -> None:
        node = self.function_node(self.adapter_tree, "stage_candidate_files")
        source = ast.get_source_segment(self.adapter_source, node) or ""
        self.assertIn("self.transaction_path / CANDIDATE_ROOT_NAME", source)
        self.assertIn("self._package_root / \"rootfs\"", source)
        self.assertIn("_atomic_copy", source)
        self.assertIn("EXPECTED_PACKAGE_FILES", source)
        self.assertIn("production_destination_writes\", \"0", source)
        for forbidden in (
            'Path("/etc")',
            'Path("/usr/local")',
            'Path("/var/lib/a-clockwork-plex/split-bus/activation-approved")',
            "copy2(source, Path(entry.destination))",
        ):
            self.assertNotIn(forbidden, source)

    def test_validator_commands_are_fixed_read_only_shapes(self) -> None:
        expected_markers = (
            '_run_fixed((aplay, "-L"), env=env)',
            '_run_fixed((visudo, "-cf", str(self._fixed_paths()["sudoers"])))',
            'analyzer,\n                    "verify"',
            'str(paths["binary"]), "--check", str(paths["camilla_config"])',
            'env["ALSA_CONFIG_PATH"] = str(config)',
            'env["SYSTEMD_UNIT_PATH"] = str(unit_dir)',
        )
        for marker in expected_markers:
            self.assertIn(marker, self.adapter_source)
        run_node = self.function_node(self.adapter_tree, "_run_fixed")
        run_source = ast.get_source_segment(self.adapter_source, run_node) or ""
        self.assertIn("capture_output=True", run_source)
        self.assertIn("text=True", run_source)
        self.assertIn("check=False", run_source)
        self.assertIn("timeout=30", run_source)
        self.assertNotIn("shell=", run_source)

    def test_unit_validation_uses_private_copies_and_inert_execstart(self) -> None:
        node = self.function_node(self.adapter_tree, "validate_candidate_units")
        source = ast.get_source_segment(self.adapter_source, node) or ""
        self.assertIn('"ExecStart=/bin/true"', source)
        self.assertIn('if not line.startswith(("User=", "Group="))', source)
        self.assertIn('env["SYSTEMD_UNIT_PATH"] = str(unit_dir)', source)
        self.assertIn('"systemd-analyze.txt"', source)
        self.assertNotIn("systemctl", source)
        contract = self.function_node(self.adapter_tree, "_unit_contract")
        contract_source = ast.get_source_segment(self.adapter_source, contract) or ""
        self.assertIn("ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved", contract_source)
        self.assertIn("compile(helper", contract_source)
        self.assertIn("stage-c1-candidate-only", contract_source)
        self.assertIn("return 78", contract_source)

    def test_adapter_has_no_service_mixer_module_or_audio_mutation_command(self) -> None:
        for marker in (
            "shell=True",
            "os.system",
            "systemctl",
            "amixer",
            "modprobe",
            "aplay -D",
            "speaker-test",
            "alsactl restore",
            "activation-approved).write",
            "install_managed_files(",
            "select_split_bus_route(",
            "start_managed_stage_c_services(",
        ):
            self.assertNotIn(marker, self.adapter_source)
        subprocess_calls = [
            node
            for node in ast.walk(self.adapter_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        self.assertEqual(len(subprocess_calls), 1)
        enclosing = self.function_node(self.adapter_tree, "_run_fixed")
        self.assertIn(subprocess_calls[0], list(ast.walk(enclosing)))

    def test_abort_retains_evidence_then_reuses_physically_proved_c15_abort(self) -> None:
        node = self.function_node(self.adapter_tree, "abort_uncommitted_transaction")
        source = ast.get_source_segment(self.adapter_source, node) or ""
        self.assertEqual(tuple(inspect.signature(
            adapter.CandidateValidationRehearsalAdapter.abort_uncommitted_transaction
        ).parameters), ("self", "transaction"))
        self.assertIn('review_copy = self._evidence_root / "candidate-review-copy"', source)
        self.assertIn('transaction_copy = self._evidence_root / "transaction-rehearsal-copy"', source)
        self.assertLess(source.index("shutil.copytree"), source.index("_remove_regular_tree"))
        self.assertLess(
            source.index("_remove_regular_tree"),
            source.index("super().abort_uncommitted_transaction"),
        )
        self.assertIn("AbortUncommittedTransactionReceipt", source)
        self.assertIn('state="aborted-before-mutation"', source)
        self.assertIn("mutation_started=False", source)
        self.assertIn("committed=False", source)

    def test_engine_has_exact_twenty_nine_checks_and_eighteen_refusals(self) -> None:
        self.assertEqual(len(engine.EXPECTED_CHECKS), 29)
        self.assertEqual(
            engine.EXPECTED_CHECKS,
            (
                "root-scope",
                "input-replay",
                "protocol-conformance",
                "pre-lock-host-contract",
                "pre-lock-boundary",
                "production-lock-acquired",
                "authoritative-transaction-created",
                "transaction-identity-binding",
                "filesystem-snapshot",
                "service-snapshot",
                "mixer-snapshot",
                "loopback-snapshot",
                "dac-snapshot",
                "snapshot-integrity",
                "candidate-staging",
                "candidate-manifest-binding",
                "candidate-alsa-validation",
                "candidate-sudoers-validation",
                "candidate-unit-validation",
                "candidate-camilladsp-validation",
                "blocked-operation-boundary",
                "pre-mutation-boundary",
                "candidate-evidence-copy",
                "transaction-abort-v2",
                "exact-transaction-cleanup",
                "production-lock-released",
                "input-integrity",
                "evidence-integrity",
                "activation-interface",
            ),
        )
        prove = self.function_node(self.engine_tree, "prove_blocked_operations")
        prove_source = ast.get_source_segment(self.engine_source, prove) or ""
        self.assertEqual(prove_source.count("_expect_blocked("), 18)
        self.assertIn("STOP_CAPTURED_APPLICATION_SERVICES", prove_source)
        self.assertIn("VERIFY_EXACT_ROLLBACK", prove_source)

    def test_blocked_calls_exist_only_inside_blocked_proof(self) -> None:
        blocked_methods = {
            "stop_captured_application_services",
            "verify_dac_released",
            "install_managed_files",
            "reload_systemd",
            "select_split_bus_route",
            "start_managed_stage_c_services",
            "stop_managed_stage_c_services",
            "verify_split_bus_health",
            "run_finite_music_probe",
            "run_finite_alarm_probe",
            "restore_captured_application_services",
            "verify_dashboard_health",
            "write_commit_manifest",
            "select_direct_failback_route",
            "restore_exact_snapshot",
            "restore_mixer_state",
            "restore_service_state",
            "verify_exact_rollback",
        }
        functions = {
            node.name: node
            for node in ast.walk(self.engine_tree)
            if isinstance(node, ast.FunctionDef)
        }
        for name, node in functions.items():
            calls = set(self.called_names(node))
            if name == "prove_blocked_operations":
                self.assertEqual(blocked_methods.intersection(calls), blocked_methods)
            else:
                self.assertTrue(
                    blocked_methods.isdisjoint(calls),
                    f"blocked operation leaked into {name}",
                )

    def test_engine_has_no_direct_process_lock_service_or_audio_boundary(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.engine_tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {"fcntl", "requests", "shlex", "socket", "subprocess", "urllib"}.isdisjoint(imported)
        )
        calls = set(self.called_names(self.engine_tree))
        self.assertTrue(
            {"open", "flock", "system", "run", "Popen"}.isdisjoint(calls)
        )
        for marker in (
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
            "camilladsp --check",
            "--activate",
            "--install",
            "--rollback",
            "--failback",
            "--uninstall",
        ):
            self.assertNotIn(marker, self.engine_source)

    def test_stage_c15_replay_is_exact_and_non_reusable(self) -> None:
        node = self.function_node(self.engine_tree, "validate_stage_c15")
        source = ast.get_source_segment(self.engine_source, node) or ""
        self.assertIn("STAGE_C15_CHECKS", source)
        self.assertIn("len(blocked) != 23", source)
        self.assertIn('identity.get("committed") != "false"', source)
        self.assertIn('identity.get("reusable_after_abort") != "false"', source)
        self.assertIn('root / "transaction-rehearsal-copy"', source)
        self.assertIn("_validate_evidence_manifest", source)

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
            'REQUIRED_CONFIRMATION="STAGE-C16-CANDIDATE-STAGE-VALIDATE-ABORT"',
            self.wrapper_source,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.wrapper_source)
        self.assertIn('PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts"', self.wrapper_source)
        self.assertIn(
            "-m stage_c_transaction.candidate_validation_rehearsal",
            self.wrapper_source,
        )
        self.assertIn(
            "/var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.wg3sxB",
            self.wrapper_source,
        )
        for forbidden in ("--activate", "--install", "--rollback", "--failback", "--uninstall"):
            self.assertNotIn(forbidden, self.wrapper_source)


if __name__ == "__main__":
    unittest.main()
