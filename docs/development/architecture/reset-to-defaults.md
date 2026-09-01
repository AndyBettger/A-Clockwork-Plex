# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** remains **physical acceptance open**, but the commissioned 1280×720 Pi has now proved the core **A Clockwork Plex reset transaction** in production.

On 2 September 2026 the corrected ACP reset applied and verified **27 supported changes** on the commissioned appliance after an earlier physical pass exposed the real ALSA Music Master round-trip boundary. The nominal shipped 80% Music Master request quantises through the existing integer softvol mapping and is observed back as **79%**; Reset now targets that physically observable value and regression coverage pins the conversion.

The remaining #93 blocker is the optional **Plexamp Home factory-reset meaning**, not ACP reset integrity. Physical testing disproved the assumption that absence/deletion of the known browser `order` / `hidden` override records necessarily means Plexamp factory Home. The product UI therefore keeps Plexamp Home **inspection-only** until the effective baseline authority is identified and a truthful factory target can be defined.

The latest baseline-safe UI/code candidate is `c88377675e336a10267221b7dd73bb6e70c79179`, which passed **Tests #4466: 1006 tests, `OK`**, including Python compilation, JavaScript/page wiring, shell checks, direct-import smoke and the synthetic low-level Home bridge safety exercise.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing ACP path is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Ordinary unsaved Settings changes block Preview/Apply so a reset cannot silently overwrite staged work.

The current product boundary has one mutating owner and one read-only discovery owner:

1. **A Clockwork Plex** — always selected; resets supported ACP user configuration through the existing server-side transaction.
2. **Plexamp Home inspection** — read-only; reports only the already-classified local Home `order` / `hidden` override records. It is deliberately not selectable for reset until Plexamp's effective factory-baseline authority is proven.

This is stricter than the original #93 design. The first implementation allowed optional deletion of the known local Home override records. Physical testing showed that such deletion returned Plexamp to the appliance's **current effective baseline**, which can itself be a previously customised layout. Therefore “no local overrides” is not equivalent to “Plexamp factory default”.

## A Clockwork Plex reset owner

`app/configuration_reset.py` owns the server-side target.

The browser never supplies replacement default values. `ConfigurationResetPlanner` reads the version-controlled `config.example.json`, projects it through the **production Settings normalisers**, narrows that result through the existing portable-settings ownership boundary, and adds specialist audio defaults only when their established owners are available.

The resulting target contains:

- portable dashboard/display choices;
- Weather and News non-secret user settings;
- alarm schedules and ordinary alarm choices;
- AirPlay user preferences;
- Master EQ enabled with neutral `0 / 0 / 0 dB` bands when the EQ owner is available;
- persistent mixer defaults from the current `MIXER_CHANNELS` authority when the mixer owner is available.

It does not serialize or overwrite raw `config.json`, EQ state files or ALSA state.

`POST /api/settings/reset/preview` is read-only and returns changed paths/counts plus a state-bound reset token. `POST /api/settings/reset/apply` requires explicit `confirm_reset: true`, rebuilds the server-owned target and delegates application to the physically proven #90 restore planner/executor. That reuses stale-preview refusal, owner preflight, AirPlay restart confirmation where required, Unified Settings/EQ/mixer application, post-apply verification and reverse-order rollback.

### Real mixer round-trip boundary

The first commissioned-Pi ACP reset attempt reached mutation but failed during post-apply verification. The failure was rollback-protected.

Investigation proved that the existing restricted ALSA helper maps the nominal Music Master default of 80% through an integer `-51..0 dB` softvol range and reads the resulting state back as 79%. A fake mixer can round-trip 80 exactly; the real appliance cannot.

Reset therefore targets the **observable physical default** of 79% for Music Master while retaining 100% for Plexamp, AirPlay and Alarm. A regression test now calls the real restricted mixer conversion helper so this hardware-facing contract cannot silently drift.

The follow-up commissioned-Pi run completed successfully and reported:

> Reset complete — Selected reset completed and verified. 27 changes applied across A Clockwork Plex.

The physically previewed changes covered EQ, all four persistent mixer values, AirPlay starting volume, alarm schedule/enabled state, display/theme/night/transition settings and Weather provider/location/card/history choices.

### Alarm sound safety switches

The two alarm-audio arming controls — `alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` — are **preserved deliberately**.

They are safety arming state rather than portable appliance personality. Reset therefore never silently arms or disarms scheduled alarm sound. Alarm schedules and their ordinary user choices can return to defaults while the owner's existing sound-safety state remains unchanged.

Alarm hardware/ALSA/helper fields are also outside the reset target.

## Always-preserved ownership

A normal #93 Reset keeps all of the following intact:

- Weather Underground API key and other managed credentials;
- Plex/Plexamp login, claim, authentication and browser session state;
- Plexamp player identity;
- all allow-listed and unknown Plexamp Headless preferences;
- Chromium profile/session/cache as a whole;
- alarm sound master/scheduled safety arming switches;
- DAC, ALSA, mixer topology and installer-owned hardware configuration;
- installed runtimes, systemd units, sudo policies and appliance service ownership;
- Weather/News downloaded caches, rainfall history and other runtime/history state.

A deeper decommissioning/factory-wipe operation is a different product and is not implied by Reset to defaults.

## Plexamp Headless preferences are a separate owner

The eight approved Headless scalar preferences discovered at checkpoint #88 remain part of **backup/restore**, not ordinary #93 Reset. Reset deliberately preserves them while the high-resolution-audio work remains a separate roadmap item.

The supported allow-list is:

- `audioConversionBitrate`
- `autoPlayEnabled`
- `cacheSize`
- `cachingWiFi`
- `loudnessLeveling`
- `precacheNetworkSpeed`
- `sampleRateConversionQuality`
- `sampleRateMatching`

`audioDeviceUuid` is device-specific and excluded; `premium` is account/capability-derived and excluded; authentication/claim/session state and player identity are excluded.

## Plexamp Home inspection and baseline discovery

The browser bridge remains scoped to the already-physically-classified Home Local Storage families:

- `mmkv.default\\discovery:customizations:<context>::/library/sections/<id>:order`
- `mmkv.default\\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden`

`browser/plexamp-bridge/reset.js` is loaded by the same unpacked Manifest V3 extension. The extension remains:

- scoped only to `http://localhost:32500/*` and `http://127.0.0.1:32500/*`;
- permission-free;
- without background worker, network/cookie authority or remote-debugging access.

The content script enumerates key names and calls `getItem()` only after a key matches the exact allow-list. `editing`, caches, resources, auth/session state and unrelated Local Storage values are therefore not opened by this owner.

### What the low-level bridge proves

The low-level bridge can safely:

- count matching local `order` / `hidden` records;
- fail closed if more than one customization context is present;
- return a bounded fingerprint without exposing raw values;
- require an exact fresh fingerprint before mutation;
- delete only the classified records;
- restore exact raw values after an injected failure.

Synthetic CI continues to prove stale-target refusal, scoped deletion, auth/cache/editor preservation, exact rollback and ambiguous-context refusal.

### What physical testing disproved

Those safety properties do **not** prove the semantic claim “delete these records = Plexamp factory Home”.

On the commissioned Pi:

1. the Home bridge successfully loaded after Chromium was fully restarted;
2. the visible Home screen was a layout the owner had deliberately configured after installation;
3. Preview reported **zero** allow-listed local `order` / `hidden` records;
4. after making a new visible Home change, the bridge could detect/remove the corresponding local override;
5. Plexamp then returned to the owner's existing configured Home layout, **not** Plexamp's original factory Home.

Therefore the known browser records are at least partly **delta overrides over another effective baseline**. The authority for that baseline may be another local Plexamp state family, account/library-derived state, or another owner; it is not yet established.

The UI now uses truthful language:

- `No local overrides` means exactly that, not “Already default”;
- `N local overrides` reports the bounded known records;
- Plexamp Home remains disabled for mutation while baseline discovery is open.

No broader browser permissions or arbitrary storage reads are introduced to solve this discovery problem.

## Reset presentation evidence

The first physical layout pass exposed that Reset reused Restore component markup without an equivalent Reset layout scope. A dedicated `settings-reset-defaults.css` fixed the overlapping/crowded target and status presentation.

A second physical pass exposed a separate CSS specificity bug: a Reset `.settings-card { display: grid; }` rule overrode the browser's native `[hidden]` behaviour, causing an empty Preview card to appear before Preview had been requested. The current stylesheet explicitly protects the hidden contract.

The owner also requested Review/Confirm to match the already-accepted Backup/Restore interaction hierarchy. The current Reset layout therefore presents:

**Preview result → Review reset action + Ready-to-confirm status → full-width Final confirmation card**

with the same visual staging philosophy as Backup/Restore.

## Automated evidence

Key green gates:

- implementation head `2944a876284535121f63e256b88696c860317fea` — **Tests #4452: 1005 tests, `OK`**;
- docs-synchronised pre-physical head `7e7c1ddf019f11813bcdcf31287c5c5aa57208a0` — **Tests #4456: 1005 tests, `OK`**;
- first physical-follow-up head `3e627472eaa73079d194ffc5aed4878d61c4f88b` — **Tests #4462: 1006 tests, `OK`**;
- baseline-safe UI head `c88377675e336a10267221b7dd73bb6e70c79179` — **Tests #4466: 1006 tests, `OK`**.

## Physical acceptance gate — OPEN

The ACP mutation boundary is physically proven. Before checkpoint #93 can close:

1. pull the latest baseline-safe candidate and verify the Reset Preview is hidden until Preview is requested;
2. verify the Reset Review/Confirm staging is visually consistent with accepted Backup/Restore at 1280×720;
3. verify Plexamp Home reports only `No local overrides`, `N local overrides`, or a bounded inspection failure and cannot currently be selected for mutation;
4. identify the actual authority that supplies Plexamp's effective Home baseline;
5. decide from evidence whether a safe factory-Home reset can be implemented without touching login/claim/player identity or unrelated browser state;
6. if implemented, physically prove the resulting Plexamp Home reset on the commissioned Pi; otherwise explicitly defer/remove that optional scope from #93 with owner agreement;
7. run a final zero-difference ACP Preview and confirm normal navigation/playback remains healthy.

Only then can #93 move from **ACP reset physically proven / full checkpoint open** to **COMPLETE**.