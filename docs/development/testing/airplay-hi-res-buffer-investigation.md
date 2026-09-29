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

## Time-scaled fixed-192 candidate — PHYSICALLY PASSED, 29 September 2026

The second candidate keeps **S32_LE / 192 kHz**, the same source routing, the same EQ/mixer graph, `queuelimit=4`, rate-adjust policy and AirPlay source. Only the frame geometry is increased as one timing-headroom experiment:

| Setting | Unchanged 192 candidate | Time-scaled 192 candidate | Candidate duration |
| --- | ---: | ---: | ---: |
| ALSA `period_size` | 1024 | **4096** | ~21.33 ms |
| ALSA `buffer_size` | 8192 | **32768** | ~170.67 ms |
| CamillaDSP `chunksize` | 1024 | **4096** | ~21.33 ms |
| CamillaDSP `target_level` | 2048 | **8192** | ~42.67 ms |

These are deliberately power-of-two values close to the accepted 44.1 kHz graph's time durations. CamillaDSP's documented 176.4/192 kHz starting point is 4096 samples (~22 ms), while the accepted ACP graph historically used a target level of two chunks; the candidate preserves that two-chunk target relationship rather than changing queue policy independently.

The rehearsal tool exposes this only through the explicit `--timing-profile time-scaled` option. Its default `unchanged` profile preserves the already-measured experiment, and the normal exact-backup/restore contract is unchanged.

The commissioned Pi then ran this exact time-scaled candidate on branch head `cf705b914c4028facea42e7ce82d76f88ef59efc`. The same audiobook opening/theme section that made the original fault easy to hear was played twice for roughly one to two minutes per pass. Both passes were subjectively clean with **no audible choppiness**.

The objective evidence matched that listening result:

- the candidate activated as **S32_LE / 192000 Hz** with configured ALSA **period 4096 / buffer 32768** and CamillaDSP **chunksize 4096 / target_level 8192**;
- live ACP dmix used **4096 / 32768**, while CamillaDSP capture and physical DAC playback settled at **2048 / 16384** at 192 kHz;
- two read-only snapshots, including a later snapshot with the same CamillaDSP process at roughly **207 seconds** elapsed, showed no playback underrun, capture overrun, stalled-processing or write-underrun messages;
- CamillaDSP CPU was approximately **1.9%**, comfortably below any processor-saturation concern; and
- exact restore returned the accepted **S16_LE / 44100 Hz** graph, with both the restore-time verifier and a separate independent verifier succeeding.

The A/B evidence therefore supports the original diagnosis: the choppy AirPlay behaviour was caused by inadequate high-rate time-domain buffering/scheduling headroom in the unchanged-frame 192 kHz graph. The fixed-192 architecture remains viable and now advances to the broader functional/stability gate using the time-scaled geometry. These values are still a physically proven candidate rather than the production profile until that wider gate is complete.

## Plex source-rate matrix on the time-scaled fixed-192 graph — PASSED, 29 September 2026

The same physically stable time-scaled candidate was then exercised with the known Plex matrix: **16/44.1, 24/48, 24/96 and 24/192**. All four sources played correctly while the managed bus, CamillaDSP capture and physical DAC remained fixed at **S32_LE / 192000 Hz**.

The Plexamp negotiation evidence shows the intended fixed-processing-domain behaviour:

| Known source | Plexamp source/mixer evidence | Managed output-device evidence | Downstream graph |
| --- | --- | --- | --- |
| **16/44.1** | pipeline/mixer/source stream at **44.1 kHz** | Device 9 was already open at 192 kHz from the prior 192 kHz stream, so no fresh reopen line was emitted | loopback → CamillaDSP → DAC remained **S32_LE / 192 kHz** |
| **24/48** | pipeline/mixer/source stream at **48 kHz** | Device 9 opened **192 kHz**, while Plexamp reported preferred/best **48 kHz** | loopback → CamillaDSP → DAC remained **S32_LE / 192 kHz** |
| **24/96** | pipeline/mixer/source stream at **96 kHz** | Device 9 opened **192 kHz**, while Plexamp reported preferred/best **96 kHz** | loopback → CamillaDSP → DAC remained **S32_LE / 192 kHz** |
| **24/192** | pipeline/mixer/source stream at **192 kHz** | Device 9 opened **192 kHz**, preferred/best **192 kHz** | loopback → CamillaDSP → DAC remained **S32_LE / 192 kHz** |

The 44.1 kHz case is not evidence of an unobserved 44.1→192 conversion location by itself because Device 9 was already open at 192 kHz before the track change. Taken together with the fresh 48/96/192 opens and the fixed live downstream state, however, the appliance contract is clear: **Plexamp can keep source-rate decoding/mixing while the ACP managed output remains a fixed 192 kHz processing domain**. The exact implementation boundary performing rate conversion remains intentionally unspecified; it may involve BASS output conversion, ALSA `plug`, or cooperation between them.

CamillaDSP stayed around **1.7–1.8% CPU** during the four-source pass, the same process remained active across the matrix, and exact restore again returned the accepted **S16_LE / 44.1 kHz** graph with both restore-time and independent verifier success.

This closes the lower-rate Plex/resampling-truthfulness part of the wider fixed-192 gate. The truthful product wording for EQ-active playback is therefore **fixed 192 kHz processing/output**, not “native 192 kHz” for lower-rate sources.

## CamillaDSP Controller candidate — deferred fallback

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

The time-scaled fixed graph has now made AirPlay stable in the bounded physical comparison, so Controller-driven dynamic topology is **not currently required**. Retain it as the next architecture fallback only if the wider fixed-192 gate later exposes source-rate, clocking or long-run behaviour that the fixed graph cannot handle cleanly.

## Rejected/low-priority alternative: parallel CamillaDSP instances

Running several preconfigured CamillaDSP capture paths/instances for different AirPlay rates is technically possible to construct, but it duplicates routing/lifecycle ownership, makes shared EQ/volume state harder to keep atomic, and solves a format-negotiation problem in a layer that ALSA plus the Controller are already designed to handle. Keep this only as an architectural fallback, not an implementation target.

## Next physical gate

The fixed **S32_LE / 192 kHz** graph is now the installed production profile. The remaining gate is production resilience/diagnostic closure rather than another candidate-topology experiment.

1. Re-enter the time-scaled 192 kHz rehearsal from the accepted baseline.
2. **Complete:** known Plex **16/44.1, 24/48, 24/96 and 24/192** sources all played correctly; Plexamp retained source-rate pipeline/mixer behaviour while the managed device/downstream graph stayed fixed at S32_LE/192 kHz.
3. **Plexamp side complete:** Bass changes were audibly effective, Music Master and Plexamp trim behaved correctly, CamillaDSP retained the same PID and the 192 kHz graph stayed clean. The pass also exposed and prompted correction of stale mixer API sample-rate metadata.
4. **AirPlay-side partial pass / source-volume fault found, 29 September 2026:** EQ was audibly effective, Music Master and AirPlay trim behaved correctly, and the graph stayed S32_LE/192 kHz. The main AirPlay sender-volume slider had no audible effect and the configured starting volume was not applied reliably on reconnect, forcing the sender volume to be raised on the iPhone. The same run physically proved the mixer diagnostic-rate fix (44.1 kHz baseline → 192 kHz candidate → 44.1 kHz restore). It also logged two isolated CamillaDSP playback-buffer underrun recoveries during the longer reconnect/control exercise, so the AirPlay stability gate remains open.
5. **Native RemoteControl follow-up exposed two distinct issues:** native `AirplayVolume` readback is working and truthfully reported **-20 dB / 33% sender level**, but the configured **100%** starting-volume write remained unconfirmed and the sender stayed at -20 dB. Separately, moving the main ACP AirPlay slider to a value that maps to a negative dB caused `/usr/bin/busctl: invalid option` because the command did not protect the negative positional argument from option parsing. The command now inserts the required `--` before the D-Bus destination, with regression coverage.
6. **Capability result:** the corrected native slider was tested at the accepted 44.1 kHz baseline and is still ignored by the established iPhone/AirPlay 2 session. Moving the ACP slider low or high caused no audible change, no visible iPhone volume movement and no change from `AirplayVolume = -20 dB`. After a genuine disconnect/reconnect, a delayed direct `SetAirplayVolume d 0.0` command also completed locally but the native readback stayed at -20 dB. Receiver-originated sender-volume control is therefore not a usable production capability on this AirPlay 2 path; the failed starting-volume feature is not merely firing too early.
7. **Design selected / software implemented:** ACP now owns AirPlay volume locally. Shairport is rendered with `ignore_volume_control = "yes"`; the sender's `pvol` remains readable metadata but no longer attenuates the audio path. A new runtime-only `A Clockwork AirPlay Live` softvol sits before the existing persistent AirPlay Trim and Music Master. The visible AirPlay fader writes this local control, while the Start knob/starting-volume setting, sender-scale conversion and `SetAirplayVolume` command path are removed. The live stage is excluded from portable mixer backup/reset ownership.
8. **First 44.1 kHz deployment attempt failed safely before acceptance:** the guarded EQ repair was invoked with the already-installed verified CamillaDSP binary as its source. GNU `install` rejected source and destination as the same file, the repair reported `file repair failed`, and its transaction restored the previous installed state. The installer now detects/reuses that exact managed binary instead of self-copying. Review also confirmed the pinned Direct/failback route intentionally remains the exact physically proven alarm-safe profile; receiver-owned AirPlay live-fader parity in Direct is therefore deferred to its own explicit physical gate rather than silently changing the rollback reference.
9. **44.1 kHz receiver-owned functional pass — PASSED:** the hardened repair completed, the helper exposed `airplay_live` as an available PCM/control, the Shairport config installed `ignore_volume_control = "yes"`, and the normal audio verifier passed. Playback begun with the iPhone at a very low sender volume was heard at ACP's local level. AirPlay Live, AirPlay Trim, Music Master and EQ all worked audibly; moving the iPhone slider changed `pvol` metadata over the full range but did not alter audible level; reconnecting did not change local level; and Starting volume UI/settings were gone. The helper reports AirPlay Live/Trim, Plexamp Trim and Music Master on the same `perceptual-amplitude` scale, confirming the former AirPlay sender-specific scale conversion has been retired. Plexamp's main live fader remains a native Plexamp player-volume command, so identical dB law at equal numeric percentages is not assumed.
10. **44.1 kHz journal result — audible pass, diagnostic warning:** the receiver-owned path sounded clean and Shairport's filtered journal was empty, but CamillaDSP logged repeated playback-buffer underrun recoveries and one capture overrun/Broken pipe/stall sequence during the control/reconnect exercise. The final verifier still passed. Keep the 44.1 kHz stability gate open until a steadier-state capture distinguishes transition-induced recovery from continuous-playback XRUNs.
11. **Receiver-owned time-scaled 192 wider run — FAILED:** functionality remained correct, but the audiobook became audibly skippy. After candidate activation the new CamillaDSP PID repeatedly logged playback-buffer underruns over several minutes. The graph remained S32_LE/192 kHz with managed ALSA 4096/32768, CamillaDSP 4096 chunksize / 8192 target, DAC/capture 2048/16384 and only ~2.1% CPU. Exact restore returned S16_LE/44.1 and verifier success.
12. **High-target bounded classification run — CLEAN STABILITY/CONTROL PASS:** the exact `time-scaled-high-target` candidate was repeated with no geometry change. Activation, a one-minute idle interval, AirPlay startup, five minutes of untouched steady playback and the subsequent EQ/volume/trim-control exercise were each bounded separately. Playback was subjectively clean throughout, including startup and the full steady window. Every phase-specific filter was empty. The final snapshot confirmed S32_LE/192 kHz, ACP dmix 4096/32768, capture/DAC 2048/16384, chunksize 4096, `target_level=12288`, rate adjustment enabled, ~2.0% CamillaDSP CPU, and **no matching timing/buffer/error lines** in either Shairport or CamillaDSP over the ten-minute snapshot window. Exact restore returned S16_LE/44.1 and verifier success.
13. **AirPlay disconnect/reconnect sub-gate — PASSED:** on the same 12288-target S32_LE/192 kHz candidate, one deliberate disconnect/reconnect preserved receiver-owned AirPlay Live level and the expected EQ/Trim/Music Master behaviour with no audible chop. The bounded reconnect journal filter produced no underrun/overrun/stall/xrun/Broken pipe/error/fail lines. The subsequent snapshot retained the expected 4096/32768 managed bus, 4096 chunk, 12288 target and 2048/16384 capture/DAC geometry at ~2.2% CPU; its only relevant lines were normal Shairport service/start and CamillaDSP prepared/rate-adjust informational messages. Exact restore returned S16_LE/44.1 and verifier success. **The fixed-192 AirPlay timing/control/transition gate is closed.**
14. **44.1 kHz managed supporting evidence:** a fresh accepted-baseline playback interval was audibly clean and its bounded CamillaDSP error filter produced no matches. The selected managed path is now fixed 192 kHz, so do not spend another gate on 44.1 split-bus reconnect behaviour.
15. **Direct/failback receiver-owned AirPlay + alarm gate — PASSED:** the physically tested candidate hash `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb` entered managed Direct/failback with CamillaDSP inactive, S16_LE/44.1 at the DAC and AirPlay Live present. AirPlay Live/Trim/Music Master worked correctly. A fixed 15% Classic Klaxon preview remained audible with Music Master at 0%, directly proving the alarm lane bypasses music attenuation without falsely invoking takeover. A real scheduled occurrence then took the Alarm screen, produced the configured independent alarm level, paused AirPlay once through PlaybackCoordinator, stopped on Dismiss and left AirPlay paused under the documented manual-resume policy. AirPlay resumed correctly from both Pi and iPhone controls. The bounded dashboard/Shairport error filter returned no matches. Exact restore reinstated the old Direct file, reactivated split-bus/CamillaDSP and passed the verifier; this proves the candidate without weakening recovery.
16. **Promotion complete in source:** the exact tested Direct candidate now owns both first-class Direct and EQ failback, and the EQ production source now pins S32_LE/192 kHz with 4096/32768 ALSA geometry, CamillaDSP 4096 chunks and target 12288. Temporary mutation/recovery rehearsal scripts were retired; the read-only hi-res snapshot remains.
17. **Promoted production deployment — PASSED:** guarded repair on branch head `6b51eb2f30237c89432f954e6811ab1f9de88bb2` installed the production fixed-192 assets without touching the original pre-EQ uninstall backup or saved EQ state. Repair-time and independent verification both passed. Route status reported `split-bus-active`, split-route SHA-256 `9de505b8e9ef326558fd317f22afaba2006d056efb0c34c79457c43ec9881fec`, promoted Direct/failback SHA-256 `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb` and healthy services. The read-only snapshot confirmed configured and live S32_LE/192 kHz processing with 4096/32768 ACP dmix, 4096 CamillaDSP chunks, 12288 target, and 2048/16384 CamillaDSP-capture/DAC endpoint geometry. The five-minute journal contained only normal Shairport stop/start from the repair and normal CamillaDSP rate-adjust/prepared-start informational lines. Physical Plexamp and AirPlay playback were correct; all three EQ bands, both source trims/live controls, source volume controls and Music Master behaved correctly.
18. **Promoted Direct failback/return — PASSED:** the normal managed route owner selected active Direct hash `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb` with `active_matches_direct_failback=true`, CamillaDSP inactive and the physical DAC at S16_LE/44.1, period 1024 and buffer 8192. AirPlay playback was clean and AirPlay Live, AirPlay Trim and Music Master worked. Normal `activate-split-bus` then restored split hash `9de505b8e9ef326558fd317f22afaba2006d056efb0c34c79457c43ec9881fec`, CamillaDSP active, verifier success and the full S32_LE/192 kHz production graph. The bounded transition journal error filter returned no matches; the follow-up snapshot showed only expected Shairport service transitions, PlaybackCoordinator ownership and normal CamillaDSP rate-adjust/prepared-start informational lines.
19. **Truthful audio-path diagnostics implemented / CI passed:** `/api/audio/mixer` now carries an `audio_path` object with separate Source, Processing and DAC authorities. Processing is parsed from the active ALSA route, DAC state from live `hw_params`, and source format/rate remains explicitly unavailable until a runtime source observer genuinely reports it. Settings → Audio adds a read-only three-stage Audio path card and corrected AirPlay Trim copy now says it is downstream of the receiver-owned AirPlay live level. Automated coverage proves both S32_LE/192 split and S16_LE/44.1 Direct parsing plus closed-DAC behaviour.
20. **Active next:** physically verify the new API/card in production split mode and one short Direct → split round trip, then run a longer ordinary mixed-source production stability period and inspect CamillaDSP/Shairport journals for XRUN/stall recovery. Only if those gates expose a fixed-graph limitation reconsider Controller Adapt/source-rate capture.

The acceptance boundary remains appliance reliability first: AirPlay must be stable and truthfully described even though high-resolution processing is primarily a Plexamp requirement.
