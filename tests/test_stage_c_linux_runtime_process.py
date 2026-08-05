from __future__ import annotations

import hashlib
import inspect
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.linux_runtime_process import (
    LinuxRuntimeProcess,
    START_POLL_SECONDS,
    START_TIMEOUT_SECONDS,
    _SystemdNotifier,
)
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
)
from stage_c_runtime_authority.supervisor_model import SupervisorMode


class FakeChild:
    def __init__(self, pid: int = 4242, *, stubborn: bool = False):
        self.pid = pid
        self.returncode: int | None = None
        self.stubborn = stubborn
        self.terminated = False
        self.killed = False
        self.wait_timeouts: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        if not self.stubborn:
            self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if self.returncode is None and timeout is not None:
            raise subprocess.TimeoutExpired("camilladsp", timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class RecordingFactory:
    def __init__(self, child: FakeChild):
        self.child = child
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, argv: list[str], **kwargs: object) -> FakeChild:
        self.calls.append((list(argv), dict(kwargs)))
        return self.child


class RecordingNotifier:
    def __init__(self):
        self.calls: list[tuple[SupervisorMode, str]] = []

    def notify_ready(self, mode: SupervisorMode, reason: str) -> None:
        self.calls.append((mode, reason))


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []
        self.on_sleep = None

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        if self.on_sleep is not None:
            self.on_sleep()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeProcessFixture:
    def __init__(self, root: Path, child: FakeChild):
        self.root = root
        self.child = child
        self.factory = RecordingFactory(child)
        self.notifier = RecordingNotifier()
        self.clock = FakeClock()
        self.state_root = root / "var/lib/a-clockwork-plex/split-bus"
        self.defaults = root / "etc/default/a-clockwork-plex-split-bus"
        self.binary = root / "usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp"
        self.config = root / "etc/a-clockwork-plex/camilladsp-split-bus.yml"
        self.dac_device = root / "dev/snd/pcmC2D0p"
        self.loopback_device = root / "dev/snd/pcmC7D1c"
        self.dac_params = root / "proc/asound/card2/pcm0p/sub0/hw_params"
        self.loopback_params = root / "proc/asound/card7/pcm1c/sub0/hw_params"
        for path in (
            self.state_root,
            self.defaults.parent,
            self.binary.parent,
            self.config.parent,
            self.dac_device.parent,
            self.dac_params.parent,
            self.loopback_params.parent,
            root / "proc/asound",
            root / f"proc/{child.pid}/fd",
        ):
            path.mkdir(parents=True, exist_ok=True)
        self._write(self.defaults, b"PROJECT_USER=testuser\n", 0o644)
        self._write(self.binary, b"pinned-camilladsp\n", 0o755)
        self._write(self.config, b"split-bus-config\n", 0o644)
        self._write(self.dac_device, b"device\n", 0o644)
        self._write(self.loopback_device, b"device\n", 0o644)
        (root / "proc/asound/Pro").symlink_to("card2")
        self._write(
            self.dac_params,
            b"access: MMAP_INTERLEAVED\nformat: S16_LE\nsubformat: STD\nchannels: 2\nrate: 44100 (44100/1)\nperiod_size: 1024\nbuffer_size: 8192\n",
            0o644,
        )
        self._write(
            self.loopback_params,
            b"access: MMAP_INTERLEAVED\nformat: S16_LE\nsubformat: STD\nchannels: 4\nrate: 44100\nperiod_size: 1024\nbuffer_size: 8192\n",
            0o644,
        )
        process_root = root / f"proc/{child.pid}"
        (process_root / "exe").symlink_to(
            "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp"
        )
        (process_root / "cmdline").write_bytes(
            str(self.binary).encode("utf-8")
            + b"\0"
            + str(self.config).encode("utf-8")
            + b"\0"
        )
        (process_root / "fd/3").symlink_to("/dev/snd/pcmC2D0p")
        (process_root / "fd/4").symlink_to("/dev/snd/pcmC7D1c")
        self.approval = ActivationApprovalRecord(
            schema_version=1,
            phase=ApprovalPhase.COMMITTED,
            transaction_id="stage-c21-process-test",
            lock_lease_id="stage-c21-process-test-lease",
            package_fingerprint="a" * 64,
            commit_manifest_sha256="f" * 64,
            active_route_sha256="b" * 64,
            direct_route_sha256="c" * 64,
            camilladsp_config_sha256=sha256(self.config),
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=sha256(self.binary),
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
            committed_at="2026-08-05T20:01:00Z",
        )
        ApprovalStore(self.state_root).publish_new(self.approval, lock_held=True)
        self.adapter = LinuxRuntimeProcess._for_test(
            root,
            process_factory=self.factory,
            notifier=self.notifier,
            monotonic=self.clock.monotonic,
            sleep=self.clock.sleep,
        )

    @staticmethod
    def _write(path: Path, payload: bytes, mode: int) -> None:
        path.write_bytes(payload)
        path.chmod(mode)

    def start(self) -> bool:
        with mock.patch.object(
            self.adapter,
            "_child_identity",
            return_value=(1000, 29, (29, 1000), "/home/testuser"),
        ):
            return self.adapter.start_camilladsp_child()

    def add_competing_owner(self, pid: int, device: str) -> None:
        fd_root = self.root / f"proc/{pid}/fd"
        fd_root.mkdir(parents=True)
        (fd_root / "9").symlink_to(device)


class StageCLinuxRuntimeProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.child = FakeChild()
        self.fixture = RuntimeProcessFixture(self.root, self.child)

    def tearDown(self):
        self.temporary.cleanup()

    def test_public_constructor_accepts_no_paths(self):
        self.assertEqual(tuple(inspect.signature(LinuxRuntimeProcess).parameters), ())
        with self.assertRaises(TypeError):
            LinuxRuntimeProcess(self.root)

    def test_start_uses_one_exact_argv_and_drops_to_fixed_identity(self):
        self.assertTrue(self.fixture.start())
        self.assertEqual(len(self.fixture.factory.calls), 1)
        argv, kwargs = self.fixture.factory.calls[0]
        self.assertEqual(argv, [str(self.fixture.binary), str(self.fixture.config)])
        self.assertEqual(kwargs["user"], 1000)
        self.assertEqual(kwargs["group"], 29)
        self.assertEqual(kwargs["extra_groups"], (29, 1000))
        self.assertEqual(kwargs["cwd"], "/")
        self.assertTrue(kwargs["close_fds"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["env"]["USER"], "testuser")
        self.assertEqual(self.fixture.adapter.child_pid, self.child.pid)

    def test_start_refuses_changed_binary_config_or_temporary_approval(self):
        self.fixture.binary.write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeAuthorityError, "binary differs"):
            self.fixture.start()
        self.fixture.binary.write_text("pinned-camilladsp\n", encoding="utf-8")
        self.fixture.config.write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeAuthorityError, "configuration differs"):
            self.fixture.start()
        self.fixture.config.write_text("split-bus-config\n", encoding="utf-8")
        temporary = ActivationApprovalRecord(
            **{
                **self.fixture.approval.__dict__,
                "phase": ApprovalPhase.TEMPORARY,
                "commit_manifest_sha256": None,
                "committed_at": None,
            }
        )
        ApprovalStore(self.fixture.state_root).replace_exact(
            self.fixture.approval,
            temporary,
            lock_held=True,
        )
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires a committed approval"):
            self.fixture.start()

    def test_defaults_parser_rejects_shell_syntax_duplicate_and_invalid_user(self):
        for payload in (
            "PROJECT_USER=$(id)\n",
            "PROJECT_USER=testuser\nPROJECT_USER=other\n",
            "PROJECT_USER=Bad User\n",
            "source=/tmp/file\n",
        ):
            with self.subTest(payload=payload):
                self.fixture.defaults.write_text(payload, encoding="utf-8")
                with self.assertRaises(RuntimeAuthorityError):
                    self.fixture.start()
                self.fixture.adapter._child = None

    def test_exact_child_ownership_and_hw_params_pass_health(self):
        self.assertTrue(self.fixture.start())
        self.assertTrue(self.fixture.adapter.verify_split_bus_health())
        self.assertEqual(self.fixture.clock.sleeps, [])

    def test_competing_dac_or_loopback_owner_fails_health(self):
        self.assertTrue(self.fixture.start())
        self.fixture.add_competing_owner(5001, "/dev/snd/pcmC2D0p")
        self.fixture.clock.now = START_TIMEOUT_SECONDS
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())
        (self.root / "proc/5001/fd/9").unlink()
        self.fixture.add_competing_owner(5002, "/dev/snd/pcmC7D1c")
        self.fixture.clock.now = START_TIMEOUT_SECONDS * 2
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())

    def test_dac_and_loopback_contract_mismatches_fail_health(self):
        self.assertTrue(self.fixture.start())
        original_dac = self.fixture.dac_params.read_text(encoding="utf-8")
        original_loop = self.fixture.loopback_params.read_text(encoding="utf-8")
        self.fixture.dac_params.write_text(original_dac.replace("channels: 2", "channels: 1"), encoding="utf-8")
        self.fixture.clock.now = START_TIMEOUT_SECONDS
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())
        self.fixture.dac_params.write_text(original_dac, encoding="utf-8")
        self.fixture.loopback_params.write_text(
            original_loop.replace("channels: 4", "channels: 2"),
            encoding="utf-8",
        )
        self.fixture.clock.now = START_TIMEOUT_SECONDS * 2
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())
        self.fixture.loopback_params.write_text(
            original_loop.replace("buffer_size: 8192", "buffer_size: 1500"),
            encoding="utf-8",
        )
        self.fixture.clock.now = START_TIMEOUT_SECONDS * 3
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())

    def test_command_identity_or_missing_endpoint_owner_fails_health(self):
        self.assertTrue(self.fixture.start())
        (self.root / f"proc/{self.child.pid}/cmdline").write_bytes(b"wrong\0")
        self.fixture.clock.now = START_TIMEOUT_SECONDS
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())
        (self.root / f"proc/{self.child.pid}/fd/4").unlink()
        self.fixture.clock.now = START_TIMEOUT_SECONDS * 2
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())

    def test_bounded_poll_accepts_late_complete_health(self):
        self.assertTrue(self.fixture.start())
        owner = self.root / f"proc/{self.child.pid}/fd/4"
        owner.unlink()

        def restore_owner() -> None:
            if len(self.fixture.clock.sleeps) == 2 and not owner.exists():
                owner.symlink_to("/dev/snd/pcmC7D1c")

        self.fixture.clock.on_sleep = restore_owner
        self.assertTrue(self.fixture.adapter.verify_split_bus_health())
        self.assertEqual(self.fixture.clock.sleeps, [START_POLL_SECONDS, START_POLL_SECONDS])

    def test_dead_child_stops_poll_immediately(self):
        self.assertTrue(self.fixture.start())
        self.child.returncode = 1
        self.assertFalse(self.fixture.adapter.verify_split_bus_health())
        self.assertEqual(self.fixture.clock.sleeps, [])

    def test_stop_terminates_then_kills_only_after_timeout(self):
        self.assertTrue(self.fixture.start())
        self.fixture.adapter.stop_camilladsp_child()
        self.assertTrue(self.child.terminated)
        self.assertFalse(self.child.killed)
        self.assertIsNone(self.fixture.adapter.child_pid)

        stubborn = FakeChild(pid=4343, stubborn=True)
        fixture = RuntimeProcessFixture(self.root / "stubborn", stubborn)
        self.assertTrue(fixture.start())
        fixture.adapter.stop_camilladsp_child()
        self.assertTrue(stubborn.terminated)
        self.assertTrue(stubborn.killed)
        self.assertIsNone(fixture.adapter.child_pid)

    def test_notifier_boundary_receives_only_typed_mode_and_reason(self):
        self.fixture.adapter.notify_systemd_ready(SupervisorMode.SPLIT_ACTIVE, "strict health passed")
        self.assertEqual(
            self.fixture.notifier.calls,
            [(SupervisorMode.SPLIT_ACTIVE, "strict health passed")],
        )

    def test_real_notifier_emits_exact_ready_and_status_datagram(self):
        socket_path = self.root / "notify.sock"
        receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            receiver.bind(str(socket_path))
            receiver.settimeout(1.0)
            with mock.patch.dict(os.environ, {"NOTIFY_SOCKET": str(socket_path)}, clear=False):
                _SystemdNotifier().notify_ready(
                    SupervisorMode.DIRECT_FAILBACK,
                    "DSP unavailable",
                )
            payload = receiver.recv(2048)
        finally:
            receiver.close()
        self.assertEqual(
            payload,
            b"READY=1\nSTATUS=A Clockwork Plex audio ready: direct-failback; DSP unavailable\n",
        )

    def test_notifier_refuses_missing_socket_or_multiline_reason(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeAuthorityError, "NOTIFY_SOCKET"):
                _SystemdNotifier().notify_ready(SupervisorMode.SPLIT_ACTIVE, "ready")
        with mock.patch.dict(os.environ, {"NOTIFY_SOCKET": "/tmp/unused"}, clear=True):
            with self.assertRaisesRegex(RuntimeAuthorityError, "newline"):
                _SystemdNotifier().notify_ready(SupervisorMode.SPLIT_ACTIVE, "bad\nreason")

    def test_wait_for_child_exit_is_bound_to_supervised_child(self):
        self.assertTrue(self.fixture.start())
        self.child.returncode = 7
        self.assertEqual(self.fixture.adapter.wait_for_child_exit(), 7)
        self.assertEqual(self.child.wait_timeouts[-1], None)

    def test_module_exposes_no_generic_command_or_caller_path_boundary(self):
        source = (SCRIPTS / "stage_c_runtime_authority/linux_runtime_process.py").read_text(encoding="utf-8")
        self.assertIn("subprocess.Popen", source)
        self.assertIn("shell=False", source)
        self.assertIn("Type=notify", LinuxRuntimeProcess.__doc__)
        for forbidden in (
            "systemctl",
            "amixer",
            "aplay",
            "shell=True",
            "os.system",
            "os.exec",
            "def dispatch",
            "command:",
            "path_override",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp", source)
        self.assertIn("/etc/a-clockwork-plex/camilladsp-split-bus.yml", source)
        self.assertIn("/dev/snd/pcmC7D1c", source)


if __name__ == "__main__":
    unittest.main()
