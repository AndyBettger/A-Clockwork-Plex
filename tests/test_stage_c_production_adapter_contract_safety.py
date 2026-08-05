from __future__ import annotations

import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.stage_c_transaction import production_adapter_contract as contract


class StageCProductionAdapterContractSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.module = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "production_adapter_contract.py"
        )
        self.source = self.module.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @staticmethod
    def _service_snapshot() -> contract.ServiceSnapshot:
        return contract.ServiceSnapshot(
            tuple(
                contract.ServiceState(
                    unit=unit,
                    load=contract.ServiceLoadState.LOADED,
                    active=contract.ServiceActiveState.ACTIVE,
                    enabled=contract.ServiceEnableState.ENABLED,
                )
                for unit in contract.ServiceUnit
            )
        )

    def test_module_has_no_execution_or_entrypoint_imports(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        forbidden = {
            "argparse",
            "fcntl",
            "os",
            "pathlib",
            "requests",
            "shlex",
            "shutil",
            "socket",
            "subprocess",
            "urllib",
        }
        self.assertTrue(forbidden.isdisjoint(imported))
        self.assertNotIn("if __name__", self.source)
        self.assertNotIn("def main(", self.source)
        self.assertNotIn("REQUIRED_CONFIRMATION", self.source)
        self.assertNotIn("--confirm", self.source)
        self.assertNotIn("shell=True", self.source)

    def test_no_generic_command_or_dispatch_escape_hatch_exists(self) -> None:
        forbidden_names = {
            "command",
            "execute",
            "execute_command",
            "run",
            "run_command",
            "spawn",
            "popen",
        }
        methods = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(forbidden_names.isdisjoint(methods))
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called = node.func.id.lower()
            elif isinstance(node.func, ast.Attribute):
                called = node.func.attr.lower()
            else:
                continue
            self.assertNotIn(called, {"eval", "exec", "system", "popen"})

    def test_fixed_production_paths_have_no_caller_override(self) -> None:
        self.assertEqual(
            contract.PRODUCTION_LOCK_PATH,
            "/run/lock/a-clockwork-plex-audio-route.lock",
        )
        self.assertEqual(
            contract.AUTHORITATIVE_TRANSACTION_ROOT,
            "/var/lib/a-clockwork-plex/split-bus/transactions",
        )
        dataclass_fields = {
            field.name
            for item in (
                contract.PackageFingerprint,
                contract.TransactionIdentity,
                contract.SnapshotIdentity,
                contract.AdapterResult,
                contract.ServiceState,
                contract.ServiceSnapshot,
                contract.MixerSnapshot,
                contract.LoopbackContract,
                contract.DacContract,
            )
            for field in getattr(item, "__dataclass_fields__", {}).values()
        }
        self.assertTrue(
            {"path", "root", "command", "argv", "unit_name", "control_name"}.isdisjoint(
                dataclass_fields
            )
        )

    def test_service_and_mixer_boundaries_are_exact_enums(self) -> None:
        self.assertEqual(
            tuple(item.value for item in contract.ServiceUnit),
            contract.EXPECTED_SERVICE_UNITS,
        )
        self.assertEqual(
            tuple(item.value for item in contract.MixerControl),
            contract.EXPECTED_MIXER_CONTROLS,
        )
        self.assertEqual(len(contract.ServiceUnit), 6)
        self.assertEqual(len(contract.MixerControl), 4)

    def test_loopback_and_dac_contracts_match_physical_discovery(self) -> None:
        self.assertEqual(
            contract.LOOPBACK_CONTRACT,
            contract.LoopbackContract(
                module="snd_aloop",
                card_index=7,
                card_id="ACP_Loopback",
                pcm_substreams=2,
                pcm_notify=1,
            ),
        )
        self.assertEqual(
            contract.DAC_CONTRACT,
            contract.DacContract(
                sample_format="S16_LE",
                channels=2,
                rate=44100,
                period_size=1024,
                buffer_size=8192,
            ),
        )

    def test_operation_vocabulary_is_complete_and_partitioned_once(self) -> None:
        operations = tuple(contract.AdapterOperation)
        self.assertEqual(len(operations), 33)
        self.assertEqual(len(contract.READ_ONLY_OPERATIONS), 17)
        self.assertEqual(len(contract.MUTATING_OPERATIONS), 16)
        self.assertEqual(
            set(contract.READ_ONLY_OPERATIONS).union(contract.MUTATING_OPERATIONS),
            set(operations),
        )
        self.assertTrue(
            set(contract.READ_ONLY_OPERATIONS).isdisjoint(
                contract.MUTATING_OPERATIONS
            )
        )
        self.assertEqual(
            contract.MUTATING_OPERATIONS,
            tuple(
                operation
                for operation in operations
                if operation not in contract.READ_ONLY_OPERATIONS
            ),
        )

    def test_protocol_and_blocked_adapter_expose_the_same_public_operations(self) -> None:
        protocol_methods = {
            name
            for name, value in contract.ProductionAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        adapter_methods = {
            name
            for name, value in contract.BlockedProductionAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(protocol_methods, adapter_methods)
        self.assertEqual(len(protocol_methods), len(contract.AdapterOperation))
        self.assertNotIn("execute", protocol_methods)
        self.assertNotIn("run", protocol_methods)
        self.assertNotIn("explicit_uninstall", protocol_methods)
        self.assertIn(
            contract.TransactionAction.EXPLICIT_UNINSTALL,
            tuple(contract.TransactionAction),
        )

    def test_every_typed_operation_fails_closed_with_its_exact_identity(self) -> None:
        adapter = contract.BlockedProductionAdapter()
        transaction = contract.TransactionIdentity("stage-c10-test")
        snapshot = contract.SnapshotIdentity("stage-c10-snapshot")
        package = contract.PackageFingerprint("0" * 64)
        services = self._service_snapshot()
        mixer = contract.MixerSnapshot(50, 50, 50, 50)

        calls = (
            ("inspect_host_contract", (), contract.AdapterOperation.INSPECT_HOST_CONTRACT),
            ("inspect_production_lock", (), contract.AdapterOperation.INSPECT_PRODUCTION_LOCK),
            ("acquire_production_lock", (), contract.AdapterOperation.ACQUIRE_PRODUCTION_LOCK),
            ("release_production_lock", (), contract.AdapterOperation.RELEASE_PRODUCTION_LOCK),
            (
                "create_authoritative_transaction",
                (contract.TransactionAction.INSTALL, package),
                contract.AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            ),
            (
                "capture_filesystem_state",
                (transaction,),
                contract.AdapterOperation.CAPTURE_FILESYSTEM_STATE,
            ),
            (
                "capture_service_state",
                (transaction,),
                contract.AdapterOperation.CAPTURE_SERVICE_STATE,
            ),
            (
                "capture_mixer_state",
                (transaction,),
                contract.AdapterOperation.CAPTURE_MIXER_STATE,
            ),
            (
                "capture_loopback_state",
                (transaction,),
                contract.AdapterOperation.CAPTURE_LOOPBACK_STATE,
            ),
            (
                "capture_dac_state",
                (transaction,),
                contract.AdapterOperation.CAPTURE_DAC_STATE,
            ),
            (
                "stage_candidate_files",
                (transaction, package),
                contract.AdapterOperation.STAGE_CANDIDATE_FILES,
            ),
            (
                "validate_candidate_alsa",
                (transaction,),
                contract.AdapterOperation.VALIDATE_CANDIDATE_ALSA,
            ),
            (
                "validate_candidate_sudoers",
                (transaction,),
                contract.AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
            ),
            (
                "validate_candidate_units",
                (transaction,),
                contract.AdapterOperation.VALIDATE_CANDIDATE_UNITS,
            ),
            (
                "validate_candidate_camilladsp",
                (transaction,),
                contract.AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
            ),
            (
                "stop_captured_application_services",
                (transaction, services),
                contract.AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            ),
            (
                "verify_dac_released",
                (transaction,),
                contract.AdapterOperation.VERIFY_DAC_RELEASED,
            ),
            (
                "install_managed_files",
                (transaction,),
                contract.AdapterOperation.INSTALL_MANAGED_FILES,
            ),
            ("reload_systemd", (transaction,), contract.AdapterOperation.RELOAD_SYSTEMD),
            (
                "select_split_bus_route",
                (transaction,),
                contract.AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
            ),
            (
                "start_managed_stage_c_services",
                (transaction,),
                contract.AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
            ),
            (
                "stop_managed_stage_c_services",
                (transaction,),
                contract.AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
            ),
            (
                "verify_split_bus_health",
                (transaction,),
                contract.AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
            ),
            (
                "run_finite_music_probe",
                (transaction,),
                contract.AdapterOperation.RUN_FINITE_MUSIC_PROBE,
            ),
            (
                "run_finite_alarm_probe",
                (transaction,),
                contract.AdapterOperation.RUN_FINITE_ALARM_PROBE,
            ),
            (
                "restore_captured_application_services",
                (transaction, services),
                contract.AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
            ),
            (
                "verify_dashboard_health",
                (transaction,),
                contract.AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            ),
            (
                "write_commit_manifest",
                (transaction,),
                contract.AdapterOperation.WRITE_COMMIT_MANIFEST,
            ),
            (
                "select_direct_failback_route",
                (transaction,),
                contract.AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
            ),
            (
                "restore_exact_snapshot",
                (transaction, snapshot),
                contract.AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            ),
            (
                "restore_mixer_state",
                (transaction, mixer),
                contract.AdapterOperation.RESTORE_MIXER_STATE,
            ),
            (
                "restore_service_state",
                (transaction, services),
                contract.AdapterOperation.RESTORE_SERVICE_STATE,
            ),
            (
                "verify_exact_rollback",
                (transaction, snapshot),
                contract.AdapterOperation.VERIFY_EXACT_ROLLBACK,
            ),
        )
        self.assertEqual(len(calls), len(contract.AdapterOperation))
        for method_name, arguments, operation in calls:
            with self.subTest(operation=operation.value):
                with self.assertRaises(contract.ProductionAdapterBlocked) as raised:
                    getattr(adapter, method_name)(*arguments)
                self.assertIs(raised.exception.operation, operation)
                self.assertIn(operation.value, str(raised.exception))

    def test_contract_records_are_frozen_and_mixer_values_are_bounded(self) -> None:
        package = contract.PackageFingerprint("1" * 64)
        with self.assertRaises(FrozenInstanceError):
            package.sha256 = "2" * 64  # type: ignore[misc]
        for values in ((-1, 50, 50, 50), (50, 101, 50, 50), (True, 50, 50, 50)):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    contract.MixerSnapshot(*values)

    def test_contract_snapshot_is_static_and_explicitly_blocked(self) -> None:
        snapshot = dict(contract.contract_snapshot())
        self.assertEqual(snapshot["status"], "blocked")
        self.assertEqual(snapshot["production_lock"], contract.PRODUCTION_LOCK_PATH)
        self.assertEqual(
            snapshot["transaction_root"],
            contract.AUTHORITATIVE_TRANSACTION_ROOT,
        )
        self.assertEqual(snapshot["activation_interface"], "absent")
        self.assertEqual(
            snapshot["operations"].split(","),
            [operation.value for operation in contract.AdapterOperation],
        )

    def test_no_adapter_method_accepts_raw_command_or_path_parameters(self) -> None:
        for name, method in inspect.getmembers(
            contract.ProductionAdapter, predicate=inspect.isfunction
        ):
            if name.startswith("_"):
                continue
            parameters = tuple(inspect.signature(method).parameters)
            self.assertTrue(
                {"command", "argv", "path", "root", "unit_name", "control_name"}.isdisjoint(
                    parameters
                ),
                name,
            )


if __name__ == "__main__":
    unittest.main()
