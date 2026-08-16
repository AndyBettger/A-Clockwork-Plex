from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNINSTALL_EQ = ROOT / "scripts" / "audio" / "uninstall-eq.sh"


class EqUninstallDesktopAudioQuiesceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = UNINSTALL_EQ.read_text(encoding="utf-8")

    def test_wireplumber_is_only_quiesced_when_loopback_must_be_removed(self) -> None:
        function = self.source.split("quiesce_wireplumber_for_loopback_restore() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn('[[ "$before" == absent && -d /sys/module/snd_aloop ]] || return 0', function)
        self.assertIn('systemctl --user is-active --quiet wireplumber.service', function)
        self.assertIn('systemctl --user stop wireplumber.service', function)
        self.assertNotIn("kill ", function)
        self.assertNotIn("pkill", function)

    def test_wireplumber_is_restored_after_loopback_transition(self) -> None:
        activate = self.source.split("activate_uninstall() {", 1)[1]
        quiesce = activate.index("quiesce_wireplumber_for_loopback_restore")
        loopback = activate.index("acp_restore_loopback_state")
        restore = activate.index("restore_wireplumber_after_loopback_restore")
        app_restore = activate.index('acp_restore_captured_enablement "$original_services"')
        self.assertLess(quiesce, loopback)
        self.assertLess(loopback, restore)
        self.assertLess(restore, app_restore)
        self.assertIn('systemctl --user start wireplumber.service', self.source)

    def test_managed_eq_units_are_verified_stopped_before_loopback_restore(self) -> None:
        activate = self.source.split("activate_uninstall() {", 1)[1]
        stop = activate.index("acp_stop_eq_audio_units")
        verify = activate.index("verify_eq_audio_units_stopped")
        loopback = activate.index("acp_restore_loopback_state")
        self.assertLess(stop, verify)
        self.assertLess(verify, loopback)

    def test_failure_recovery_reloads_loopback_before_camilladsp_restart(self) -> None:
        restore = self.source.split("restore_current_install() {", 1)[1].split("\n}\n", 1)[0]
        loopback_reload = restore.index("sudo -- modprobe snd_aloop")
        managed_services = restore.index("acp_restore_managed_service_state")
        self.assertLess(loopback_reload, managed_services)


if __name__ == "__main__":
    unittest.main()
