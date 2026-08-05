#!/usr/bin/python3
from __future__ import annotations

import errno
import fcntl
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

from .approval_store import ApprovalStore
from .linux_runtime_filesystem import (
    FILE_MODE,
    LOCK_MODE,
    LinuxRuntimeFilesystem,
    _require_real_ancestor_chain,
    _require_real_directory,
    _require_regular,
    _sha256,
    _write_all,
)
from .model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
    canonical_json_bytes,
    utc_timestamp,
)
from .supervisor_model import PreparedRoute, SupervisorMode


class InstallRuntimeFilesystem(LinuxRuntimeFilesystem):
    """Temporary transaction-held lease adapter; it never acquires or releases the transaction lock."""

    def __init__(self) -> None:
        super().__init__()
        self._borrowed_fd: int | None = None
        self._borrowed_inode: tuple[int, int] | None = None
        self._borrowed_lease_id: str | None = None

    @classmethod
    def _for_test(cls, root: Path) -> "InstallRuntimeFilesystem":
        instance = super()._for_test(root)
        instance.__class__ = cls
        instance._borrowed_fd = None
        instance._borrowed_inode = None
        instance._borrowed_lease_id = None
        return instance

    @property
    def borrowed_lock_asserted(self) -> bool:
        return (
            self._borrowed_fd is not None
            and self._borrowed_inode is not None
            and self._borrowed_lease_id is not None
        )

    def read_temporary_approval(self) -> ActivationApprovalRecord:
        record = ApprovalStore(self._paths.state_root).read()
        if record.phase is not ApprovalPhase.TEMPORARY:
            raise RuntimeAuthorityError("install runtime requires a temporary transaction-bound approval")
        return record

    def _lock_content(self, fd: int) -> str:
        raw = os.pread(fd, 512, 0)
        try:
            value = raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RuntimeAuthorityError("transaction lock lease is not ASCII") from exc
        if not value.endswith("\n") or value.count("\n") != 1:
            raise RuntimeAuthorityError("transaction lock lease content is not canonical")
        return value[:-1]

    @staticmethod
    def _prove_externally_held(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return
            raise RuntimeAuthorityError(f"transaction lock contention proof failed: {exc}") from exc
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            raise RuntimeAuthorityError("transaction lock is not held by the authoritative installer")

    def assert_borrowed_transaction_lock(self) -> str:
        if self.lock_held or self.borrowed_lock_asserted:
            raise RuntimeAuthorityError("install runtime lock authority is already established")
        approval = self.read_temporary_approval()
        parent = self._paths.lock.parent
        _require_real_directory(
            parent,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        info = _require_regular(
            self._paths.lock,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=LOCK_MODE,
        )
        fd = os.open(self._paths.lock, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            descriptor = os.fstat(fd)
            if (descriptor.st_dev, descriptor.st_ino) != (info.st_dev, info.st_ino):
                raise RuntimeAuthorityError("transaction lock identity changed during assertion")
            if self._lock_content(fd) != approval.lock_lease_id:
                raise RuntimeAuthorityError("transaction lock lease differs from temporary approval")
            self._prove_externally_held(fd)
        except BaseException:
            os.close(fd)
            raise
        self._borrowed_fd = fd
        self._borrowed_inode = (descriptor.st_dev, descriptor.st_ino)
        self._borrowed_lease_id = approval.lock_lease_id
        return approval.lock_lease_id

    def _verify_borrowed_transaction_lock(self, lease_id: str | None = None) -> None:
        if not self.borrowed_lock_asserted:
            raise RuntimeAuthorityError("temporary install mutation requires an asserted transaction lock")
        if lease_id is not None and lease_id != self._borrowed_lease_id:
            raise RuntimeAuthorityError("borrowed transaction lock lease identity mismatch")
        assert self._borrowed_fd is not None
        assert self._borrowed_inode is not None
        assert self._borrowed_lease_id is not None
        descriptor = os.fstat(self._borrowed_fd)
        info = _require_regular(
            self._paths.lock,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=LOCK_MODE,
        )
        if (
            (descriptor.st_dev, descriptor.st_ino) != self._borrowed_inode
            or (info.st_dev, info.st_ino) != self._borrowed_inode
        ):
            raise RuntimeAuthorityError("borrowed transaction lock pathname was substituted")
        if self._lock_content(self._borrowed_fd) != self._borrowed_lease_id:
            raise RuntimeAuthorityError("borrowed transaction lock lease content changed")
        self._prove_externally_held(self._borrowed_fd)

    def release_borrowed_transaction_lock_assertion(self, lease_id: str) -> None:
        self._verify_borrowed_transaction_lock(lease_id)
        assert self._borrowed_fd is not None
        os.close(self._borrowed_fd)
        self._borrowed_fd = None
        self._borrowed_inode = None
        self._borrowed_lease_id = None

    def acquire_production_lock(self) -> str:
        raise RuntimeAuthorityError("install runtime must use the transaction's already-held lease")

    def release_production_lock(self, lease_id: str) -> None:
        del lease_id
        raise RuntimeAuthorityError("install runtime must not release the transaction's lock")

    def select_split_bus_route(self) -> None:
        raise RuntimeAuthorityError("install runtime must not reselect the transaction-selected route")

    def select_direct_failback_route(self) -> None:
        raise RuntimeAuthorityError("pre-commit failure belongs to exact transaction rollback, not runtime failback")

    def validate_install_prepared_contract(self) -> ActivationApprovalRecord:
        self._verify_borrowed_transaction_lock()
        approval = self.read_temporary_approval()
        if approval.lock_lease_id != self._borrowed_lease_id:
            raise RuntimeAuthorityError("temporary approval no longer matches the asserted transaction lease")
        contract = self._load_contract()
        if contract["package_fingerprint"] != approval.package_fingerprint:
            raise RuntimeAuthorityError("temporary approval package fingerprint mismatch")
        if not self._contract_files_valid(contract):
            raise RuntimeAuthorityError("temporary install package files are invalid")
        comparisons = (
            (self._paths.active_route, approval.active_route_sha256, "active split-bus route"),
            (self._paths.split_route, approval.active_route_sha256, "split-bus candidate"),
            (self._paths.direct_route, approval.direct_route_sha256, "direct failback candidate"),
            (self._paths.camilladsp_config, approval.camilladsp_config_sha256, "CamillaDSP configuration"),
            (self._paths.camilladsp_binary, approval.camilladsp_binary_sha256, "CamillaDSP binary"),
        )
        for path, expected, label in comparisons:
            if self._digest_or_empty(path) != expected:
                raise RuntimeAuthorityError(f"temporary install {label} mismatch")
        if not self._loopback_valid(approval):
            raise RuntimeAuthorityError("temporary install loopback contract mismatch")
        if not self._dac_valid():
            raise RuntimeAuthorityError("temporary install DAC contract mismatch")
        return approval

    def _publish_install_state(self, payload: dict[str, Any]) -> None:
        self._verify_borrowed_transaction_lock()
        approval = self.read_temporary_approval()
        root = self._paths.state_root
        _require_real_directory(
            root,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        complete = {
            "schema_version": 1,
            "approval_sha256": approval.record_sha256,
            "updated_at": utc_timestamp(),
            **payload,
        }
        data = canonical_json_bytes(complete) + b"\n"
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        temp_name = f".route-state.install-{secrets.token_hex(8)}"
        fd: int | None = None
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                FILE_MODE,
                dir_fd=root_fd,
            )
            _write_all(fd, data)
            os.fchmod(fd, FILE_MODE)
            os.fchown(fd, self._paths.expected_uid, self._paths.expected_gid)
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.replace(temp_name, self._paths.runtime_state.name, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            os.fsync(root_fd)
        except BaseException:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temp_name, dir_fd=root_fd)
            except FileNotFoundError:
                pass
            raise
        finally:
            os.close(root_fd)

    def publish_install_prepared_route(self, reason: str) -> None:
        if not reason.strip():
            raise RuntimeAuthorityError("install preparation reason is empty")
        approval = self.validate_install_prepared_contract()
        if self._digest_or_empty(self._paths.active_route) != approval.active_route_sha256:
            raise RuntimeAuthorityError("transaction-selected split route changed before publication")
        self._publish_install_state(
            {
                "prepared_route": PreparedRoute.SPLIT_PENDING.value,
                "runtime_mode": None,
                "reason": reason,
            }
        )

    def _read_install_state(self) -> dict[str, Any]:
        _require_real_ancestor_chain(
            self._paths.runtime_state,
            root=self._paths.system_root,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        _require_regular(
            self._paths.runtime_state,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=FILE_MODE,
        )
        payload = json.loads(self._paths.runtime_state.read_text(encoding="utf-8"))
        expected = {
            "schema_version",
            "approval_sha256",
            "updated_at",
            "prepared_route",
            "runtime_mode",
            "reason",
        }
        approval = self.read_temporary_approval()
        if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != 1:
            raise RuntimeAuthorityError("temporary install route state schema is invalid")
        if payload.get("approval_sha256") != approval.record_sha256:
            raise RuntimeAuthorityError("temporary install route state approval identity mismatch")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            raise RuntimeAuthorityError("temporary install route state reason is invalid")
        return payload

    def read_install_prepared_route(self) -> PreparedRoute:
        self._verify_borrowed_transaction_lock()
        payload = self._read_install_state()
        if payload.get("runtime_mode") is not None:
            raise RuntimeAuthorityError("temporary install state is no longer a preparation record")
        if payload.get("prepared_route") != PreparedRoute.SPLIT_PENDING.value:
            raise RuntimeAuthorityError("temporary install prepared route is not split-bus pending")
        return PreparedRoute.SPLIT_PENDING

    def publish_install_split_active(self, reason: str) -> None:
        if not reason.strip():
            raise RuntimeAuthorityError("install split-active reason is empty")
        approval = self.validate_install_prepared_contract()
        if self._digest_or_empty(self._paths.active_route) != approval.active_route_sha256:
            raise RuntimeAuthorityError("temporary install split route changed before health publication")
        self._publish_install_state(
            {
                "prepared_route": PreparedRoute.SPLIT_PENDING.value,
                "runtime_mode": SupervisorMode.SPLIT_ACTIVE.value,
                "reason": reason,
            }
        )
