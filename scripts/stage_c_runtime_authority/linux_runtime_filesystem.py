#!/usr/bin/python3
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .approval_store import ApprovalStore
from .model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    BootObservation,
    RuntimeAuthorityError,
    canonical_json_bytes,
    utc_timestamp,
)
from .supervisor_model import PreparedRoute, SupervisorMode


LOCK_MODE = 0o600
FILE_MODE = 0o644
LOCK_LEASE_PREFIX = "stage-c21-runtime-lock-"
EXPECTED_CONTRACT_FIELDS = {
    "schema_version",
    "package_phase",
    "package_fingerprint",
    "host_mutation_available",
    "files",
}


@dataclass(frozen=True)
class _RuntimePaths:
    system_root: Path
    expected_uid: int
    expected_gid: int

    @classmethod
    def production(cls) -> "_RuntimePaths":
        return cls(Path("/"), 0, 0)

    @classmethod
    def test_root(cls, root: Path) -> "_RuntimePaths":
        return cls(root, os.geteuid(), os.getegid())

    def map(self, absolute: str) -> Path:
        pure = PurePosixPath(absolute)
        if not pure.is_absolute() or ".." in pure.parts:
            raise RuntimeAuthorityError(f"invalid fixed runtime path: {absolute}")
        return self.system_root.joinpath(*pure.parts[1:])

    @property
    def lock(self) -> Path:
        return self.map("/run/lock/a-clockwork-plex-audio-route.lock")

    @property
    def state_root(self) -> Path:
        return self.map("/var/lib/a-clockwork-plex/split-bus")

    @property
    def active_route(self) -> Path:
        return self.map("/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf")

    @property
    def split_route(self) -> Path:
        return self.map("/etc/a-clockwork-plex/audio-routes/split-bus.conf")

    @property
    def direct_route(self) -> Path:
        return self.map("/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf")

    @property
    def package_contract(self) -> Path:
        return self.map("/usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json")

    @property
    def camilladsp_config(self) -> Path:
        return self.map("/etc/a-clockwork-plex/camilladsp-split-bus.yml")

    @property
    def camilladsp_binary(self) -> Path:
        return self.map("/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp")

    @property
    def module_parameters(self) -> Path:
        return self.map("/sys/module/snd_aloop/parameters")

    @property
    def dac_alias(self) -> Path:
        return self.map("/proc/asound/Pro")

    @property
    def runtime_state(self) -> Path:
        return self.state_root / "route-state.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_real_directory(path: Path, *, uid: int, gid: int) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise RuntimeAuthorityError(f"runtime directory is not real: {path}")
    if info.st_uid != uid or info.st_gid != gid:
        raise RuntimeAuthorityError(f"runtime directory owner mismatch: {path}")
    return info


def _require_real_ancestor_chain(
    path: Path,
    *,
    root: Path,
    uid: int,
    gid: int,
) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RuntimeAuthorityError(f"runtime path escaped fixed system root: {path}") from exc
    current = root
    _require_real_directory(current, uid=uid, gid=gid)
    for part in relative.parts[:-1]:
        current = current / part
        _require_real_directory(current, uid=uid, gid=gid)


def _require_regular(path: Path, *, uid: int, gid: int, mode: int | None = None) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeAuthorityError(f"runtime object is not a real regular file: {path}")
    if info.st_uid != uid or info.st_gid != gid:
        raise RuntimeAuthorityError(f"runtime file owner mismatch: {path}")
    if mode is not None and stat.S_IMODE(info.st_mode) != mode:
        raise RuntimeAuthorityError(f"runtime file mode mismatch: {path}")
    return info


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise RuntimeAuthorityError("short runtime filesystem write")
        view = view[written:]


class LinuxRuntimeFilesystem:
    """Fixed production filesystem adapter; public construction accepts no paths."""

    def __init__(self) -> None:
        self._paths = _RuntimePaths.production()
        self._lock_fd: int | None = None
        self._lock_inode: tuple[int, int] | None = None
        self._lease_id: str | None = None

    @classmethod
    def _for_test(cls, root: Path) -> "LinuxRuntimeFilesystem":
        instance = cls.__new__(cls)
        instance._paths = _RuntimePaths.test_root(root)
        instance._lock_fd = None
        instance._lock_inode = None
        instance._lease_id = None
        return instance

    @property
    def lock_held(self) -> bool:
        return self._lock_fd is not None and self._lease_id is not None

    def _require_lock(self) -> None:
        if not self.lock_held:
            raise RuntimeAuthorityError("runtime filesystem mutation requires the production lock")

    def acquire_production_lock(self) -> str:
        if self.lock_held:
            raise RuntimeAuthorityError("production lock is already held by this runtime adapter")
        parent = self._paths.lock.parent
        _require_real_directory(
            parent,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        try:
            self._paths.lock.lstat()
        except FileNotFoundError:
            pass
        else:
            raise RuntimeAuthorityError("production lock path already exists")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(self._paths.lock, flags, LOCK_MODE)
        try:
            os.fchmod(fd, LOCK_MODE)
            os.fchown(fd, self._paths.expected_uid, self._paths.expected_gid)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            info = os.fstat(fd)
            path_info = self._paths.lock.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_dev != path_info.st_dev
                or info.st_ino != path_info.st_ino
            ):
                raise RuntimeAuthorityError("production lock descriptor identity mismatch")
            second = os.open(self._paths.lock, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                try:
                    fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                else:
                    fcntl.flock(second, fcntl.LOCK_UN)
                    raise RuntimeAuthorityError("production lock contention proof failed")
            finally:
                os.close(second)
            lease = f"{LOCK_LEASE_PREFIX}{secrets.token_hex(12)}"
            os.ftruncate(fd, 0)
            _write_all(fd, (lease + "\n").encode("ascii"))
            os.fsync(fd)
        except BaseException:
            try:
                descriptor = os.fstat(fd)
                path_info = self._paths.lock.lstat()
                if (
                    stat.S_ISREG(path_info.st_mode)
                    and descriptor.st_dev == path_info.st_dev
                    and descriptor.st_ino == path_info.st_ino
                ):
                    self._paths.lock.unlink()
            except OSError:
                pass
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
            raise
        self._lock_fd = fd
        self._lock_inode = (info.st_dev, info.st_ino)
        self._lease_id = lease
        return lease

    def release_production_lock(self, lease_id: str) -> None:
        self._require_lock()
        if lease_id != self._lease_id:
            raise RuntimeAuthorityError("production lock lease identity mismatch")
        assert self._lock_fd is not None
        assert self._lock_inode is not None
        info = self._paths.lock.lstat()
        if (info.st_dev, info.st_ino) != self._lock_inode or not stat.S_ISREG(info.st_mode):
            raise RuntimeAuthorityError("refusing to release a substituted production lock")
        self._paths.lock.unlink()
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._lock_fd = None
        self._lock_inode = None
        self._lease_id = None

    def read_committed_approval(self) -> ActivationApprovalRecord:
        record = ApprovalStore(self._paths.state_root).read()
        if record.phase is not ApprovalPhase.COMMITTED:
            raise RuntimeAuthorityError("runtime filesystem requires a committed approval")
        return record

    def _load_contract(self) -> dict[str, Any]:
        _require_real_ancestor_chain(
            self._paths.package_contract,
            root=self._paths.system_root,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        _require_regular(
            self._paths.package_contract,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=FILE_MODE,
        )
        payload = json.loads(self._paths.package_contract.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != EXPECTED_CONTRACT_FIELDS:
            raise RuntimeAuthorityError("runtime package contract fields are invalid")
        if payload["schema_version"] != 1 or not isinstance(payload["files"], list):
            raise RuntimeAuthorityError("runtime package contract schema is invalid")
        rows = payload["files"]
        if any(not isinstance(row, dict) or set(row) != {"path", "sha256"} for row in rows):
            raise RuntimeAuthorityError("runtime package contract row is invalid")
        ordered = sorted(rows, key=lambda row: row["path"])
        if rows != ordered or len({row["path"] for row in rows}) != len(rows):
            raise RuntimeAuthorityError("runtime package file rows are not unique and ordered")
        fingerprint = hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if payload["package_fingerprint"] != fingerprint:
            raise RuntimeAuthorityError("runtime package fingerprint mismatch")
        return payload

    @staticmethod
    def _expected_payload_mode(absolute: str) -> int:
        if absolute in {
            "/usr/local/bin/a-clockwork-plex-audio-route",
            "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp",
        }:
            return 0o755
        if absolute == "/etc/sudoers.d/a-clockwork-plex-audio-route":
            return 0o440
        return FILE_MODE

    def _contract_files_valid(self, contract: dict[str, Any]) -> bool:
        for row in contract["files"]:
            absolute = str(row["path"])
            path = self._paths.map(absolute)
            try:
                _require_real_ancestor_chain(
                    path,
                    root=self._paths.system_root,
                    uid=self._paths.expected_uid,
                    gid=self._paths.expected_gid,
                )
                _require_regular(
                    path,
                    uid=self._paths.expected_uid,
                    gid=self._paths.expected_gid,
                    mode=self._expected_payload_mode(absolute),
                )
            except (OSError, RuntimeAuthorityError):
                return False
            if _sha256(path) != row["sha256"]:
                return False
        return True

    def _module_value(self, name: str) -> str | None:
        try:
            return (self._paths.module_parameters / name).read_text(encoding="utf-8").strip().split(",", 1)[0]
        except OSError:
            return None

    def _loopback_valid(self, approval: ActivationApprovalRecord) -> bool:
        expected = {
            "index": str(approval.loopback_index),
            "id": approval.loopback_id,
            "pcm_substreams": str(approval.loopback_pcm_substreams),
            "pcm_notify": str(approval.loopback_pcm_notify),
            "enable": "Y",
        }
        return all(self._module_value(name) == value for name, value in expected.items())

    def _dac_valid(self) -> bool:
        try:
            alias_info = self._paths.dac_alias.lstat()
            if not stat.S_ISLNK(alias_info.st_mode):
                return False
            target = os.readlink(self._paths.dac_alias)
        except OSError:
            return False
        name = Path(target).name
        if not (name.startswith("card") and name[4:].isdigit()):
            return False
        device = self._paths.map(f"/dev/snd/pcmC{name[4:]}D0p")
        try:
            device_info = device.lstat()
        except OSError:
            return False
        return not stat.S_ISLNK(device_info.st_mode) and (
            stat.S_ISCHR(device_info.st_mode)
            or (self._paths.system_root != Path("/") and stat.S_ISREG(device_info.st_mode))
        )

    def _digest_or_empty(self, path: Path) -> str:
        try:
            _require_real_ancestor_chain(
                path,
                root=self._paths.system_root,
                uid=self._paths.expected_uid,
                gid=self._paths.expected_gid,
            )
            _require_regular(
                path,
                uid=self._paths.expected_uid,
                gid=self._paths.expected_gid,
            )
            return _sha256(path)
        except (OSError, RuntimeAuthorityError):
            return ""

    def observe_boot_contract(self) -> BootObservation:
        approval = self.read_committed_approval()
        contract = self._load_contract()
        return BootObservation(
            package_fingerprint=str(contract["package_fingerprint"]),
            split_route_sha256=self._digest_or_empty(self._paths.split_route),
            direct_route_sha256=self._digest_or_empty(self._paths.direct_route),
            camilladsp_config_sha256=self._digest_or_empty(self._paths.camilladsp_config),
            camilladsp_binary_version=approval.camilladsp_binary_version,
            camilladsp_binary_sha256=self._digest_or_empty(self._paths.camilladsp_binary),
            loopback_index=approval.loopback_index,
            loopback_id=approval.loopback_id,
            loopback_pcm_substreams=approval.loopback_pcm_substreams,
            loopback_pcm_notify=approval.loopback_pcm_notify,
            dac_card=approval.dac_card,
            dac_device=approval.dac_device,
            sample_rate=approval.sample_rate,
            sample_format=approval.sample_format,
            period_size=approval.period_size,
            buffer_size=approval.buffer_size,
            managed_files_valid=self._contract_files_valid(contract),
            split_route_valid=self._digest_or_empty(self._paths.split_route) == approval.active_route_sha256,
            direct_route_valid=self._digest_or_empty(self._paths.direct_route) == approval.direct_route_sha256,
            loopback_valid=self._loopback_valid(approval),
            dac_valid=self._dac_valid(),
            camilladsp_start_succeeded=False,
            split_bus_health_valid=False,
        )

    def _atomic_route_replace(self, source: Path, expected_sha256: str) -> None:
        self._require_lock()
        _require_real_ancestor_chain(
            source,
            root=self._paths.system_root,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        source_identity = _require_regular(
            source,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=FILE_MODE,
        )
        source_before = _sha256(source)
        if source_before != expected_sha256:
            raise RuntimeAuthorityError("route source digest differs from committed approval")
        active = self._paths.active_route
        _require_real_ancestor_chain(
            active,
            root=self._paths.system_root,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        active_identity = _require_regular(
            active,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=FILE_MODE,
        )
        approval = self.read_committed_approval()
        if _sha256(active) not in {approval.active_route_sha256, approval.direct_route_sha256}:
            raise RuntimeAuthorityError("active route is outside committed Stage C runtime identities")
        parent = active.parent
        _require_real_directory(
            parent,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        temp_name = f".{active.name}.runtime-{secrets.token_hex(8)}"
        fd: int | None = None
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                FILE_MODE,
                dir_fd=parent_fd,
            )
            source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                opened_source = os.fstat(source_fd)
                if (opened_source.st_dev, opened_source.st_ino) != (
                    source_identity.st_dev,
                    source_identity.st_ino,
                ):
                    raise RuntimeAuthorityError("route source identity changed before copy")
                while True:
                    chunk = os.read(source_fd, 1024 * 1024)
                    if not chunk:
                        break
                    _write_all(fd, chunk)
            finally:
                os.close(source_fd)
            os.fchmod(fd, FILE_MODE)
            os.fchown(fd, self._paths.expected_uid, self._paths.expected_gid)
            os.fsync(fd)
            temporary_info = os.fstat(fd)
            os.close(fd)
            fd = None
            if _sha256(source) != source_before:
                raise RuntimeAuthorityError("route source changed during atomic copy")
            temporary_path = parent / temp_name
            if _sha256(temporary_path) != expected_sha256:
                raise RuntimeAuthorityError("temporary route digest mismatch")
            current = active.lstat()
            if (current.st_dev, current.st_ino) != (
                active_identity.st_dev,
                active_identity.st_ino,
            ):
                raise RuntimeAuthorityError("active route identity changed before publication")
            if (temporary_info.st_dev, temporary_info.st_ino) != (
                temporary_path.lstat().st_dev,
                temporary_path.lstat().st_ino,
            ):
                raise RuntimeAuthorityError("temporary route identity changed before publication")
            os.replace(temp_name, active.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            os.fsync(parent_fd)
        except BaseException:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temp_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            raise
        finally:
            os.close(parent_fd)
        _require_regular(
            active,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
            mode=FILE_MODE,
        )
        if _sha256(active) != expected_sha256:
            raise RuntimeAuthorityError("atomically published active route digest mismatch")

    def select_split_bus_route(self) -> None:
        approval = self.read_committed_approval()
        self._atomic_route_replace(self._paths.split_route, approval.active_route_sha256)

    def select_direct_failback_route(self) -> None:
        approval = self.read_committed_approval()
        self._atomic_route_replace(self._paths.direct_route, approval.direct_route_sha256)

    def _publish_state(self, payload: dict[str, Any]) -> None:
        self._require_lock()
        root = self._paths.state_root
        _require_real_directory(
            root,
            uid=self._paths.expected_uid,
            gid=self._paths.expected_gid,
        )
        complete = {
            "schema_version": 1,
            "approval_sha256": self.read_committed_approval().record_sha256,
            "updated_at": utc_timestamp(),
            **payload,
        }
        data = canonical_json_bytes(complete) + b"\n"
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        temp_name = f".route-state.new-{secrets.token_hex(8)}"
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

    def publish_prepared_route(self, route: PreparedRoute, reason: str) -> None:
        if not reason.strip():
            raise RuntimeAuthorityError("prepared route reason is empty")
        approval = self.read_committed_approval()
        expected = (
            approval.active_route_sha256
            if route is PreparedRoute.SPLIT_PENDING
            else approval.direct_route_sha256
        )
        if self._digest_or_empty(self._paths.active_route) != expected:
            raise RuntimeAuthorityError("prepared route publication does not match active route")
        self._publish_state(
            {
                "prepared_route": route.value,
                "runtime_mode": None,
                "reason": reason,
            }
        )

    def read_prepared_route(self) -> PreparedRoute:
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
        expected_fields = {
            "schema_version",
            "approval_sha256",
            "updated_at",
            "prepared_route",
            "runtime_mode",
            "reason",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != expected_fields
            or payload.get("schema_version") != 1
        ):
            raise RuntimeAuthorityError("runtime route state schema is invalid")
        if payload.get("approval_sha256") != self.read_committed_approval().record_sha256:
            raise RuntimeAuthorityError("runtime route state approval identity mismatch")
        if payload.get("runtime_mode") is not None:
            raise RuntimeAuthorityError("runtime route state is not a preparation record")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            raise RuntimeAuthorityError("runtime route state reason is invalid")
        try:
            return PreparedRoute(str(payload["prepared_route"]))
        except (KeyError, ValueError) as exc:
            raise RuntimeAuthorityError("runtime prepared route state is invalid") from exc

    def publish_runtime_mode(self, mode: SupervisorMode, reason: str) -> None:
        if not reason.strip():
            raise RuntimeAuthorityError("runtime mode reason is empty")
        approval = self.read_committed_approval()
        expected = (
            approval.active_route_sha256
            if mode is SupervisorMode.SPLIT_ACTIVE
            else approval.direct_route_sha256
        )
        if self._digest_or_empty(self._paths.active_route) != expected:
            raise RuntimeAuthorityError("runtime mode publication does not match active route")
        prepared = (
            PreparedRoute.SPLIT_PENDING
            if mode is SupervisorMode.SPLIT_ACTIVE
            else PreparedRoute.DIRECT_READY
        )
        self._publish_state(
            {
                "prepared_route": prepared.value,
                "runtime_mode": mode.value,
                "reason": reason,
            }
        )
