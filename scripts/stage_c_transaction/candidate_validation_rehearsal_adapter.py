#!/usr/bin/python3
from __future__ import annotations

"""Stage C16 transaction-private candidate staging and validation adapter."""

import hashlib
import os
import secrets
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Mapping

from scripts.stage_c_package.core import PUBLIC_PCMS, build_validation_root

from .authoritative_snapshot_rehearsal_adapter import (
    AuthoritativeSnapshotFailure,
    AuthoritativeSnapshotRehearsalAdapter,
    _assert_regular_tree,
    _remove_regular_tree,
)
from .package_review import EXPECTED_PACKAGE_FILES, ManifestEntry, sha256
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    PackageFingerprint,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import (
    AbortUncommittedTransactionReceipt,
    LifecycleAdapterResult,
    ProductionAdapterV2,
    TransactionLifecycleOperation,
)
from .read_only_host_adapter import _fail
from .sandbox_transaction import tree_fingerprint


CANDIDATE_ROOT_NAME = "candidate-rootfs"
VALIDATION_ROOT_NAME = "candidate-validation"
PERMITTED_V1_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
    AdapterOperation.RELEASE_PRODUCTION_LOCK,
    AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
    AdapterOperation.CAPTURE_FILESYSTEM_STATE,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
    AdapterOperation.STAGE_CANDIDATE_FILES,
    AdapterOperation.VALIDATE_CANDIDATE_ALSA,
    AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
    AdapterOperation.VALIDATE_CANDIDATE_UNITS,
    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
)
PERMITTED_V2_COUNT = len(PERMITTED_V1_OPERATIONS) + 1
BLOCKED_V2_COUNT = 34 - PERMITTED_V2_COUNT


class CandidateValidationFailure(RuntimeError):
    """The staged candidate or its private validation boundary failed."""


def _atomic_copy(source: Path, destination: Path, mode: int) -> None:
    source_before = sha256(source)
    source_info = source.lstat()
    if (
        stat.S_ISLNK(source_info.st_mode)
        or not stat.S_ISREG(source_info.st_mode)
        or source_info.st_nlink != 1
    ):
        raise CandidateValidationFailure(f"candidate source is not a single-link regular file: {source}")
    temporary = destination.with_name(f".{destination.name}.tmp-{secrets.token_hex(6)}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temporary, flags, mode)
    try:
        os.fchmod(fd, mode)
        os.fchown(fd, 0, 0)
        with source.open("rb") as reader, os.fdopen(fd, "wb", closefd=False) as writer:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    finally:
        os.close(fd)
    source_after = sha256(source)
    staged = sha256(temporary)
    if source_before != source_after or staged != source_before:
        temporary.unlink(missing_ok=True)
        raise CandidateValidationFailure(f"candidate changed during staging: {source}")
    os.replace(temporary, destination)
    info = destination.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != mode
        or info.st_uid != 0
        or info.st_gid != 0
        or info.st_nlink != 1
    ):
        raise CandidateValidationFailure(f"staged candidate metadata mismatch: {destination}")


def _run_fixed(
    command: tuple[str, ...],
    *,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=dict(env) if env is not None else None,
        timeout=30,
    )


def _write_command_evidence(
    output: Path,
    result: subprocess.CompletedProcess[str],
) -> None:
    output.write_text(
        f"returncode={result.returncode}\n--- stdout ---\n{result.stdout}"
        f"\n--- stderr ---\n{result.stderr}",
        encoding="utf-8",
    )


class CandidateValidationRehearsalAdapter(
    AuthoritativeSnapshotRehearsalAdapter,
    ProductionAdapterV2,
):
    """Stage C15 plus transaction-private staging, validation and v2 abort."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user)
        self._evidence_root = evidence_root.resolve()
        self._candidate_root: Path | None = None
        self._candidate_device: int | None = None
        self._candidate_inode: int | None = None
        self._validation_root: Path | None = None
        self._candidate_staged = False
        self._alsa_validated = False
        self._sudoers_validated = False
        self._units_validated = False
        self._camilladsp_validated = False
        self._candidate_review_copy: Path | None = None

    @property
    def candidate_root(self) -> Path | None:
        return self._candidate_root

    @property
    def candidate_review_copy(self) -> Path | None:
        return self._candidate_review_copy

    def _require_candidate(
        self,
        operation: AdapterOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None] | None:
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        root = self._candidate_root
        if not self._candidate_staged or root is None:
            return _fail(operation, "no transaction-private candidate has been staged")
        try:
            info = root.lstat()
        except OSError as exc:
            return _fail(operation, f"candidate root is unavailable: {exc}")
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or info.st_dev != self._candidate_device
            or info.st_ino != self._candidate_inode
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != 0
            or info.st_gid != 0
        ):
            return _fail(operation, "candidate root identity changed")
        try:
            _assert_regular_tree(root)
        except AuthoritativeSnapshotFailure as exc:
            return _fail(operation, str(exc))
        return None

    def _snapshot_complete(self) -> bool:
        return all(
            (
                self._filesystem_captured,
                self._service_captured,
                self._mixer_captured,
                self._loopback_captured,
                self._dac_captured,
            )
        )

    def _candidate_path(self, destination: str) -> Path:
        assert self._candidate_root is not None
        relative = Path(destination.lstrip("/"))
        path = self._candidate_root / relative
        if self._candidate_root not in path.parents:
            raise CandidateValidationFailure(f"candidate path escaped transaction root: {destination}")
        return path

    def _fixed_paths(self) -> dict[str, Path]:
        assert self._candidate_root is not None
        root = self._candidate_root
        return {
            "split": root / "etc/a-clockwork-plex/audio-routes/split-bus.conf",
            "direct": root / "etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf",
            "camilla_config": root / "etc/a-clockwork-plex/camilladsp-split-bus.yml",
            "sudoers": root / "etc/sudoers.d/a-clockwork-plex-audio-route",
            "route_helper": root / "usr/local/bin/a-clockwork-plex-audio-route",
            "route_unit": root / "etc/systemd/system/a-clockwork-plex-audio-route.service",
            "camilla_unit": root / "etc/systemd/system/a-clockwork-plex-camilladsp.service",
            "failback_unit": root / "etc/systemd/system/a-clockwork-plex-audio-failback.service",
            "binary": root / "usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp",
        }

    def stage_candidate_files(
        self,
        transaction: TransactionIdentity,
        package: PackageFingerprint,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.STAGE_CANDIDATE_FILES
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._snapshot_complete():
            return _fail(operation, "candidate staging requires all five snapshot domains")
        if package != self.package:
            return _fail(operation, "candidate package fingerprint is not transaction-bound")
        if self._candidate_root is not None:
            return _fail(operation, "candidate files were already staged")
        assert self.transaction_path is not None
        candidate = self.transaction_path / CANDIDATE_ROOT_NAME
        try:
            candidate.mkdir(mode=0o700, exist_ok=False)
            os.chown(candidate, 0, 0)
            candidate.chmod(0o700)
            for entry in sorted(
                (item for item in self._entries if item.kind == "directory"),
                key=lambda item: len(Path(item.destination).parts),
            ):
                destination = candidate / entry.destination.lstrip("/")
                destination.mkdir(parents=True, exist_ok=True)
                os.chown(destination, 0, 0)
                destination.chmod(int(entry.mode, 8))
            for entry in (item for item in self._entries if item.kind == "file"):
                source = self._package_root / "rootfs" / entry.destination.lstrip("/")
                destination = candidate / entry.destination.lstrip("/")
                destination.parent.mkdir(parents=True, exist_ok=True)
                _atomic_copy(source, destination, int(entry.mode, 8))
                if sha256(destination) != entry.digest:
                    raise CandidateValidationFailure(
                        f"staged digest differs from manifest: {entry.destination}"
                    )
            _assert_regular_tree(candidate)
            files = [path for path in candidate.rglob("*") if path.is_file()]
            if len(files) != EXPECTED_PACKAGE_FILES:
                raise CandidateValidationFailure(
                    f"staged file count mismatch: expected {EXPECTED_PACKAGE_FILES}, found {len(files)}"
                )
            staged_rows = tree_fingerprint(candidate)
            (self.transaction_path / "candidate-tree.tsv").write_text(
                "path\ttype\tmode\tsha256\n"
                + "".join(
                    f"{relative}\t{kind}\t{mode}\t{value}\n"
                    for relative, kind, mode, value in staged_rows
                ),
                encoding="utf-8",
            )
            info = candidate.lstat()
        except (OSError, SystemExit, CandidateValidationFailure, AuthoritativeSnapshotFailure) as exc:
            if candidate.exists():
                try:
                    _remove_regular_tree(candidate)
                except (OSError, AuthoritativeSnapshotFailure):
                    pass
            return _fail(operation, str(exc))
        self._candidate_root = candidate
        self._candidate_device = info.st_dev
        self._candidate_inode = info.st_ino
        self._candidate_staged = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="twelve manifest files staged atomically inside the authoritative transaction",
            evidence=(
                ("candidate_root", str(candidate)),
                ("file_count", str(EXPECTED_PACKAGE_FILES)),
                ("production_destination_writes", "0"),
            ),
        )

    def _ensure_validation_root(self) -> Path:
        if self._validation_root is not None:
            return self._validation_root
        assert self.transaction_path is not None
        root = self.transaction_path / VALIDATION_ROOT_NAME
        root.mkdir(mode=0o700, exist_ok=False)
        os.chown(root, 0, 0)
        root.chmod(0o700)
        self._validation_root = root
        return root

    def validate_candidate_alsa(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VALIDATE_CANDIDATE_ALSA
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if self._alsa_validated:
            return _fail(operation, "candidate ALSA was already validated")
        paths = self._fixed_paths()
        validation_root = self._ensure_validation_root()
        try:
            aplay = shutil.which("aplay")
            if not aplay:
                raise CandidateValidationFailure("required fixed validator is unavailable: aplay")
            for name in ("split", "direct"):
                config = validation_root / f"alsa-{name}.conf"
                build_validation_root(paths[name], config)
                env = os.environ.copy()
                env["ALSA_CONFIG_PATH"] = str(config)
                result = _run_fixed((aplay, "-L"), env=env)
                _write_command_evidence(validation_root / f"aplay-{name}.txt", result)
                if result.returncode != 0:
                    raise CandidateValidationFailure(f"ALSA {name} candidate did not parse")
                names = set(result.stdout.splitlines())
                missing = set(PUBLIC_PCMS).difference(names)
                if missing:
                    raise CandidateValidationFailure(
                        f"ALSA {name} candidate omitted public PCMs: {sorted(missing)}"
                    )
        except (OSError, SystemExit, subprocess.SubprocessError, CandidateValidationFailure) as exc:
            return _fail(operation, str(exc))
        self._alsa_validated = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="both staged ALSA routes parsed in isolated private configuration roots",
            evidence=(("pcm_opened", "false"), ("public_pcm_count", str(len(PUBLIC_PCMS)))),
        )

    def validate_candidate_sudoers(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VALIDATE_CANDIDATE_SUDOERS
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if self._sudoers_validated:
            return _fail(operation, "candidate sudoers was already validated")
        validation_root = self._ensure_validation_root()
        try:
            visudo = shutil.which("visudo")
            if not visudo:
                raise CandidateValidationFailure("required fixed validator is unavailable: visudo")
            result = _run_fixed((visudo, "-cf", str(self._fixed_paths()["sudoers"])))
            _write_command_evidence(validation_root / "visudo.txt", result)
            if result.returncode != 0:
                raise CandidateValidationFailure("staged sudoers candidate failed visudo")
        except (OSError, subprocess.SubprocessError, CandidateValidationFailure) as exc:
            return _fail(operation, str(exc))
        self._sudoers_validated = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="staged restricted sudoers candidate accepted by visudo",
        )

    @staticmethod
    def _unit_contract(paths: dict[str, Path]) -> None:
        route = paths["route_unit"].read_text(encoding="utf-8")
        camilla = paths["camilla_unit"].read_text(encoding="utf-8")
        failback = paths["failback_unit"].read_text(encoding="utf-8")
        combined = "\n".join((route, camilla, failback))
        required = (
            "Before=a-clockwork-plex-camilladsp.service plexamp.service shairport-sync.service a-clockwork-plex.service",
            "Requires=a-clockwork-plex-audio-route.service sound.target",
            "OnFailure=a-clockwork-plex-audio-failback.service",
            "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route boot-select",
            "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route activate-direct-failback",
        )
        for marker in required:
            if marker not in combined:
                raise CandidateValidationFailure(f"staged unit contract omitted: {marker}")
        approval = "ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved"
        if sum(text.count(approval) for text in (route, camilla, failback)) != 3:
            raise CandidateValidationFailure("all three staged units must retain the approval gate")
        helper = paths["route_helper"].read_text(encoding="utf-8")
        compile(helper, str(paths["route_helper"]), "exec")
        if "stage-c1-candidate-only" not in helper or "return 78" not in helper:
            raise CandidateValidationFailure("staged route helper is not the inert candidate")

    def validate_candidate_units(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VALIDATE_CANDIDATE_UNITS
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if self._units_validated:
            return _fail(operation, "candidate units were already validated")
        paths = self._fixed_paths()
        validation_root = self._ensure_validation_root()
        try:
            self._unit_contract(paths)
            analyzer = shutil.which("systemd-analyze")
            if not analyzer:
                raise CandidateValidationFailure(
                    "required fixed validator is unavailable: systemd-analyze"
                )
            unit_dir = validation_root / "units"
            unit_dir.mkdir(mode=0o700, exist_ok=False)
            unit_names = (
                "a-clockwork-plex-audio-route.service",
                "a-clockwork-plex-camilladsp.service",
                "a-clockwork-plex-audio-failback.service",
            )
            for key, name in zip(
                ("route_unit", "camilla_unit", "failback_unit"),
                unit_names,
                strict=True,
            ):
                text = paths[key].read_text(encoding="utf-8")
                rewritten = "\n".join(
                    "ExecStart=/bin/true" if line.startswith("ExecStart=") else line
                    for line in text.splitlines()
                    if not line.startswith(("User=", "Group="))
                ) + "\n"
                target = unit_dir / name
                target.write_text(rewritten, encoding="utf-8")
                target.chmod(0o644)
            for name in (
                "plexamp.service",
                "shairport-sync.service",
                "a-clockwork-plex.service",
                "systemd-modules-load.service",
            ):
                (unit_dir / name).write_text(
                    "[Unit]\nDescription=Stage C16 validation stub\n[Service]\nType=oneshot\nExecStart=/bin/true\n",
                    encoding="utf-8",
                )
            for name in ("sound.target", "multi-user.target"):
                (unit_dir / name).write_text(
                    "[Unit]\nDescription=Stage C16 validation target\n",
                    encoding="utf-8",
                )
            env = os.environ.copy()
            env["SYSTEMD_UNIT_PATH"] = str(unit_dir)
            result = _run_fixed(
                (
                    analyzer,
                    "verify",
                    *(str(unit_dir / name) for name in unit_names),
                ),
                env=env,
            )
            _write_command_evidence(validation_root / "systemd-analyze.txt", result)
            if result.returncode != 0:
                raise CandidateValidationFailure("staged systemd candidates failed verification")
        except (
            OSError,
            SyntaxError,
            subprocess.SubprocessError,
            CandidateValidationFailure,
        ) as exc:
            return _fail(operation, str(exc))
        self._units_validated = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="three staged units and inert route helper passed private validation",
            evidence=(("service_manager_contacted", "false"),),
        )

    def validate_candidate_camilladsp(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if self._camilladsp_validated:
            return _fail(operation, "candidate CamillaDSP was already validated")
        paths = self._fixed_paths()
        validation_root = self._ensure_validation_root()
        try:
            binary_entry = next(
                entry
                for entry in self._entries
                if entry.destination.endswith("/camilladsp") and entry.kind == "file"
            )
            if sha256(paths["binary"]) != binary_entry.digest:
                raise CandidateValidationFailure("staged CamillaDSP digest differs from manifest")
            result = _run_fixed(
                (str(paths["binary"]), "--check", str(paths["camilla_config"]))
            )
            _write_command_evidence(validation_root / "camilladsp-check.txt", result)
            if result.returncode != 0:
                raise CandidateValidationFailure("staged CamillaDSP configuration failed --check")
        except (
            OSError,
            StopIteration,
            subprocess.SubprocessError,
            CandidateValidationFailure,
        ) as exc:
            return _fail(operation, str(exc))
        self._camilladsp_validated = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="digest-pinned staged CamillaDSP accepted the staged configuration",
            evidence=(("audio_endpoint_opened", "false"),),
        )

    def abort_uncommitted_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> LifecycleAdapterResult:
        operation = TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return LifecycleAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="rejected non-authoritative transaction identity",
            )
        if not all(
            (
                self._candidate_staged,
                self._alsa_validated,
                self._sudoers_validated,
                self._units_validated,
                self._camilladsp_validated,
            )
        ):
            return LifecycleAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="candidate staging and all four validation domains must complete before abort",
            )
        invalid = self._require_candidate(AdapterOperation.STAGE_CANDIDATE_FILES, transaction)
        if invalid is not None:
            return LifecycleAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=invalid.detail,
            )
        assert self._candidate_root is not None
        assert self.transaction_path is not None
        review_copy = self._evidence_root / "candidate-review-copy"
        transaction_copy = self._evidence_root / "transaction-rehearsal-copy"
        try:
            if review_copy.exists() or transaction_copy.exists():
                raise CandidateValidationFailure("Stage C16 audit destination already exists")
            review_copy.mkdir(mode=0o700, exist_ok=False)
            os.chown(review_copy, 0, 0)
            review_copy.chmod(0o700)
            shutil.copytree(
                self._candidate_root,
                review_copy / CANDIDATE_ROOT_NAME,
                copy_function=shutil.copy2,
            )
            if self._validation_root is not None:
                shutil.copytree(
                    self._validation_root,
                    review_copy / VALIDATION_ROOT_NAME,
                    copy_function=shutil.copy2,
                )
            _assert_regular_tree(review_copy)
            _remove_regular_tree(self._candidate_root)
            self._candidate_root = None
            self._candidate_staged = False
            if self._validation_root is not None:
                _remove_regular_tree(self._validation_root)
                self._validation_root = None
            inherited = super().abort_uncommitted_transaction(transaction_copy)
            if inherited.status is not AdapterStatus.PASS or inherited.payload is None:
                raise CandidateValidationFailure(inherited.detail)
        except (
            OSError,
            AuthoritativeSnapshotFailure,
            CandidateValidationFailure,
        ) as exc:
            return LifecycleAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        self._candidate_review_copy = review_copy
        receipt = AbortUncommittedTransactionReceipt(
            transaction=transaction,
            state="aborted-before-mutation",
            mutation_started=False,
            committed=False,
            transaction_path_absent=inherited.payload.transaction_path_absent,
            parents_restored=inherited.payload.parents_restored,
            audit_evidence=str(self._evidence_root),
        )
        return LifecycleAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="validated candidate retained as evidence and transaction aborted exactly",
            payload=receipt,
        )
