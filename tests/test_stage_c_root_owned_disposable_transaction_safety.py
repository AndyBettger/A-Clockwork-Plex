from __future__ import annotations

import ast
import csv
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.stage_c_transaction import root_owned_transaction as transaction
from scripts.stage_c_transaction.package_review import ManifestEntry


class StageCRootOwnedDisposableTransactionSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.wrapper = self.repo / "scripts/test-stage-c-root-owned-disposable-transaction.sh"
        self.module = self.repo / "scripts/stage_c_transaction/root_owned_transaction.py"

    def _write(self, path: Path, content: str | bytes, mode: int = 0o644) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        path.chmod(mode)

    def _build_package(self, root: Path) -> Path:
        package = root / "stage-c1"
        rootfs = package / "rootfs"
        directories = [
            "/etc",
            "/etc/a-clockwork-plex",
            "/etc/a-clockwork-plex/audio-routes",
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
            "/usr/local/lib/a-clockwork-plex",
            "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3",
            "/var",
            "/var/lib",
            "/var/lib/a-clockwork-plex",
            "/var/lib/a-clockwork-plex/split-bus",
        ]
        files = [
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
        ]
        rows = [("type", "destination", "mode", "owner", "sha256")]
        for destination in directories:
            path = rootfs / destination.lstrip("/")
            path.mkdir(parents=True, exist_ok=True)
            mode = 0o755
            path.chmod(mode)
            rows.append(("directory", destination, f"{mode:o}", "root:root", "-"))

        marker = "ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved"
        for index, destination in enumerate(files):
            mode = 0o755 if destination.startswith("/usr/local/") else 0o644
            if destination == transaction.SPLIT_ROUTE_DESTINATION:
                content = "synthetic split route\n"
            elif destination == "/usr/local/bin/a-clockwork-plex-audio-route":
                content = "stage-c1-candidate-only\ndef main():\n    return 78\n"
            elif destination.endswith(".service"):
                content = f"[Unit]\n{marker}\n# fixture {index}\n"
            else:
                content = f"fixture {index} {destination}\n"
            path = rootfs / destination.lstrip("/")
            self._write(path, content, mode)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            rows.append(("file", destination, f"{mode:o}", "root:root", digest))

        with (package / "manifest.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerows(rows)
        self._write(package / "results.tsv", "check\tresult\tdetail\nfixture\tPASS\tcomplete\n")
        self._write(
            package / "report.txt",
            "\n".join(
                (
                    "Package version: 2",
                    "Package files: 12",
                    "- no activation option exists",
                    "- generated route mutation actions return exit 78",
                    "- generated units require an absent activation-approved marker",
                    "",
                )
            ),
        )
        return package

    def _build_c6(self, root: Path, package: Path) -> tuple[Path, str]:
        c6 = root / "stage-c6"
        c6.mkdir()
        current_content = b"accepted pre-stage-c route\n"
        current_digest = hashlib.sha256(current_content).hexdigest()
        current = c6 / "rootfs/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        self._write(current, current_content)
        for directory in (
            current.parent,
            current.parent.parent,
            current.parent.parent.parent,
        ):
            directory.chmod(0o755)

        result_rows = [("check", "result", "detail")]
        result_rows.extend((check, "PASS", "fixture") for check in transaction.EXPECTED_C6_CHECKS)
        with (c6 / "results.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(result_rows)
        self._write(
            c6 / "lock-state.tsv",
            "item\tvalue\n"
            "production.lock_path\t/run/lock/a-clockwork-plex-audio-route.lock\n"
            "production.lock_state\tabsent\n"
            "production.lock_opened\tfalse\n"
            "rehearsal.lock_acquired\ttrue\n"
            "rehearsal.lock_released\ttrue\n",
        )
        self._write(
            c6 / "identity.tsv",
            "item\tvalue\ncaller_supplied\tfalse\nactivation_authoritative\tfalse\n",
        )
        self._write(
            c6 / "report.txt",
            "Production lock state: absent and never opened\n"
            "this rehearsal must never be reused as an activation-authoritative snapshot\n"
            "persistent Stage C activation remains blocked\n",
        )

        present_directories = {
            "/etc": "755",
            "/etc/default": "755",
            "/etc/modprobe.d": "755",
            "/etc/modules-load.d": "755",
            "/etc/sudoers.d": "750",
            "/etc/systemd": "755",
            "/etc/systemd/system": "755",
            "/usr": "755",
            "/usr/local": "755",
            "/usr/local/bin": "755",
            "/usr/local/lib": "755",
            "/var": "755",
            "/var/lib": "755",
            "/var/lib/a-clockwork-plex": "755",
        }
        absent_directories = {
            "/etc/a-clockwork-plex",
            "/etc/a-clockwork-plex/audio-routes",
            "/usr/local/lib/a-clockwork-plex",
            "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3",
            "/var/lib/a-clockwork-plex/split-bus",
        }
        rows = [
            (
                "file",
                transaction.CURRENT_ALSA_DESTINATION,
                "present",
                "644",
                "root:root",
                current_digest,
                str(current),
            )
        ]
        with (package / "manifest.tsv").open(encoding="utf-8", newline="") as handle:
            package_rows = list(csv.DictReader(handle, delimiter="\t"))
        for row in package_rows:
            if row["type"] == "file":
                rows.append(
                    (
                        "file",
                        row["destination"],
                        "absent",
                        "-",
                        "-",
                        "-",
                        str(c6 / "absence"),
                    )
                )
        for destination, mode in sorted(present_directories.items()):
            rows.append(("directory", destination, "present", mode, "root:root", "-", "-"))
        for destination in sorted(absent_directories):
            rows.append(("directory", destination, "absent", "-", "-", "-", "-"))
        with (c6 / "filesystem-state.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(
                (
                    "kind",
                    "destination",
                    "preinstall_state",
                    "mode",
                    "owner",
                    "sha256",
                    "snapshot",
                )
            )
            writer.writerows(rows)
        self._write(c6 / "evidence-manifest.tsv", "path\ttype\tmode\tsha256\n")
        return c6, current_digest

    def test_wrapper_and_module_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(self.wrapper)], check=True)
        compile(self.module.read_text(encoding="utf-8"), str(self.module), "exec")

    def test_prepare_only_has_no_privileged_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._build_package(root)
            c6, _ = self._build_c6(root, package)
            completed = subprocess.run(
                [
                    "bash",
                    str(self.wrapper),
                    "--package-root",
                    str(package),
                    "--stage-c6-root",
                    str(c6),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        self.assertIn("is prepared", completed.stdout)
        self.assertIn("Prepare-only invoked no sudo", completed.stdout)
        self.assertIn("--run-disposable-root", completed.stdout)
        self.assertIn(transaction.REQUIRED_CONFIRMATION, completed.stdout)

    def test_wrapper_has_one_constrained_sudo_command(self) -> None:
        source = self.wrapper.read_text(encoding="utf-8")
        self.assertEqual(source.count("exec sudo env"), 1)
        self.assertIn("stage_c_transaction.root_owned_transaction", source)
        command_heads = {
            stripped.split()[0].lower()
            for line in source.splitlines()
            if (stripped := line.strip())
            and not stripped.startswith(("#", "'", '"'))
        }
        self.assertTrue(
            {"systemctl", "amixer", "modprobe", "aplay", "camilladsp"}.isdisjoint(
                command_heads
            )
        )

    def test_engine_has_no_command_or_dynamic_execution_adapter(self) -> None:
        source = self.module.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse({"eval", "exec", "compile"}.intersection(calls))

        production_lock = "/run/lock/a-clockwork-plex-audio-route.lock"
        path_or_mutation_calls = {
            "Path",
            "open",
            "mkdir",
            "touch",
            "write_text",
            "write_bytes",
            "unlink",
            "replace",
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            else:
                continue
            if call_name not in path_or_mutation_calls:
                continue
            string_constants = {
                value.value
                for value in ast.walk(node)
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            }
            self.assertNotIn(production_lock, string_constants)

    def test_cli_is_disposable_only(self) -> None:
        source = self.module.read_text(encoding="utf-8")
        for option in ("--package-root", "--stage-c6-root", "--rehearsal-root", "--confirm"):
            self.assertIn(option, source)
        for forbidden in ("--install", "--activate", "--keep", "--failback", "--uninstall"):
            self.assertNotIn(forbidden, source)

    def test_mapping_rejects_escape_and_symlinked_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(SystemExit):
                transaction.mapped_path(root, "../etc/passwd")
            (root / "etc").symlink_to(root / "elsewhere", target_is_directory=True)
            with self.assertRaises(SystemExit):
                transaction.mapped_path(root, "/etc/example")

    def test_atomic_copy_verifies_mode_owner_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            self._write(source, "atomic fixture\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            observed = transaction.atomic_copy(
                source, destination, 0o640, os.getuid(), os.getgid(), digest
            )
            self.assertEqual(observed, digest)
            info = destination.stat()
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o640)
            self.assertEqual(info.st_uid, os.getuid())
            self.assertEqual(info.st_gid, os.getgid())

    def test_real_c6_shape_seeds_unlisted_current_alsa_parent_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._build_package(root)
            c6, current_digest = self._build_c6(root, package)
            with (c6 / "filesystem-state.tsv").open(
                encoding="utf-8", newline=""
            ) as handle:
                filesystem_rows = list(csv.DictReader(handle, delimiter="\t"))
            listed_directories = {
                row["destination"]
                for row in filesystem_rows
                if row["kind"] == "directory"
            }
            self.assertNotIn("/etc/alsa", listed_directories)
            self.assertNotIn("/etc/alsa/conf.d", listed_directories)

            scenario = root / "scenario"
            scenario.mkdir()
            entries = transaction.parse_manifest(package)
            with mock.patch.object(
                transaction,
                "EXPECTED_PRE_STAGE_C_ALSA_SHA256",
                current_digest,
            ):
                evidence = transaction.validate_c6(c6)
                baseline, existing, _ = transaction.seed_scenario(
                    scenario,
                    evidence,
                    entries,
                    os.getuid(),
                    os.getgid(),
                )

            self.assertTrue(baseline)
            for destination in ("/etc/alsa", "/etc/alsa/conf.d"):
                self.assertIn(destination, existing)
                self.assertEqual(existing[destination][0], 0o755)
                path = transaction.mapped_path(
                    scenario / "system-root", destination
                )
                self.assertTrue(path.is_dir())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)
            current = transaction.mapped_path(
                scenario / "system-root",
                transaction.CURRENT_ALSA_DESTINATION,
            )
            self.assertEqual(transaction.sha256(current), current_digest)

    def test_existing_directory_is_never_rechmodded_during_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "etc").mkdir()
            target = root / "etc/sudoers.d"
            target.mkdir()
            target.chmod(0o750)
            entry = ManifestEntry("directory", "/etc/sudoers.d", "755", "root:root", "-")
            existing = {"/etc/sudoers.d": (0o750, os.getuid(), os.getgid())}
            transaction.create_manifest_directories(
                root, [entry], existing, os.getuid(), os.getgid()
            )
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o750)

    def test_full_rehearsal_installs_fails_rolls_back_and_preserves_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture_root = Path(temporary)
            package = self._build_package(fixture_root)
            c6, current_digest = self._build_c6(fixture_root, package)
            package_before = transaction.tree_fingerprint(package)
            c6_before = transaction.tree_fingerprint(c6)
            rehearsal = Path(
                tempfile.mkdtemp(
                    prefix=transaction.ROOT_PREFIX,
                    dir="/var/tmp",
                )
            )
            rehearsal.chmod(0o700)
            try:
                with mock.patch.object(
                    transaction,
                    "EXPECTED_PRE_STAGE_C_ALSA_SHA256",
                    current_digest,
                ):
                    scenarios = transaction.run_rehearsal(
                        package,
                        c6,
                        rehearsal,
                        os.getuid(),
                        os.getgid(),
                        os.getuid(),
                        os.getgid(),
                    )
                self.assertEqual(len(scenarios), 4)
                self.assertTrue(scenarios[0].install_verified)
                self.assertTrue(all(item.rollback_mismatches == 0 for item in scenarios))
                self.assertTrue(all(item.existing_directories_preserved for item in scenarios))

                with (rehearsal / "results.tsv").open(
                    encoding="utf-8", newline=""
                ) as handle:
                    result_rows = list(csv.DictReader(handle, delimiter="\t"))
                self.assertEqual(
                    tuple(row["check"] for row in result_rows),
                    transaction.TOP_LEVEL_CHECKS,
                )
                installed = (
                    rehearsal
                    / "scenarios/success-explicit-uninstall/installed-fingerprint.tsv"
                )
                with installed.open(encoding="utf-8", newline="") as handle:
                    installed_rows = list(csv.DictReader(handle, delimiter="\t"))
                sudoers = next(
                    row for row in installed_rows if row["path"] == "etc/sudoers.d"
                )
                self.assertEqual(sudoers["mode"], "750")
                self.assertEqual(sudoers["uid"], str(os.getuid()))
                self.assertEqual(sudoers["gid"], str(os.getgid()))

                for scenario_root in (rehearsal / "scenarios").iterdir():
                    self.assertFalse(
                        (
                            scenario_root
                            / "system-root/var/lib/a-clockwork-plex/split-bus/activation-approved"
                        ).exists()
                    )
                self.assertEqual(transaction.tree_fingerprint(package), package_before)
                self.assertEqual(transaction.tree_fingerprint(c6), c6_before)
            finally:
                shutil.rmtree(rehearsal)

    def test_all_failure_paths_call_the_same_rollback_function(self) -> None:
        source = self.module.read_text(encoding="utf-8")
        run_scenario = source.split("def run_scenario", 1)[1].split(
            "def write_file_plan", 1
        )[0]
        self.assertEqual(run_scenario.count("mismatches = rollback("), 1)
        for failure in transaction.FAILURE_POINTS:
            self.assertIn(failure, source)

    def test_atomic_source_is_hashed_before_and_after_copy(self) -> None:
        source = self.module.read_text(encoding="utf-8")
        atomic = source.split("def atomic_copy", 1)[1].split(
            "def _captured_directories", 1
        )[0]
        self.assertLess(
            atomic.index("source_before = sha256(source)"),
            atomic.index("shutil.copyfileobj"),
        )
        self.assertGreater(
            atomic.index("source_after = sha256(source)"),
            atomic.index("shutil.copyfileobj"),
        )
        self.assertIn("os.replace", atomic)
        self.assertIn("_fsync_directory", atomic)

    def test_exact_top_level_result_contract(self) -> None:
        self.assertEqual(len(transaction.TOP_LEVEL_CHECKS), 12)
        self.assertEqual(transaction.TOP_LEVEL_CHECKS[-1], "activation-interface")


if __name__ == "__main__":
    unittest.main()
