from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.linux_runtime_filesystem import LinuxRuntimeFilesystem
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
)
from stage_c_runtime_authority.supervisor_model import PreparedRoute, SupervisorMode


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeFilesystemFixture:
    def __init__(self, root: Path):
        self.root = root
        self.state_root = root / "var/lib/a-clockwork-plex/split-bus"
        self.active = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        self.split = root / "etc/a-clockwork-plex/audio-routes/split-bus.conf"
        self.direct = root / "etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf"
        self.config = root / "etc/a-clockwork-plex/camilladsp-split-bus.yml"
        self.binary = root / "usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp"
        self.launcher = root / "usr/local/bin/a-clockwork-plex-audio-route"
        self.sudoers = root / "etc/sudoers.d/a-clockwork-plex-audio-route"
        self.contract = root / "usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json"
        for directory in (
            root / "run/lock",
            self.state_root,
            self.active.parent,
            self.split.parent,
            self.config.parent,
            self.binary.parent,
            self.launcher.parent,
            self.sudoers.parent,
            self.contract.parent,
            root / "sys/module/snd_aloop/parameters",
            root / "proc/asound",
            root / "dev/snd",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self._write(self.split, b"split-route\n", 0o644)
        self._write(self.direct, b"direct-route\n", 0o644)
        self._write(self.active, self.direct.read_bytes(), 0o644)
        self._write(self.config, b"camilladsp-config\n", 0o644)
        self._write(self.binary, b"camilladsp-binary\n", 0o755)
        self._write(self.launcher, b"#!/usr/bin/python3\n", 0o755)
        self._write(self.sudoers, b"andy ALL=(root) NOPASSWD: status\n", 0o440)
        parameters = root / "sys/module/snd_aloop/parameters"
        for name, value in {
            "index": "7\n",
            "id": "ACP_Loopback\n",
            "pcm_substreams": "2\n",
            "pcm_notify": "1\n",
            "enable": "Y\n",
        }.items():
            self._write(parameters / name, value.encode("ascii"), 0o644)
        (root / "proc/asound/Pro").symlink_to("card2")
        self._write(root / "dev/snd/pcmC2D0p", b"test-device\n", 0o644)

        payload_paths = (
            "/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf",
            "/etc/a-clockwork-plex/audio-routes/split-bus.conf",
            "/etc/a-clockwork-plex/camilladsp-split-bus.yml",
            "/etc/sudoers.d/a-clockwork-plex-audio-route",
            "/usr/local/bin/a-clockwork-plex-audio-route",
            "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp",
        )
        rows = [
            {"path": absolute, "sha256": sha256(self._map(absolute))}
            for absolute in sorted(payload_paths)
        ]
        fingerprint = hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        contract_payload = {
            "schema_version": 1,
            "package_phase": "stage-c21-test",
            "package_fingerprint": fingerprint,
            "host_mutation_available": False,
            "files": rows,
        }
        self._write(
            self.contract,
            (json.dumps(contract_payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
            0o644,
        )
        self.approval = ActivationApprovalRecord(
            schema_version=1,
            phase=ApprovalPhase.COMMITTED,
            transaction_id="stage-c21-test-transaction",
            lock_lease_id="stage-c21-test-lease",
            package_fingerprint=fingerprint,
            commit_manifest_sha256="f" * 64,
            active_route_sha256=sha256(self.split),
            direct_route_sha256=sha256(self.direct),
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

    def _map(self, absolute: str) -> Path:
        return self.root.joinpath(*Path(absolute).parts[1:])

    @staticmethod
    def _write(path: Path, payload: bytes, mode: int) -> None:
        path.write_bytes(payload)
        path.chmod(mode)


class StageCLinuxRuntimeFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = RuntimeFilesystemFixture(self.root)
        self.adapter = LinuxRuntimeFilesystem._for_test(self.root)

    def tearDown(self):
        if self.adapter.lock_held:
            lock = self.root / "run/lock/a-clockwork-plex-audio-route.lock"
            parked = lock.with_name(lock.name + ".parked-test")
            if parked.exists() and lock.exists():
                lock.unlink()
                parked.rename(lock)
            self.adapter.release_production_lock(self.adapter._lease_id)
        self.temporary.cleanup()

    def test_public_constructor_accepts_no_paths(self):
        signature = inspect.signature(LinuxRuntimeFilesystem)
        self.assertEqual(tuple(signature.parameters), ())
        with self.assertRaises(TypeError):
            LinuxRuntimeFilesystem(self.root)

    def test_exact_lock_acquisition_contention_and_release(self):
        lease = self.adapter.acquire_production_lock()
        lock = self.root / "run/lock/a-clockwork-plex-audio-route.lock"
        self.assertTrue(self.adapter.lock_held)
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        self.assertEqual(lock.read_text(encoding="ascii").strip(), lease)
        second = LinuxRuntimeFilesystem._for_test(self.root)
        with self.assertRaisesRegex(RuntimeAuthorityError, "already exists"):
            second.acquire_production_lock()
        self.adapter.release_production_lock(lease)
        self.assertFalse(lock.exists())
        self.assertFalse(self.adapter.lock_held)

    def test_substituted_lock_inode_is_never_unlinked(self):
        lease = self.adapter.acquire_production_lock()
        lock = self.root / "run/lock/a-clockwork-plex-audio-route.lock"
        parked = lock.with_name(lock.name + ".parked-test")
        lock.rename(parked)
        lock.write_text("replacement\n", encoding="ascii")
        lock.chmod(0o600)
        with self.assertRaisesRegex(RuntimeAuthorityError, "substituted"):
            self.adapter.release_production_lock(lease)
        self.assertEqual(lock.read_text(encoding="ascii"), "replacement\n")
        self.assertTrue(self.adapter.lock_held)

    def test_boot_observation_validates_package_loopback_routes_and_dac(self):
        observed = self.adapter.observe_boot_contract()
        self.assertEqual(observed.package_fingerprint, self.fixture.approval.package_fingerprint)
        self.assertTrue(observed.managed_files_valid)
        self.assertTrue(observed.split_route_valid)
        self.assertTrue(observed.direct_route_valid)
        self.assertTrue(observed.loopback_valid)
        self.assertTrue(observed.dac_valid)
        self.assertFalse(observed.camilladsp_start_succeeded)
        self.assertFalse(observed.split_bus_health_valid)

    def test_modified_payload_or_mode_fails_managed_file_validation(self):
        self.fixture.config.write_text("changed\n", encoding="utf-8")
        self.assertFalse(self.adapter.observe_boot_contract().managed_files_valid)
        self.fixture.config.write_text("camilladsp-config\n", encoding="utf-8")
        self.fixture.config.chmod(0o600)
        self.assertFalse(self.adapter.observe_boot_contract().managed_files_valid)

    def test_route_mutation_requires_held_lock(self):
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires the production lock"):
            self.adapter.select_split_bus_route()
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires the production lock"):
            self.adapter.publish_prepared_route(PreparedRoute.DIRECT_READY, "blocked")

    def test_split_and_direct_routes_are_atomically_published(self):
        lease = self.adapter.acquire_production_lock()
        original_inode = self.fixture.active.stat().st_ino
        self.adapter.select_split_bus_route()
        self.assertEqual(sha256(self.fixture.active), self.fixture.approval.active_route_sha256)
        self.assertNotEqual(self.fixture.active.stat().st_ino, original_inode)
        self.adapter.publish_prepared_route(PreparedRoute.SPLIT_PENDING, "split prepared")
        self.assertIs(self.adapter.read_prepared_route(), PreparedRoute.SPLIT_PENDING)
        self.adapter.publish_runtime_mode(SupervisorMode.SPLIT_ACTIVE, "split healthy")
        state = json.loads((self.fixture.state_root / "route-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["runtime_mode"], "split-bus-active")
        self.adapter.select_direct_failback_route()
        self.assertEqual(sha256(self.fixture.active), self.fixture.approval.direct_route_sha256)
        self.adapter.publish_runtime_mode(SupervisorMode.DIRECT_FAILBACK, "DSP failed")
        state = json.loads((self.fixture.state_root / "route-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["runtime_mode"], "direct-failback")
        self.adapter.release_production_lock(lease)

    def test_unknown_active_route_is_refused(self):
        self.fixture.active.write_text("unknown-route\n", encoding="utf-8")
        lease = self.adapter.acquire_production_lock()
        with self.assertRaisesRegex(RuntimeAuthorityError, "outside committed"):
            self.adapter.select_direct_failback_route()
        self.assertEqual(self.fixture.active.read_text(encoding="utf-8"), "unknown-route\n")
        self.adapter.release_production_lock(lease)

    def test_symlinked_source_or_ancestor_is_refused(self):
        self.fixture.split.unlink()
        self.fixture.split.symlink_to(self.fixture.direct)
        lease = self.adapter.acquire_production_lock()
        with self.assertRaisesRegex(RuntimeAuthorityError, "not a real regular file"):
            self.adapter.select_split_bus_route()
        self.adapter.release_production_lock(lease)

    def test_prepared_state_is_bound_to_current_approval(self):
        lease = self.adapter.acquire_production_lock()
        self.adapter.publish_prepared_route(PreparedRoute.DIRECT_READY, "direct prepared")
        replacement = ActivationApprovalRecord(
            **{
                **self.fixture.approval.__dict__,
                "transaction_id": "stage-c21-replacement-transaction",
            }
        )
        ApprovalStore(self.fixture.state_root).replace_exact(
            self.fixture.approval,
            replacement,
            lock_held=True,
        )
        with self.assertRaisesRegex(RuntimeAuthorityError, "approval identity mismatch"):
            self.adapter.read_prepared_route()
        ApprovalStore(self.fixture.state_root).replace_exact(
            replacement,
            self.fixture.approval,
            lock_held=True,
        )
        self.adapter.release_production_lock(lease)

    def test_temporary_approval_is_not_runtime_eligible(self):
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
            self.adapter.read_committed_approval()

    def test_module_has_no_process_service_pcm_or_generic_command_boundary(self):
        source = (SCRIPTS / "stage_c_runtime_authority/linux_runtime_filesystem.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "subprocess",
            "systemctl",
            "aplay",
            "amixer",
            "NOTIFY_SOCKET",
            "shell=True",
            "os.system",
            "os.exec",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("O_NOFOLLOW", source)
        self.assertIn("O_EXCL", source)
        self.assertIn("os.replace", source)
        self.assertIn("source changed during atomic copy", source)


if __name__ == "__main__":
    unittest.main()
