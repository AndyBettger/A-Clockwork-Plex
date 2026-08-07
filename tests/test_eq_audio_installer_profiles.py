from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "installer" / "profiles" / "eq-split-bus"
PUBLIC_PCMS = ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm")


class EqAudioInstallerProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.split = (PROFILE / "split-bus.conf").read_text(encoding="utf-8")
        self.direct = (PROFILE / "direct-alarm-bypass.conf").read_text(encoding="utf-8")
        self.camilla = (PROFILE / "camilladsp-split-bus.yml").read_text(encoding="utf-8")

    def test_both_routes_preserve_the_public_pcm_contract(self) -> None:
        for pcm in PUBLIC_PCMS:
            self.assertIn(f"pcm.{pcm}", self.split)
            self.assertIn(f"pcm.{pcm}", self.direct)

    def test_split_route_keeps_alarm_on_channels_two_and_three(self) -> None:
        self.assertIn('pcm "hw:7,0,0"', self.split)
        self.assertIn("channels 4", self.split)
        self.assertIn("0.2 1", self.split)
        self.assertIn("1.3 1", self.split)
        alarm_start = self.split.index("pcm.acp_alarm_volume")
        alarm_end = self.split.index("pcm.acp_alarm {", alarm_start)
        alarm_block = self.split[alarm_start:alarm_end]
        self.assertIn('slave.pcm "acp_alarm_route"', alarm_block)
        self.assertNotIn('slave.pcm "acp_master"', alarm_block)

    def test_direct_failback_keeps_alarm_outside_music_master(self) -> None:
        alarm_start = self.direct.index("pcm.acp_alarm_volume")
        alarm_end = self.direct.index("pcm.acp_alarm {", alarm_start)
        alarm_block = self.direct[alarm_start:alarm_end]
        self.assertIn('slave.pcm "acp_dmix"', alarm_block)
        self.assertNotIn('slave.pcm "acp_master"', alarm_block)

    def test_camilladsp_pipeline_processes_music_before_alarm_combine(self) -> None:
        music_filter = self.camilla.index("names: [bass, mid, treble, headroom]")
        combine = self.camilla.index("name: combine_music_and_alarm", music_filter)
        limiter = self.camilla.index("names: [final_safety_limiter]", combine)
        self.assertLess(music_filter, combine)
        self.assertLess(combine, limiter)
        self.assertIn("bypassed: false", self.camilla[:music_filter])
        self.assertIn('device: "hw:7,1,0"', self.camilla)
        self.assertIn('device: "hw:CARD=Pro,DEV=0"', self.camilla)
        self.assertIn("clip_limit: -1.0", self.camilla)

    def test_profile_does_not_reintroduce_alsaequal(self) -> None:
        combined = "\n".join((self.split, self.direct, self.camilla)).lower()
        self.assertNotIn("alsaequal", combined)
        self.assertNotIn("acp_equal", combined)

    def test_loopback_persistence_matches_the_accepted_contract(self) -> None:
        module_load = (
            PROFILE / "modules-load.d" / "a-clockwork-plex-aloop.conf"
        ).read_text(encoding="utf-8")
        module_options = (
            PROFILE / "modprobe.d" / "a-clockwork-plex-aloop.conf"
        ).read_text(encoding="utf-8")
        self.assertEqual(module_load.splitlines()[-1], "snd_aloop")
        self.assertIn("index=7", module_options)
        self.assertIn("id=ACP_Loopback", module_options)
        self.assertIn("pcm_substreams=2", module_options)
        self.assertIn("pcm_notify=1", module_options)


if __name__ == "__main__":
    unittest.main()
