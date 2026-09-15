# High-resolution audio and EQ architecture

## Status

Implementation is active on `feature/hi-res-audio-eq`, branched from the accepted `develop` head after PR #12 merged on 14 September 2026.

The current managed Plexamp/EQ path still uses a fixed **S16_LE / 44100 Hz** shared music path. The goal of this work is to remove that bottleneck where it is technically safe, while preserving the existing appliance ownership model, alarm takeover, AirPlay behaviour, mixer semantics and reliable recovery.

## Development appliance policy

The bedroom Raspberry Pi is the development/test appliance for this work. A separate spare SD card is **not** required as an acceptance boundary.

Recovery/safety comes from repository state and controlled checkpoints:

- all hi-res/EQ work stays on `feature/hi-res-audio-eq` until physically accepted;
- `develop` remains the accepted integration rollback point;
- `main` remains the supported stable rebuild baseline;
- commit before materially risky route/lifecycle changes so the appliance can be returned to a known-good repository state;
- keep current configuration backups where a test could deliberately disturb user-owned settings;
- do not make bit-perfect/native/high-resolution claims until ALSA/DAC state has been measured on the real appliance.

The historical `scripts/audio/preflight-eq.sh` is **not** the baseline tool for this phase. It is the old pre-EQ-install gate and deliberately expects the managed EQ files to be absent and the previous direct route to be active. Running it against the commissioned managed-EQ installation would therefore fail by design.

For this phase the baseline is:

- `scripts/audio/verify-audio.sh` — verifies the currently installed managed EQ/split-bus contract; and
- `scripts/audio/audit-hi-res-audio.sh` — a read-only audit that reports the current installed format/rate settings, ALSA card/PCM state, available DAC descriptors, live hw_params, route/EQ status and CamillaDSP process/service state without opening a PCM or mutating the appliance.

## Physically captured baseline — 14 September 2026

The first commissioned-appliance baseline was captured on `feature/hi-res-audio-eq` head `d723b8c44e17b1cca5a97f2a4d697101238b9703` on the Raspberry Pi 5 bedroom test appliance.

- `bash scripts/audio/verify-audio.sh` passed the installed EQ-capable contract before any mutation.
- The physical DAC is ALSA card **Pro**, `RPi_DAC_Pro`, device 0 (`Raspberry Pi DAC Pro HiFi pcm512x-hifi-0`).
- The live DAC `hw_params` were **S16_LE, 2 channels, 44100 Hz**, with `period_size=512` and `buffer_size=4096`.
- The active ACP split route is SHA-256 `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` and fixes its four-channel loopback `dmix` slave to **S16_LE / 44100 Hz**.
- The installed profile independently fixes `SAMPLE_RATE=44100` and `FORMAT=S16_LE`.
- The live CamillaDSP configuration independently fixes capture and playback to **S16_LE / 44100 Hz**; capture is four channels from `hw:7,1,0`, playback is stereo to `hw:CARD=Pro,DEV=0`.
- Route state was healthy `split-bus-active`; Plexamp, Shairport Sync, dashboard, route and CamillaDSP services were active, with the failback service correctly inactive/static.
- Managed EQ was active with Bass **+2 dB**, Mid **0 dB**, Treble **+2 dB**, permanent music reserve **-6.5 dB** and final limiter **-1 dB**.
- CamillaDSP was using approximately **0.6% CPU** during the snapshot. That is a useful 44.1 kHz baseline, not evidence that every higher rate will be stable.

Two audit-tool assumptions were also corrected from this physical run:

1. repository shell scripts are intentionally invoked with `bash`, so the audit must not require `verify-audio.sh` itself to have an executable bit before calling it; and
2. the configured snd-aloop id is `ACP_Loopback`, while the kernel card short name is `ACPLoopback`; the reliable procfs path for the accepted index is `/proc/asound/card7` rather than `/proc/asound/ACP_Loopback`.

The Raspberry Pi DAC Pro is an **I2S** device, so `/proc/asound/Pro/stream0` is not exposed. That USB-style procfs descriptor therefore cannot be used to infer its format/rate limits. Exact hardware capability must be measured while the DAC is temporarily idle.

`scripts/audio/probe-hi-res-dac.py` implements that bounded gate. Its default invocation is plan-only. `--apply` first verifies the healthy split bus, snapshots the application/CamillaDSP service state, deliberately stops dashboard → AirPlay → Plexamp → CamillaDSP, waits for the DAC to report `closed`, opens `hw:CARD=Pro,DEV=0` non-blocking, and queries exact stereo `RW_INTERLEAVED` constraints for **S16_LE, S24_LE, S24_3LE and S32_LE** at **44.1/48/88.2/96/176.4/192 kHz**. It never calls the ALSA operation that applies hw_params and never starts/writes a playback stream. It then closes the PCM, restores CamillaDSP → Plexamp → AirPlay → dashboard, and re-runs the managed audio verifier. If CamillaDSP cannot return, it attempts the already accepted managed Direct failback and reports the probe as failed rather than pretending the original graph was restored.

### Physical DAC capability result — 14 September 2026

The guarded probe was physically run on head `b910bdeb82b004c516c6631a9cfd42d0a8e68aca`. The corrected installed-stack audit first passed its own managed audio verifier and confirmed the live split bus remained healthy. The plan-only probe made no changes; the explicit `--apply` run then quiesced the four managed services, reached an idle DAC, queried the exact hardware constraints and restored the original graph successfully.

| ALSA format | 44.1 kHz | 48 kHz | 88.2 kHz | 96 kHz | 176.4 kHz | 192 kHz |
| --- | --- | --- | --- | --- | --- | --- |
| `S16_LE` | accepted | accepted | accepted | accepted | accepted | accepted |
| `S24_LE` | accepted | accepted | accepted | accepted | accepted | accepted |
| `S24_3LE` | rejected | rejected | rejected | rejected | rejected | rejected |
| `S32_LE` | accepted | accepted | accepted | accepted | accepted | accepted |

After the query the probe restarted CamillaDSP → Plexamp → AirPlay → dashboard, `verify-audio.sh` passed again, and route state returned to **`split-bus-active` / `split-bus-selected`** with the split route still selected and Direct failback unused. The bounded quiesce/query/restore transaction is therefore physically proven on this appliance.

This closes the hardware-format discovery gate but does **not** yet prove sustained playback, clock stability, bit-perfect behaviour or low-load operation at every accepted rate. It proves that the Raspberry Pi DAC Pro ALSA hardware PCM/driver accepts exact stereo `RW_INTERLEAVED` constraints for `S16_LE`, `S24_LE` and `S32_LE` through 192 kHz. The current 16/44.1 ceiling is therefore in the managed software graph rather than an exposed DAC hardware-format/rate limit.

For the first managed high-resolution processing experiment, **`S32_LE` is the cleanest format candidate**: the DAC accepted it at every target rate, it can carry 24-bit programme precision without packed-24 handling, and the current CamillaDSP configuration model can use the same `S32_LE` spelling as ALSA. `S24_LE` remains a hardware-capable option, but CamillaDSP's ALSA backend names ALSA's padded `S24_LE` representation differently, so the current single `FORMAT` setting must not be changed to `S24_LE` blindly. This is a candidate-selection observation, not yet the final production format decision.

## Known-source playback baseline — 15 September 2026

The current fixed managed graph was exercised with known Plex material at **16/44.1, 24/48, 24/96 and 24/192** while capturing Plexamp Headless's own log plus the live ACP loopback, CamillaDSP capture and physical-DAC `hw_params`.

Plexamp's allow-listed preferences remained `sampleRateMatching = 0`, `sampleRateConversionQuality = 2` and `loudnessLeveling = false`. Plexamp Headless writes the useful BASS/mixer negotiation to `~/.cache/Plexamp/log/Plexamp.log`, not the systemd journal.

| Known source | Plexamp pipeline / mixer / source stream | Device 9 (`A Clockwork Plex - Plexamp`) | ACP loopback → Camilla → DAC |
| --- | --- | --- | --- |
| **16-bit / 44.1 kHz** | 44.1 kHz / 44.1 kHz / 44.1 kHz | no fresh open line was captured in that snapshot; the 44.1 kHz control case was already active | **S16_LE / 44.1 kHz** throughout |
| **24-bit / 48 kHz** | 48 kHz / 48 kHz / 48 kHz | opened **44.1 kHz**, `preferred was 48000, best was 48000` | **S16_LE / 44.1 kHz** throughout |
| **24-bit / 96 kHz** | 96 kHz / 96 kHz / 96 kHz | opened **44.1 kHz**, `preferred was 96000, best was 96000` | **S16_LE / 44.1 kHz** throughout |
| **24-bit / 192 kHz** | 192 kHz / 192 kHz / 192 kHz | opened **44.1 kHz**, `preferred was 192000, best was 192000` | **S16_LE / 44.1 kHz** throughout |

The 48/96/192 cases all direct-played and show the same architecture: Plexamp keeps the source rate through its decoder/source stream and internal mixer and explicitly prefers that source rate for the managed output device, but the ACP device opens at 44.1 kHz. The downstream loopback, CamillaDSP capture and physical DAC are then all forced to **S16_LE / 44.1 kHz** by the current `acp_dmix` slave.

That completes the source-rate baseline and localises the current rate bottleneck to the **managed ACP output-device chain**, not to Plexamp's decoder or internal mixer. It also confirms the current managed graph reduces the known 24-bit sources to an exposed **S16_LE** bus before CamillaDSP. The exact converter implementation at the negotiation boundary — BASS output conversion, ALSA `plug`, or cooperation between them — is secondary to the appliance contract: the fixed ACP `S16_LE / 44100` slave is the constraint that forces both the output rate and exposed downstream sample format.

CamillaDSP remained approximately **0.6–0.7% CPU** during these 44.1 kHz baseline snapshots. That is only the accepted low-rate reference; the candidate 96/192 kHz graphs must be measured separately.

`sampleRateMatching = 0` does not prevent Plexamp from constructing and preferring source-rate 48/96/192 kHz pipelines. Its eventual production setting therefore remains part of the later native/bypass investigation rather than a prerequisite for removing the EQ-active managed-device ceiling.

The configured split-bus `PERIOD_SIZE=1024` / `BUFFER_SIZE=8192` and the observed physical DAC `512` / `4096` values describe different points in the current graph; that difference is recorded rather than treated as an error until the higher-resolution topology is measured.

## First reversible managed-bus rehearsal

`scripts/audio/rehearse-hi-res-bus.py` is the bounded bridge between the completed observation phase and the first actual high-resolution graph test. It deliberately does **not** change the repository profile or claim a production format/rate.

The tool supports only two first-pass candidates: **S32_LE / 96 kHz** and **S32_LE / 192 kHz**. Its default invocation is plan-only. An explicit root `--apply --rate 96000|192000` requires the exact accepted repository/installed **S16_LE / 44100** split-route and defaults, runs the normal managed verifier, saves checksum-protected copies of those installed files under `/var/lib/a-clockwork-plex/hi-res-rehearsal/`, stages only the candidate split-route/default values, and then delegates the real service/route transition to the already accepted installed `a-clockwork-plex-audio-route activate-split-bus` owner. That owner regenerates CamillaDSP from the persisted EQ state, quiesces/restarts the application services in the established order and retains Direct failback behaviour if candidate activation fails.

A successful candidate is intentionally left active for a deliberate playback test. `--snapshot` is read-only and is intended to be run as the normal project user while the matching known Plex source is playing; it prints the recent Plexamp negotiation, live loopback/Camilla/DAC `hw_params`, route state and CamillaDSP CPU. `--restore` is then run as root to restore the exact saved route/defaults, reactivate the normal split bus and require `verify-audio.sh` to pass before the rehearsal state is removed. If restoration cannot be fully verified, the backup is retained rather than erased.

The rehearsal is therefore a temporary development state, not a supported installed profile. Do not run `setup.sh`, repair/convergence, or unrelated audio mutation while a rehearsal state is active. The first 96 kHz rehearsal should be completed and restored before starting the 192 kHz rehearsal.

## Non-negotiable constraints

- AirPlay behaviour must remain truthful to the received source format and to any resampling actually performed.
- Scheduled-alarm takeover, Maximum Alarm Volume, limiter/safety behaviour and recovery remain non-negotiable.
- The existing logical mixer ownership and Music Master path must not be silently bypassed by an EQ-active hi-res mode.
- EQ-active and native/bypass modes must report what is really reaching the DAC rather than infer it from source metadata.
- Appliance reliability outranks a bit-perfect badge.

## Initial investigation order

1. **Complete:** capture the current read-only installed-stack baseline with `scripts/audio/verify-audio.sh` and `scripts/audio/audit-hi-res-audio.sh`.
2. **Complete:** measure the idle physical DAC's exact accepted format/rate combinations with `python3 scripts/audio/probe-hi-res-dac.py --apply`; `S16_LE`, `S24_LE` and `S32_LE` were accepted at every tested rate through 192 kHz, `S24_3LE` was rejected, and the original split bus restored cleanly.
3. **Complete:** exercise known Plex material at **16/44.1, 24/48, 24/96 and 24/192**. Plexamp remains source-rate internally and prefers 48/96/192 kHz for the managed device, but the current ACP PCM opens at 44.1 kHz and the downstream graph is always S16_LE/44.1.
4. **Located:** the current fixed ACP output-device chain is the rate/sample-format bottleneck; the decoder/internal Plexamp mixer is not.
5. **Next physical gate:** use the guarded rehearsal tool to compare **S32_LE / 96 kHz** and **S32_LE / 192 kHz** with matching Plex material, measuring Plexamp device-open rate, loopback/Camilla/DAC format/rate and CamillaDSP CPU. Restore the accepted baseline after each candidate.
6. After one candidate survives basic Plex playback, extend that candidate's physical gate to EQ changes/bypass, AirPlay, alarm preview/scheduled takeover, mixer controls, latency and recovery before selecting a managed production bus.
7. Define an EQ-active high-resolution contract separately from a measured native/bypass contract.
8. Test source-rate-native Direct Plexamp across **44.1/48/88.2/96/176.4/192 kHz** where the hardware and Plexamp path permit it.
9. Expose source format, processing format and final DAC format/rate separately in diagnostics.
10. Regression-test EQ active/bypass, route/fallback, AirPlay transitions, alarm takeover and recovery before merge.

## Acceptance boundary

This feature does not merge to `develop` on CI alone. Automated checks must be green and the relevant format/rate, alarm, AirPlay, EQ and recovery behaviour must be physically proven on the development appliance.
