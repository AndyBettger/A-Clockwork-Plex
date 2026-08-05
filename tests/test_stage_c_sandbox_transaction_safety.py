from __future__ import annotations

import ast
import hashlib
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.stage_c_transaction import sandbox_transaction_runtime as sandbox
from scripts.stage_c_transaction.package_review import sha256


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/test-stage-c-sandbox-transaction.sh"
ENGINE = ROOT / "scripts/stage_c_transaction/sandbox_transaction_runtime.py"
BASE_ENGINE = ROOT / "scripts/stage_c_transaction/sandbox_transaction.py"
TOKEN = "STAGE-C4-SANDBOX-TRANSACTION"
CURRENT_ALSA = "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
FILES = (
    "/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf",
    "/etc/a-clockwork-plex/audio-routes/split-bus.conf",
    "/etc/a-clockwork-plex/camilladsp-split-bus.yml",
    "/etc/default/a-clockwork-plex-split-bus",
    "/etc/modprobe.d/a-clockwork-plex-aloop.conf",
    "/etc/modules-load.d/a-clockwork-plex-aloop.conf",
    "/etc/sudoers.d/a-clockwork-plex-audio-route",
    "/etc/systemd/system/a-clockwork-plex-audio-failback.service",
    "/etc/systemd/system/a-clockwork-plex-audio-route.service",
    "/etc/systemd/system/a-clockwork-plex-camilladsp.service",
    "/usr/local/bin/a-clockwork-plex-audio-route",
    "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp",
)


def fingerprint(root: Path) -> tuple[tuple[str, str, int, str], ...]:
    rows: list[tuple[str, str, int, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        info = path.lstat()
        relative = str(path.relative_to(root))
        if stat.S_ISDIR(info.st_mode):
            rows.append((relative, "directory", stat.S_IMODE(info.st_mode), "-"))
        elif stat.S_ISREG(info.st_mode):
            rows.append((relative, "file", stat.S_IMODE(info.st_mode), sha256(path)))
        elif stat.S_ISLNK(info.st_mode):
            rows.append((relative, "symlink", stat.S_IMODE(info.st_mode), os.readlink(path)))
        else:
            rows.append((relative, "special", stat.S_IMODE(info.st_mode), "-"))
    return tuple(rows)


def _write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def create_fake_package(root: Path) -> None:
    rootfs = root / "rootfs"
    marker = "ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved\n"
    contents = {
        FILES[0]: "pcm.acp_direct_failback { type null }\n",
        FILES[1]: "pcm.acp_split_bus { type null }\n",
        FILES[2]: "version: 4.1.3\n",
        FILES[3]: "ACP_STAGE_C=prepared\n",
        FILES[4]: "options snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1\n",
        FILES[5]: "snd_aloop\n",
        FILES[6]: "andy ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route status\n",
        FILES[7]: "[Unit]\n" + marker,
        FILES[8]: "[Unit]\n" + marker,
        FILES[9]: "[Unit]\n" + marker,
        FILES[10]: "stage-c1-candidate-only\ndef mutate():\n    return 78\n",
        FILES[11]: "fake-camilladsp-binary\n",
    }
    executable = {FILES[10], FILES[11]}
    for destination, text in contents.items():
        _write(rootfs / destination.lstrip("/"), text, 0o755 if destination in executable else 0o644)
    (rootfs / "var/lib/a-clockwork-plex/split-bus").mkdir(parents=True)
    (rootfs / "var/lib/a-clockwork-plex/split-bus").chmod(0o755)

    rows = ["type\tdestination\tmode\towner\tsha256"]
    for directory in sorted((path for path in rootfs.rglob("*") if path.is_dir()), key=str):
        destination = "/" + str(directory.relative_to(rootfs))
        rows.append(
            f"directory\t{destination}\t{stat.S_IMODE(directory.stat().st_mode):o}\troot:root\t-"
        )
    for file in sorted((path for path in rootfs.rglob("*") if path.is_file()), key=str):
        destination = "/" + str(file.relative_to(rootfs))
        rows.append(
            f"file\t{destination}\t{stat.S_IMODE(file.stat().st_mode):o}\troot:root\t{sha256(file)}"
        )
    _write(root / "manifest.tsv", "\n".join(rows) + "\n")
    _write(root / "results.tsv", "check\tresult\tdetail\npackage\tPASS\tfake validated package\n")
    _write(
        root / "report.txt",
        "Package version: 2\n"
        "Package files: 12\n"
        "- no activation option exists\n"
        "- generated route mutation actions return exit 78\n"
        "- generated units require an absent activation-approved marker\n",
    )


def create_fake_stage_c3(root: Path, package: Path, current_bytes: bytes) -> str:
    current_digest = hashlib.sha256(current_bytes).hexdigest()
    current = root / "rootfs" / CURRENT_ALSA.lstrip("/")
    current.parent.mkdir(parents=True)
    current.write_bytes(current_bytes)
    current.chmod(0o644)

    results = ["check\tresult\tdetail"]
    results.extend(f"{check}\tPASS\tfake {check}" for check in sandbox.EXPECTED_STAGE_C3_CHECKS)
    _write(root / "results.tsv", "\n".join(results) + "\n")
    _write(
        root / "report.txt",
        "Managed package files: 12\n"
        "Verified absent managed files: 12\n"
        "Existing managed files: 0\n"
        "Managed destination conflicts: 0\n"
        "Protected sudoers destination resolved: absent\n"
        "- no production path was written\n"
        "- this rehearsal evidence must never be reused as the future activation snapshot\n",
    )

    entries = sandbox.parse_manifest(package)
    filesystem = [
        "kind\tdestination\tpreinstall_state\tmode\towner\tsha256\tsnapshot",
        f"file\t{CURRENT_ALSA}\tpresent\t644\troot:root\t{current_digest}\t{current}",
    ]
    marker_root = root / "absence-markers"
    marker_root.mkdir()
    for entry in (item for item in entries if item.kind == "file"):
        marker = marker_root / (entry.destination.lstrip("/").replace("/", "__") + ".absent")
        _write(marker, f"ABSENT\t{entry.destination}\n")
        filesystem.append(
            f"file\t{entry.destination}\tabsent\t-\t-\t-\t{marker}"
        )
    present_dirs = {
        "/etc",
        "/etc/default",
        "/etc/modprobe.d",
        "/etc/modules-load.d",
        "/etc/sudoers.d",
        "/etc/systemd",
        "/etc/systemd/system",
        "/usr",
        "/usr/local",
        "/usr/local/bin",
        "/usr/local/lib",
        "/var",
        "/var/lib",
        "/var/lib/a-clockwork-plex",
    }
    manifest_dirs = {entry.destination for entry in entries if entry.kind == "directory"}
    all_dirs = sorted(present_dirs | manifest_dirs)
    for destination in all_dirs:
        if destination in present_dirs:
            mode = "750" if destination == "/etc/sudoers.d" else "755"
            filesystem.append(f"directory\t{destination}\tpresent\t{mode}\troot:root\t-\t-")
        else:
            filesystem.append(f"directory\t{destination}\tabsent\t-\t-\t-\t-")
    _write(root / "filesystem-state.tsv", "\n".join(filesystem) + "\n")

    services = [
        "service\tload_state\tactive_state\tenabled_state",
        "plexamp.service\tloaded\tactive\tenabled",
        "shairport-sync.service\tloaded\tactive\tenabled",
        "a-clockwork-plex.service\tloaded\tactive\tenabled",
        "a-clockwork-plex-audio-route.service\tnot-found\tinactive\tnot-found",
        "a-clockwork-plex-camilladsp.service\tnot-found\tinactive\tnot-found",
        "a-clockwork-plex-audio-failback.service\tnot-found\tinactive\tnot-found",
    ]
    _write(root / "service-state.tsv", "\n".join(services) + "\n")

    mixers = ["control\tpercent\traw_output"]
    for control, percent in zip(sandbox.MIXER_CONTROLS, ("100", "94", "100", "100")):
        raw = root / "mixer-raw" / (control.lower().replace(" ", "-") + ".txt")
        _write(raw, f"{control} {percent}%\n")
        mixers.append(f"{control}\t{percent}\t{raw}")
    _write(root / "mixer-state.tsv", "\n".join(mixers) + "\n")

    module = [
        "item\tvalue",
        "snd_aloop.loaded\ttrue",
        "snd_aloop.index\t7",
        "snd_aloop.id\tACP_Loopback",
        "snd_aloop.pcm_substreams\t2",
        "snd_aloop.pcm_notify\t1",
        "snd_aloop.enable\tY",
        "dac.device\t/dev/snd/pcmC2D0p",
        "dac.exists\ttrue",
        "dac.owner.count\t1",
        "dac.owner.1.pid\t1234",
        "dac.owner.1.user\tandy",
        "dac.owner.1.command\tnode",
        "dac.owner.1.fd\t19w",
        f"dac.hw_params\t{root / 'dac-hw-params.txt'}",
    ]
    _write(root / "module-dac-state.tsv", "\n".join(module) + "\n")
    _write(
        root / "dac-hw-params.txt",
        "access: MMAP_INTERLEAVED\nformat: S16_LE\nsubformat: STD\nchannels: 2\nrate: 44100\nperiod_size: 1024\nbuffer_size: 8192\n",
    )

    rollback = ["order\tarea\trestore_action\tmandatory_verification"]
    for number in range(1, 24):
        area = "final" if number == 23 else f"area-{number}"
        rollback.append(f"{number}\t{area}\trestore-{number}\tverify-{number}")
    _write(root / "rollback-ledger.tsv", "\n".join(rollback) + "\n")
    _write(root / "package-fingerprint.tsv", "item\tvalue\npackage\tfake\n")
    sandbox.write_evidence_manifest(root)
    return current_digest


class StageCSandboxTransactionSafetyTests(unittest.TestCase):
    def test_wrapper_and_engine_syntax(self):
        shell = subprocess.run(["bash", "-n", str(WRAPPER)], capture_output=True, text=True)
        self.assertEqual(shell.returncode, 0, shell.stderr)
        for path in (ENGINE, BASE_ENGINE):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        self.assertIn("sandbox_transaction_runtime", WRAPPER.read_text(encoding="utf-8"))

    def test_prepare_only_has_no_sudo_and_prints_guarded_sandbox_command(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?m)^\s*sudo\s+", text), [])
        self.assertIn("if [[ \"$MODE\" == \"prepare\" ]]", text)
        self.assertIn("--run-sandbox", text)
        self.assertIn(TOKEN, text)
        self.assertNotRegex(text, r"(?m)^\s*--activate\)")
        self.assertNotRegex(text, r"(?m)^\s*--install\)")

    def test_engine_has_no_privileged_or_audio_command_execution(self):
        for path in (ENGINE, BASE_ENGINE):
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            imported_modules = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imported_from = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            self.assertNotIn("subprocess", imported_modules)
            self.assertNotIn("subprocess", imported_from)
            forbidden_calls = []
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and (
                        node.func.value.id,
                        node.func.attr,
                    ) in {
                        ("os", "system"),
                        ("os", "popen"),
                        ("subprocess", "run"),
                        ("subprocess", "Popen"),
                    }:
                        forbidden_calls.append(node)
            self.assertEqual(forbidden_calls, [])
            self.assertNotIn("os.chown", text)
            self.assertNotIn("/run/", text)

    def test_cli_is_sandbox_only(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            'parser.add_argument("--package-root"',
            'parser.add_argument("--stage-c3-root"',
            'parser.add_argument("--sandbox-root"',
            'parser.add_argument("--confirm"',
            TOKEN,
        ):
            self.assertIn(expected, text)
        for forbidden in (
            'add_argument("--activate"',
            'add_argument("--install"',
            'add_argument("--route"',
            'add_argument("--rollback"',
            'add_argument("--uninstall"',
        ):
            self.assertNotIn(forbidden, text)

    def test_sandbox_mapping_never_returns_production_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "system-root"
            root.mkdir()
            destination = sandbox.mapped_path(root, "/etc/example.conf")
            self.assertEqual(destination, root / "etc/example.conf")
            self.assertNotEqual(destination, Path("/etc/example.conf"))
            with self.assertRaises(SystemExit):
                sandbox.mapped_path(root, "/../../etc/passwd")

    def test_full_rehearsal_installs_fails_rolls_back_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory(
            dir="/var/tmp", prefix="stage-c4-package-test."
        ) as package_dir, tempfile.TemporaryDirectory(
            dir="/var/tmp", prefix="stage-c4-c3-test."
        ) as c3_dir, tempfile.TemporaryDirectory(
            dir="/var/tmp", prefix=sandbox.SANDBOX_PREFIX
        ) as sandbox_dir:
            package = Path(package_dir)
            stage_c3 = Path(c3_dir)
            sandbox_root = Path(sandbox_dir)
            sandbox_root.chmod(0o700)
            create_fake_package(package)
            current_digest = create_fake_stage_c3(
                stage_c3, package, b"physically validated fake direct route\n"
            )
            package_before = fingerprint(package)
            c3_before = fingerprint(stage_c3)
            with mock.patch.object(
                sandbox.base, "EXPECTED_PRE_STAGE_C_ALSA_SHA256", current_digest
            ), mock.patch.object(
                sandbox, "EXPECTED_PRE_STAGE_C_ALSA_SHA256", current_digest
            ):
                scenarios = sandbox.run_rehearsal(package, stage_c3, sandbox_root)

            self.assertEqual(len(scenarios), 4)
            self.assertTrue(scenarios[0].install_verified)
            self.assertEqual(
                tuple(item.injected_failure for item in scenarios[1:]), sandbox.FAILURE_POINTS
            )
            self.assertTrue(all(item.rollback_mismatches == 0 for item in scenarios))
            self.assertEqual(fingerprint(package), package_before)
            self.assertEqual(fingerprint(stage_c3), c3_before)

            results = sandbox._read_tsv(sandbox_root / "results.tsv")
            self.assertEqual(len(results), 9)
            self.assertTrue(all(row["result"] == "PASS" for row in results))
            scenario_rows = sandbox._read_tsv(sandbox_root / "scenario-state.tsv")
            self.assertEqual(len(scenario_rows), 4)
            self.assertTrue(all(row["rollback_mismatches"] == "0" for row in scenario_rows))

            for scenario in (sandbox_root / "scenarios").iterdir():
                active = scenario / "system-root" / CURRENT_ALSA.lstrip("/")
                self.assertEqual(sha256(active), current_digest)
                for destination in FILES:
                    self.assertFalse((scenario / "system-root" / destination.lstrip("/")).exists())
                sudoers_dir = scenario / "system-root/etc/sudoers.d"
                self.assertEqual(stat.S_IMODE(sudoers_dir.stat().st_mode), 0o750)
                journal = (scenario / "journal.tsv").read_text(encoding="utf-8")
                self.assertIn("directory-modes\trestored", journal)
                self.assertIn("rollback-finish\tbaseline mismatches=0", journal)

    def test_sandbox_root_must_be_fresh_direct_var_tmp_and_mode_0700(self):
        with tempfile.TemporaryDirectory() as package_dir, tempfile.TemporaryDirectory() as c3_dir, tempfile.TemporaryDirectory() as elsewhere:
            with self.assertRaises(SystemExit):
                sandbox.validate_sandbox_root(Path(elsewhere), Path(package_dir), Path(c3_dir))

        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix=sandbox.SANDBOX_PREFIX) as directory:
            root = Path(directory)
            root.chmod(0o755)
            with self.assertRaises(SystemExit):
                sandbox.validate_sandbox_root(root, Path("/tmp/package"), Path("/tmp/c3"))

    def test_symlinked_input_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as package_dir, tempfile.TemporaryDirectory() as c3_dir:
            package = Path(package_dir)
            stage_c3 = Path(c3_dir)
            _write(package / "ordinary", "ok\n")
            (package / "link").symlink_to(package / "ordinary")
            with self.assertRaises(SystemExit):
                sandbox._assert_regular_tree(package, "package")
            _write(stage_c3 / "ordinary", "ok\n")
            (stage_c3 / "link").symlink_to(stage_c3 / "ordinary")
            with self.assertRaises(SystemExit):
                sandbox._assert_regular_tree(stage_c3, "stage c3")

    def test_three_failure_points_use_same_rollback_function(self):
        text = ENGINE.read_text(encoding="utf-8")
        for point in sandbox.FAILURE_POINTS:
            self.assertIn(point, BASE_ENGINE.read_text(encoding="utf-8"))
        self.assertEqual(text.count("rollback_sandbox("), 2)
        self.assertIn("automatic:{fail_after}", text)
        self.assertIn("explicit-uninstall", text)
        self.assertIn("present_directory_modes", text)
        self.assertIn("path.chmod(mode)", text)

    def test_source_has_no_hidden_dynamic_execution(self):
        for path in (ENGINE, BASE_ENGINE):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"eval", "exec", "compile"}
            ]
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
