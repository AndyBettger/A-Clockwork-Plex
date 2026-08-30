from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.plexamp_preferences import PlexampPreferenceManager


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-helpers.sh"
ALARM_SOURCE = ROOT / "scripts" / "a-clockwork-plex-alarm-audio-helper.sh"
NAME_SOURCE = ROOT / "scripts" / "a-clockwork-plex-shairport-name.py"
MIXER_SOURCE = ROOT / "scripts" / "a-clockwork-plex-audio-mixer.py"
PLEXAMP_PREF_SOURCE = ROOT / "scripts" / "a-clockwork-plex-plexamp-preferences.py"


def load_plexamp_preference_helper():
    module_name = "acp_plexamp_preference_helper_test"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, PLEXAMP_PREF_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Plexamp preference helper for tests.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ApplianceHelpersInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        root: Path,
        *arguments: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            ["bash", str(INSTALLER), "--root", str(root), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=merged,
            check=False,
        )

    @staticmethod
    def target(root: Path, logical: str) -> Path:
        return root / logical.lstrip("/")

    def test_prepare_only_does_not_change_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio")
            existing.parent.mkdir(parents=True)
            existing.write_text("old helper\n", encoding="utf-8")

            result = self.run_installer(root, "--prepare-only", "--project-user", "clockuser")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(existing.read_text(encoding="utf-8"), "old helper\n")
            self.assertIn("No production file, service, route, mixer or PCM was changed", result.stdout)

    def test_guarded_activation_installs_runtime_sources_and_restricted_policies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-HELPERS",
                "--project-user",
                "clockuser",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            alarm = self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio")
            alarm_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-alarm-audio")
            name = self.target(root, "/usr/local/bin/a-clockwork-plex-shairport-name")
            name_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-shairport-name")
            mixer = self.target(root, "/usr/local/bin/a-clockwork-plex-audio-mixer")
            mixer_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-audio-mixer")
            mixer_defaults = self.target(root, "/etc/default/a-clockwork-plex-audio")
            plexamp_preferences = self.target(
                root, "/usr/local/bin/a-clockwork-plex-plexamp-preferences"
            )
            plexamp_sudoers = self.target(
                root, "/etc/sudoers.d/a-clockwork-plex-plexamp-preferences"
            )
            plexamp_defaults = self.target(
                root, "/etc/default/a-clockwork-plex-plexamp-preferences"
            )

            self.assertEqual(alarm.read_bytes(), ALARM_SOURCE.read_bytes())
            self.assertEqual(name.read_bytes(), NAME_SOURCE.read_bytes())
            self.assertEqual(mixer.read_bytes(), MIXER_SOURCE.read_bytes())
            self.assertEqual(plexamp_preferences.read_bytes(), PLEXAMP_PREF_SOURCE.read_bytes())
            self.assertEqual(oct(alarm.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(name.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(mixer.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(plexamp_preferences.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(alarm_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(name_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(mixer_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(plexamp_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(mixer_defaults.stat().st_mode & 0o777), "0o644")
            self.assertEqual(oct(plexamp_defaults.stat().st_mode & 0o777), "0o644")
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-alarm-audio release",
                alarm_sudoers.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-shairport-name status",
                name_sudoers.read_text(encoding="utf-8"),
            )
            mixer_policy = mixer_sudoers.read_text(encoding="utf-8")
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-mixer status",
                mixer_policy,
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-mixer set *",
                mixer_policy,
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-mixer live *",
                mixer_policy,
            )
            defaults = mixer_defaults.read_text(encoding="utf-8")
            self.assertIn("ALSA_CARD=Pro", defaults)
            self.assertIn("ALSA_DEVICE=0", defaults)
            self.assertIn("SAMPLE_RATE=44100", defaults)
            self.assertIn("CHANNELS=2", defaults)

            plexamp_policy = plexamp_sudoers.read_text(encoding="utf-8")
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-plexamp-preferences status",
                plexamp_policy,
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-plexamp-preferences apply",
                plexamp_policy,
            )
            self.assertNotIn("a-clockwork-plex-plexamp-preferences *", plexamp_policy)
            self.assertNotIn("systemctl", plexamp_policy)
            plexamp_config = plexamp_defaults.read_text(encoding="utf-8")
            self.assertIn("PROJECT_USER=clockuser", plexamp_config)
            self.assertIn("PROJECT_HOME=/home/clockuser", plexamp_config)
            self.assertIn("PLEXAMP_SERVICE=plexamp.service", plexamp_config)
            self.assertIn("PLEXAMP_PORT=32500", plexamp_config)

    def test_wrong_token_and_invalid_user_are_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "WRONG",
                "--project-user",
                "clockuser",
            )
            invalid = self.run_installer(root, "--prepare-only", "--project-user", "bad user")

            self.assertEqual(wrong.returncode, 64)
            self.assertEqual(invalid.returncode, 64)
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio").exists()
            )

    def test_injected_failure_restores_exact_prior_targets_and_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alarm = self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio")
            alarm_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-alarm-audio")
            alarm.parent.mkdir(parents=True)
            alarm_sudoers.parent.mkdir(parents=True)
            alarm.write_bytes(b"old-alarm-helper\n")
            alarm_sudoers.write_bytes(b"old-policy\n")
            os.chmod(alarm, 0o700)
            os.chmod(alarm_sudoers, 0o400)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-HELPERS",
                "--project-user",
                "clockuser",
                env={"ACP_HELPERS_TEST_FAIL_AFTER_INSTALL": "1"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(alarm.read_bytes(), b"old-alarm-helper\n")
            self.assertEqual(alarm_sudoers.read_bytes(), b"old-policy\n")
            self.assertEqual(oct(alarm.stat().st_mode & 0o777), "0o700")
            self.assertEqual(oct(alarm_sudoers.stat().st_mode & 0o777), "0o400")
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-shairport-name").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/sudoers.d/a-clockwork-plex-shairport-name").exists()
            )
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-audio-mixer").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/sudoers.d/a-clockwork-plex-audio-mixer").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/default/a-clockwork-plex-audio").exists()
            )
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-plexamp-preferences").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/sudoers.d/a-clockwork-plex-plexamp-preferences").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/default/a-clockwork-plex-plexamp-preferences").exists()
            )
            self.assertIn("restoring captured state", result.stderr)
            self.assertIn("pre-state restored", result.stderr)

    def test_protected_post_install_verification_uses_root_boundary(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("verify_regular_file()", source)
        self.assertIn("verify_mode()", source)
        self.assertIn("verify_contains()", source)
        self.assertIn('acp_run_root test -f "$physical"', source)
        self.assertIn('acp_run_root test -L "$physical"', source)
        self.assertIn("acp_run_root stat -c '%a'", source)
        self.assertIn('acp_run_root grep -Fq -- "$expected" "$physical"', source)
        self.assertIn("Installed helper target is not a regular non-symlink file", source)
        self.assertIn("Installed helper policy is missing required rule", source)
        self.assertNotIn('[[ -f "$(acp_path "$installed")"', source)
        self.assertNotIn('grep -Fq "$PROJECT_USER ALL=(root)', source)

    def test_installer_packages_existing_runtime_sources_without_reimplementing_them(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-alarm-audio-helper.sh", source)
        self.assertIn("a-clockwork-plex-shairport-name.py", source)
        self.assertIn("a-clockwork-plex-audio-mixer.py", source)
        self.assertIn("a-clockwork-plex-plexamp-preferences.py", source)
        self.assertIn("ACP_HELPERS_TEST_FAIL_AFTER_INSTALL", source)
        self.assertIn('[[ "$ROOT" != / && "${ACP_HELPERS_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]', source)
        self.assertIn("prime_mixer_controls()", source)
        self.assertIn("acp_master acp_plexamp acp_airplay acp_alarm", source)
        self.assertNotIn("def apply_name", source)
        self.assertNotIn("amixer", source)


class FakePlexampConnection:
    def close(self) -> None:
        return None


class FakePlexampServiceRunner:
    def __init__(self) -> None:
        self.active = True
        self.fail_start_once = False
        self.calls: list[list[str]] = []

    def __call__(self, arguments, **_kwargs):
        command = list(arguments)
        self.calls.append(command)
        if command[:2] == ["systemctl", "is-active"]:
            return subprocess.CompletedProcess(command, 0 if self.active else 3, "", "")
        if command[:2] == ["systemctl", "stop"]:
            self.active = False
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["systemctl", "start"]:
            if self.fail_start_once:
                self.fail_start_once = False
                return subprocess.CompletedProcess(command, 1, "", "injected start failure")
            self.active = True
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")


class PlexampPreferenceHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.helper = load_plexamp_preference_helper()

    def build_home(self, root: Path):
        home = root / "home" / "clockuser"
        package = home / "plexamp" / "package.json"
        package.parent.mkdir(parents=True)
        package.write_text(json.dumps({"version": "4.13.2"}), encoding="utf-8")
        settings = home / ".local" / "share" / "Plexamp" / "Settings"
        settings.mkdir(parents=True)
        values = {
            "audioConversionBitrate": 256,
            "autoPlayEnabled": False,
            "cacheSize": 32768,
            "cachingWiFi": 10,
            "loudnessLeveling": False,
            "precacheNetworkSpeed": 0,
            "sampleRateConversionQuality": 4,
            "sampleRateMatching": 2,
        }
        paths = {}
        for key, value in values.items():
            path = settings / f"@Plexamp:settings:{key}"
            path.write_bytes(self.helper._encode_scalar(key, value))
            paths[key] = path
        return home, values, paths

    def owner(self, root: Path, runner: FakePlexampServiceRunner):
        home, values, paths = self.build_home(root)

        def connector(_address, timeout=0.25):
            del timeout
            if not runner.active:
                raise OSError("service is stopped")
            return FakePlexampConnection()

        owner = self.helper.PlexampPreferenceTransaction(
            self.helper.HelperConfig("clockuser", home),
            runner=runner,
            connector=connector,
            sleeper=lambda _seconds: None,
            lock_path=root / "plexamp-preferences.lock",
        )
        return owner, values, paths

    def test_helper_restores_only_existing_allowlisted_values_and_restarts_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = FakePlexampServiceRunner()
            owner, _values, paths = self.owner(root, runner)

            status = owner.status()
            self.assertTrue(status["restore_ready"])
            self.assertEqual(status["installed_version"], "4.13.2")
            self.assertEqual(status["allowlisted_preferences_present"], 8)
            self.assertNotIn("preferences", status)

            result = owner.apply(
                source_version="4.13.2",
                preferences={"autoPlayEnabled": True, "cacheSize": 16384},
            )

            self.assertTrue(result["verified"])
            self.assertEqual(result["changed_count"], 2)
            self.assertTrue(result["service_restarted"])
            self.assertEqual(paths["autoPlayEnabled"].read_bytes(), b"Btrue")
            self.assertEqual(paths["cacheSize"].read_bytes(), b"N16384")
            self.assertTrue(runner.active)
            self.assertIn(["systemctl", "stop", "plexamp.service"], runner.calls)
            self.assertIn(["systemctl", "start", "plexamp.service"], runner.calls)

    def test_version_mismatch_refuses_before_service_or_preference_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = FakePlexampServiceRunner()
            owner, _values, paths = self.owner(root, runner)
            before = paths["autoPlayEnabled"].read_bytes()

            with self.assertRaises(RuntimeError) as context:
                owner.apply(
                    source_version="4.14.0",
                    preferences={"autoPlayEnabled": True},
                )

            self.assertIn("not compatible", str(context.exception))
            self.assertEqual(paths["autoPlayEnabled"].read_bytes(), before)
            self.assertEqual(runner.calls, [])

    def test_late_service_restart_failure_restores_exact_preference_bytes_and_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = FakePlexampServiceRunner()
            owner, _values, paths = self.owner(root, runner)
            before = {
                "autoPlayEnabled": paths["autoPlayEnabled"].read_bytes(),
                "cacheSize": paths["cacheSize"].read_bytes(),
            }
            runner.fail_start_once = True

            with self.assertRaises(self.helper.PreferenceTransactionError) as context:
                owner.apply(
                    source_version="4.13.2",
                    preferences={"autoPlayEnabled": True, "cacheSize": 16384},
                )

            self.assertEqual(context.exception.stage, "service restart")
            self.assertEqual(context.exception.rollback_failures, [])
            self.assertEqual(paths["autoPlayEnabled"].read_bytes(), before["autoPlayEnabled"])
            self.assertEqual(paths["cacheSize"].read_bytes(), before["cacheSize"])
            self.assertTrue(runner.active)

    def test_missing_allowlisted_target_is_never_created_implicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = FakePlexampServiceRunner()
            owner, _values, paths = self.owner(root, runner)
            paths["autoPlayEnabled"].unlink()

            with self.assertRaises(RuntimeError) as context:
                owner.apply(
                    source_version="4.13.2",
                    preferences={"autoPlayEnabled": True},
                )

            self.assertIn("will not be created implicitly", str(context.exception))
            self.assertFalse(paths["autoPlayEnabled"].exists())
            self.assertEqual(runner.calls, [])

    def test_app_manager_passes_values_on_stdin_not_argv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper_path = Path(directory) / "helper"
            helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(helper_path, 0o755)
            captured = {}

            def runner(command, **kwargs):
                captured["command"] = list(command)
                captured["input"] = kwargs.get("input")
                payload = {
                    "ok": True,
                    "applied": True,
                    "verified": True,
                    "changed_count": 1,
                    "installed_version": "4.13.2",
                    "service_restarted": True,
                }
                return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

            manager = PlexampPreferenceManager(helper_path=helper_path, runner=runner)
            result = manager.apply(
                {"autoPlayEnabled": True},
                source_version="4.13.2",
            )

            self.assertTrue(result["verified"])
            self.assertEqual(
                captured["command"],
                ["sudo", "-n", str(helper_path), "apply"],
            )
            self.assertNotIn("autoPlayEnabled", " ".join(captured["command"]))
            request = json.loads(captured["input"])
            self.assertEqual(request["source_version"], "4.13.2")
            self.assertEqual(request["preferences"], {"autoPlayEnabled": True})


if __name__ == "__main__":
    unittest.main()
