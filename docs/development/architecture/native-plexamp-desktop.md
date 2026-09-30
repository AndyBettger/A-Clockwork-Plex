# Native Plexamp desktop / visualiser migration

**Status:** queued investigation after Astronomy; no production migration authorised  
**Roadmap item:** #94  
**Last updated:** 30 September 2026

## Goal

Investigate replacing the legacy Plexamp Headless + embedded browser UI with the
current ARM64 Linux desktop Plexamp so the bedside appliance gains native
visualisers and a supported desktop-player lifecycle without losing the parts of
A Clockwork Plex that are already physically accepted:

- NFC media launch;
- the managed `acp_plexamp` audio entry point and downstream trim / Music Master /
  CamillaDSP EQ / limiter / alarm-safe graph;
- alarm and AirPlay playback ownership;
- touchscreen-first navigation;
- backup/reset ownership;
- deterministic recovery and rollback.

This is a rehearsal-first migration. The accepted Headless runtime remains the
rollback until a native-player candidate passes all physical gates.

## Preferred player architecture

The preferred experiment is **native Plexamp as the real local decoder/player**,
not a second Plexamp instance acting only as a remote UI for Headless.

Target:

```text
NFC / ACP playback policy
          |
          v
native Plexamp
          |
          v
     acp_plexamp
          |
          v
Plexamp Trim -> Music Master -> reserve -> EQ -> limiter
          |
          +---- alarm-safe join
          |
          v
         DAC
```

A two-player arrangement may still be useful temporarily for discovery, but is
not the intended visualiser architecture because a remote controller does not
own the locally decoded audio data required by the visualiser.

## Display ownership

### Preferred first experiment: two compositor workspaces

Rather than stacking two fullscreen applications on one desktop, test:

- workspace 1: Chromium A Clockwork Plex dashboard;
- workspace 2: native Plexamp;
- deterministic ACP-owned switching between them;
- window rules that keep each application on its intended workspace;
- alarm takeover allowed to force the ACP workspace immediately.

The appliance must first verify its actual compositor/session at runtime rather
than assume labwc merely because it is the current Raspberry Pi OS default.

### Transitions

The current ACP screen changes feel deliberately polished and should not regress
to an abrupt desktop flash merely because Plexamp becomes native.

Preferred investigation:

1. ACP requests a screen/application transition.
2. A small ACP-owned Wayland overlay covers the output.
3. The overlay performs a short fade/slide.
4. The compositor switches workspace underneath.
5. The overlay reveals the destination.

This keeps animation policy under ACP while leaving the supported compositor
responsible for actual window/workspace ownership.

Compiz-style cube/exposé experiments are welcome as a development curiosity, but
must not become a reason to replace the supported compositor unless an
alternative proves equally reliable for boot, VNC, touch, alarms and recovery.

Alarm takeover is safety/product behaviour and may bypass decorative animation
if necessary.

## ACP desktop shell candidate

A small, independently restartable **ACP desktop shell** is worth prototyping as
the shared owner of UI that must appear above both Chromium and native Plexamp.

Possible responsibilities:

- native version of the existing bottom navigation pill;
- narrow edge-swipe detector that reveals navigation;
- transition overlay;
- optional system-level on-screen keyboard surface.

Explicit non-responsibilities:

- no audio routing;
- no playback arbitration;
- no NFC media interpretation;
- no alarm scheduling;
- no persistent settings authority beyond its own presentation preferences.

The shell should fail open: if it crashes, Chromium/Plexamp audio must continue,
and there must remain an SSH/VNC recovery path.

## Navigation pill and edge gesture

The current ACP navigation pill works over the embedded Plexamp UI because both
belong to Chromium. It cannot literally overlay a separate native Plexamp
window.

First-stage migration:

- retain the existing browser pill inside Chromium;
- show a visually matching ACP-owned overlay pill only while native Plexamp is
  foreground;
- tapping it returns to the ACP workspace/navigation.

Optional later unification:

- one desktop-shell navigation surface across both workspaces;
- hidden by default;
- reveal with a bottom- or side-edge swipe.

The edge gesture must be physically tested for:

- accidental triggers during Plexamp gestures;
- scrolling conflicts in Settings/News/etc.;
- visualiser interaction;
- alarm screens;
- swipe direction and target width;
- VNC behaviour.

A visible pill remains the fallback if an invisible gesture proves discoverability
or reliability is worse.

## Touchscreen keyboard

The existing ACP Search keyboard is browser/DOM-owned and therefore cannot type
into a separate native Plexamp window.

Native migration is blocked until Plexamp Search and other ordinary text fields
are usable from the touchscreen.

Investigation order:

1. test the current Raspberry Pi OS Wayland on-screen keyboard over native
   fullscreen/maximised Plexamp;
2. test the same keyboard over Chromium kiosk to document the current layering
   difference;
3. if the distribution keyboard is unreliable, prototype an ACP-owned overlay
   keyboard using an appropriate Wayland input / virtual-keyboard mechanism;
4. keep password/login/claim entry outside any broad ACP key-injection bridge
   unless separately reviewed;
5. verify focus, Shift/backspace, dismissal, repeated searches and return to ACP.

If an ACP desktop shell is created, the navigation overlay and keyboard may share
that process, but the keyboard remains presentation/input plumbing rather than
playback authority.

## NFC / Companion compatibility

Current NFC tags contain Plex playMedia URLs which the listener rewrites to the
local Plexamp Companion receiver. Discovery must establish whether native Linux
Plexamp exposes compatible local receiver endpoints for:

- `/player/playback/playMedia`;
- timeline/status polling used by ACP;
- queue/activity semantics used to detect a fresh NFC launch.

Prefer adapting the endpoint/configuration around the existing tag format rather
than rewriting the physical NFC library.

## Audio acceptance

Native Plexamp must be able to feed the existing ACP-owned audio boundary.

Preferred route:

```text
native Plexamp -> ALSA acp_plexamp -> accepted fixed-192 managed graph
```

Physical gates include:

- native app sees/selects `acp_plexamp` or an equivalent controlled host ALSA
  endpoint;
- no competing Plexamp EQ/volume authority is silently introduced;
- Plexamp trim, Music Master and ACP EQ remain effective;
- fixed-192 processing/DAC diagnostics remain truthful;
- Direct failback/recovery remains valid;
- AirPlay and alarm takeover behaviour remains accepted.

## Runtime and resilience boundary

#94 comes **after Astronomy and before the full Appliance Resilience track**.

Reason: native Plexamp may change player process ownership, display switching,
autostart, crash behaviour and the browser/native boundary. The subsequent
resilience work should harden the architecture that actually survives #94 rather
than fully hardening components that may be retired.

However, #94 itself must still prove minimum resilience before migration:

- reversible install/uninstall;
- Headless rollback retained;
- clean reboot/autostart;
- Plexamp crash and restart;
- Chromium crash and restart;
- desktop-shell crash and restart if introduced;
- alarm behaviour during/after player failure;
- VNC/SSH recovery;
- no boot loop if native Plexamp cannot start.

## Remote support

The commissioned appliance is routinely inspected over VNC/SSH. Any workspace,
overlay, native Plexamp or keyboard design must remain visible and operable both
on the physical touchscreen and through the supported remote-access path.

A design that works locally but leaves VNC blind to the foreground Plexamp or ACP
overlay is not acceptable.

## Backup / reset ownership

Do not assume the current browser bridges or Headless storage map directly onto
the rewritten native app.

Classify before migration:

- login/claim identity;
- player identity/name;
- native Plexamp preferences;
- Home customisation;
- visualiser preference;
- selected ACP audio device;
- portable vs machine-local state;
- Reset behaviour;
- Backup/Restore behaviour.

## Acceptance boundary

Headless may be retired only after the native candidate passes:

- visualiser/GPU load;
- ALSA/ACP audio path;
- NFC;
- Companion/timeline observation;
- touchscreen keyboard;
- Chromium/Plexamp workspace switching;
- navigation/edge return path;
- transition presentation;
- alarms;
- AirPlay handoff;
- Direct failback/recovery;
- backup/reset ownership;
- reboot/autostart;
- crash/recovery;
- longer ordinary-use stability.
