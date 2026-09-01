# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** is implemented and CI-green on the feature branch, but **physical acceptance is still open**. The commissioned 1280×720 appliance must prove the real Reset workflow, the preserved ownership boundaries and Plexamp's visible Home regeneration before this checkpoint can be called complete.

The pre-documentation implementation head `2944a876284535121f63e256b88696c860317fea` passed **Tests #4452: 1005 tests, `OK`**, including Python compilation, JavaScript/page wiring, shell checks, direct-import smoke and the synthetic Plexamp Home reset safety exercise.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing path is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Ordinary unsaved Settings changes block Preview/Apply so a reset cannot silently overwrite staged work.

The workflow has two independently protected owners:

1. **A Clockwork Plex** — always selected; resets supported ACP user configuration through the existing server-side transaction.
2. **Plexamp Home customisation** — optional and off by default; removes only the already-classified Home ordering/hidden overrides through the permission-free local browser bridge.

These owners are deliberately not presented as one globally atomic transaction. When both are selected, Home is applied and verified first, then the ACP transaction runs. A Home failure prevents ACP mutation. If Home succeeds and a later ACP stage fails, the UI reports the partial cross-owner outcome truthfully rather than claiming a rollback guarantee that cannot span Chromium Local Storage and the server transaction.

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

## Plexamp Home reset owner

The optional Home reset is intentionally separate from the accepted #90 Home restore operation.

`browser/plexamp-bridge/reset.js` is loaded by the same unpacked Manifest V3 extension. The extension remains:

- scoped only to `http://localhost:32500/*` and `http://127.0.0.1:32500/*`;
- permission-free;
- without background worker, network/cookie authority or remote-debugging access.

The reset content script recognises only the already-physically-classified Local Storage records:

- `mmkv.default\\discovery:customizations:<context>::/library/sections/<id>:order`
- `mmkv.default\\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden`

It first enumerates key names and calls `getItem()` only after a key matches the exact allow-list. `editing`, caches, resources, auth/session state and unrelated Local Storage values are therefore not merely excluded from output: the reset owner does not open their values.

### Home reset planning

A read-only plan:

- fails closed if more than one Home customization scope/context is present;
- bounds the number of matching records;
- keeps raw key/value state inside the Plexamp frame;
- returns only a bounded change count plus an 8-hex target fingerprint;
- performs no Local Storage mutation.

### Home reset apply

Apply requires explicit confirmation and the exact fresh fingerprint. The owner rebuilds the plan immediately before mutation and refuses a stale target before deleting anything.

For a valid target it:

1. captures the exact raw value of every matching Home `order`/`hidden` record;
2. removes only those allow-listed records;
3. verifies that no classified Home override record remains;
4. if any delete/verification step fails, restores the exact original raw records in reverse order and verifies rollback.

The software contract therefore proves that ACP removed only the known customization overrides. It does **not** by itself prove what Plexamp 4.13.2 will visibly regenerate after those overrides disappear. That final behaviour belongs to the commissioned-Pi physical gate.

## Automated evidence

The #93 CI gate directly exercises the browser owner with synthetic Local Storage containing Home overrides plus authentication/cache/editor decoys. It proves:

- Preview reads only classified `order`/`hidden` values;
- stale fingerprint refuses before mutation;
- successful reset removes only those overrides;
- auth/cache/editor records remain unchanged;
- an injected mid-delete failure restores exact original bytes;
- ambiguous Home context fails closed.

The full pre-documentation candidate `2944a876284535121f63e256b88696c860317fea` passed **Tests #4452: 1005 tests, `OK`**.

## Physical acceptance gate — OPEN

Before checkpoint #93 can close on `develop`, test on the commissioned 1280×720 Pi:

1. take a fresh configuration backup;
2. make a few harmless ACP changes, including small EQ/mixer differences;
3. make a visible Plexamp Home order/hidden customization;
4. record the current two alarm-audio safety-switch states;
5. open **Advanced → Reset to defaults** and Preview;
6. first leave Plexamp Home **off** and reset ACP only;
7. verify ACP returned to defaults while Home customization, Plexamp login/claim and alarm-audio safety switches stayed unchanged;
8. create/reconfirm harmless ACP differences as needed, select Plexamp Home and run Preview → Review → Confirm again;
9. verify the classified Home overrides disappear and Plexamp visibly regenerates its expected default Home without losing login/claim;
10. verify a follow-up Preview reports no remaining supported ACP changes / no classified Home overrides and normal navigation/playback still works.

Only that physical pass can change #93 from **implementation complete / physical acceptance open** to **COMPLETE**.