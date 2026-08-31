# Touchscreen text-entry architecture

**Status:** shared Settings keyboard physically accepted; first Plexamp Search slice implemented with physical Search acceptance pending in the post-v0.4.0 `develop` cycle.  
**Initial acceptance target:** embedded Plexamp Search on the 1280×720 Raspberry Pi Touch Display 2.

## Goal

A Clockwork Plex needs dependable touch-only text entry inside the embedded Plexamp surface without depending on a desktop-environment on-screen keyboard and without changing normal physical-keyboard behaviour.

The existing ACP Settings touchscreen keyboard is the presentation baseline. Plexamp remains a separate local surface inside the persistent iframe, so cross-surface text entry reuses the deliberately narrow localhost content-bridge pattern already accepted for Plexamp Home backup/restore.

## Shared keyboard baseline

`app/static/js/settings-keyboard.js` is now the shared interaction implementation. Settings continues to use its existing keyboard markup and script include; non-Settings dashboard documents load the same client from `base.html`, where it creates the same keyboard shell lazily only when needed.

- **Shift is one-shot.** Tapping Shift arms uppercase for the next alphabetic character only; that character then returns the keyboard to lowercase. Tapping Shift again before a letter cancels it.
- While Shift is armed, alphabetic **keycaps visibly change to capitals** and the Shift key exposes an active/`aria-pressed` state.
- Space, Backspace and Clear do not consume the armed Shift state.
- Switching to the number/symbol layout or back to letters clears Shift.
- The internal layout description such as **“Text keyboard”** is not user-facing chrome; the header is reserved for the useful Done action.
- Keyboard surface, key, border, active-Shift, Search and Done colours consume the existing ACP theme variables, with Classic Dark fallbacks rather than a separate hard-coded keyboard palette.
- `app/static/css/touch-keyboard.css` is loaded globally so the same presentation sits above the persistent Plexamp iframe as well as Settings. The older Settings-local declarations remain compatible fallbacks, but the global stylesheet is the cross-surface owner.
- Physical keyboard input remains native browser input. ACP does not intercept or rewrite Plexamp physical-keyboard events.

The owner physically re-checked the corrected Settings keyboard at 1280×720 on 31 August 2026 and confirmed the revised Shift/presentation behaviour is working better. That shared baseline is accepted; checkpoint #91 now remains open only for the Plexamp Search path and its physical-keyboard non-regression check.

## Plexamp bridge boundary

Search deliberately uses a small companion extension at `browser/plexamp-search-bridge/` instead of adding DOM-editing responsibility to the physically accepted Home-preference bridge at `browser/plexamp-bridge/`.

That separation is intentional: Home backup/restore keeps its existing storage allow-list and code unchanged, while Search has no storage authority at all. The kiosk launcher loads whichever of the two local bridge directories are complete, as one comma-separated Chromium `--load-extension` set. Neither bridge needs permissions, host permissions, a background worker or remote debugging.

Implemented Search boundaries:

- the Search manifest is limited to `localhost:32500` and `127.0.0.1:32500`, with no permissions, host permissions or background worker;
- dashboard-side messaging validates the exact persistent Plexamp iframe `contentWindow` and its allow-listed loopback origin;
- Plexamp-side messaging accepts commands only from the two expected ACP dashboard origins on port `8088`;
- Search focus is represented only by `focused` / `blurred`, the fixed kind `search`, and an opaque random session ID — **the Search text is never sent to ACP**;
- the parent can send only `insert`, `backspace`, `clear`, `submit` or `done`; insert accepts exactly one non-control Unicode character and every edit must match the currently focused session;
- session IDs require browser cryptographic randomness; if neither `randomUUID()` nor `getRandomValues()` is available the bridge fails closed instead of creating a predictable text-entry session;
- the Plexamp side refuses commands if the eligible Search input is no longer the actual focused element or has left the document;
- there is no selector, arbitrary DOM command, script execution, cookie, browser-storage, network or authentication authority in the text-entry contract;
- authentication/account state, player identity and Home layout remain outside text-entry ownership.

## First slice: Plexamp Search

The implemented first slice is intentionally narrow:

1. a user taps an eligible Plexamp Search `<input>` (`type=search`, `role=searchbox`, an explicit Search label/placeholder/name/test marker, or a Search-labelled container);
2. the local Search bridge creates an opaque focus session and reports only that session to ACP;
3. ACP presents the shared keyboard above the persistent Plexamp layer;
4. letters, one-shot Shift, symbols, Space, Backspace and Clear send bounded edit commands to that still-focused target;
5. the Search key sends a synthetic Enter sequence and preserves normal form submission semantics where Plexamp uses a form;
6. Done asks the focused Search target to blur and closes the ACP keyboard without navigating away from Plexamp;
7. leaving/hiding the Plexamp surface closes any remote keyboard session;
8. ordinary physical keyboard entry remains entirely inside Plexamp/browser handling.

Search is intentionally first. Other Plexamp text fields must be added through explicit future eligibility rules rather than assuming every editable-looking element is part of the supported appliance contract.

## Acceptance gates

The checkpoint remains open until the commissioned appliance proves the remaining Plexamp layer:

- **Settings keyboard — accepted at 1280×720 on 31 August 2026:** corrected one-shot Shift/presentation behaviour was owner-confirmed working better after the baseline follow-up.
- **Plexamp Search — pending at 1280×720:** touch focus opens the ACP keyboard, editing/backspace/clear/symbols work, Search submits, Done dismisses cleanly, and normal Plexamp browsing/playback remains intact.
- Physical-keyboard behaviour remains unchanged.
- Plex login, library selection, player identity and Home layout remain unchanged by text entry.

Automated source/syntax/Node bridge tests protect the narrow contract, but they do not replace the physical touchscreen pass.
