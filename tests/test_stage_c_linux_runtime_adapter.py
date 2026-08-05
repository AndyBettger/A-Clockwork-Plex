from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.linux_runtime_adapter import LinuxRuntimeHostAdapter
from stage_c_runtime_authority.model import ActivationApprovalRecord, BootObservation
from stage_c_runtime_authority.runtime_executor import RuntimeHostAdapter
from stage_c_runtime_authority.supervisor_model import PreparedRoute, SupervisorMode


class StageCLinuxRuntimeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.filesystem = Mock()
        self.process = Mock()
        self.adapter = LinuxRuntimeHostAdapter.__new__(LinuxRuntimeHostAdapter)
        self.adapter._filesystem = self.filesystem
        self.adapter._process = self.process

    def test_public_constructor_accepts_no_paths_and_protocol_is_complete(self):
        self.assertEqual(tuple(inspect.signature(LinuxRuntimeHostAdapter).parameters), ())
        self.assertIsInstance(LinuxRuntimeHostAdapter(), RuntimeHostAdapter)
        with self.assertRaises(TypeError):
            LinuxRuntimeHostAdapter(Path("/tmp/not-allowed"))

    def test_lock_approval_observation_and_routes_delegate_only_to_filesystem(self):
        approval = Mock(spec=ActivationApprovalRecord)
        observation = Mock(spec=BootObservation)
        self.filesystem.acquire_production_lock.return_value = "lease"
        self.filesystem.read_committed_approval.return_value = approval
        self.filesystem.observe_boot_contract.return_value = observation
        self.filesystem.read_prepared_route.return_value = PreparedRoute.SPLIT_PENDING

        self.assertEqual(self.adapter.acquire_production_lock(), "lease")
        self.adapter.release_production_lock("lease")
        self.assertIs(self.adapter.read_committed_approval(), approval)
        self.assertIs(self.adapter.observe_boot_contract(), observation)
        self.adapter.select_split_bus_route()
        self.adapter.select_direct_failback_route()
        self.adapter.publish_prepared_route(PreparedRoute.DIRECT_READY, "reason")
        self.assertIs(self.adapter.read_prepared_route(), PreparedRoute.SPLIT_PENDING)
        self.adapter.publish_runtime_mode(SupervisorMode.DIRECT_FAILBACK, "reason")

        self.filesystem.acquire_production_lock.assert_called_once_with()
        self.filesystem.release_production_lock.assert_called_once_with("lease")
        self.filesystem.read_committed_approval.assert_called_once_with()
        self.filesystem.observe_boot_contract.assert_called_once_with()
        self.filesystem.select_split_bus_route.assert_called_once_with()
        self.filesystem.select_direct_failback_route.assert_called_once_with()
        self.filesystem.publish_prepared_route.assert_called_once_with(
            PreparedRoute.DIRECT_READY,
            "reason",
        )
        self.filesystem.read_prepared_route.assert_called_once_with()
        self.filesystem.publish_runtime_mode.assert_called_once_with(
            SupervisorMode.DIRECT_FAILBACK,
            "reason",
        )
        self.process.assert_not_called()

    def test_child_health_notification_and_wait_delegate_only_to_process(self):
        self.process.start_camilladsp_child.return_value = True
        self.process.verify_split_bus_health.return_value = True
        self.process.wait_for_child_exit.return_value = 7
        self.process.child_running = True

        self.assertTrue(self.adapter.start_camilladsp_child())
        self.assertTrue(self.adapter.verify_split_bus_health())
        self.adapter.stop_camilladsp_child()
        self.adapter.notify_systemd_ready(SupervisorMode.SPLIT_ACTIVE, "healthy")
        self.assertEqual(self.adapter.wait_for_child_exit(), 7)
        self.assertTrue(self.adapter.child_running)

        self.process.start_camilladsp_child.assert_called_once_with()
        self.process.verify_split_bus_health.assert_called_once_with()
        self.process.stop_camilladsp_child.assert_called_once_with()
        self.process.notify_systemd_ready.assert_called_once_with(
            SupervisorMode.SPLIT_ACTIVE,
            "healthy",
        )
        self.process.wait_for_child_exit.assert_called_once_with()
        self.filesystem.assert_not_called()

    def test_composition_contains_no_third_host_boundary_or_generic_dispatch(self):
        source = (SCRIPTS / "stage_c_runtime_authority/linux_runtime_adapter.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("LinuxRuntimeFilesystem", source)
        self.assertIn("LinuxRuntimeProcess", source)
        for forbidden in (
            "subprocess",
            "socket",
            "systemctl",
            "aplay",
            "amixer",
            "os.replace",
            "open(",
            "def dispatch",
            "command:",
            "path_override",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
