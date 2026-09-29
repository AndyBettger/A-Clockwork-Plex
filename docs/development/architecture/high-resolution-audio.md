# High-resolution audio and EQ architecture

## Status

Implementation is active on `feature/hi-res-audio-eq`, branched from the accepted `develop` head after PR #12 merged on 14 September 2026.

The current accepted managed Plexamp/EQ baseline still uses a fixed **S16_LE / 44100 Hz** shared music path. The goal of this work is to remove that bottleneck where it is technically safe, while preserving the existing appliance ownership model, alarm takeover, AirPlay behaviour, mixer semantics and reliable recovery.

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

## Guarded managed-bus rehearsal

`scripts/audio/rehearse-hi-res-bus.py` is the bounded bridge between the completed observation phase and actual high-resolution graph tests. It deliberately does **not** change the repository production profile or claim a production format/rate.

The tool supports only two first-pass candidates: **S32_LE / 96 kHz** and **S32_LE / 192 kHz**. Its default invocation is plan-only. An explicit root `--apply --rate 96000|192000` requires the exact accepted repository/installed **S16_LE / 44100** split-route and defaults and runs the normal managed verifier before mutation.

The first physical 96 kHz attempt exposed a recovery-persistence weakness rather than an audio-format failure. Candidate activation succeeded, but the Pi was restarted before the intended snapshot/restore. After reboot the candidate route/defaults and `state.json` persisted, while the two original `shutil.copy2` backup files had become zero-length files. Normal restore correctly refused the checksum mismatch. A separate checksum-gated recovery audit proved that the state-recorded original hashes exactly matched the feature-branch accepted profile and that the installed files exactly matched the recorded candidate hashes; recovery then reconstructed only from that checksum-matching repository baseline, reactivated the normal graph, passed `verify-audio.sh`, and archived the failed rehearsal evidence rather than deleting it.

The rehearsal transaction was then hardened before another attempt: recovery copies are written atomically through tempfile → flush → `fsync` → replace, their containing directories are `fsync`ed, both backup hashes are verified before `state.json` is committed and before any candidate mutation, state records `durable_backups=true`, a new apply refuses immediately if earlier rehearsal state exists, and the installed candidate files are verified against the state-recorded candidate hashes before route activation. The separate `scripts/audio/recover-hi-res-rehearsal.py` remains the exceptional checksum-gated recovery path if normal restore ever refuses again.

### Physical S32_LE / 96 kHz rehearsal — PASSED, 15 September 2026

The hardened transaction completed its full apply → real playback snapshot → restore cycle on head `31c63208ea38ed0ceb105a25413adb92afdf3c74`.

- plan-only mode described the candidate without mutation and confirmed the durable-backup sequence;
- `--apply --rate 96000` passed the accepted baseline verifier, installed the candidate route/defaults, returned `split-bus-active / split-bus-selected`, and the subsequent snapshot reported `durable_backups=True`;
- with the known **24-bit / 96 kHz** Plex source playing, Plexamp device 9 opened at **96000 Hz** with `preferred was 96000, best was 96000`, while its mixer/source stream remained at 96 kHz;
- the ACP loopback was **S32_LE / 96000 Hz / 4 channels**;
- CamillaDSP capture was **S32_LE / 96000 Hz / 4 channels**;
- the physical Raspberry Pi DAC Pro was **S32_LE / 96000 Hz / 2 channels**;
- the loopback retained `period_size=1024`, `buffer_size=8192`, while CamillaDSP capture and the DAC used `period_size=512`, `buffer_size=4096`;
- CamillaDSP used approximately **1.2% CPU**, compared with roughly 0.6–0.7% on the accepted 44.1 kHz baseline;
- `--restore` returned the exact accepted route hash `1bc69f...`, regenerated the accepted CamillaDSP config, and `verify-audio.sh` passed;
- an independent second verifier pass also succeeded, and the physical DAC was confirmed back at **S16_LE / 44100 Hz**.

This established the first fully measured high-resolution managed-bus candidate. The existing managed split-bus/EQ topology carried a real Plex 24/96 source end-to-end at **S32_LE / 96 kHz** without the former 44.1 kHz output-device collapse, and the separate 192 kHz comparison was then performed before selecting a candidate for the wider functional gate.

### Physical S32_LE / 192 kHz rehearsal and reboot durability — PASSED, 16 September 2026

The same hardened transaction was run independently at **S32_LE / 192 kHz** with known **24-bit / 192 kHz** Plex material, then deliberately repeated across a real reboot to prove the recovery hardening under the exact interruption class that exposed the original zero-length-backup fault.

- direct 192 kHz rehearsal activated `split-bus-active / split-bus-selected`; the ACP loopback, CamillaDSP capture and physical DAC all ran at **S32_LE / 192000 Hz**, with CamillaDSP using approximately **2.4% CPU**;
- explicit restore returned the exact accepted split-route and CamillaDSP configuration, `verify-audio.sh` passed, a second independent verifier pass passed, and the physical DAC returned to **S16_LE / 44100 Hz**;
- the 192 kHz candidate was then activated again and the durable recovery files were hashed before reboot: split-route `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` and defaults `f9b852092e2ea8929bcc8f9aa3563ad94abde08160da2b09b9d9f16802ac305f`;
- the Pi was rebooted **without a manual `sync`**, and both recovery files retained those exact hashes afterwards, closing the earlier zero-length-backup durability defect;
- after reboot, Plexamp direct-played the known 24/192 source, built its pipeline/mixer/source stream at **192000 Hz**, and device 9 (`A Clockwork Plex - Plexamp`) opened at **192000 Hz** with `preferred was 192000, best was 192000`;
- after reboot the ACP loopback was **S32_LE / 192000 Hz / 4 channels**, CamillaDSP capture was **S32_LE / 192000 Hz / 4 channels**, and the Raspberry Pi DAC Pro was **S32_LE / 192000 Hz / 2 channels**;
- CamillaDSP used approximately **2.2% CPU** in the post-reboot snapshot;
- normal `--restore` succeeded after reboot; the exceptional recovery tool was not required, `verify-audio.sh` passed inside restore and again independently, and the physical DAC was independently confirmed back at **S16_LE / 44100 Hz**.

The two first-pass candidates therefore both work physically with matching Plex material and exact rollback. Measured CamillaDSP load was roughly **1.2% at 96 kHz** and **2.2–2.4% at 192 kHz**; the latter remains a small load on this Raspberry Pi 5. **S32_LE / 192 kHz is the provisional fixed EQ-active managed-bus candidate**, with **S32_LE / 96 kHz retained as the fallback** if the broader functional/stability gate exposes a reason to prefer it. This is explicitly provisional, not yet the production managed-bus policy or a bit-perfect claim: lower-rate Plex resampling behaviour, live EQ/bypass, mixer semantics, AirPlay, alarms, latency/long-run stability and recovery still require physical acceptance.

## AirPlay fixed-192 wider-gate finding — ACTIVE, 16 September 2026

The first AirPlay pass on the provisional **S32_LE / 192 kHz** managed bus acquired ownership successfully, but playback was persistently choppy. Repository tracing corrected an earlier working assumption: **PipeWire is not in the current AirPlay path after Shairport Sync**. `scripts/a-clockwork-plex-shairport-integration.py` sets Shairport's ALSA `output_device` to `acp_airplay`, so the active route is:

```text
AirPlay sender
    -> Shairport Sync
    -> ALSA acp_airplay
    -> ALSA plug / AirPlay softvol / Music Master
    -> acp_dmix fixed managed bus
    -> ALSA loopback
    -> CamillaDSP
    -> Raspberry Pi DAC Pro
```

The guarded rehearsal deliberately changes only managed sample format/rate, so the accepted 44.1 kHz frame counts were retained unchanged at 192 kHz. Their time-domain headroom therefore contracted substantially:

| Setting | Frames | 44.1 kHz duration | 192 kHz duration |
| --- | ---: | ---: | ---: |
| ALSA `period_size` | 1024 | ~23.220 ms | ~5.333 ms |
| ALSA `buffer_size` | 8192 | ~185.760 ms | ~42.667 ms |
| CamillaDSP `chunksize` | 1024 | ~23.220 ms | ~5.333 ms |
| CamillaDSP `target_level` | 2048 | ~46.440 ms | ~10.667 ms |
| CamillaDSP one-queue limit (`chunksize * queuelimit`, q=4) | 4096 | ~92.880 ms | ~21.333 ms |

This makes buffer/timing pressure the first hypothesis to measure. Local Plexamp has already tolerated the current 192 kHz geometry, whereas AirPlay adds sender/network timing and Shairport synchronization before the ALSA rate/format-conversion boundary. CamillaDSP 4.1 documentation recommends **4096** as the starting `chunksize` for 176.4/192 kHz and notes that shorter chunks increase vulnerability to system disruption and buffer underruns; that is a candidate comparison point, not yet an appliance setting.

`scripts/audio/snapshot-airplay-hi-res.py` now provides the bounded evidence capture for the unchanged failing graph. It is read-only: it opens no PCM and changes no service, route, mixer or configuration. While the 192 kHz rehearsal and choppy AirPlay stream are active it records the live loopback/Camilla/DAC `hw_params`, converts configured frame counts to milliseconds, reports a safe allow-list of Shairport timing/output settings and CamillaDSP rate-adjust/resampler settings, and filters recent Shairport/CamillaDSP journals for timing, buffering, synchronization and error clues with IPv4/MAC redaction.

The unchanged-geometry physical capture was completed on 29 September 2026 and strongly supports the buffer-pressure hypothesis. The live fixed-192 graph was genuinely S32_LE / 192000 end-to-end, but CamillaDSP repeatedly logged playback underruns, capture overruns, capture/processing stalls and playback write underruns while the audible AirPlay fault was present. CamillaDSP CPU was only about 2.9%, so the evidence points to timing/buffer headroom rather than simple processor saturation. CamillaDSP capture and DAC playback also exposed live ALSA period/buffer values of 512/4096 at 192 kHz, making the endpoint timing windows even shorter than the already contracted configured dmix geometry.

The controlled time-scaled comparison then physically passed on 29 September 2026. With the exact same fixed S32_LE/192 kHz topology, ALSA period/buffer **4096/32768**, CamillaDSP chunksize **4096**, target level **8192** and `queuelimit=4`, the same audiobook opening/theme section was played twice without audible choppiness. Live dmix remained 4096/32768; CamillaDSP capture and DAC playback settled at 2048/16384. Two snapshots — the later one with the same CamillaDSP process at about 207 seconds — contained no underrun, overrun, stalled-processing or write-underrun evidence. CPU was about 1.9%, and exact restore returned the accepted S16/44.1 graph with verifier success.

That A/B result makes inadequate time-domain buffer/scheduling headroom the supported explanation for the original AirPlay failure and keeps the **fixed S32_LE/192 kHz architecture** as the preferred managed candidate. The time-scaled values are physically proven candidate geometry, not yet the production profile; the remaining wider Plex/EQ/mixer/alarm/long-run gate must pass before production promotion. The ordinary rehearsal default remains the original unchanged-frame profile so the failure remains reproducible.

The fixed-processing-domain interpretation was then physically checked with known **16/44.1, 24/48, 24/96 and 24/192** Plex material on the time-scaled candidate. All four played correctly. Plexamp rebuilt its internal pipeline/mixer/source stream at the source rate; for fresh 48/96/192 transitions Device 9 nevertheless opened at **192000 Hz** while reporting the source rate as its preferred/best rate. In the 44.1 kHz case Device 9 was already open at 192 kHz from the preceding stream and did not emit a fresh reopen line, while the live loopback/Camilla/DAC path remained S32_LE/192 kHz. This establishes the truthful EQ-active contract as a **fixed S32_LE/192 kHz processing/output domain with lower-rate sources resampled before the fixed managed boundary**, without claiming a specific converter implementation that the evidence does not isolate. CamillaDSP stayed around 1.7–1.8% CPU and exact restore again returned the accepted S16/44.1 graph.

The next Plexamp-side control pass also physically passed on 29 September 2026. With a 192 kHz Plex source playing, Bass changes were audibly effective, Music Master and Plexamp trim changed level as intended, and the saved EQ/mixer values were returned to their starting state before restore. CamillaDSP remained the **same PID (68242)** throughout the live control exercise, the final snapshot still showed S32_LE/192 kHz through loopback → CamillaDSP → DAC, CPU was about **1.6%**, and a bounded journal check found no underrun, overrun, stall, xrun or error lines. Exact restore again returned the accepted S16/44.1 graph and the independent verifier passed.

That pass also exposed a diagnostics-only inconsistency: `/api/audio/mixer` reported `sample_rate_hz: 44100` while the live graph was physically at 192 kHz. The mixer controls themselves were correct; the helper was reading its legacy control-creation defaults instead of the active managed split-bus defaults for rate metadata. The helper now keeps its existing mixer-control authority but takes DAC/rate status metadata from `/etc/default/a-clockwork-plex-split-bus` when present, with the legacy file retained as fallback.


The current CamillaDSP Controller remains a credible fallback rather than a speculative custom mechanism. Its Linux ALSA listener can watch a loopback/device for sample-rate or format changes, and its Adapt provider can update capture format and `capture_samplerate` for a base configuration that contains a resampler while leaving the processing/output `samplerate` fixed. That supports a future shape of source-rate ALSA capture → Controller → asynchronous SRC/rate adjustment → fixed S32_LE/192 kHz processing/output. Parallel rate-specific CamillaDSP instances remain a last-resort topology because they would duplicate routing/lifecycle and shared EQ/volume ownership.

Detailed physical procedure and evidence boundary: [`../testing/airplay-hi-res-buffer-investigation.md`](../testing/airplay-hi-res-buffer-investigation.md).

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
5. **96 kHz complete:** the hardened guarded rehearsal physically carried known 24/96 Plex material end-to-end as **S32_LE / 96 kHz**, with device 9 opening at 96 kHz, CamillaDSP at about 1.2% CPU, and exact restoration back to the accepted S16/44.1 graph.
6. **192 kHz + reboot durability complete:** matching 24/192 material physically traversed device 9 → ACP loopback → CamillaDSP → DAC at **S32_LE / 192 kHz**; CamillaDSP used about 2.2–2.4% CPU; fsynced recovery hashes survived an un-synced reboot unchanged; and normal restore returned the accepted S16/44.1 graph with verifier success.
7. **Provisional managed candidate:** advance **S32_LE / 192 kHz** to the wider functional gate, retaining **S32_LE / 96 kHz** as fallback. This is explicitly provisional until the wider gate passes.
8. **AirPlay buffer diagnosis complete:** the unchanged-frame 192 kHz graph reproduced choppiness plus repeated underrun/overrun/stall evidence; the otherwise-identical time-scaled 4096/32768 ALSA + 4096/8192 CamillaDSP candidate played the same AirPlay material cleanly twice and produced two clean timing snapshots. Fixed S32_LE/192 kHz therefore remains the preferred architecture; Controller Adapt is deferred unless a later gate requires it.
9. **Plex source-rate matrix complete:** known 16/44.1, 24/48, 24/96 and 24/192 material all played correctly; Plexamp retained source-rate pipeline/mixer behaviour while Device 9/downstream processing stayed fixed at S32_LE/192 kHz. This closes lower-rate resampling truthfulness for the managed candidate.
10. **Plexamp live-control pass complete:** Bass changes, Music Master and Plexamp trim behaved correctly at fixed S32_LE/192 kHz; CamillaDSP retained the same PID, the graph stayed at 192 kHz, no XRUN/stall/error evidence was logged, and exact recovery passed. A stale mixer API sample-rate field was identified as metadata-only and corrected to follow the managed split-bus profile.
11. **AirPlay-side partial pass:** EQ, Music Master and AirPlay trim all worked at fixed S32_LE/192 kHz, and the mixer rate diagnostic correctly tracked 44.1 → 192 → 44.1 kHz. The main AirPlay sender slider and configured starting volume did not control the iPhone reliably. Inspection found ACP was using Shairport's MPRIS SetVolume request, whose upstream contract does not guarantee the sender applies the request. Two isolated CamillaDSP playback-buffer underrun recoveries were also logged during the longer reconnect/control run, so this gate is not accepted yet.
12. **AirPlay 2 sender-volume capability classified:** native `AirplayVolume` readback is reliable enough for truthful diagnostics, but receiver-originated writes are not a supported control authority on the commissioned iPhone/AirPlay 2 path. With the corrected `busctl --system call -- ...` form, established-session slider commands caused no audible change, no iPhone slider movement and no native readback change; a delayed manual `SetAirplayVolume d 0.0` likewise left the sender at **-20 dB**. This matches current Shairport Sync master documentation, which says AirPlay 2 remote-control facilities are not implemented and describes D-Bus/MPRIS remote control for Classic AirPlay clients.
13. **Receiver-owned AirPlay volume selected:** the commissioned `pvol` test showed prompt sender metadata changes across the full iPhone range, including mute at **-144 dB** and full scale at **0 dB**. That confirms useful read-only diagnostics but does not change the control decision. Shairport now renders `ignore_volume_control = "yes"` so the sender's attenuation is not applied to audio. ACP owns audible AirPlay level with a new runtime-only `A Clockwork AirPlay Live` softvol upstream of the existing persistent AirPlay Trim → Music Master chain. The main ACP/AirPlay-page sliders write this local stage. Starting-volume configuration and all receiver→sender volume writers are removed; the live stage defaults full-scale when ALSA creates it and is intentionally not part of persistent trim backup/reset ownership.
14. **Deployment hardening before physical acceptance:** the first guarded 44.1 kHz repair attempt used the already-installed CamillaDSP binary as its verified source and exposed GNU `install` rejecting a self-copy; the repair transaction restored the previous state. The installer now reuses an exact source/destination binary safely. Review also confirmed that Direct/failback is deliberately pinned to the exact physically proven alarm-safe route; it is not being changed opportunistically for the new live fader. Receiver-owned AirPlay parity in Direct/failback is a separate explicit gate before merge.
15. **Receiver-owned 44.1 kHz functional acceptance passed, stability still open:** after the hardened repair, helper installation and guarded Shairport activation, a deliberately low iPhone sender no longer attenuated playback; AirPlay Live, AirPlay Trim, Music Master and EQ were all audibly effective; iPhone volume movement changed only read-only `pvol` metadata; reconnecting preserved the ACP-owned live level; and Starting volume UI/settings were absent. All ACP-owned ALSA gain stages use the same `perceptual-amplitude` mapping, including AirPlay Live/Trim and Plexamp Trim. The historic AirPlay sender/UI scale factor is retired. Plexamp's main live fader remains its native player-volume API. The bounded 44.1 kHz journal was not clean: CamillaDSP logged multiple playback underrun recoveries plus one capture overrun/Broken pipe/stall sequence during the reconnect/control exercise, despite no audible fault.
16. **Receiver-owned fixed-192 high-target stability/control/transition gate passed:** a second run of the exact 12288-target candidate separated activation, idle, AirPlay startup, five minutes of untouched steady playback and live EQ/volume/trim control into independent journal windows; all were audibly clean and produced no filtered errors. A targeted follow-up then deliberately disconnected and reconnected AirPlay. Receiver-owned AirPlay Live level, EQ, AirPlay Trim and Music Master behaviour all remained correct, the bounded reconnect window produced no underrun/overrun/stall/xrun/Broken pipe/error/fail match, and the subsequent snapshot showed only normal service/start informational lines. The live graph remained S32_LE/192 kHz with managed ALSA 4096/32768, chunksize 4096, target 12288 and capture/DAC 2048/16384 at ~2.0–2.2% CamillaDSP CPU. Exact restore returned the accepted 16/44.1 baseline. This closes AirPlay timing/control/transition acceptance for the candidate and justifies promoting the same geometry into the managed production profile before the remaining alarm/failback gates.
17. **44.1 kHz managed supporting evidence was clean, but no further 44.1 split-bus gate is required:** a fresh accepted-baseline playback interval was audibly clean and its bounded CamillaDSP error filter returned no matches. The selected managed candidate is now the physically accepted fixed-192 graph; 44.1 kHz remains relevant separately as the conservative Direct/failback domain.
18. **Direct/failback receiver-owned AirPlay + alarm acceptance passed and was promoted:** the exact one-delta candidate hash `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb` was physically exercised as Direct/failback with CamillaDSP off and S16_LE/44.1 at the DAC. Receiver-owned AirPlay Live/Trim/Music Master remained functional; a controlled preview stayed audible with Music Master at 0%; a real scheduled alarm paused AirPlay, owned screen/audio priority, bypassed music controls and released to the intentional manual-resume policy; AirPlay then resumed correctly. No bounded error lines were found and exact split-bus restoration verified cleanly. The same bytes now own both the first-class Direct profile and EQ failback. The temporary Direct and hi-res mutation/recovery rehearsal tools were retired after promotion; the read-only high-resolution snapshot diagnostic remains.
19. **Production EQ deployment physically accepted:** guarded repair on the commissioned Pi installed the promoted fixed-192 graph and passed verification both inside the repair transaction and again independently. Live route status reported `split-bus-active`, active split-route identity `9de505b8e9ef326558fd317f22afaba2006d056efb0c34c79457c43ec9881fec`, Direct/failback identity `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb`, and healthy managed services. The live ACP dmix was S32_LE/192 kHz with 4096/32768 geometry; CamillaDSP capture and the physical DAC were S32_LE/192 kHz with 2048/16384 endpoint geometry; chunksize remained 4096, target_level 12288, queuelimit 4 and rate adjustment enabled. Physical Plexamp and AirPlay playback were correct, all three EQ bands were effective, source/live volume and trims worked, and Music Master remained correct. The fixed-192 graph is therefore the accepted installed production profile, not merely a rehearsal candidate.
20. Define an EQ-active high-resolution contract separately from a measured native/bypass contract.
21. Test source-rate-native Direct Plexamp across **44.1/48/88.2/96/176.4/192 kHz** where the hardware and Plexamp path permit it.
22. Expose source format, processing format and final DAC format/rate separately in diagnostics.
23. Regression-test EQ active/bypass, route/fallback, AirPlay transitions, alarm takeover and recovery before merge.

## Acceptance boundary

This feature does not merge to `develop` on CI alone. Automated checks must be green and the relevant format/rate, alarm, AirPlay, EQ and recovery behaviour must be physically proven on the development appliance.
