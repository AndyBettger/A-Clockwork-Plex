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

The first physical test keeps the original 1024/8192/1024/2048 frame counts unchanged. This is intentional: establish evidence from the failing graph before changing buffer geometry.

## Candidate follow-up if buffer pressure is confirmed

Do **not** adopt this until the unchanged-geometry snapshot has been captured.

A controlled second candidate can scale the high-rate frame counts so their time durations remain approximately comparable with the accepted 44.1 kHz graph. CamillaDSP's documented 192 kHz starting point of 4096 samples is a natural candidate for `chunksize`; ALSA period/buffer and CamillaDSP `target_level` must be considered together rather than changing one value in isolation.

The comparison should retain the same S32_LE / 192 kHz processing/output rate and the same AirPlay source so the principal variable is timing headroom.

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

## Physical test sequence

1. Start from the accepted S16_LE / 44.1 kHz graph and verify it.
2. Activate the existing guarded **S32_LE / 192 kHz** rehearsal without changing its buffer/frame geometry.
3. Start the known AirPlay source that reproduced persistent choppiness.
4. While the fault is audible, run `python3 scripts/audio/snapshot-airplay-hi-res.py` and retain the complete output.
5. Restore the accepted graph with the existing rehearsal `--restore` path and verify the DAC has returned to S16_LE / 44.1 kHz.
6. Only after reviewing that evidence decide whether the next comparison is a time-scaled fixed-192 buffer candidate or a source-rate capture/Controller experiment.

The acceptance boundary remains appliance reliability first: AirPlay must be stable and truthfully described even though high-resolution processing is primarily a Plexamp requirement.
