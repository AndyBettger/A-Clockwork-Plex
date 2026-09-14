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

`scripts/audio/probe-hi-res-dac.py` implements that next bounded gate. Its default invocation is plan-only. `--apply` first verifies the healthy split bus, snapshots the application/CamillaDSP service state, deliberately stops dashboard → AirPlay → Plexamp → CamillaDSP, waits for the DAC to report `closed`, opens `hw:CARD=Pro,DEV=0` non-blocking, and queries exact stereo `RW_INTERLEAVED` constraints for **S16_LE, S24_LE, S24_3LE and S32_LE** at **44.1/48/88.2/96/176.4/192 kHz**. It never calls the ALSA operation that applies hw_params and never starts/writes a playback stream. It then closes the PCM, restores CamillaDSP → Plexamp → AirPlay → dashboard, and re-runs the managed audio verifier. If CamillaDSP cannot return, it attempts the already accepted managed Direct failback and reports the probe as failed rather than pretending the original graph was restored.

The configured split-bus `PERIOD_SIZE=1024` / `BUFFER_SIZE=8192` and the observed physical DAC `512` / `4096` values describe different points in the current graph; that difference is recorded rather than treated as an error until the higher-resolution topology is measured.

## Non-negotiable constraints

- AirPlay behaviour must remain truthful to the received source format and to any resampling actually performed.
- Scheduled-alarm takeover, Maximum Alarm Volume, limiter/safety behaviour and recovery remain non-negotiable.
- The existing logical mixer ownership and Music Master path must not be silently bypassed by an EQ-active hi-res mode.
- EQ-active and native/bypass modes must report what is really reaching the DAC rather than infer it from source metadata.
- Appliance reliability outranks a bit-perfect badge.

## Initial investigation order

1. **Complete:** capture the current read-only installed-stack baseline with `scripts/audio/verify-audio.sh` and `scripts/audio/audit-hi-res-audio.sh`.
2. **Ready for physical run:** measure the idle physical DAC's exact accepted format/rate combinations with `python3 scripts/audio/probe-hi-res-dac.py --apply` using the guarded quiesce → query → restore transaction above.
3. Exercise known Plex material at **16/44.1, 24/48, 24/96 and 24/192** and record source, processing and DAC behaviour.
4. Identify the remaining bottleneck(s): Plexamp output, ALSA virtual devices, CamillaDSP format/rate, mixer/join stages, or DAC constraints.
5. Choose and test a managed higher-resolution processing bus by measured CPU use, latency, stability and alarm/AirPlay compatibility.
6. Define an EQ-active high-resolution contract separately from a measured native/bypass contract.
7. Test source-rate-native Direct Plexamp across **44.1/48/88.2/96/176.4/192 kHz** where the hardware and Plexamp path permit it.
8. Expose source format, processing format and final DAC format/rate separately in diagnostics.
9. Regression-test EQ active/bypass, route/fallback, AirPlay transitions, alarm takeover and recovery before merge.

## Acceptance boundary

This feature does not merge to `develop` on CI alone. Automated checks must be green and the relevant format/rate, alarm, AirPlay, EQ and recovery behaviour must be physically proven on the development appliance.
