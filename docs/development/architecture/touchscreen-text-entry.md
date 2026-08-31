# Touchscreen text-entry architecture

**Status:** in progress in the post-v0.4.0 `develop` cycle.  
**Initial acceptance target:** embedded Plexamp Search on the 1280×720 Raspberry Pi Touch Display 2.

## Goal

A Clockwork Plex needs dependable touch-only text entry inside the embedded Plexamp surface without depending on a desktop-environment on-screen keyboard and without changing normal physical-keyboard behaviour.

The existing ACP Settings touchscreen keyboard is the presentation baseline. Plexamp remains a separate local surface inside the persistent iframe, so cross-surface text entry should reuse the deliberately narrow local browser-bridge pattern already accepted for Plexamp Home backup/restore.

## Shared keyboard baseline

Before the keyboard is extended over Plexamp, the Settings implementation is being normalised as the shared interaction model:

- **Shift is one-shot.** Tapping Shift arms uppercase for the next alphabetic character only; that character then returns the keyboard to lowercase. Tapping Shift again before a letter cancels it.
- While Shift is armed, alphabetic **keycaps visibly change to capitals** and the Shift key exposes an active/`aria-pressed` state.
- Space, Backspace and Clear do not consume the armed Shift state.
- Switching to the number/symbol layout or back to letters clears Shift.
- The internal layout description such as **“Text keyboard”** is not user-facing chrome; the header is reserved for the useful Done action.
- Keyboard surface, key, border, active-Shift and Done colours consume the existing ACP theme variables, with Classic Dark fallbacks rather than a separate hard-coded keyboard palette.
- Physical keyboard input remains native browser input. The touch keyboard only drives fields that explicitly opt into it.

This baseline requires physical 1280×720 confirmation before it is treated as accepted presentation.

## Plexamp bridge boundary

The Plexamp text-entry bridge should extend the existing `browser/plexamp-bridge/` authority rather than create a broad browser-control layer.

Required boundaries:

- the bridge remains limited to the two local Plexamp origins already used by the appliance;
- dashboard-side messaging continues to validate the exact Plexamp iframe origin and message source;
- Plexamp-side messaging continues to accept only the expected ACP parent origins;
- only eligible focused text-entry targets are exposed to the parent, and only a small explicit set of editing actions is accepted;
- authentication and account state remain outside text-entry ownership.

## Planned first slice: Plexamp Search

The first implementation slice should prove the smallest useful end-to-end path:

1. a user taps the Plexamp Search field on the touchscreen;
2. the local Plexamp bridge reports that an eligible text target is focused;
3. ACP presents the shared keyboard above the persistent Plexamp layer;
4. letters, one-shot Shift, symbols, Space, Backspace and Clear edit the live Search field;
5. a deliberate Enter/Search action submits the search through the focused target's normal browser behaviour;
6. Done closes the ACP keyboard without navigating away from Plexamp;
7. ordinary physical keyboard entry continues to work as Plexamp/browser normally handles it.

Search is intentionally first. Once its focus/edit/submit contract has been physically accepted, other Plexamp text fields can be added through explicit eligibility rules rather than assuming every editable-looking element is part of the supported appliance contract.

## Acceptance gates

The checkpoint remains open until the commissioned appliance proves both layers:

- Settings keyboard at 1280×720: Shift key visibly arms, keycaps become uppercase, exactly one alphabetic character is capitalised, lowercase returns automatically, a second Shift tap cancels, theme colours follow the selected daytime theme, and the old “Text keyboard” heading is absent.
- Plexamp Search at 1280×720: touch focus opens the ACP keyboard, editing/backspace/clear/symbols work, Enter/Search submits, Done dismisses cleanly, and normal Plexamp browsing/playback remains intact.
- Physical-keyboard behaviour remains unchanged.
- Plex login, library selection, player identity and Home layout remain unchanged by text entry.

Automated source/syntax/bridge tests protect the narrow contract, but they do not replace the physical touchscreen pass.
