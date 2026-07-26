# AirPlay control-plane review — 26 July 2026

The extended stage-seven CamillaDSP rehearsal again proved the physical DSP route and exact rollback, but exposed control-plane races unrelated to audio transport.

## Rehearsal observations

- Plexamp played normally through CamillaDSP.
- Starting AirPlay paused Plexamp, selected the AirPlay page and produced audio.
- Pausing from the iPhone returned the dashboard to Clock in roughly 30 seconds instead of retaining AirPlay for ten minutes.
- Resuming from the iPhone restored audio and the AirPlay page, but the dashboard play/pause icon could remain inverted.
- Pressing the stale visible Play button could pause audible playback because the page sent a blind toggle.
- CamillaDSP remained healthy and the rehearsal restored the exact ALSA checksum, service states and mixer controls with zero rollback failures.

## Root causes found in review

### Competing playback owners

The AirPlay page loaded several scripts that independently handled or rendered the same play/pause button:

1. `airplay-live.js` rendered MPRIS status and sent `play_pause`.
2. `airplay-play-state-sync.js` polled status every 500 ms and rewrote the icon/classes.
3. `airplay-volume-hold.js` captured clicks and held a guessed playback state for nine seconds.
4. `airplay-pause-hold.js` separately inferred whether the same click meant pause or resume.

This made the visual state depend on timer ordering rather than one authoritative state transition.

### Blind toggle semantics

A stale Play icon sent `PlayPause`. If audio had already resumed on the iPhone, the apparently corrective Play press actually paused it. A visible Play or Pause button must send the explicit idempotent command represented by the button, never a toggle.

### Competing timeout owners

The generic dashboard idle return treated paused AirPlay as inactivity and could select Clock after the configured 30-second timeout. The Shairport pause watchdog then exited because the dashboard was no longer in AirPlay mode. The intended 600-second hold therefore lost to the unrelated shorter timeout.

### Browser-dependent session hold

The former END hook recognised a dashboard pause only when browser heartbeats had refreshed `last_mode_change` within 20 seconds. Pausing from the iPhone supplied no such browser click, so the hold policy was unreliable by design.

## Refactor

- The AirPlay template now loads one command coordinator and no longer loads the three competing playback helpers.
- `airplay-live.js` remains the authoritative MPRIS renderer.
- The new coordinator captures the button event before the legacy bubbling handler and sends explicit `play` or `pause` actions.
- The generic idle timer treats `state.airplay.active` as a held media session, so it cannot beat the AirPlay policy timer.
- Shairport START and END wrappers own session policy without a browser heartbeat.
- A generation token cancels stale pause watchdogs when playback resumes or a newer pause begins.
- Disconnect returns to Clock immediately; pause retains AirPlay for 600 seconds; Plexamp selection cancels the hold without being overwritten by an old timeout.

## Promotion status

- Physical CamillaDSP route: **PASS**
- Automatic rollback: **PASS**
- AirPlay/Plexamp transport through CamillaDSP: **PASS**
- Extended AirPlay control-plane rehearsal: **FAIL before refactor**
- Production DSP activation: **still blocked pending direct-mixer regression and one final extended rehearsal**
- Draft PR #2: **remain draft and unmerged**
