from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority import package_entry
from stage_c_runtime_authority.model import ActivationApprovalRecord, ApprovalPhase, RuntimeAuthorityError
from stage_c_runtime_authority.supervisor_model import PreparedRoute, SupervisorMode


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


def approval(phase: ApprovalPhase) -> ActivationApprovalRecord:
    return ActivationApprovalRecord(
        schema_version=1,
        phase=phase,
        transaction_id="stage-c21-entry-test",
        lock_lease_id="stage-c21-entry-lease",
        package_fingerprint=HASH_A,
        commit_manifest_sha256=HASH_F if phase is ApprovalPhase.COMMITTED else None,
        active_route_sha256=HASH_B,
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
        created_at="2026-08-05T20:00:00Z",
        committed_at="2026-08-05T20:01:00Z" if phase is ApprovalPhase.COMMITTED else None,
    )


class InstalledGuard:
    def __init__(self, *, mutation_available: bool = True, files_valid: bool = True):
        self.instance = mock.Mock()
        self.instance._load_contract.return_value = {
            "schema_version": 1,
            "package_phase": "stage-c21-activation-capable-review-v2",
            "package_fingerprint": HASH_A,
            "host_mutation_available": mutation_available,
            "files": [{"path": "/fixed", "sha256": HASH_B}],
        }
        self.instance._contract_files_valid.return_value = files_valid

    def patches(self):
        actual = Path(package_entry.__file__).resolve().parent
        return (
            mock.patch.object(package_entry, "INSTALLED_PACKAGE_ROOT", actual),
            mock.patch.object(package_entry, "LinuxRuntimeFilesystem", return_value=self.instance),
            mock.patch.object(package_entry.os, "geteuid", return_value=0),
        )


class StageCPackageEntryTests(unittest.TestCase):
    def test_fixed_action_vocabulary_has_no_generic_dispatch(self):
        self.assertEqual(
            package_entry.FIXED_ACTIONS,
            (
                "status",
                "validate-runtime",
                "boot-prepare",
                "supervise",
                "emergency-direct-failback",
                "accept-install-handoff",
                "promote-committed-approval",
            ),
        )
        source = Path(package_entry.__file__).read_text(encoding="utf-8")
        self.assertNotIn("def dispatch", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)

    def test_repository_copy_blocks_operational_action_before_adapter_construction(self):
        stderr = io.StringIO()
        with mock.patch.object(package_entry, "LinuxRuntimeHostAdapter") as ordinary:
            with redirect_stderr(stderr):
                code = package_entry.main(("boot-prepare",))
        self.assertEqual(code, 78)
        self.assertIn("not executing from the exact installed package location", stderr.getvalue())
        ordinary.assert_not_called()

    def test_installed_guard_requires_v2_mutation_contract_exact_files_and_root(self):
        actual = Path(package_entry.__file__).resolve().parent
        cases = (
            (False, True, 0, "keeps host mutation blocked"),
            (True, False, 0, "do not match"),
            (True, True, 1000, "requires root"),
        )
        for mutation_available, files_valid, uid, message in cases:
            with self.subTest(message=message):
                guard = InstalledGuard(
                    mutation_available=mutation_available,
                    files_valid=files_valid,
                )
                with mock.patch.object(package_entry, "INSTALLED_PACKAGE_ROOT", actual), mock.patch.object(
                    package_entry,
                    "LinuxRuntimeFilesystem",
                    return_value=guard.instance,
                ), mock.patch.object(package_entry.os, "geteuid", return_value=uid):
                    with self.assertRaisesRegex(RuntimeAuthorityError, message):
                        package_entry._require_installed_image(mutation=True)

    def test_validate_runtime_returns_bound_package_identity(self):
        guard = InstalledGuard()
        first, second, third = guard.patches()
        with first, second, third:
            payload = package_entry.validate_runtime()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["package_fingerprint"], HASH_A)
        self.assertEqual(payload["checked_files"], 1)
        self.assertTrue(payload["host_mutation_available"])

    def test_temporary_boot_prepare_uses_only_install_route_entry(self):
        receipt = SimpleNamespace(
            phase="install-route-entry",
            lease_id="lease",
            prepared_route=PreparedRoute.SPLIT_PENDING,
            split_bus_healthy=False,
            borrowed_assertion_closed=True,
            systemd_ready=False,
        )
        install_adapter = object()
        with mock.patch.object(package_entry, "_approval_phase", return_value=ApprovalPhase.TEMPORARY), mock.patch.object(
            package_entry,
            "InstallLinuxRuntimeHostAdapter",
            return_value=install_adapter,
        ) as install_factory, mock.patch.object(
            package_entry,
            "run_install_route_entry",
            return_value=receipt,
        ) as install_run, mock.patch.object(package_entry, "run_boot_preparation") as ordinary_run:
            payload = package_entry._boot_prepare()
        self.assertEqual(payload["path"], "temporary-install")
        install_factory.assert_called_once_with()
        install_run.assert_called_once_with(install_adapter)
        ordinary_run.assert_not_called()

    def test_committed_boot_prepare_uses_only_ordinary_runtime(self):
        decision = SimpleNamespace(
            prepared_route=PreparedRoute.SPLIT_PENDING,
            reason="prepared",
            actions=(),
        )
        receipt = SimpleNamespace(
            phase="boot-preparation",
            mode=PreparedRoute.SPLIT_PENDING.value,
            reason="prepared",
            lease_id="lease",
            lock_released=True,
            systemd_ready=False,
        )
        ordinary_adapter = object()
        with mock.patch.object(package_entry, "_approval_phase", return_value=ApprovalPhase.COMMITTED), mock.patch.object(
            package_entry,
            "LinuxRuntimeHostAdapter",
            return_value=ordinary_adapter,
        ) as ordinary_factory, mock.patch.object(
            package_entry,
            "run_boot_preparation",
            return_value=(decision, receipt),
        ) as ordinary_run, mock.patch.object(package_entry, "run_install_route_entry") as install_run:
            payload = package_entry._boot_prepare()
        self.assertEqual(payload["path"], "committed-boot")
        ordinary_factory.assert_called_once_with()
        ordinary_run.assert_called_once_with(ordinary_adapter)
        install_run.assert_not_called()

    def test_supervise_routes_temporary_start_then_enters_shared_lifetime(self):
        adapter = object()
        decision = SimpleNamespace(mode=SupervisorMode.SPLIT_ACTIVE, reason="healthy", actions=())
        receipt = SimpleNamespace(
            phase="install-supervisor-startup",
            lease_id="lease",
            prepared_route=PreparedRoute.SPLIT_PENDING,
            split_bus_healthy=True,
            borrowed_assertion_closed=True,
            systemd_ready=True,
        )
        outcome = SimpleNamespace(
            exit_code=0,
            final_mode=SupervisorMode.SPLIT_ACTIVE,
            reason="stopped",
            child_stopped=True,
        )
        output = io.StringIO()
        with mock.patch.object(package_entry, "_approval_phase", return_value=ApprovalPhase.TEMPORARY), mock.patch.object(
            package_entry,
            "InstallLinuxRuntimeHostAdapter",
            return_value=adapter,
        ), mock.patch.object(
            package_entry,
            "run_install_supervisor_startup",
            return_value=(decision, receipt),
        ) as install_run, mock.patch.object(package_entry, "run_supervisor_startup") as ordinary_run, mock.patch.object(
            package_entry,
            "production_stop_event",
            return_value="event",
        ), mock.patch.object(
            package_entry,
            "supervise_lifetime",
            return_value=outcome,
        ) as lifetime, redirect_stdout(output):
            code = package_entry._supervise()
        self.assertEqual(code, 0)
        install_run.assert_called_once_with(adapter)
        ordinary_run.assert_not_called()
        self.assertIs(lifetime.call_args.args[0], adapter)
        self.assertIs(lifetime.call_args.args[1], SupervisorMode.SPLIT_ACTIVE)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(rows[0]["path"], "temporary-install")
        self.assertTrue(rows[1]["ok"])

    def test_emergency_failback_defers_temporary_and_executes_committed(self):
        with mock.patch.object(package_entry, "_approval_phase", return_value=ApprovalPhase.TEMPORARY), mock.patch.object(
            package_entry,
            "run_runtime_child_failure",
        ) as runtime:
            payload = package_entry._emergency_direct_failback()
        self.assertTrue(payload["deferred"])
        self.assertIn("transaction rollback", payload["reason"])
        runtime.assert_not_called()

        decision = SimpleNamespace(mode=SupervisorMode.DIRECT_FAILBACK, reason="failed", actions=())
        receipt = SimpleNamespace(
            phase="runtime-child-failure",
            mode=SupervisorMode.DIRECT_FAILBACK.value,
            reason="failed",
            lease_id="lease",
            lock_released=True,
            systemd_ready=True,
        )
        adapter = object()
        with mock.patch.object(package_entry, "_approval_phase", return_value=ApprovalPhase.COMMITTED), mock.patch.object(
            package_entry,
            "LinuxRuntimeHostAdapter",
            return_value=adapter,
        ), mock.patch.object(
            package_entry,
            "run_runtime_child_failure",
            return_value=(decision, receipt),
        ) as runtime:
            payload = package_entry._emergency_direct_failback()
        self.assertFalse(payload["deferred"])
        runtime.assert_called_once_with(adapter)

    def test_transaction_only_actions_remain_unexposed(self):
        guard = InstalledGuard()
        first, second, third = guard.patches()
        for action in package_entry.TRANSACTION_ONLY_ACTIONS:
            with self.subTest(action=action), first, second, third:
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = package_entry.main((action,))
                self.assertEqual(code, 78)
                self.assertIn("transaction-only", stderr.getvalue())
            guard = InstalledGuard()
            first, second, third = guard.patches()

    def test_extra_or_unknown_arguments_are_rejected(self):
        for arguments in (("status", "extra"), ("unknown",), ()):
            with self.subTest(arguments=arguments):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = package_entry.main(arguments)
                self.assertEqual(code, 1)
                self.assertIn("unsupported fixed runtime action", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
