#!/usr/bin/python3
from __future__ import annotations

import ctypes
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Callable

from .model import ActivationApprovalRecord, RuntimeAuthorityError, canonical_json_bytes


APPROVAL_NAME = "activation-approved"
MAX_RECORD_BYTES = 64 * 1024
RENAME_EXCHANGE = 2
FaultHook = Callable[[str], None]


def _noop_fault_hook(_point: str) -> None:
    return None


def _rename_exchange(src_dir_fd: int, src_name: str, dst_dir_fd: int, dst_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise RuntimeAuthorityError("renameat2 is unavailable") from exc
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(src_dir_fd, os.fsencode(src_name), dst_dir_fd, os.fsencode(dst_name), RENAME_EXCHANGE)
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), f"{src_name}<->{dst_name}")


def encode_record(record: ActivationApprovalRecord) -> bytes:
    envelope = {"record": record.as_dict(), "record_sha256": record.record_sha256}
    return canonical_json_bytes(envelope) + b"\n"


def decode_record(raw: bytes) -> ActivationApprovalRecord:
    if len(raw) > MAX_RECORD_BYTES:
        raise RuntimeAuthorityError("approval record is too large")
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeAuthorityError(f"approval record is not valid JSON: {exc}") from exc
    if not isinstance(envelope, dict) or set(envelope) != {"record", "record_sha256"}:
        raise RuntimeAuthorityError("approval envelope fields are invalid")
    if not isinstance(envelope["record"], dict) or not isinstance(envelope["record_sha256"], str):
        raise RuntimeAuthorityError("approval envelope types are invalid")
    record = ActivationApprovalRecord.from_dict(envelope["record"])
    if envelope["record_sha256"] != record.record_sha256:
        raise RuntimeAuthorityError("approval record checksum mismatch")
    return record


class ApprovalStore:
    """Atomic, no-follow approval storage beneath a caller-supplied state root."""

    def __init__(self, root: Path, *, fault_hook: FaultHook | None = None):
        self.root = root
        self._fault_hook = fault_hook or _noop_fault_hook

    def _open_root(self) -> int:
        info = os.lstat(self.root)
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeAuthorityError(f"approval root is not a real directory: {self.root}")
        return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    @staticmethod
    def _read_name(dir_fd: int, name: str) -> ActivationApprovalRecord:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise RuntimeAuthorityError(f"approval object is not a regular file: {name}")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RECORD_BYTES:
                    raise RuntimeAuthorityError("approval record is too large")
                chunks.append(chunk)
            return decode_record(b"".join(chunks))
        finally:
            os.close(fd)

    @staticmethod
    def _write_temp(dir_fd: int, name: str, payload: bytes) -> None:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    def read(self) -> ActivationApprovalRecord:
        dir_fd = self._open_root()
        try:
            return self._read_name(dir_fd, APPROVAL_NAME)
        except FileNotFoundError as exc:
            raise RuntimeAuthorityError("activation approval is absent") from exc
        finally:
            os.close(dir_fd)

    def publish_new(self, record: ActivationApprovalRecord, *, lock_held: bool) -> None:
        if not lock_held:
            raise RuntimeAuthorityError("approval publication requires the production lock")
        temp_name = f".{APPROVAL_NAME}.new-{secrets.token_hex(8)}"
        dir_fd = self._open_root()
        try:
            self._write_temp(dir_fd, temp_name, encode_record(record))
            self._fault_hook("new-temp-fsynced")
            try:
                os.link(temp_name, APPROVAL_NAME, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)
            except FileExistsError as exc:
                raise RuntimeAuthorityError("activation approval already exists") from exc
            self._fault_hook("new-linked")
            os.unlink(temp_name, dir_fd=dir_fd)
            os.fsync(dir_fd)
            if self._read_name(dir_fd, APPROVAL_NAME) != record:
                raise RuntimeAuthorityError("published activation approval does not match input")
        except BaseException:
            try:
                os.unlink(temp_name, dir_fd=dir_fd)
            except FileNotFoundError:
                pass
            os.fsync(dir_fd)
            raise
        finally:
            os.close(dir_fd)

    def replace_exact(self, expected: ActivationApprovalRecord, replacement: ActivationApprovalRecord, *, lock_held: bool) -> None:
        if not lock_held:
            raise RuntimeAuthorityError("approval promotion requires the production lock")
        temp_name = f".{APPROVAL_NAME}.replace-{secrets.token_hex(8)}"
        dir_fd = self._open_root()
        exchanged = False
        try:
            if self._read_name(dir_fd, APPROVAL_NAME) != expected:
                raise RuntimeAuthorityError("current activation approval differs from expected record")
            self._write_temp(dir_fd, temp_name, encode_record(replacement))
            self._fault_hook("replacement-temp-fsynced")
            _rename_exchange(dir_fd, temp_name, dir_fd, APPROVAL_NAME)
            exchanged = True
            self._fault_hook("replacement-exchanged")
            parked = self._read_name(dir_fd, temp_name)
            active = self._read_name(dir_fd, APPROVAL_NAME)
            if parked != expected or active != replacement:
                raise RuntimeAuthorityError("approval exchange identity mismatch")
            os.unlink(temp_name, dir_fd=dir_fd)
            os.fsync(dir_fd)
            exchanged = False
        except BaseException:
            if exchanged:
                try:
                    active = self._read_name(dir_fd, APPROVAL_NAME)
                    parked = self._read_name(dir_fd, temp_name)
                    if active == replacement and parked == expected:
                        _rename_exchange(dir_fd, temp_name, dir_fd, APPROVAL_NAME)
                        exchanged = False
                except (FileNotFoundError, RuntimeAuthorityError, OSError):
                    pass
            try:
                leftover = self._read_name(dir_fd, temp_name)
            except (FileNotFoundError, RuntimeAuthorityError):
                leftover = None
            if leftover == replacement:
                os.unlink(temp_name, dir_fd=dir_fd)
            os.fsync(dir_fd)
            raise
        finally:
            os.close(dir_fd)

    def remove_exact(self, expected: ActivationApprovalRecord, *, lock_held: bool) -> None:
        if not lock_held:
            raise RuntimeAuthorityError("approval removal requires the production lock")
        dir_fd = self._open_root()
        try:
            if self._read_name(dir_fd, APPROVAL_NAME) != expected:
                raise RuntimeAuthorityError("activation approval differs from expected rollback record")
            os.unlink(APPROVAL_NAME, dir_fd=dir_fd)
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
