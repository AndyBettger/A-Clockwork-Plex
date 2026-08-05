#!/usr/bin/python3
from __future__ import annotations

import grp
import os
import pwd
import re
import socket
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol

from .approval_store import ApprovalStore
from .model import ActivationApprovalRecord, ApprovalPhase, RuntimeAuthorityError
from .supervisor_model import SupervisorMode


START_TIMEOUT_SECONDS = 30.0
START_POLL_SECONDS = 0.25
STOP_TIMEOUT_SECONDS = 5.0
PROJECT_USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
DAC_HW_PARAMS = {
    "access": "MMAP_INTERLEAVED",
    "format": "S16_LE",
    "subformat": "STD",
    "channels": "2",
    "rate": "44100",
    "period_size": "1024",
    "buffer_size": "8192",
}
LOOPBACK_REQUIRED_HW_PARAMS = {
    "access": "MMAP_INTERLEAVED",
    "format": "S16_LE",
    "subformat": "STD",
    "channels": "4",
    "rate": "44100",
}


class ChildProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


@dataclass(frozen=True)
class _ProcessPaths:
    system_root: Path

    @classmethod
    def production(cls) -> "_ProcessPaths":
        return cls(Path("/"))

    @classmethod
    def test_root(cls, root: Path) -> "_ProcessPaths":
        return cls(root)

    def map(self, absolute: str) -> Path:
        pure = PurePosixPath(absolute)
        if not pure.is_absolute() or ".." in pure.parts:
            raise RuntimeAuthorityError(f"invalid fixed process path: {absolute}")
        return self.system_root.joinpath(*pure.parts[1:])

    @property
    def state_root(self) -> Path:
        return self.map("/var/lib/a-clockwork-plex/split-bus")

    @property
    def defaults(self) -> Path:
        return self.map("/etc/default/a-clockwork-plex-split-bus")

    @property
    def binary(self) -> Path:
        return self.map("/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp")

    @property
    def config(self) -> Path:
        return self.map("/etc/a-clockwork-plex/camilladsp-split-bus.yml")

    @property
    def proc(self) -> Path:
        return self.map("/proc")

    @property
    def dac_alias(self) -> Path:
        return self.map("/proc/asound/Pro")

    @property
    def loopback_capture_device(self) -> Path:
        return self.map("/dev/snd/pcmC7D1c")

    @property
    def loopback_capture_hw_params(self) -> Path:
        return self.map("/proc/asound/card7/pcm1c/sub0/hw_params")


class _SystemdNotifier:
    def notify_ready(self, mode: SupervisorMode, reason: str) -> None:
        raw = os.environ.get("NOTIFY_SOCKET", "")
        if not raw:
            raise RuntimeAuthorityError("NOTIFY_SOCKET is unavailable for Type=notify readiness")
        if "\n" in reason or "\r" in reason:
            raise RuntimeAuthorityError("systemd readiness reason contains a newline")
        status = f"A Clockwork Plex audio ready: {mode.value}; {reason}"
        if len(status.encode("utf-8")) > 900:
            raise RuntimeAuthorityError("systemd readiness status is too long")
        address: str | bytes = raw
        if raw.startswith("@"):
            address = b"\0" + raw[1:].encode("utf-8")
        payload = f"READY=1\nSTATUS={status}\n".encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC) as sender:
            sent = sender.sendto(payload, address)
        if sent != len(payload):
            raise RuntimeAuthorityError("short systemd readiness notification")


class LinuxRuntimeProcess:
    """Fixed CamillaDSP child and Type=notify boundary; public construction takes no paths."""

    def __init__(self) -> None:
        self._paths = _ProcessPaths.production()
        self._process_factory: Callable[..., ChildProcess] = subprocess.Popen
        self._notifier = _SystemdNotifier()
        self._monotonic = time.monotonic
        self._sleep = time.sleep
        self._child: ChildProcess | None = None

    @classmethod
    def _for_test(
        cls,
        root: Path,
        *,
        process_factory: Callable[..., ChildProcess],
        notifier: object,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> "LinuxRuntimeProcess":
        instance = cls.__new__(cls)
        instance._paths = _ProcessPaths.test_root(root)
        instance._process_factory = process_factory
        instance._notifier = notifier
        instance._monotonic = monotonic
        instance._sleep = sleep
        instance._child = None
        return instance

    @property
    def child_pid(self) -> int | None:
        return self._child.pid if self._child is not None else None

    @property
    def child_running(self) -> bool:
        return self._child is not None and self._child.poll() is None

    def _approval(self) -> ActivationApprovalRecord:
        record = ApprovalStore(self._paths.state_root).read()
        if record.phase is not ApprovalPhase.COMMITTED:
            raise RuntimeAuthorityError("CamillaDSP process authority requires a committed approval")
        return record

    @staticmethod
    def _require_regular(path: Path, *, mode: int) -> os.stat_result:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise RuntimeAuthorityError(f"process asset is not a real regular file: {path}")
        expected_uid = 0 if path.anchor == "/" and str(path).startswith("/") else os.geteuid()
        if info.st_uid != expected_uid:
            raise RuntimeAuthorityError(f"process asset owner mismatch: {path}")
        if stat.S_IMODE(info.st_mode) != mode:
            raise RuntimeAuthorityError(f"process asset mode mismatch: {path}")
        return info

    def _read_project_user(self) -> str:
        self._require_regular(self._paths.defaults, mode=0o644)
        values: dict[str, str] = {}
        for raw in self._paths.defaults.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise RuntimeAuthorityError("runtime defaults contain a non-assignment line")
            key, value = line.split("=", 1)
            if key in values or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                raise RuntimeAuthorityError("runtime defaults contain an invalid or duplicate key")
            if any(character.isspace() for character in value) or any(
                character in value for character in "'\"`$;|&<>"
            ):
                raise RuntimeAuthorityError("runtime defaults contain shell-like syntax")
            values[key] = value
        user = values.get("PROJECT_USER", "")
        if not PROJECT_USER_RE.fullmatch(user):
            raise RuntimeAuthorityError("runtime PROJECT_USER is invalid")
        return user

    def _child_identity(self) -> tuple[int, int, tuple[int, ...], str]:
        user = self._read_project_user()
        try:
            account = pwd.getpwnam(user)
            audio = grp.getgrnam("audio")
        except KeyError as exc:
            raise RuntimeAuthorityError("runtime project user or audio group is unavailable") from exc
        groups = set(os.getgrouplist(user, account.pw_gid))
        groups.add(audio.gr_gid)
        return account.pw_uid, audio.gr_gid, tuple(sorted(groups)), account.pw_dir

    def start_camilladsp_child(self) -> bool:
        if self._child is not None:
            raise RuntimeAuthorityError("CamillaDSP child has already been created")
        approval = self._approval()
        self._require_regular(self._paths.binary, mode=0o755)
        self._require_regular(self._paths.config, mode=0o644)
        from .linux_runtime_filesystem import _sha256

        if _sha256(self._paths.binary) != approval.camilladsp_binary_sha256:
            raise RuntimeAuthorityError("CamillaDSP binary differs from committed approval")
        if _sha256(self._paths.config) != approval.camilladsp_config_sha256:
            raise RuntimeAuthorityError("CamillaDSP configuration differs from committed approval")
        uid, audio_gid, groups, home = self._child_identity()
        environment = {
            "HOME": home,
            "USER": self._read_project_user(),
            "LOGNAME": self._read_project_user(),
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
        }
        argv = [str(self._paths.binary), str(self._paths.config)]
        self._child = self._process_factory(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            cwd="/",
            env=environment,
            close_fds=True,
            shell=False,
            user=uid,
            group=audio_gid,
            extra_groups=groups,
        )
        return self._child.poll() is None

    @staticmethod
    def _parse_hw_params(text: str) -> dict[str, str]:
        observed: dict[str, str] = {}
        for raw in text.splitlines():
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key == "rate":
                match = re.match(r"^(\d+)(?:\s|$)", value)
                if match:
                    value = match.group(1)
            observed[key] = value
        return observed

    def _resolve_dac(self) -> tuple[Path, Path]:
        try:
            target = os.readlink(self._paths.dac_alias)
        except OSError as exc:
            raise RuntimeAuthorityError(f"cannot resolve ALSA card alias Pro: {exc}") from exc
        match = re.fullmatch(r"card(\d+)", Path(target).name)
        if match is None:
            raise RuntimeAuthorityError(f"unexpected ALSA card alias target: {target}")
        card = match.group(1)
        return (
            self._paths.map(f"/dev/snd/pcmC{card}D0p"),
            self._paths.map(f"/proc/asound/card{card}/pcm0p/sub0/hw_params"),
        )

    def _owner_pids(self, device: Path) -> set[int]:
        owners: set[int] = set()
        proc = self._paths.proc
        for process_dir in proc.iterdir():
            if not process_dir.name.isdigit() or not process_dir.is_dir():
                continue
            fd_root = process_dir / "fd"
            try:
                descriptors = tuple(fd_root.iterdir())
            except OSError:
                continue
            for descriptor in descriptors:
                try:
                    target = os.readlink(descriptor)
                except OSError:
                    continue
                target_path = Path(target)
                if self._paths.system_root != Path("/") and target_path.is_absolute():
                    target_path = self._paths.map(str(target_path))
                if target_path == device:
                    owners.add(int(process_dir.name))
                    break
        return owners

    def _child_command_is_exact(self, pid: int) -> bool:
        process_root = self._paths.proc / str(pid)
        try:
            executable = os.readlink(process_root / "exe")
            cmdline = (process_root / "cmdline").read_bytes()
        except OSError:
            return False
        executable_path = Path(executable)
        if self._paths.system_root != Path("/") and executable_path.is_absolute():
            executable_path = self._paths.map(str(executable_path))
        expected_cmdline = (
            str(self._paths.binary).encode("utf-8")
            + b"\0"
            + str(self._paths.config).encode("utf-8")
            + b"\0"
        )
        return executable_path == self._paths.binary and cmdline == expected_cmdline

    @staticmethod
    def _matches(observed: dict[str, str], expected: dict[str, str]) -> bool:
        return all(observed.get(key) == value for key, value in expected.items())

    @staticmethod
    def _valid_loopback_geometry(observed: dict[str, str]) -> bool:
        try:
            period = int(observed["period_size"])
            buffer = int(observed["buffer_size"])
        except (KeyError, ValueError):
            return False
        return period > 0 and buffer >= period and buffer % period == 0

    def _strict_health_once(self) -> bool:
        if not self.child_running:
            return False
        assert self._child is not None
        pid = self._child.pid
        if not self._child_command_is_exact(pid):
            return False
        dac_device, dac_hw_params = self._resolve_dac()
        loopback_device = self._paths.loopback_capture_device
        try:
            dac = self._parse_hw_params(dac_hw_params.read_text(encoding="utf-8"))
            loopback = self._parse_hw_params(
                self._paths.loopback_capture_hw_params.read_text(encoding="utf-8")
            )
        except OSError:
            return False
        if not self._matches(dac, DAC_HW_PARAMS):
            return False
        if not self._matches(loopback, LOOPBACK_REQUIRED_HW_PARAMS):
            return False
        if not self._valid_loopback_geometry(loopback):
            return False
        return self._owner_pids(dac_device) == {pid} and self._owner_pids(loopback_device) == {pid}

    def verify_split_bus_health(self) -> bool:
        deadline = self._monotonic() + START_TIMEOUT_SECONDS
        while True:
            if self._strict_health_once():
                return True
            if not self.child_running or self._monotonic() >= deadline:
                return False
            self._sleep(START_POLL_SECONDS)

    def stop_camilladsp_child(self) -> None:
        if self._child is None:
            return
        child = self._child
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=STOP_TIMEOUT_SECONDS)
        self._child = None

    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None:
        notify = getattr(self._notifier, "notify_ready", None)
        if not callable(notify):
            raise RuntimeAuthorityError("invalid systemd notifier boundary")
        notify(mode, reason)

    def wait_for_child_exit(self) -> int | None:
        if self._child is None:
            return None
        return self._child.wait(timeout=None)
