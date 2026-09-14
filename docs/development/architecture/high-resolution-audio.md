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

The existing `scripts/audio/preflight-eq.sh` remains the first read-only baseline check before the initial audio-path mutation, but later controlled route/format/lifecycle experiments may be performed directly on the development appliance.

## Non-negotiable constraints

- AirPlay behaviour must remain truthful to the received source format and to any resampling actually performed.
- Scheduled-alarm takeover, Maximum Alarm Volume, limiter/safety behaviour and recovery remain non-negotiable.
- The existing logical mixer ownership and Music Master path must not be silently bypassed by an EQ-active hi-res mode.
- EQ-active and native/bypass modes must report what is really reaching the DAC rather than infer it from source metadata.
- Appliance reliability outranks a bit-perfect badge.

## Initial investigation order

1. Capture the current read-only audio baseline with `scripts/audio/preflight-eq.sh` and current diagnostics.
2. Exercise known Plex material at **16/44.1, 24/48, 24/96 and 24/192** and record source, processing and DAC behaviour.
3. Identify the real bottleneck(s): Plexamp output, ALSA virtual devices, CamillaDSP format/rate, mixer/join stages, or DAC constraints.
4. Choose and test a managed higher-resolution processing bus by measured CPU use, latency, stability and alarm/AirPlay compatibility.
5. Define an EQ-active high-resolution contract separately from a measured native/bypass contract.
6. Test source-rate-native Direct Plexamp across **44.1/48/88.2/96/176.4/192 kHz** where the hardware and Plexamp path permit it.
7. Expose source format, processing format and final DAC format/rate separately in diagnostics.
8. Regression-test EQ active/bypass, route/fallback, AirPlay transitions, alarm takeover and recovery before merge.

## Acceptance boundary

This feature does not merge to `develop` on CI alone. Automated checks must be green and the relevant format/rate, alarm, AirPlay, EQ and recovery behaviour must be physically proven on the development appliance.
