# AirPlay 192 kHz buffer/timing investigation

**Status:** active physical investigation on `feature/hi-res-audio-eq`  
**Started:** 16 September 2026

This note records the bounded investigation that follows the first wider-gate AirPlay result for the provisional **S32_LE / 192 kHz** managed bus.

## Observed behaviour

The fixed 192 kHz managed rehearsal is physically healthy for local Plexamp playback, including matching 24/192 material and lower-rate Plex material. AirPlay/Shairport Sync can acquire the managed music path at 192 kHz, but the commissioned test produced persistent choppy playback.

The current AirPlay path does **not** use PipeWire after Shairport. The installed contract is:

```text
AirPlay sender
    -> Shairport Sync
    -> ALSA output_device = acp_airplay
    -> ALSA plug / AirPlay softvol / Music Master
    -> acp_dmix fixed managed bus
    -> ALSA loopback
    -> CamillaDSP
    -> Raspberry Pi DAC Pro
```

During the guarded 192 kHz rehearsal, `acp_dmix`, the loopback, CamillaDSP and the DAC are moved to **S32_LE / 192000 Hz**. The ALSA `plug` PCM in front of the managed bus therefore owns any source-format/rate adaptation needed by Shairport before the fixed 192 kHz dmix boundary.

## Primary hypothesis: frame counts were raised in rate but not in time

The first rehearsal deliberately changed only sample format/rate. It retained the accepted 44.1 kHz frame-count geometry:

| Setting | Frames | At 44.1 kHz | At 192 kHz |
| --- | ---: | ---: | ---: |
| ALSA `period_size` | 1024 | ~23.220 ms | ~5.333 ms |
| ALSA `buffer_size` | 8192 | ~185.760 ms | ~42.667 ms |
| CamillaDSP `chunksize` | 1024 | ~23.220 ms | ~5.333 ms |
| CamillaDSP `target_level` | 2048 | ~46.440 ms | ~10.667 ms |
| CamillaDSP one-queue limit (`chunksize * queuelimit`, q=4) | 4096 | ~92.880 ms | ~21.333 ms |

That is a useful first suspect because local Plexamp has no network sender clock, while AirPlay adds sender/network timing and Shairport's synchronization behaviour ahead of the ALSA conversion boundary.

CamillaDSP 4.1 documentation recommends a starting `chunksize` of **4096** at 176.4/192 kHz, specifically keeping the chunk duration around 22 ms; it also warns that shorter chunks are more vulnerable to system disruption and buffer underruns. The production decision must still be based on this appliance's measured behaviour rather than adopting a documentation example blindly.

## Read-only evidence helper

`scripts/audio/snapshot-airplay-hi-res.py` is the dedicated read-only snapshot for this test. It does not open a PCM or mutate services, routes, mixers or configuration. While the guarded 192 kHz rehearsal and a choppy AirPlay stream are active it reports:

- active rehearsal state;
- configured ALSA/CamillaDSP frame counts converted to milliseconds at the active rate and, for comparison, at 44.1 kHz;
- live ACP loopback, CamillaDSP-capture and physical-DAC `hw_params`;
- a bounded allow-list of Shairport output/timing configuration keys;
- CamillaDSP samplerate/chunksize/queue/target/rate-adjust/resampler settings;
- Shairport/CamillaDSP process/service state; and
- recent journal lines limited to timing, buffer, resync, ALSA, rate, underrun/overrun and error-related terms. IPv4 and MAC addresses are redacted from those journal lines.

The first physical test kept the original 1024/8192/1024/2048 frame counts unchanged. This was intentional: establish evidence from the failing graph before changing buffer geometry.

## Physical unchanged-geometry capture — CONFIRMED, 29 September 2026

The commissioned bedroom Pi repeated the exact fixed **S32_LE / 192 kHz** rehearsal on branch head `9708da39f09658ca6d232b2903edf0f9a8725a2c`. The accepted 44.1 kHz verifier passed before apply, the candidate activated cleanly, and the same AirPlay source reproduced the choppy playback.

The read-only snapshot established:

- configured geometry remained ALSA **1024 / 8192** and CamillaDSP **chunksize 1024 / target_level 2048**, giving only ~5.33 ms chunks and ~10.67 ms target level at 192 kHz;
- the live ACP dmix/loopback was **S32_LE / 192000 / 4 channels / period 1024 / buffer 8192**;
- CamillaDSP capture and physical DAC playback were both **S32_LE / 192000**, but ALSA exposed **period 512 / buffer 4096** at those endpoints — about 2.67 ms and 21.33 ms respectively;
- CamillaDSP had `enable_rate_adjust=true`, `adjust_period=1`, no explicit `capture_samplerate`, and `resampler=null`;
- CamillaDSP was only about **2.9% CPU**, so the fault is not explained by simple processor saturation;
- the CamillaDSP journal repeatedly recorded **playback buffer underruns**, **capture read overruns**, **capture stalled / processing stalled**, and later direct playback write underruns while the audible fault was present;
- the bounded Shairport journal did not expose a corresponding stream/timing error in this capture; and
- normal `--restore` returned the exact accepted **S16_LE / 44100 Hz** graph and both the internal and independent verifier passes succeeded.

This is strong evidence that the original fixed-192 graph has inadequate time-domain buffering/scheduling headroom. It does not yet prove that buffering is the only AirPlay issue, but it is sufficient to justify the controlled buffer comparison before adding Controller-driven dynamic topology.

## Active follow-up: time-scaled fixed-192 candidate

The second candidate keeps **S32_LE / 192 kHz**, the same source routing, the same EQ/mixer graph, `queuelimit=4`, rate-adjust policy and AirPlay source. Only the frame geometry is increased as one timing-headroom experiment:

| Setting | Unchanged 192 candidate | Time-scaled 192 candidate | Candidate duration |
| --- | ---: | ---: | ---: |
| ALSA `period_size` | 1024 | **4096** | ~21.33 ms |
| ALSA `buffer_size` | 8192 | **32768** | ~170.67 ms |
| CamillaDSP `chunksize` | 1024 | **4096** | ~21.33 ms |
| CamillaDSP `target_level` | 2048 | **8192** | ~42.67 ms |

These are deliberately power-of-two values close to the accepted 44.1 kHz graph's time durations. CamillaDSP's documented 176.4/192 kHz starting point is 4096 samples (~22 ms), while the accepted ACP graph historically used a target level of two chunks; the candidate preserves that two-chunk target relationship rather than changing queue policy independently.

The rehearsal tool exposes this only through the explicit `--timing-profile time-scaled` option. Its default `unchanged` profile preserves the already-measured experiment, and the normal exact-backup/restore contract is unchanged.

## CamillaDSP Controller candidate — deferred until the fixed graph is understood

The current CamillaDSP Controller has direct relevance to the longer-term architecture. On Linux it can monitor an ALSA device for sample-rate/format changes. Its Adapt provider can keep a resampling base configuration and update `capture_samplerate` to the newly detected input rate, while also adapting capture format when configured.

That makes the following architecture a credible later candidate if a single fixed-rate ALSA front end remains fragile:

```text
Shairport / Plexamp source-rate stream
    -> ALSA loopback exposes actual source rate
    -> CamillaDSP Controller detects rate/format
    -> CamillaDSP capture_samplerate follows source
    -> asynchronous SRC + rate adjustment
    -> fixed S32_LE / 192 kHz processing/output
    -> DAC
```

It is deliberately **not** the first response to the choppy AirPlay result. A fixed processing graph has fewer lifecycle transitions and is preferable for an appliance if adequate buffering makes it stable.

## Rejected/low-priority alternative: parallel CamillaDSP instances

Running several preconfigured CamillaDSP capture paths/instances for different AirPlay rates is technically possible to construct, but it duplicates routing/lifecycle ownership, makes shared EQ/volume state harder to keep atomic, and solves a format-negotiation problem in a layer that ALSA plus the Controller are already designed to handle. Keep this only as an architectural fallback, not an implementation target.

## Next physical test sequence

1. Start from the accepted S16_LE / 44.1 kHz graph and verify it.
2. Activate **S32_LE / 192 kHz + time-scaled timing geometry** with `sudo python3 scripts/audio/rehearse-hi-res-bus.py --apply --rate 192000 --timing-profile time-scaled`.
3. Start the same AirPlay source that reproduced persistent choppiness and listen for at least several minutes.
4. While AirPlay is active, run `python3 scripts/audio/snapshot-airplay-hi-res.py` and retain the complete output whether playback is good or bad.
5. Restore with `sudo python3 scripts/audio/rehearse-hi-res-bus.py --restore` and independently re-run `bash scripts/audio/verify-audio.sh`.
6. Compare audible stability, live `hw_params` and CamillaDSP underrun/overrun/stall journal evidence with the unchanged-geometry capture.
7. Only if the scaled fixed graph remains unsuitable move to source-rate capture plus CamillaDSP Controller/async-SRC architecture.

The acceptance boundary remains appliance reliability first: AirPlay must be stable and truthfully described even though high-resolution processing is primarily a Plexamp requirement.
