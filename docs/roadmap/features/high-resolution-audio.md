# High-resolution Plexamp audio / mixer-EQ path

**Issue:** #85  
**Status:** ACTIVE — final ordinary-use stability soak before merge  
**Branch:** `feature/hi-res-audio-eq`

## Goal for this branch

Ship the physically accepted managed EQ path at **S32_LE / 192 kHz** while preserving AirPlay, alarms, source/mixer controls, Direct failback and recovery.

## Accepted implementation

- Raspberry Pi DAC Pro capability measured through 192 kHz.
- Managed split bus physically accepted at S32_LE / 192 kHz.
- Production timing geometry: ALSA 4096/32768; CamillaDSP chunksize 4096; target_level 12288; queuelimit 4.
- Plex 16/44.1, 24/48, 24/96 and 24/192 source matrix physically passed through the fixed-192 processing/output domain.
- Receiver-owned AirPlay Live volume physically accepted.
- EQ, source trims/live controls and Music Master physically accepted.
- Direct/failback remains deliberately S16_LE / 44.1 kHz and includes receiver-owned AirPlay parity.
- Real scheduled alarm takeover, dismissal/manual-resume and independent alarm lane passed.
- Promoted Direct failback → production split recovery passed.
- Truthful Source / Processing / DAC diagnostics physically accepted.

## Remaining merge gate

- [ ] Run a longer ordinary mixed-source Plexamp/AirPlay production soak.
- [ ] Inspect the bounded CamillaDSP/Shairport journals for underrun, overrun, XRUN, stall, Broken pipe, error/fail recovery.
- [ ] Confirm automated CI remains green at the final branch head.
- [ ] Reconcile docs/catalogues and open the merge to `develop`.

## Explicitly deferred from #85

A true **source-rate-native / bit-perfect Direct bypass** is not required to merge this accepted managed-hi-res implementation.

The older #85 notes mixed that future ambition into this feature. Defer it to a separate future track after #94 determines whether Plexamp Headless remains the player. Do not build a complicated native/bypass mode around a player runtime that may shortly be retired.

Likewise CamillaDSP Controller Adapt remains a fallback only if later long-run evidence exposes a limitation in the accepted fixed-192 graph.

## Detailed authorities

- `../../development/architecture/high-resolution-audio.md`
- `../../development/testing/airplay-hi-res-buffer-investigation.md`
