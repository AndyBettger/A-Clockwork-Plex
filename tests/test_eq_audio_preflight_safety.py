from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "audio" / "preflight-eq.sh"
AUDIT = ROOT / "scripts" / "audio" / "audit-hi-res-audio.sh"
PROBE = ROOT / "scripts" / "audio" / "probe-hi-res-dac.py"
REHEARSAL = ROOT / "scripts" / "audio" / "rehearse-hi-res-bus.py"
RECOVERY = ROOT / "scripts" / "audio" / "recover-hi-res-rehearsal.py"
ROADMAP = ROOT / "docs" / "roadmap" / "ROADMAP.md"


class EqAudioPreflightSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PREFLIGHT.read_text(encoding="utf-8")
        self.audit_source = AUDIT.read_text(encoding="utf-8")
        self.probe_source = PROBE.read_text(encoding="utf-8")
        self.rehearsal_source = REHEARSAL.read_text(encoding="utf-8")
        self.recovery_source = RECOVERY.read_text(encoding="utf-8")

    def test_shell_syntax_and_help(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(PREFLIGHT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        help_result = subprocess.run(
            ["bash", str(PREFLIGHT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("read-only host/parser gate", help_result.stdout)
        self.assertIn("ordinary Plexamp playback may remain", help_result.stdout)

    def test_preflight_has_no_privileged_or_audio_mutation_command(self) -> None:
        self.assertNotRegex(
            self.source,
            re.compile(r"(?m)^\s*(?:sudo|rm|cp|mv|install|modprobe|amixer|alsactl)\b"),
        )
        self.assertNotRegex(
            self.source,
            re.compile(r"\bsystemctl\s+(?:start|stop|restart|enable|disable|reload)\b"),
        )
        self.assertNotIn("aplay -D", self.source)
        self.assertNotIn("arecord", self.source)
        self.assertNotIn("source \"$REPO_ROOT/installer/lib/", self.source)
        for path in ("/etc/", "/usr/local/", "/var/lib/"):
            self.assertNotRegex(
                self.source,
                re.compile(rf">\s*['\"]?{re.escape(path)}"),
            )

    def test_real_parsers_are_used_inside_private_boundaries(self) -> None:
        for marker in (
            'ALSA_CONFIG_PATH="$config" aplay -L',
            '"$CAMILLADSP_BINARY" --check "$PROFILE/camilladsp-split-bus.yml"',
            '"$CAMILLADSP_BINARY" --check "$rendered"',
            'systemd-analyze verify',
            'SYSTEMD_UNIT_PATH="$unit_dir"',
            'visudo -cf "$rendered"',
            'ExecStart=/bin/true',
        ):
            self.assertIn(marker, self.source)
        for pcm in ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm"):
            self.assertIn(pcm, self.source)

    def test_exact_binary_and_direct_baseline_are_pinned(self) -> None:
        self.assertIn(
            "CAMILLADSP_SHA256=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa",
            self.source,
        )
        self.assertIn(
            "DIRECT_ROUTE_SHA256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9",
            self.source,
        )
        self.assertIn('[[ "$(uname -m)" == aarch64 ]]', self.source)
        self.assertIn("systemctl is-active --quiet", self.source)
        self.assertIn("systemctl is-enabled --quiet", self.source)
        self.assertIn("EQ managed path already exists", self.source)
        self.assertIn("Preflight guard path is unexpectedly present", self.source)

    def test_before_after_state_comparison_is_mandatory(self) -> None:
        for marker in (
            'capture_host_state "$EVIDENCE_ROOT/host-before.tsv"',
            'capture_host_state "$EVIDENCE_ROOT/host-after.tsv"',
            'cmp -s "$EVIDENCE_ROOT/host-before.tsv" "$EVIDENCE_ROOT/host-after.tsv"',
            "route, services, managed paths, loopback and DAC parameters unchanged",
            "EQ_AUDIO_READ_ONLY_PREFLIGHT=PASS",
        ):
            self.assertIn(marker, self.source)
        self.assertIn("/var/tmp/a-clockwork-plex-eq-preflight.XXXXXX", self.source)
        self.assertNotIn('rm -rf "$EVIDENCE_ROOT"', self.source)

    def test_installed_stack_audit_remains_read_only_and_runnable_via_bash(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(AUDIT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        help_result = subprocess.run(
            ["bash", str(AUDIT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("currently installed managed audio path", help_result.stdout)
        self.assertIn('bash "$REPO_ROOT/scripts/audio/verify-audio.sh"', self.audit_source)
        self.assertIn('loopback_proc="/proc/asound/card$loopback_index"', self.audit_source)
        self.assertIn("normal for an I2S/non-USB DAC", self.audit_source)
        self.assertNotRegex(
            self.audit_source,
            re.compile(r"\bsystemctl\s+(?:start|stop|restart|enable|disable|reload)\b"),
        )
        self.assertNotIn("aplay -D", self.audit_source)
        self.assertNotIn("arecord", self.audit_source)

    def test_guarded_dac_probe_queries_constraints_without_starting_playback(self) -> None:
        compile(self.probe_source, str(PROBE), "exec")
        for marker in (
            'DAC_PCM: Final = "hw:CARD=Pro,DEV=0"',
            'FORMATS: Final = ("S16_LE", "S24_LE", "S24_3LE", "S32_LE")',
            'RATES: Final = (44100, 48000, 88200, 96000, 176400, 192000)',
            "snd_pcm_hw_params_test_rate",
            "SND_PCM_ACCESS_RW_INTERLEAVED",
            "wait_dac_closed()",
            "verify_audio(\"before capability probe\")",
            "verify_audio(\"after capability probe\")",
            '"--apply"',
        ):
            self.assertIn(marker, self.probe_source)
        self.assertNotIn("snd_pcm_write", self.probe_source)
        self.assertNotIn("snd_pcm_start", self.probe_source)
        self.assertNotIn("lib.snd_pcm_hw_params(pcm", self.probe_source)
        self.assertIn("APP_STOP_ORDER", self.probe_source)
        self.assertIn("APP_START_ORDER", self.probe_source)
        self.assertIn("activate-direct-failback", self.probe_source)

    def test_hi_res_bus_rehearsal_is_explicit_reversible_and_guarded(self) -> None:
        compile(self.rehearsal_source, str(REHEARSAL), "exec")
        plan = subprocess.run(
            ["python3", str(REHEARSAL), "--rate", "96000"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertIn("Default mode: plan only", plan.stdout)
        self.assertIn("Candidate format: S32_LE", plan.stdout)
        self.assertIn("Candidate rate:   96000", plan.stdout)
        for marker in (
            'CANDIDATE_FORMAT: Final = "S32_LE"',
            "ALLOWED_RATES: Final = (96000, 192000)",
            'STATE_ROOT: Final = Path("/var/lib/a-clockwork-plex/hi-res-rehearsal")',
            "ensure_no_existing_rehearsal()",
            "ensure_accepted_baseline()",
            'verify_audio("before hi-res rehearsal")',
            'activate_split_bus()',
            'HI_RES_REHEARSAL_ACTIVE',
            'HI_RES_REHEARSAL_RESTORED',
            'verify_audio("after hi-res rehearsal restoration")',
            'The candidate remains active until --restore is run.',
            'Rehearsal backup is retained',
            '"durable_backups": True',
            "fsync_directory(path.parent)",
            "atomic_write(BACKUP_ROUTE, original_route, 0o600)",
            "atomic_write(BACKUP_DEFAULTS, original_defaults, 0o600)",
            "Durable split-route backup verification failed.",
            "Durable defaults backup verification failed.",
        ):
            self.assertIn(marker, self.rehearsal_source)
        self.assertNotIn("shutil.copy2(INSTALLED_ROUTE, BACKUP_ROUTE)", self.rehearsal_source)
        self.assertNotIn("shutil.copy2(INSTALLED_DEFAULTS, BACKUP_DEFAULTS)", self.rehearsal_source)
        self.assertIn("original_route_sha256", self.rehearsal_source)
        self.assertIn("original_defaults_sha256", self.rehearsal_source)
        self.assertNotIn("snd_pcm_write", self.rehearsal_source)
        self.assertNotIn("snd_pcm_start", self.rehearsal_source)

    def test_hi_res_rehearsal_recovery_is_checksum_gated_and_preserves_evidence(self) -> None:
        compile(self.recovery_source, str(RECOVERY), "exec")
        help_result = subprocess.run(
            ["python3", str(RECOVERY), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("Checksum-gated recovery", help_result.stdout)
        for marker in (
            'PROFILE_ROUTE: Final = PROFILE_ROOT / "split-bus.conf"',
            'PROFILE_DEFAULTS: Final = PROFILE_ROOT / "a-clockwork-plex-split-bus.defaults"',
            'originals_match_repository',
            'installed_route_known',
            'installed_defaults_known',
            'recovery_permitted',
            'atomic_write(INSTALLED_ROUTE, baseline_route, 0o644)',
            'atomic_write(INSTALLED_DEFAULTS, baseline_defaults, 0o644)',
            'activate_baseline()',
            'verify_audio()',
            'HI_RES_REHEARSAL_RECOVERY=PASS',
            'archive_rehearsal_state()',
        ):
            self.assertIn(marker, self.recovery_source)
        self.assertIn("READ-ONLY unless --apply is supplied", self.recovery_source)
        self.assertIn("Recovery evidence remains", self.recovery_source)
        self.assertNotIn("snd_pcm_write", self.recovery_source)
        self.assertNotIn("snd_pcm_start", self.recovery_source)

    def test_roadmap_keeps_preflight_historical_and_tracks_installed_stack_gate(self) -> None:
        roadmap = ROADMAP.read_text(encoding="utf-8")
        self.assertIn("scripts/audio/preflight-eq.sh", roadmap)
        self.assertIn("old pre-EQ-install gate", roadmap)
        self.assertIn("scripts/audio/verify-audio.sh", roadmap)
        self.assertIn("scripts/audio/audit-hi-res-audio.sh", roadmap)
        self.assertIn("known-good `develop` and `main` rebuild baselines", roadmap)
        self.assertIn("a separate spare SD card is not a project requirement", roadmap)


if __name__ == "__main__":
    unittest.main()
