from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "settings-completion.js"
STYLE = ROOT / "app" / "static" / "css" / "settings-completion.css"
BASE = ROOT / "app" / "templates" / "base.html"
SETTINGS_TEMPLATE = ROOT / "app" / "templates" / "settings.html"
ABOUT = ROOT / "app" / "static" / "app-version.json"
ABOUT_CLIENT = ROOT / "app" / "static" / "js" / "settings-about.js"
ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"
BACKUP_RESTORE = ROOT / "app" / "static" / "js" / "settings-backup-restore.js"


class SettingsCompletionTests(unittest.TestCase):
    def test_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, ABOUT_CLIENT, BACKUP_RESTORE):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_completion_assets_are_settings_only(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("settings-completion.css", text)
        self.assertIn("settings-completion.js", text)
        self.assertIn("20260823-about-release-metadata-v1", text)
        self.assertIn("active_page | default(state.mode) == 'settings'", text)
        self.assertTrue(STYLE.exists())

    def test_advanced_route_controls_are_removed_from_diagnostics(self):
        text = CLIENT.read_text(encoding="utf-8")
        for path in (
            "alarm_audio.shared_mixer_enabled",
            "alarm_audio.hardware_device",
            "alarm_audio.alsa_device",
        ):
            self.assertIn(path, text)
        self.assertIn("closest('label')?.remove()", text)
        self.assertIn("Read-only audio route", text)
        self.assertIn("test_duration_seconds", text)

    def test_false_advanced_dirty_markers_are_cleared_at_all_levels(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("settings-subpage-dirty-dot", text)
        self.assertIn("settings-option-dirty", text)
        self.assertIn("data-settings-section-target=\"advanced\"", text)
        self.assertIn("dot.hidden = true", text)

    def test_about_metadata_is_durable_release_identity(self):
        metadata = json.loads(ABOUT.read_text(encoding="utf-8"))
        self.assertEqual(
            set(metadata),
            {
                "name",
                "version",
                "tag",
                "release_name",
                "repository",
                "companion_repository",
            },
        )
        self.assertEqual(metadata["name"], "A Clockwork Plex")
        self.assertEqual(metadata["version"], "0.4.0")
        self.assertRegex(metadata["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(metadata["tag"], f"v{metadata['version']}")
        self.assertEqual(metadata["release_name"], "Unified Bedside Appliance")

        durable_values = " ".join(str(value) for value in metadata.values()).lower()
        for stale in ("feature/alarm-engine", "-dev", "next phase", "rollout next"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, durable_values)

        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("Appliance capabilities", client)
        self.assertIn("Managed EQ", client)
        self.assertIn("Guarded setup", client)
        self.assertNotIn("Next phase", client)
        self.assertNotIn("Production EQ", client)
        self.assertNotIn("old bare installer remains blocked", client)

        about_client = ABOUT_CLIENT.read_text(encoding="utf-8")
        self.assertIn("metadata.version", about_client)
        self.assertIn("metadata.release_name", about_client)
        self.assertIn("metadata.tag", about_client)
        self.assertNotIn("metadata.phase", about_client)

    def test_advanced_alarm_poll_is_slow_and_visibility_scoped(self):
        text = ADVANCED.read_text(encoding="utf-8")
        self.assertIn("PASSIVE_REFRESH_MS = 30000", text)
        self.assertIn("pageVisible()", text)
        self.assertNotIn("5000", text)

    def test_complete_backup_restore_controller_is_owned_by_thin_about_bootstrap(self):
        self.assertTrue(BACKUP_RESTORE.exists())
        for template in (BASE, SETTINGS_TEMPLATE):
            self.assertNotIn(
                "settings-backup-restore.js",
                template.read_text(encoding="utf-8"),
            )

        about_text = ABOUT_CLIENT.read_text(encoding="utf-8")
        self.assertIn("settings-backup-restore.js?v=20260910-controller-v1", about_text)
        self.assertIn("window.__aClockworkPlexBackupRestoreClientRequested", about_text)
        self.assertNotIn("data-settings-subpage=\"advanced:backup\"", about_text)
        self.assertNotIn("/api/settings/backup", about_text)
        self.assertNotIn("/api/settings/restore/apply", about_text)
        self.assertNotIn("MAX_RESTORE_FILE_BYTES", about_text)

        text = BACKUP_RESTORE.read_text(encoding="utf-8")
        self.assertIn("window.__aClockworkPlexBackupRestoreLoaded", text)
        self.assertIn("advanced:backup", text)
        self.assertIn("/api/settings/backup", text)
        self.assertIn("/api/settings/restore/apply", text)

    def test_complete_backup_export_wires_v2_with_safe_v1_fallback(self):
        text = BACKUP_RESTORE.read_text(encoding="utf-8")
        for marker in (
            "settings-backup-restore-v2.js?v=20260910-v2-transaction-v1",
            "plexamp-native-portability-bridge.js?v=20260910-portability-v1",
            "plexamp-home-portability-v2-bridge.js?v=20260910-portability-v1",
            "ACPPlexampNativePortability.snapshot",
            "ACPPlexampHomePortabilityV2.snapshot",
            "ACPConfigurationBackupRestoreV2.assembleBackupV2",
            "recordCompatibilityFallback",
            "includeV1BrowserPreferences",
            "Complete schema-v2 backup downloaded",
            "Schema-v1 compatibility backup downloaded",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

        self.assertIn("const [nativeSnapshot, homeSnapshot] = await Promise.all", text)
        self.assertIn("return { backup: serverBackup, complete: false, homeIncluded };", text)

    def test_complete_restore_preview_and_review_are_read_only_and_refreshed(self):
        text = BACKUP_RESTORE.read_text(encoding="utf-8")
        review_start = text.index("reviewButton?.addEventListener('click'")
        review_end = text.index("cancelButton?.addEventListener('click'", review_start)
        review = text[review_start:review_end]

        self.assertIn("const plan = await previewServer(serverBackup);", review)
        self.assertIn("const browserPlan = targets.plexamp ? await previewBrowser(serverBackup) : null;", review)
        self.assertIn("Refreshing the selected owners and confirmation boundary. Nothing is changing.", review)
        self.assertIn("settingsHaveUnsavedChanges()", review)
        self.assertIn("reviewedTargetSignature = currentTargetSignature();", review)
        self.assertNotIn("applyServer(", review)
        self.assertNotIn("runRestoreTransaction", review)

        preview_endpoint = text.index("'/api/settings/restore/preview'")
        apply_endpoint = text.index("'/api/settings/restore/apply'")
        self.assertLess(preview_endpoint, apply_endpoint)
        self.assertIn("Preview and Review never change the appliance.", text)

    def test_complete_restore_routes_v2_atomically_and_keeps_v1_compatibility(self):
        text = BACKUP_RESTORE.read_text(encoding="utf-8")
        v1_start = text.index("async function confirmV1()")
        v2_start = text.index("async function confirmV2()")
        confirm_start = text.index("confirmButton?.addEventListener('click'", v2_start)
        v1 = text[v1_start:v2_start]
        v2 = text[v2_start:confirm_start]

        self.assertIn("homeApplied = await applyV1Home", v1)
        self.assertIn("serverResult = await applyServer", v1)
        self.assertLess(v1.index("await applyV1Home"), v1.index("await applyServer"))
        self.assertIn("plexamp_headless_applied_change_count", v1)

        for marker in (
            "ACPConfigurationBackupRestoreV2.runRestoreTransaction",
            "nativeClient: window.ACPPlexampNativePortability",
            "homeClient: window.ACPPlexampHomePortabilityV2",
            "const serverApply = selectedTargets.acp",
            "native_applied_change_count",
            "home_applied_change_count",
            "server_result?.server_applied_change_count",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, v2)
        self.assertIn(": null;", v2)

    def test_complete_restore_failure_copy_is_fail_closed_and_browser_scope_is_bounded(self):
        text = BACKUP_RESTORE.read_text(encoding="utf-8")
        for marker in (
            "Earlier Plexamp browser changes were rolled back and verified.",
            "Browser rollback could not be fully verified; do not retry",
            "The failed owner also reported its own rollback complete.",
            "Run Preview restore again before another attempt.",
            "restoreInFlight",
            "settingsHaveUnsavedChanges()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

        for unsafe in (
            "localStorage.clear",
            "eval(",
            "remote-debugging",
            "LevelDB",
            "User Data/Default",
        ):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, text)


if __name__ == "__main__":
    unittest.main()
