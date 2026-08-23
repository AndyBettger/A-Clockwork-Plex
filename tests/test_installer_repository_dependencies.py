from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "installer/repository-dependencies.txt"

EXPECTED_DEPENDENCIES = {
    "appliance-installer.sh",
    "config.example.json",
    "requirements.txt",
    "app/runner.py",
    "systemd/a-clockwork-plex.service",
    "installer/lib/application_transaction.sh",
    "installer/lib/audio.sh",
    "installer/lib/common.sh",
    "installer/lib/components.sh",
    "installer/lib/direct_audio.sh",
    "installer/lib/packages.sh",
    "installer/lib/platform_hardware.sh",
    "installer/lib/plexamp_runtime.sh",
    "installer/lib/prerequisites.sh",
    "installer/lib/runtime.sh",
    "installer/lib/services.sh",
    "installer/lib/transaction.sh",
    "installer/lib/verification.sh",
    "installer/profiles/direct/alarm-safe.conf",
    "installer/profiles/eq-split-bus/split-bus.conf",
    "installer/profiles/eq-split-bus/direct-alarm-bypass.conf",
    "installer/profiles/eq-split-bus/camilladsp-split-bus.yml",
    "installer/profiles/eq-split-bus/a-clockwork-plex-split-bus.defaults",
    "installer/profiles/eq-split-bus/modules-load.d/a-clockwork-plex-aloop.conf",
    "installer/profiles/eq-split-bus/modprobe.d/a-clockwork-plex-aloop.conf",
    "installer/profiles/eq-split-bus/systemd/a-clockwork-plex-audio-route.service",
    "installer/profiles/eq-split-bus/systemd/a-clockwork-plex-camilladsp.service",
    "installer/profiles/eq-split-bus/systemd/a-clockwork-plex-audio-failback.service",
    "installer/templates/a-clockwork-plex-audio-route.sudoers.in",
    "installer/templates/a-clockwork-plex-audio-eq.sudoers.in",
    "scripts/fetch-camilladsp-4.1.3.sh",
    "scripts/check-appliance-components.sh",
    "scripts/check-appliance-packages.sh",
    "scripts/check_nfc_python_deps.py",
    "scripts/preflight-appliance.sh",
    "scripts/verify-appliance.sh",
    "scripts/verify-fresh-bootstrap.sh",
    "scripts/install-appliance-packages.sh",
    "scripts/install-platform-hardware.sh",
    "scripts/install-plexamp-runtime.sh",
    "scripts/install-nfc-listener.sh",
    "scripts/install-weather-config.sh",
    "scripts/install-dashboard-integration.sh",
    "scripts/install-appliance-application.sh",
    "scripts/install-appliance-helpers.sh",
    "scripts/install-airplay-integration.sh",
    "scripts/install-airplay-hooks.sh",
    "scripts/launch-dashboard-kiosk.sh",
    "scripts/nfc-plexamp-mode.sh",
    "scripts/audio/install-direct.sh",
    "scripts/audio/install-eq.sh",
    "scripts/audio/repair-audio.sh",
    "scripts/audio/uninstall-eq.sh",
    "scripts/audio/verify-audio.sh",
    "scripts/a-clockwork-plex-airplay-wrappers.py",
    "scripts/a-clockwork-plex-shairport-integration.py",
    "scripts/airplay-metadata-listener.py",
    "scripts/a-clockwork-plex-alarm-audio-helper.sh",
    "scripts/a-clockwork-plex-shairport-name.py",
    "scripts/a-clockwork-plex-weather-secret.py",
    "scripts/a-clockwork-plex-audio-mixer.py",
    "scripts/a-clockwork-plex-audio-route.py",
    "scripts/a-clockwork-plex-audio-eq.py",
    "scripts/audio_eq_camilladsp/__init__.py",
    "scripts/audio_eq_camilladsp/model.py",
    "scripts/audio_eq_camilladsp/runtime.py",
    "scripts/audio_eq_camilladsp/cli.py",
    "vendor/plexamp-nfc-listener/SOURCE.md",
    "vendor/plexamp-nfc-listener/requirements.txt",
    "vendor/plexamp-nfc-listener/nfc_listener.py",
}


def manifest_entries() -> list[str]:
    return [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class InstallerRepositoryDependencyTests(unittest.TestCase):
    def test_manifest_is_exact_unique_safe_dependency_closure(self) -> None:
        entries = manifest_entries()
        self.assertEqual(len(entries), len(set(entries)), "duplicate dependency path")
        self.assertEqual(EXPECTED_DEPENDENCIES, set(entries))
        for relative in entries:
            path = Path(relative)
            self.assertFalse(path.is_absolute(), relative)
            self.assertNotIn("..", path.parts, relative)

    def test_every_pinned_dependency_is_a_regular_repository_file(self) -> None:
        missing: list[str] = []
        unsafe: list[str] = []
        for relative in manifest_entries():
            path = REPO_ROOT / relative
            if not path.is_file():
                missing.append(relative)
            elif path.is_symlink():
                unsafe.append(relative)
        self.assertEqual([], missing, f"missing dependencies: {missing}")
        self.assertEqual([], unsafe, f"symlink dependencies: {unsafe}")

    def test_setup_fails_closed_on_manifest_before_first_installer_source(self) -> None:
        source = (REPO_ROOT / "setup.sh").read_text(encoding="utf-8")
        manifest_gate = source.index('INSTALL_DEPENDENCY_MANIFEST="$REPO_ROOT/installer/repository-dependencies.txt"')
        plexamp_source = source.index('source "$REPO_ROOT/installer/lib/plexamp_runtime.sh"')
        camilla_fetch = source.index('bash "$REPO_ROOT/scripts/fetch-camilladsp-4.1.3.sh"')
        appliance_apply = source.index('bash "$REPO_ROOT/appliance-installer.sh"')
        self.assertLess(manifest_gate, plexamp_source)
        self.assertLess(manifest_gate, camilla_fetch)
        self.assertLess(manifest_gate, appliance_apply)
        self.assertIn('done <"$INSTALL_DEPENDENCY_MANIFEST"', source)
        self.assertIn("required fresh-install repository dependency is unavailable", source)
        subprocess.run(["bash", "-n", str(REPO_ROOT / "setup.sh")], check=True)

    def test_lower_level_engine_reuses_same_manifest_gate(self) -> None:
        components = (REPO_ROOT / "installer/lib/components.sh").read_text(encoding="utf-8")
        installer = (REPO_ROOT / "appliance-installer.sh").read_text(encoding="utf-8")
        self.assertIn(
            'ACP_INSTALL_DEPENDENCY_MANIFEST="$ACP_REPO_ROOT/installer/repository-dependencies.txt"',
            components,
        )
        self.assertIn("acp_verify_repository_dependencies || return 1", components)
        self.assertIn("acp_verify_component_sources || fail", installer)
        subprocess.run(["bash", "-n", str(REPO_ROOT / "installer/lib/components.sh")], check=True)

    def test_transitive_cleanup_risks_are_explicitly_pinned(self) -> None:
        entries = set(manifest_entries())
        high_risk_transitive = {
            "scripts/audio/repair-audio.sh",
            "scripts/check_nfc_python_deps.py",
            "vendor/plexamp-nfc-listener/requirements.txt",
            "vendor/plexamp-nfc-listener/nfc_listener.py",
            "scripts/nfc-plexamp-mode.sh",
            "config.example.json",
            "systemd/a-clockwork-plex.service",
            "installer/lib/common.sh",
            "installer/lib/services.sh",
            "installer/lib/audio.sh",
            "installer/lib/runtime.sh",
            "installer/lib/verification.sh",
            "installer/templates/a-clockwork-plex-audio-route.sudoers.in",
            "installer/templates/a-clockwork-plex-audio-eq.sudoers.in",
        }
        self.assertTrue(high_risk_transitive <= entries, sorted(high_risk_transitive - entries))


if __name__ == "__main__":
    unittest.main()
