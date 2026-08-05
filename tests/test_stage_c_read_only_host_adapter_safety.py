from __future__ import annotations

import ast
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.stage_c_transaction import production_adapter_contract as contract
from scripts.stage_c_transaction import read_only_host_adapter as adapter_module
from scripts.stage_c_transaction import read_only_host_adapter_rehearsal as rehearsal


class StageCReadOnlyHostAdapterSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.adapter_path = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "read_only_host_adapter.py"
        )
        self.engine_path = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "read_only_host_adapter_rehearsal.py"
        )
        self.wrapper_path = (
            self.repo
            / "scripts"
            / "test-stage-c-read-only-host-adapter.sh"
        )
        self.adapter_source = self.adapter_path.read_text(encoding="utf-8")
        self.engine_source = self.engine_path.read_text(encoding="utf-8")
        self.wrapper_source = self.wrapper_path.read_text(encoding="utf-8")
        self.adapter_tree = ast.parse(self.adapter_source)
        self.engine_tree = ast.parse(self.engine_source)

    @staticmethod
    def service_snapshot() -> contract.ServiceSnapshot:
        states = []
        for unit in contract.ServiceUnit:
            if unit in {
                contract.ServiceUnit.PLEXAMP,
                contract.ServiceUnit.SHAIRPORT_SYNC,
                contract.ServiceUnit.DASHBOARD,
            }:
                states.append(
                    contract.ServiceState(
                        unit=unit,
                        load=contract.ServiceLoadState.LOADED,
                        active=contract.ServiceActiveState.ACTIVE,
                        enabled=contract.ServiceEnableState.ENABLED,
                    )
                )
            else:
                states.append(
                    contract.ServiceState(
                        unit=unit,
                        load=contract.ServiceLoadState.NOT_FOUND,
                        active=contract.ServiceActiveState.INACTIVE,
                        enabled=contract.ServiceEnableState.NOT_FOUND,
                    )
                )
        return contract.ServiceSnapshot(tuple(states))

    @staticmethod
    def typed_payloads():
        host = contract.HostContractSnapshot(
            service_units=tuple(contract.ServiceUnit),
            mixer_controls=tuple(contract.MixerControl),
            loopback=contract.LOOPBACK_CONTRACT,
            dac=contract.DAC_CONTRACT,
        )
        lock = contract.ProductionLockObservation(
            path=contract.PRODUCTION_LOCK_PATH,
            exists=False,
            held_by_caller=False,
            owner_uid=None,
            owner_gid=None,
            mode=None,
        )
        services = StageCReadOnlyHostAdapterSafetyTests.service_snapshot()
        mixer = contract.MixerSnapshot(70, 70, 65, 80)
        loopback = contract.LoopbackSnapshot(
            contract=contract.LOOPBACK_CONTRACT,
            loaded=True,
        )
        dac = contract.DacSnapshot(
            contract=contract.DAC_CONTRACT,
            owners=(contract.DacOwner(123, "andy", "node", "read-write"),),
            released=False,
        )
        return host, lock, services, mixer, loopback, dac

    def test_exact_six_observations_and_twenty_seven_blocked_operations(self) -> None:
        self.assertEqual(
            adapter_module.PERMITTED_OPERATIONS,
            (
                contract.AdapterOperation.INSPECT_HOST_CONTRACT,
                contract.AdapterOperation.INSPECT_PRODUCTION_LOCK,
                contract.AdapterOperation.CAPTURE_SERVICE_STATE,
                contract.AdapterOperation.CAPTURE_MIXER_STATE,
                contract.AdapterOperation.CAPTURE_LOOPBACK_STATE,
                contract.AdapterOperation.CAPTURE_DAC_STATE,
            ),
        )
        self.assertEqual(len(adapter_module.PERMITTED_OPERATIONS), 6)
        self.assertEqual(
            len(
                set(contract.AdapterOperation).difference(
                    adapter_module.PERMITTED_OPERATIONS
                )
            ),
            27,
        )

    def test_adapter_overrides_only_the_six_observation_methods(self) -> None:
        overrides = {
            name
            for name, value in adapter_module.ReadOnlyHostProductionAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        expected = {
            "inspect_host_contract",
            "inspect_production_lock",
            "capture_service_state",
            "capture_mixer_state",
            "capture_loopback_state",
            "capture_dac_state",
        }
        self.assertEqual(overrides, expected)
        adapter = adapter_module.ReadOnlyHostProductionAdapter()
        self.assertIsInstance(adapter, contract.BlockedProductionAdapter)
        self.assertIsInstance(adapter, contract.ProductionAdapter)
        self.assertTrue(
            adapter.observation_transaction.value.startswith(
                adapter_module.OBSERVATION_PREFIX
            )
        )

    def test_adapter_has_no_cli_or_generic_command_boundary(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.adapter_tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {
                "argparse",
                "fcntl",
                "requests",
                "shlex",
                "socket",
                "urllib",
            }.isdisjoint(imported)
        )
        for marker in (
            "if __name__",
            "def main(",
            "shell=True",
            "getattr(",
            "eval(",
            "exec(",
            "os.open(",
            "flock",
        ):
            self.assertNotIn(marker, self.adapter_source)

    def test_every_host_command_call_is_fixed_and_read_only(self) -> None:
        calls = []
        for node in ast.walk(self.adapter_tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "host_run":
                continue
            self.assertTrue(node.args)
            command = node.args[0]
            self.assertIsInstance(command, ast.List)
            values = [
                item.value if isinstance(item, ast.Constant) else None
                for item in command.elts
            ]
            calls.append(values)
        self.assertEqual(len(calls), 5)
        self.assertIn(
            ["systemctl", "show", None, "--property=LoadState", "--value"],
            calls,
        )
        self.assertIn(["systemctl", "is-active", None], calls)
        self.assertIn(["systemctl", "is-enabled", None], calls)
        self.assertIn(["amixer", "-c", "Pro", "sget", None], calls)
        self.assertIn(["fuser", None], calls)
        for forbidden in ('"sset"', '"cset"', '"modprobe"', '"aplay"'):
            self.assertNotIn(forbidden, self.adapter_source)

    def test_production_lock_is_observed_only_with_lstat(self) -> None:
        function = next(
            node
            for node in self.adapter_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_observe_production_lock"
        )
        attributes = {
            node.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Attribute)
        }
        self.assertIn("lstat", attributes)
        self.assertNotIn("open", attributes)
        self.assertNotIn("write_text", attributes)
        self.assertNotIn("touch", attributes)
        self.assertNotIn("mkdir", attributes)

    def test_substituted_identity_fails_before_observation(self) -> None:
        adapter = adapter_module.ReadOnlyHostProductionAdapter()
        reader = Mock(return_value=self.service_snapshot())
        with patch.object(adapter_module, "_observe_service_snapshot", reader):
            wrong = adapter.capture_service_state(
                contract.TransactionIdentity("stage-c13-substituted")
            )
            self.assertIs(wrong.status, contract.AdapterStatus.FAIL)
            self.assertIsNone(wrong.payload)
            reader.assert_not_called()

            accepted = adapter.capture_service_state(
                adapter.observation_transaction
            )
            self.assertIs(accepted.status, contract.AdapterStatus.PASS)
            self.assertEqual(accepted.payload, self.service_snapshot())
            reader.assert_called_once_with()

    def test_six_methods_return_exact_typed_payloads(self) -> None:
        host, lock, services, mixer, loopback, dac = self.typed_payloads()
        adapter = adapter_module.ReadOnlyHostProductionAdapter()
        with (
            patch.object(adapter_module, "_observe_host_contract", return_value=host),
            patch.object(adapter_module, "_observe_production_lock", return_value=lock),
            patch.object(adapter_module, "_observe_service_snapshot", return_value=services),
            patch.object(adapter_module, "_observe_mixer_snapshot", return_value=mixer),
            patch.object(adapter_module, "_observe_loopback_snapshot", return_value=loopback),
            patch.object(adapter_module, "_observe_dac_snapshot", return_value=dac),
        ):
            results = (
                adapter.inspect_host_contract(),
                adapter.inspect_production_lock(),
                adapter.capture_service_state(adapter.observation_transaction),
                adapter.capture_mixer_state(adapter.observation_transaction),
                adapter.capture_loopback_state(adapter.observation_transaction),
                adapter.capture_dac_state(adapter.observation_transaction),
            )
        self.assertEqual(
            tuple(result.operation for result in results),
            adapter_module.PERMITTED_OPERATIONS,
        )
        self.assertTrue(
            all(result.status is contract.AdapterStatus.PASS for result in results)
        )
        self.assertEqual(
            tuple(result.payload for result in results),
            (host, lock, services, mixer, loopback, dac),
        )

    def test_all_other_methods_still_raise_exact_blocked_identity(self) -> None:
        _host, _lock, services, mixer, _loopback, _dac = self.typed_payloads()
        adapter = adapter_module.ReadOnlyHostProductionAdapter()
        rows = rehearsal.prove_blocked_operations(
            adapter,
            transaction=adapter.observation_transaction,
            services=services,
            mixer=mixer,
        )
        expected = set(contract.AdapterOperation).difference(
            adapter_module.PERMITTED_OPERATIONS
        )
        self.assertEqual(len(rows), 27)
        self.assertEqual(
            {
                contract.AdapterOperation(operation)
                for operation, state in rows
                if state == "blocked"
            },
            expected,
        )

    def test_dac_alias_and_owner_evidence_are_structured(self) -> None:
        with (
            patch.object(adapter_module.os, "readlink", return_value="card3"),
            patch.object(Path, "exists", return_value=True),
        ):
            self.assertEqual(
                adapter_module._physical_dac_device(),
                Path("/dev/snd/pcmC3D0p"),
            )
        rows = [
            "dac.owner_count\t1",
            "dac.owners\t123",
            "dac.owner.1.pid\t123",
            "dac.owner.1.user\tandy",
            "dac.owner.1.command\tnode",
            "dac.owner.1.fds\t41:read-write",
        ]
        with patch.object(adapter_module, "_dac_owner_rows", return_value=rows):
            owners = adapter_module._parse_dac_owners(
                Path("/dev/snd/pcmC3D0p"),
                "123",
            )
        self.assertEqual(
            owners,
            (contract.DacOwner(123, "andy", "node", "read-write"),),
        )

    def test_result_contract_and_evidence_root_are_exact(self) -> None:
        self.assertEqual(
            rehearsal.EXPECTED_CHECKS,
            (
                "root-scope",
                "observation-identity",
                "protocol-conformance",
                "host-contract",
                "production-lock-boundary",
                "service-snapshot",
                "mixer-snapshot",
                "loopback-snapshot",
                "dac-snapshot",
                "blocked-operation-boundary",
                "evidence-integrity",
                "activation-interface",
            ),
        )
        root = Path(
            tempfile.mkdtemp(
                prefix=rehearsal.EVIDENCE_PREFIX,
                dir="/var/tmp",
            )
        )
        try:
            root.chmod(0o700)
            self.assertEqual(
                rehearsal.validate_evidence_root(root, os.getuid()),
                root.resolve(),
            )
            (root / "unexpected").write_text("x", encoding="utf-8")
            with self.assertRaises(SystemExit):
                rehearsal.validate_evidence_root(root, os.getuid())
        finally:
            shutil.rmtree(root)

    def test_rehearsal_engine_has_no_direct_host_command_or_lock_access(self) -> None:
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

        for node in ast.walk(self.engine_tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                self.assertNotIn(
                    node.func.id.lower(),
                    {"host_run", "popen", "system"},
                )
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            self.assertNotEqual(node.func.attr.lower(), "flock")
            if isinstance(node.func.value, ast.Name):
                owner = node.func.value.id.lower()
                called = node.func.attr.lower()
                self.assertNotEqual((owner, called), ("os", "open"))
                self.assertNotEqual((owner, called), ("subprocess", "run"))

        for marker in (
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
        ):
            self.assertNotIn(marker, self.engine_source.lower())

    def test_wrapper_is_prepare_only_and_has_one_constrained_sudo_command(self) -> None:
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
            'REQUIRED_CONFIRMATION="STAGE-C13-TYPED-READ-ONLY-HOST-ADAPTER"',
            self.wrapper_source,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.wrapper_source)
        self.assertIn(
            "-m stage_c_transaction.read_only_host_adapter_rehearsal",
            self.wrapper_source,
        )
        self.assertNotIn("--activate", self.wrapper_source)
        self.assertNotIn("--install", self.wrapper_source)
        self.assertNotIn("--rollback", self.wrapper_source)


if __name__ == "__main__":
    unittest.main()
