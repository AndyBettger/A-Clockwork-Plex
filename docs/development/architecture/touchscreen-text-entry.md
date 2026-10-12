# Touchscreen text-entry architecture

**Status:** checkpoint #91 physically accepted on the commissioned 1280×720 appliance on 31 August 2026.  
**Physical target:** embedded Plexamp on the 1280×720 Raspberry Pi Touch Display 2.

## Goal

A Clockwork Plex needs dependable touch-only text entry inside the embedded Plexamp surface without depending on a desktop-environment on-screen keyboard and without changing normal physical-keyboard behaviour.

The existing ACP Settings touchscreen keyboard is the presentation baseline. Plexamp remains a separate local surface inside the persistent iframe, so cross-surface text entry reuses the deliberately narrow localhost content-bridge pattern already accepted for Plexamp Home backup/restore.

## 12 October 2026 — proposed OS-wide Squeekboard consolidation (#94 Phase B)

The accepted #91 browser DOM keyboard remains the physically proven fallback. During Phase B, an isolated `1.43.1-1+rpt1` Raspberry Pi Squeekboard rebuilt with Wayland layer `OVERLAY` has now **physically displayed and typed above genuine fullscreen native Plexamp**. The user confirmed Shift, numbers, punctuation and dismissal/accessible modal actions in true fullscreen; after the guarded three-minute test the original distro keyboard was restored without installation.

It is attractive to use **one** ACP-managed Wayland OSK for both native Plexamp and ACP Chromium, but this is **not automatic**: #91's keyboard is a JavaScript DOM overlay with ACP CSS tokens, specialised Settings layouts (number, decimal, time, URL and quick-entry keys), and a narrowly scoped Headless Plexamp text-field content bridge. The current Chromium kiosk does not explicitly pin an Ozone Wayland backend; OS-level text-input focus/visibility and actual text injection into ACP Settings and its embedded Headless player must be physically proved before deactivating the existing accepted keyboard. Preserve opt-in fallback and do not show both OSK and DOM overlays simultaneously.

Squeekboard's GTK CSS resources live outside browser CSS variables, so ACP theme matching requires a private palette-to-GTK stylesheet bridge, with a bounded app-specific CSS provider, dark/colour themes and scheduled dim/night mode handled explicitly (including eventual Astronomy red). Avoid global GTK styling. The current experimental log shows the local `gb` layouts missing and falling back to `us_wide`, a British keyboard fidelity gap to resolve without overwriting distro resources. Never remove or regress the accepted #91 flow while evaluating OS-wide keyboard ownership.

## 12 October 2026 — Phase B Stage C1 voluntary native OSK trial inside Chromium

The accepted #91 keyboard remains the default. The user physically demonstrated that the new compositor `OVERLAY` Squeekboard already appears inside ACP Settings/Chromium but **simultaneously triggers ACP's legacy DOM keyboard** when a `data-keyboard` text field is focused. The problem is a duplicate-input overlay, not a lack of Wayland text-input events in this Chromium Settings case.

A reversible single-tab trial choice now lives at **Settings → Advanced → Keyboard trial**. `app/static/js/osk-keyboard-choice.js` owns a five-minute sessionStorage expiry, a tappable enable/restore control and restoration of inputmode attributes when trial mode ends. The selection is loaded before `settings-keyboard.js` on every ACP page, including Settings. Native mode exposes explicit input hints to Squeekboard in place of older ACP `inputmode=none`, suppresses the HTML keyboard for local and allow-listed Headless Plexamp focus messages, and uses a CSS last-resort hide guard against double-overlay. Input and message-validation code and the custom keyboard remain present/unchanged for fallback mode; no storage or network authority is added. This UI switch **does not start Squeekboard**: native mode is only useful while the independently guarded 180s system keyboard trial is active, or later if ACP explicitly owns a running compatible OSK. No behaviour survives browser-tab closure; the previous mode returns after five minutes (or a tap on Restore).

Focus parity, specialised number/decimal/time/URL layout usability, Headless iframe focus and browser auto-save behaviour still require physical Pi proof before decommissioning the DOM implementation. Native GTK theme palette and missing `gb`/British layout also remain future tasks. This is a preparation feature, **not** completed OSK consolidation or default appliance startup.

## Shared keyboard baseline

`app/static/js/settings-keyboard.js` is the shared interaction implementation. Settings continues to use its existing keyboard markup and script include; non-Settings dashboard documents load the same client from `base.html`, where it creates the same keyboard shell lazily only when needed.

- **Shift is one-shot.** Tapping Shift arms uppercase for the next alphabetic character only; that character then returns the keyboard to lowercase. Tapping Shift again before a letter cancels it.
- While Shift is armed, alphabetic **keycaps visibly change to capitals** and the Shift key exposes an active/`aria-pressed` state.
- Space, Backspace and Clear do not consume the armed Shift state.
- Switching to the number/symbol layout or back to letters clears Shift.
- The internal layout description such as **“Text keyboard”** is not user-facing chrome; the header is reserved for the useful Done action.
- **Done is the only Plexamp keyboard action.** Plexamp Search updates live while the query is typed, so ACP does not need a visible synthetic Search/Enter key. The original `submit` protocol action remains only as a rolling-deployment compatibility path and is not rendered by the keyboard.
- Keyboard surface, key, border, active-Shift and Done colours consume the existing ACP theme variables, with Classic Dark fallbacks rather than a separate hard-coded keyboard palette.
- `app/static/css/touch-keyboard.css` is loaded globally so the same presentation sits above the persistent Plexamp iframe as well as Settings. The older Settings-local declarations remain compatible fallbacks, but the global stylesheet is the cross-surface owner.
- Physical keyboard input remains native browser input. ACP does not intercept or rewrite Plexamp physical-keyboard events.

The owner physically re-checked the corrected Settings keyboard at 1280×720 on 31 August 2026 and confirmed the revised Shift/presentation behaviour is working better. The later Plexamp passes confirmed the same shared keyboard works very well over the embedded player.

## Plexamp bridge boundary

Plexamp text entry deliberately uses the small companion extension at `browser/plexamp-search-bridge/` instead of adding DOM-editing responsibility to the physically accepted Home-preference bridge at `browser/plexamp-bridge/`. The directory/protocol retain the original Search naming for backwards-safe deployment, while the payload `kind` is the explicit allow-list for supported text fields.

That separation is intentional: Home backup/restore keeps its existing storage allow-list and code unchanged, while text entry has no storage authority at all. The kiosk launcher loads whichever of the two local bridge directories are complete, as one comma-separated Chromium `--load-extension` set. Neither bridge needs permissions, host permissions, a background worker or remote debugging.

Implemented boundaries:

- the text-entry manifest is limited to `localhost:32500` and `127.0.0.1:32500`, with no permissions, host permissions or background worker;
- dashboard-side messaging validates the exact persistent Plexamp iframe `contentWindow` and its allow-listed loopback origin;
- Plexamp-side messaging accepts commands only from the two expected ACP dashboard origins on port `8088`;
- focus is represented only by `focused` / `blurred`, an allow-listed field `kind`, and an opaque random session ID — **field contents are never sent to ACP**;
- the normal visible keyboard sends only one-character `insert`, `backspace`, `clear` and `done`; insert accepts exactly one non-control Unicode character and every edit must match the currently focused session;
- the original Search-only `submit` command is retained only for protocol compatibility during rolling updates and has no rendered ACP key;
- session IDs require browser cryptographic randomness; if neither `randomUUID()` nor `getRandomValues()` is available the bridge fails closed instead of creating a predictable text-entry session;
- the Plexamp side refuses commands if the eligible input/textarea is no longer the actual focused element or has left the document;
- there is no selector, arbitrary DOM command, script execution, cookie, browser-storage, network or authentication authority in the text-entry contract;
- authentication/account state and library selection remain outside the required text-entry scope. Login-field keyboard support is optional future resilience because normal commissioning already documents VNC.

## Physically accepted Plexamp fields

The commissioned appliance proved the cross-frame interaction end-to-end on 31 August 2026.

### Search

1. touching Plexamp Search opens the shared ACP keyboard above Plexamp;
2. letters, one-shot Shift, symbols, Space, Backspace and Clear edit the live Plexamp Search input;
3. Plexamp updates results as the query changes, so no explicit Search submission is required;
4. Done blurs the focused field and closes the ACP keyboard without leaving Plexamp;
5. normal Plexamp browsing/playback remains usable.

Search remains recognised by `type=search`, `role=searchbox`, explicit Search label/placeholder/name/test markers, or a Search-labelled container.

### Explicit general text fields

The bridge does **not** accept every `<input>`. It classifies only a deliberately small set of user-visible fields from their stable semantic clues and surrounding Plexamp UI context:

- **Home `+Home` section title** — the `Header title… (* required)` field;
- **Create Smart Playlist → Name** — `Playlist name…`;
- **Create Smart Playlist → Description** — `Playlist description…`, accepting either Plexamp `<input>` or `<textarea>` rendering;
- **Settings → Experience → Home Screen → section Title** — recognised only inside the section editor context containing Title plus Display as and Visible/Subtype controls;
- **Settings → Experience → Player Name** — recognised from the Player Name field/page context.

The owner physically tested all five field groups at 1280×720 on 31 August 2026 and confirmed they open the ACP keyboard, accept/edit text correctly and dismiss cleanly with Done. Search was re-checked after the generalisation and remained working correctly with live-as-you-type results and Done-only dismissal.

Ordinary unrelated text fields and password fields remain ineligible. Login support can be added later as an explicit separate field kind if it proves useful; it is not silently enabled by this expansion and is not required for checkpoint #91 because commissioning already documents VNC.

All supported Plexamp fields use the ordinary text layout and **Done**. The keyboard does not attempt to press Plexamp's Add/Create/Save controls; those remain normal explicit Plexamp touches after text entry.

## Acceptance gates

- **Settings keyboard — accepted at 1280×720 on 31 August 2026:** corrected one-shot Shift/presentation behaviour was owner-confirmed working better after the baseline follow-up.
- **Plexamp Search — accepted at 1280×720 on 31 August 2026:** the owner confirmed the shared keyboard works very well for live Search entry; the follow-up also confirmed the simplified Done-only Search keyboard.
- **General Plexamp text fields — accepted at 1280×720 on 31 August 2026:** Home section Title, Smart Playlist Name/Description, Home Screen section Title and Player Name all open/edit/dismiss correctly with Done.
- Normal Plexamp browsing/playback remains intact and physical-keyboard behaviour remains native.
- Login/library authentication state and the accepted Home backup/restore bridge remain unchanged by text entry.

**Checkpoint #91 required scope is complete.** Login-field keyboard support remains an optional resilience enhancement rather than an acceptance blocker.

Automated source/syntax/Node bridge tests protect the narrow contract, but they do not replace the physical touchscreen pass.
