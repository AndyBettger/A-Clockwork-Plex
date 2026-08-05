from __future__ import annotations

import fcntl
import hashlib
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
from stage_c_runtime_authority.install_runtime_filesystem import InstallRuntimeFilesystem
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
)
from stage_c_runtime_authority.supervisor_model import PreparedRoute


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstallFilesystemFixture:
    def __init__(self, root: Path):
        self.root = root
        self.lease = "stage-c21-install-lease-test"
        self.state_root = root / "var/lib/a-clockwork-plex/split-bus"
        self.lock = root / "run/lock/a-clockwork-plex-audio-route.lock"
        self.active = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        self.split = root / "etc/a-clockwork-plex/audio-routes/split-bus.conf"
        self.direct = root / "etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf"
        self.config = root / "etc/a-clockwork-plex/camilladsp-split-bus.yml"
        self.binary = root / "usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp"
        self.launcher = root / "usr/local/bin/a-clockwork-plex-audio-route"
        self.sudoers = root / "etc/sudoers.d/a-clockwork-plex-audio-route"
        self.contract = root / "usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json"
        for directory in (
            self.state_root,
            self.lock.parent,
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
        self._write(self.active, self.split.read_bytes(), 0o644)
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
            "package_phase": "stage-c21-install-test",
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
            phase=ApprovalPhase.TEMPORARY,
            transaction_id="stage-c21-install-transaction-test",
            lock_lease_id=self.lease,
            package_fingerprint=fingerprint,
            commit_manifest_sha256=None,
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
            committed_at=None,
        )
        ApprovalStore(self.state_root).publish_new(self.approval, lock_held=True)
        self.lock_fd = os.open(
            self.lock,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        os.fchmod(self.lock_fd, 0o600)
        os.write(self.lock_fd, (self.lease + "\n").encode("ascii"))
        os.fsync(self.lock_fd)
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _map(self, absolute: str) -> Path:
        return self.root.joinpath(*Path(absolute).parts[1:])

    @staticmethod
    def _write(path: Path, payload: bytes, mode: int) -> None:
        path.write_bytes(payload)
        path.chmod(mode)

    def close(self) -> None:
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self.lock_fd)
        except OSError:
            pass


class StageCInstallRuntimeFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = InstallFilesystemFixture(self.root)
        self.adapter = InstallRuntimeFilesystem._for_test(self.root)

    def tearDown(self):
        if self.adapter.borrowed_lock_asserted and self.adapter._borrowed_fd is not None:
            os.close(self.adapter._borrowed_fd)
            self.adapter._borrowed_fd = None
            self.adapter._borrowed_inode = None
            self.adapter._borrowed_lease_id = None
        self.fixture.close()
        self.temporary.cleanup()

    def test_borrowed_assertion_proves_external_lock_and_never_owns_it(self):
        lease = self.adapter.assert_borrowed_transaction_lock()
        self.assertEqual(lease, self.fixture.lease)
        self.assertTrue(self.adapter.borrowed_lock_asserted)
        self.assertFalse(self.adapter.lock_held)
        self.adapter.release_borrowed_transaction_lock_assertion(lease)
        self.assertFalse(self.adapter.borrowed_lock_asserted)
        self.assertTrue(self.fixture.lock.exists())
        second_fd = os.open(self.fixture.lock, os.O_RDWR | os.O_NOFOLLOW)
        try:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(second_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(second_fd)

    def test_unlocked_wrong_lease_or_noncanonical_lock_is_refused(self):
        fcntl.flock(self.fixture.lock_fd, fcntl.LOCK_UN)
        with self.assertRaisesRegex(RuntimeAuthorityError, "not held"):
            self.adapter.assert_borrowed_transaction_lock()
        fcntl.flock(self.fixture.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        os.pwrite(self.fixture.lock_fd, b"wrong-lease\n", 0)
        os.ftruncate(self.fixture.lock_fd, len(b"wrong-lease\n"))
        with self.assertRaisesRegex(RuntimeAuthorityError, "differs"):
            self.adapter.assert_borrowed_transaction_lock()

        os.pwrite(self.fixture.lock_fd, self.fixture.lease.encode("ascii"), 0)
        os.ftruncate(self.fixture.lock_fd, len(self.fixture.lease))
        with self.assertRaisesRegex(RuntimeAuthorityError, "not canonical"):
            self.adapter.assert_borrowed_transaction_lock()

    def test_substituted_lock_is_detected_without_unlinking_replacement(self):
        lease = self.adapter.assert_borrowed_transaction_lock()
        parked = self.fixture.lock.with_name(self.fixture.lock.name + ".parked")
        self.fixture.lock.rename(parked)
        self.fixture.lock.write_text("replacement\n", encoding="ascii")
        self.fixture.lock.chmod(0o600)
        with self.assertRaisesRegex(RuntimeAuthorityError, "substituted"):
            self.adapter.release_borrowed_transaction_lock_assertion(lease)
        self.assertEqual(self.fixture.lock.read_text(encoding="ascii"), "replacement\n")
        self.fixture.lock.unlink()
        parked.rename(self.fixture.lock)

    def test_external_release_before_assertion_close_is_detected(self):
        lease = self.adapter.assert_borrowed_transaction_lock()
        fcntl.flock(self.fixture.lock_fd, fcntl.LOCK_UN)
        with self.assertRaisesRegex(RuntimeAuthorityError, "not held"):
            self.adapter.release_borrowed_transaction_lock_assertion(lease)
        fcntl.flock(self.fixture.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_valid_temporary_contract_publishes_pending_and_split_active_state(self):
        lease = self.adapter.assert_borrowed_transaction_lock()
        approval = self.adapter.validate_install_prepared_contract()
        self.assertEqual(approval, self.fixture.approval)
        self.adapter.publish_install_prepared_route("transaction route accepted")
        self.assertIs(self.adapter.read_install_prepared_route(), PreparedRoute.SPLIT_PENDING)
        state = json.loads((self.fixture.state_root / "route-state.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["runtime_mode"])
        self.adapter.publish_install_split_active("strict health passed")
        state = json.loads((self.fixture.state_root / "route-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["runtime_mode"], "split-bus-active")
        self.assertEqual(sha256(self.fixture.active), self.fixture.approval.active_route_sha256)
        self.adapter.release_borrowed_transaction_lock_assertion(lease)

    def test_package_route_loopback_and_dac_mismatches_fail_closed(self):
        mutations = (
            (self.fixture.config, b"changed-config\n", "package files are invalid"),
            (self.fixture.active, b"changed-route\n", "active split-bus route mismatch"),
            (
                self.root / "sys/module/snd_aloop/parameters/id",
                b"WrongLoopback\n",
                "loopback contract mismatch",
            ),
        )
        for path, payload, message in mutations:
            with self.subTest(path=path):
                original = path.read_bytes()
                lease = self.adapter.assert_borrowed_transaction_lock()
                path.write_bytes(payload)
                with self.assertRaisesRegex(RuntimeAuthorityError, message):
                    self.adapter.validate_install_prepared_contract()
                path.write_bytes(original)
                self.adapter.release_borrowed_transaction_lock_assertion(lease)

        lease = self.adapter.assert_borrowed_transaction_lock()
        (self.root / "proc/asound/Pro").unlink()
        with self.assertRaisesRegex(RuntimeAuthorityError, "DAC contract mismatch"):
            self.adapter.validate_install_prepared_contract()
        self.adapter.release_borrowed_transaction_lock_assertion(lease)

    def test_committed_approval_is_not_accepted_by_install_runtime(self):
        committed = self.fixture.approval.promote(
            commit_manifest_sha256="f" * 64,
            committed_at="2026-08-05T20:01:00Z",
        )
        ApprovalStore(self.fixture.state_root).replace_exact(
            self.fixture.approval,
            committed,
            lock_held=True,
        )
        with self.assertRaisesRegex(RuntimeAuthorityError, "temporary"):
            self.adapter.assert_borrowed_transaction_lock()

    def test_install_runtime_cannot_acquire_release_or_reselect_routes(self):
        with self.assertRaisesRegex(RuntimeAuthorityError, "already-held lease"):
            self.adapter.acquire_production_lock()
        with self.assertRaisesRegex(RuntimeAuthorityError, "must not release"):
            self.adapter.release_production_lock("lease")
        with self.assertRaisesRegex(RuntimeAuthorityError, "must not reselect"):
            self.adapter.select_split_bus_route()
        with self.assertRaisesRegex(RuntimeAuthorityError, "exact transaction rollback"):
            self.adapter.select_direct_failback_route()

    def test_state_publication_requires_live_borrowed_assertion(self):
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires an asserted"):
            self.adapter.publish_install_prepared_route("not allowed")
        lease = self.adapter.assert_borrowed_transaction_lock()
        self.adapter.publish_install_prepared_route("allowed")
        self.adapter.release_borrowed_transaction_lock_assertion(lease)
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires an asserted"):
            self.adapter.publish_install_split_active("not allowed")

    def test_module_has_no_process_systemd_pcm_or_direct_failback_command_boundary(self):
        source = (SCRIPTS / "stage_c_runtime_authority/install_runtime_filesystem.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("flock", source)
        self.assertIn("lock_lease_id", source)
        self.assertIn("O_NOFOLLOW", source)
        for forbidden in (
            "subprocess",
            "systemctl",
            "aplay",
            "amixer",
            "shell=True",
            "os.system",
            "os.exec",
            "select_direct_failback_route()",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("pre-commit failure belongs to exact transaction rollback", source)


if __name__ == "__main__":
    unittest.main()
