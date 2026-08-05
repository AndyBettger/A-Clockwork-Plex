from __future__ import annotations

import ast
import csv
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_transaction import sandbox_transaction as transaction


class StageCSandboxTransactionSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.wrapper = self.repo / "scripts/test-stage-c-sandbox-transaction.sh"
        self.module = self.repo / "scripts/stage_c_transaction/sandbox_transaction.py"
        self.retired_module = (
            self.repo / "scripts/stage_c_transaction/sandbox_transaction_runtime.py"
        )

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
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(rows)
        self._write(
            package / "results.tsv",
            "check\tresult\tdetail\nfixture\tPASS\tcomplete\n",
        )
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

    def _build_c3(self, root: Path, package: Path) -> tuple[Path, str]:
        c3 = root / "stage-c3"
        c3.mkdir()
        current_content = b"accepted pre-stage-c route\n"
        current_digest = hashlib.sha256(current_content).hexdigest()
        current = c3 / "rootfs/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
        self._write(current, current_content)

        result_rows = [("check", "result", "detail")]
        result_rows.extend(
            (check, "PASS", "fixture") for check in transaction.EXPECTED_STAGE_C3_CHECKS
        )
        with (c3 / "results.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(result_rows)

        self._write(
            c3 / "report.txt",
            "Managed package files: 12\n"
            "Verified absent managed files: 12\n"
            "Existing managed files: 0\n"
            "Managed destination conflicts: 0\n"
            "Protected sudoers destination resolved: absent\n"
            "no production path was written\n"
            "this rehearsal evidence must never be reused as the future activation snapshot\n",
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
                        str(c3 / "absence"),
                    )
                )
        for destination, mode in sorted(present_directories.items()):
            rows.append(
                ("directory", destination, "present", mode, "root:root", "-", "-")
            )
        for destination in sorted(absent_directories):
            rows.append(("directory", destination, "absent", "-", "-", "-", "-"))
        with (c3 / "filesystem-state.tsv").open("w", encoding="utf-8", newline="") as handle:
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

        service_rows = [
            ("service", "load_state", "active_state", "enabled_state"),
            ("plexamp.service", "loaded", "active", "enabled"),
            ("shairport-sync.service", "loaded", "active", "enabled"),
            ("a-clockwork-plex.service", "loaded", "active", "enabled"),
            (
                "a-clockwork-plex-audio-route.service",
                "not-found",
                "inactive",
                "not-found",
            ),
            (
                "a-clockwork-plex-camilladsp.service",
                "not-found",
                "inactive",
                "not-found",
            ),
            (
                "a-clockwork-plex-audio-failback.service",
                "not-found",
                "inactive",
                "not-found",
            ),
        ]
        with (c3 / "service-state.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(service_rows)

        mixer_rows = [("control", "value")]
        mixer_rows.extend((control, "0") for control in transaction.MIXER_CONTROLS)
        with (c3 / "mixer-state.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(mixer_rows)

        module_rows = [
            ("item", "value"),
            ("snd_aloop.loaded", "true"),
            ("snd_aloop.index", "7"),
            ("snd_aloop.id", "ACP_Loopback"),
            ("snd_aloop.pcm_substreams", "2"),
            ("snd_aloop.pcm_notify", "1"),
            ("snd_aloop.enable", "Y"),
            ("dac.device", "/dev/snd/pcmC2D0p"),
            ("dac.exists", "true"),
        ]
        with (c3 / "module-dac-state.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(module_rows)

        rollback_rows = [("step", "area", "action")]
        rollback_rows.extend(
            (str(index), "filesystem", "fixture") for index in range(1, 23)
        )
        rollback_rows.append(("23", "final", "fixture"))
        with (c3 / "rollback-ledger.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows(rollback_rows)

        transaction.write_evidence_manifest(c3)
        return c3, current_digest

    def test_wrapper_and_engine_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(self.wrapper)], check=True)
        compile(self.module.read_text(encoding="utf-8"), str(self.module), "exec")

    def test_prepare_only_has_no_sudo_and_prints_guarded_sandbox_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._build_package(root)
            c3, _ = self._build_c3(root, package)
            completed = subprocess.run(
                [
                    "bash",
                    str(self.wrapper),
                    "--package-root",
                    str(package),
                    "--stage-c3-root",
                    str(c3),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        self.assertIn("is prepared", completed.stdout)
        self.assertIn("Prepare-only invoked no sudo", completed.stdout)
        self.assertIn("--run-sandbox", completed.stdout)
        self.assertIn(transaction.REQUIRED_CONFIRMATION, completed.stdout)

    def test_single_authority_and_retired_runtime_absent(self) -> None:
        self.assertFalse(self.retired_module.exists())
        wrapper = self.wrapper.read_text(encoding="utf-8")
        self.assertIn("stage_c_transaction.sandbox_transaction", wrapper)
        self.assertNotIn("sandbox_transaction_runtime", wrapper)
        source = self.module.read_text(encoding="utf-8")
        self.assertEqual(source.count("def run_rehearsal("), 1)
        self.assertEqual(source.count("def rollback_sandbox("), 1)
        self.assertEqual(source.count("def main()"), 1)

    def test_engine_has_no_privileged_or_audio_command_execution(self) -> None:
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
        for forbidden in ("systemctl", "amixer", "modprobe", "aplay", "camilladsp"):
            self.assertNotIn(f"{forbidden}(", source)

    def test_cli_is_sandbox_only(self) -> None:
        source = self.module.read_text(encoding="utf-8")
        for option in (
            "--package-root",
            "--stage-c3-root",
            "--sandbox-root",
            "--confirm",
        ):
            self.assertIn(option, source)
        for forbidden in (
            "--install",
            "--activate",
            "--keep",
            "--failback",
            "--uninstall",
        ):
            self.assertNotIn(forbidden, source)

    def test_sandbox_mapping_never_returns_production_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mapped = transaction.mapped_path(root, "/etc/example.conf")
            self.assertEqual(mapped, root / "etc/example.conf")
            with self.assertRaises(SystemExit):
                transaction.mapped_path(root, "../etc/passwd")

    def test_full_rehearsal_installs_fails_rolls_back_and_preserves_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture_root = Path(temporary)
            package = self._build_package(fixture_root)
            c3, current_digest = self._build_c3(fixture_root, package)
            package_before = transaction.tree_fingerprint(package)
            c3_before = transaction.tree_fingerprint(c3)
            sandbox = Path(
                tempfile.mkdtemp(
                    prefix=transaction.SANDBOX_PREFIX,
                    dir="/var/tmp",
                )
            )
            sandbox.chmod(0o700)
            try:
                original_digest = transaction.EXPECTED_PRE_STAGE_C_ALSA_SHA256
                transaction.EXPECTED_PRE_STAGE_C_ALSA_SHA256 = current_digest
                try:
                    scenarios = transaction.run_rehearsal(package, c3, sandbox)
                finally:
                    transaction.EXPECTED_PRE_STAGE_C_ALSA_SHA256 = original_digest
                self.assertEqual(len(scenarios), 4)
                self.assertTrue(scenarios[0].install_verified)
                self.assertTrue(all(item.rollback_mismatches == 0 for item in scenarios))

                with (sandbox / "results.tsv").open(
                    encoding="utf-8",
                    newline="",
                ) as handle:
                    result_rows = list(csv.DictReader(handle, delimiter="\t"))
                self.assertEqual(
                    [row["check"] for row in result_rows],
                    [
                        "input-replay",
                        "sandbox-scope",
                        "first-install-boundary",
                        "install-success",
                        "explicit-uninstall-rollback",
                        "failure-injection",
                        "automatic-rollback",
                        "exact-state-verification",
                        "production-boundary",
                    ],
                )

                sudoers_modes = []
                for scenario_root in (sandbox / "scenarios").iterdir():
                    post = scenario_root / "post-rollback-fingerprint.tsv"
                    with post.open(encoding="utf-8", newline="") as handle:
                        rows = list(csv.DictReader(handle, delimiter="\t"))
                    sudoers = next(
                        row
                        for row in rows
                        if row["path"] == "system-root/etc/sudoers.d"
                    )
                    sudoers_modes.append(sudoers["mode"])
                self.assertEqual(sudoers_modes, ["750"] * 4)
                self.assertEqual(transaction.tree_fingerprint(package), package_before)
                self.assertEqual(transaction.tree_fingerprint(c3), c3_before)
                self.assertIn(
                    "Transaction authority: scripts.stage_c_transaction.sandbox_transaction",
                    (sandbox / "report.txt").read_text(encoding="utf-8"),
                )
            finally:
                shutil.rmtree(sandbox)

    def test_three_failure_points_use_same_rollback_function(self) -> None:
        source = self.module.read_text(encoding="utf-8")
        run_scenario = source.split("def run_scenario", 1)[1].split(
            "def result",
            1,
        )[0]
        self.assertEqual(run_scenario.count("mismatches = rollback_sandbox("), 1)
        for failure in transaction.FAILURE_POINTS:
            self.assertIn(failure, source)

    def test_symlinked_input_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._build_package(root)
            c3, current_digest = self._build_c3(root, package)
            (c3 / "unsafe-link").symlink_to(c3 / "report.txt")
            original_digest = transaction.EXPECTED_PRE_STAGE_C_ALSA_SHA256
            transaction.EXPECTED_PRE_STAGE_C_ALSA_SHA256 = current_digest
            try:
                with self.assertRaises(SystemExit):
                    transaction.validate_inputs(package, c3)
            finally:
                transaction.EXPECTED_PRE_STAGE_C_ALSA_SHA256 = original_digest


if __name__ == "__main__":
    unittest.main()
