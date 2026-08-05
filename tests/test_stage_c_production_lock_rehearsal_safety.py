from __future__ import annotations

import ast
import errno
import inspect
import stat
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.stage_c_transaction import production_adapter_contract as contract
from scripts.stage_c_transaction import production_lock_rehearsal as rehearsal
from scripts.stage_c_transaction import production_lock_rehearsal_adapter as lock_adapter


class StageCProductionLockRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        self.adapter_path = repo / "scripts/stage_c_transaction/production_lock_rehearsal_adapter.py"
        self.engine_path = repo / "scripts/stage_c_transaction/production_lock_rehearsal.py"
        self.wrapper_path = repo / "scripts/test-stage-c-production-lock-rehearsal.sh"
        self.adapter_source = self.adapter_path.read_text(encoding="utf-8")
        self.engine_source = self.engine_path.read_text(encoding="utf-8")
        self.wrapper_source = self.wrapper_path.read_text(encoding="utf-8")
        self.adapter_tree = ast.parse(self.adapter_source)
        self.engine_tree = ast.parse(self.engine_source)

    @staticmethod
    def service_snapshot() -> contract.ServiceSnapshot:
        application = {
            contract.ServiceUnit.PLEXAMP,
            contract.ServiceUnit.SHAIRPORT_SYNC,
            contract.ServiceUnit.DASHBOARD,
        }
        return contract.ServiceSnapshot(
            tuple(
                contract.ServiceState(
                    unit=unit,
                    load=(
                        contract.ServiceLoadState.LOADED
                        if unit in application
                        else contract.ServiceLoadState.NOT_FOUND
                    ),
                    active=(
                        contract.ServiceActiveState.ACTIVE
                        if unit in application
                        else contract.ServiceActiveState.INACTIVE
                    ),
                    enabled=(
                        contract.ServiceEnableState.ENABLED
                        if unit in application
                        else contract.ServiceEnableState.NOT_FOUND
                    ),
                )
                for unit in contract.ServiceUnit
            )
        )

    def test_exact_eight_operations_and_twenty_five_blocked(self) -> None:
        self.assertEqual(
            lock_adapter.PERMITTED_OPERATIONS,
            (
                contract.AdapterOperation.INSPECT_HOST_CONTRACT,
                contract.AdapterOperation.INSPECT_PRODUCTION_LOCK,
                contract.AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
                contract.AdapterOperation.RELEASE_PRODUCTION_LOCK,
                contract.AdapterOperation.CAPTURE_SERVICE_STATE,
                contract.AdapterOperation.CAPTURE_MIXER_STATE,
                contract.AdapterOperation.CAPTURE_LOOPBACK_STATE,
                contract.AdapterOperation.CAPTURE_DAC_STATE,
            ),
        )
        self.assertEqual(len(lock_adapter.PERMITTED_OPERATIONS), 8)
        self.assertEqual(
            len(set(contract.AdapterOperation).difference(lock_adapter.PERMITTED_OPERATIONS)),
            25,
        )

    def test_adapter_extends_observer_and_only_overrides_lock_boundary(self) -> None:
        adapter = lock_adapter.ProductionLockRehearsalAdapter()
        self.assertIsInstance(adapter, contract.ProductionAdapter)
        overrides = {
            name
            for name, value in lock_adapter.ProductionLockRehearsalAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            overrides,
            {
                "inspect_production_lock",
                "acquire_production_lock",
                "release_production_lock",
            },
        )
        self.assertFalse(hasattr(adapter, "create_transaction"))
        self.assertFalse(hasattr(adapter, "execute"))

    def test_lock_path_mode_and_lease_are_fixed_not_caller_inputs(self) -> None:
        self.assertEqual(
            str(lock_adapter.LOCK_PATH),
            "/run/lock/a-clockwork-plex-audio-route.lock",
        )
        self.assertEqual(lock_adapter.LOCK_MODE, 0o600)
        self.assertEqual(lock_adapter.LEASE_PREFIX, "stage-c14-lock-")
        for method_name in (
            "inspect_production_lock",
            "acquire_production_lock",
            "release_production_lock",
        ):
            self.assertEqual(
                tuple(
                    inspect.signature(
                        getattr(lock_adapter.ProductionLockRehearsalAdapter, method_name)
                    ).parameters
                ),
                ("self",),
                method_name,
            )

    def test_adapter_has_no_cli_command_runner_or_audio_command(self) -> None:
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
            "if __name__",
            "def main(",
            "shell=true",
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
            "camilladsp ",
            "transaction_root",
        ):
            self.assertNotIn(marker, self.adapter_source.lower())

    def test_acquisition_flags_are_exclusive_nonfollowing_and_close_on_exec(self) -> None:
        function = next(
            node
            for node in self.adapter_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_open_flags"
        )
        text = ast.get_source_segment(self.adapter_source, function) or ""
        self.assertIn("os.O_CREAT | os.O_EXCL", text)
        self.assertIn("os.O_CLOEXEC", text)
        self.assertIn("os.O_NOFOLLOW", text)
        acquire_start = self.adapter_source.index("def acquire_production_lock")
        release_start = self.adapter_source.index("def release_production_lock")
        acquire = self.adapter_source[acquire_start:release_start]
        self.assertIn("fcntl.LOCK_EX | fcntl.LOCK_NB", acquire)
        self.assertIn("os.fchmod(fd, LOCK_MODE)", acquire)
        self.assertIn("os.fchown(fd, 0, 0)", acquire)
        self.assertIn("_prove_contention()", acquire)

    def test_exact_unlink_checks_inode_and_device_before_removal(self) -> None:
        function = next(
            node
            for node in self.adapter_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_safe_unlink_exact"
        )
        text = ast.get_source_segment(self.adapter_source, function) or ""
        self.assertLess(
            text.index("descriptor.st_ino != path.st_ino"),
            text.index("LOCK_PATH.unlink()"),
        )
        self.assertIn("descriptor.st_dev != path.st_dev", text)
        self.assertIn("stat.S_ISREG", text)

    def test_successful_mocked_acquire_and_release_are_typed(self) -> None:
        evidence = lock_adapter.HeldLockEvidence(321, 0o600, 0, 0, True)
        fake_path = Mock()
        fake_path.lstat.side_effect = FileNotFoundError
        adapter = lock_adapter.ProductionLockRehearsalAdapter()
        absent = contract.ProductionLockObservation(
            path=contract.PRODUCTION_LOCK_PATH,
            exists=False,
            held_by_caller=False,
            owner_uid=None,
            owner_gid=None,
            mode=None,
        )
        with (
            patch.object(lock_adapter, "LOCK_PATH", fake_path),
            patch.object(lock_adapter.os, "geteuid", return_value=0),
            patch.object(lock_adapter, "_validate_parent"),
            patch.object(lock_adapter, "_observe_production_lock", return_value=absent),
            patch.object(lock_adapter.os, "open", return_value=10),
            patch.object(lock_adapter.os, "fchmod"),
            patch.object(lock_adapter.os, "fchown"),
            patch.object(lock_adapter.fcntl, "flock"),
            patch.object(lock_adapter.os, "close"),
            patch.object(lock_adapter, "_descriptor_evidence", return_value=evidence),
            patch.object(lock_adapter, "_prove_contention"),
            patch.object(lock_adapter, "_safe_unlink_exact"),
            patch.object(lock_adapter.secrets, "token_hex", return_value="abc123"),
        ):
            acquired = adapter.acquire_production_lock()
            self.assertIs(acquired.status, contract.AdapterStatus.PASS)
            self.assertIsInstance(acquired.payload, contract.ProductionLockLease)
            self.assertEqual(acquired.payload.lease_id, "stage-c14-lock-abc123")
            self.assertTrue(adapter.lock_held)
            released = adapter.release_production_lock()
            self.assertIs(released.status, contract.AdapterStatus.PASS)
            self.assertIsNone(released.payload)
            self.assertFalse(adapter.lock_held)

    def test_preexisting_lock_fails_before_open(self) -> None:
        adapter = lock_adapter.ProductionLockRehearsalAdapter()
        present = contract.ProductionLockObservation(
            path=contract.PRODUCTION_LOCK_PATH,
            exists=True,
            held_by_caller=False,
            owner_uid=0,
            owner_gid=0,
            mode=0o600,
        )
        with (
            patch.object(lock_adapter.os, "geteuid", return_value=0),
            patch.object(lock_adapter, "_validate_parent"),
            patch.object(lock_adapter, "_observe_production_lock", return_value=present),
            patch.object(lock_adapter.os, "open") as opened,
        ):
            result = adapter.acquire_production_lock()
        self.assertIs(result.status, contract.AdapterStatus.FAIL)
        self.assertIsNone(result.payload)
        opened.assert_not_called()
        self.assertFalse(adapter.lock_held)

    def test_substituted_inode_is_never_unlinked(self) -> None:
        descriptor = SimpleNamespace(
            st_ino=10,
            st_dev=1,
            st_mode=stat.S_IFREG | 0o600,
            st_uid=0,
            st_gid=0,
        )
        path_info = SimpleNamespace(
            st_ino=11,
            st_dev=1,
            st_mode=stat.S_IFREG | 0o600,
            st_uid=0,
            st_gid=0,
        )
        fake_path = Mock()
        fake_path.lstat.return_value = path_info
        with (
            patch.object(lock_adapter, "LOCK_PATH", fake_path),
            patch.object(lock_adapter.os, "fstat", return_value=descriptor),
        ):
            with self.assertRaises(lock_adapter.ProductionLockFailure):
                lock_adapter._safe_unlink_exact(10)
        fake_path.unlink.assert_not_called()

    def test_contention_accepts_busy_and_rejects_second_acquisition(self) -> None:
        fake_path = Mock()
        with (
            patch.object(lock_adapter, "LOCK_PATH", fake_path),
            patch.object(lock_adapter.os, "open", return_value=20),
            patch.object(lock_adapter.os, "close") as close,
            patch.object(
                lock_adapter.fcntl,
                "flock",
                side_effect=BlockingIOError(errno.EAGAIN, "busy"),
            ),
        ):
            lock_adapter._prove_contention()
        close.assert_called_once_with(20)

        with (
            patch.object(lock_adapter, "LOCK_PATH", fake_path),
            patch.object(lock_adapter.os, "open", return_value=21),
            patch.object(lock_adapter.os, "close"),
            patch.object(lock_adapter.fcntl, "flock", return_value=None),
        ):
            with self.assertRaises(lock_adapter.ProductionLockFailure):
                lock_adapter._prove_contention()

    def test_all_twenty_five_transaction_and_audio_operations_remain_blocked(self) -> None:
        adapter = lock_adapter.ProductionLockRehearsalAdapter()
        rows = rehearsal.prove_blocked_operations(
            adapter,
            transaction=adapter.observation_transaction,
            services=self.service_snapshot(),
            mixer=contract.MixerSnapshot(94, 100, 100, 100),
        )
        expected = set(contract.AdapterOperation).difference(
            lock_adapter.PERMITTED_OPERATIONS
        )
        self.assertEqual(len(rows), 25)
        self.assertEqual(
            {
                contract.AdapterOperation(operation)
                for operation, state in rows
                if state == "blocked"
            },
            expected,
        )

    def test_engine_contract_is_lock_only_and_transaction_root_is_read_only(self) -> None:
        self.assertEqual(
            rehearsal.EXPECTED_CHECKS,
            (
                "root-scope",
                "protocol-conformance",
                "pre-lock-host-contract",
                "pre-lock-boundary",
                "production-lock-acquired",
                "lock-file-contract",
                "lock-contention",
                "held-lock-observation",
                "read-only-host-observations",
                "blocked-operation-boundary",
                "production-lock-released",
                "exact-lock-cleanup",
                "evidence-integrity",
                "activation-interface",
            ),
        )
        imported: set[str] = set()
        for node in ast.walk(self.engine_tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {"fcntl", "requests", "shlex", "socket", "subprocess", "urllib"}.isdisjoint(
                imported
            )
        )
        forbidden_calls: list[str] = []
        for node in ast.walk(self.engine_tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called = node.func.id
            elif isinstance(node.func, ast.Attribute):
                owner = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
                called = f"{owner}.{node.func.attr}" if owner else node.func.attr
            else:
                continue
            if called in {
                "host_run",
                "run",
                "popen",
                "system",
                "os.open",
                "subprocess.run",
                "fcntl.flock",
            }:
                forbidden_calls.append(called)
        self.assertEqual(forbidden_calls, [])
        for marker in (
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
            "mkdir(",
            "write_text(TRANSACTION_ROOT",
        ):
            self.assertNotIn(marker, self.engine_source)
        self.assertIn("TRANSACTION_ROOT.lstat()", self.engine_source)
        self.assertNotIn("--activate", self.engine_source)
        self.assertNotIn("--install", self.engine_source)
        self.assertNotIn("--rollback", self.engine_source)

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
            'REQUIRED_CONFIRMATION="STAGE-C14-PRODUCTION-LOCK-ONLY"',
            self.wrapper_source,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.wrapper_source)
        self.assertIn(
            "-m stage_c_transaction.production_lock_rehearsal",
            self.wrapper_source,
        )
        self.assertNotIn("--activate", self.wrapper_source)
        self.assertNotIn("--install", self.wrapper_source)
        self.assertNotIn("--rollback", self.wrapper_source)


if __name__ == "__main__":
    unittest.main()