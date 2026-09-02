# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** remains **physical acceptance open**. The commissioned 1280×720 Pi has already proved the core **A Clockwork Plex reset transaction and final guided presentation** in production; a new narrowly scoped **Plexamp commissioning reset participant** is now implemented and CI-green but still needs physical acceptance on that appliance.

On 2 September 2026 the corrected ACP reset applied and verified **27 supported changes** after an earlier physical pass exposed the real ALSA Music Master round-trip boundary. The nominal shipped 80% Music Master request quantises through the existing integer softvol mapping and is observed back as **79%**; Reset now targets that physically observable value and regression coverage pins the conversion.

A later physical pass on exact branch head `526f580a4802c7c20dd00c96ab63b97a03d5122c` confirmed that the Preview panel stays hidden before Preview, Plexamp Home is clearly inspection-only, the **Review reset → Ready to confirm → full-width Final confirmation** staging matches the accepted Backup/Restore interaction, and a repeated 27-change ACP reset again completed and verified successfully. That exact source/docs head passed **Tests #4468: 1006 tests, `OK`**.

The next implementation step deliberately did **not** broaden Plexamp Home access. Instead, two already-understood appliance commissioning choices were given their own narrow owner:

- the **claimed Plexamp player name** used for this appliance;
- the exact managed audio output labelled **`A Clockwork Plex - Plexamp`**.

Those values are not portable backup state. `setup.sh` now records the player name once as this appliance's local Reset baseline and resolves the managed audio device dynamically from Plexamp's loopback settings API. Reset can therefore return a later renamed player and/or changed output to the commissioned appliance state without copying a source-machine UUID, touching Plex credentials, or pretending the Home baseline problem has been solved.

Implementation/catalogue head `fc1c9462957a6533e833a53d6d61e6453e133c14` passed **Tests #4479: 1023 tests, `OK`** on 3 September 2026, with Python compile, JavaScript/page-wiring and shell syntax gates green. Physical commissioning/reset acceptance remains outstanding.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing path is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Ordinary unsaved Settings changes block Preview/Apply so a reset cannot silently overwrite staged work.

The current product boundary contains **two mutating reset participants and one read-only discovery owner**:

1. **A Clockwork Plex** — always selected; resets supported ACP user configuration through the existing server-side transaction.
2. **Plexamp commissioning** — participates when a setup-owned commissioning baseline exists and the current player name and/or managed output differs. It can restore only those two appliance-local choices.
3. **Plexamp Home inspection** — read-only; reports only the already-classified local Home `order` / `hidden` override records plus bounded key-name-only diagnostics. It remains non-selectable for Reset because Plexamp's effective factory-Home baseline authority has not been established.

This is intentionally different from portable Backup & restore. A value can be **nonportable** yet still have a legitimate same-appliance Reset owner. `playerName` and `audioDeviceUuid` remain excluded from backup files because another appliance must not inherit this device's identity/binding. The local commissioning owner instead records only the intended player label and resolves the target output UUID afresh on the same appliance.

## A Clockwork Plex reset owner

`app/configuration_reset.py` owns the server-side ACP target.

The browser never supplies replacement default values. `ConfigurationResetPlanner` reads the version-controlled `config.example.json`, projects it through the **production Settings normalisers**, narrows that result through the existing portable-settings ownership boundary, and adds specialist audio defaults only when their established owners are available.

The resulting ACP target contains:

- portable dashboard/display choices;
- Weather and News non-secret user settings;
- alarm schedules and ordinary alarm choices;
- AirPlay user preferences;
- Master EQ enabled with neutral `0 / 0 / 0 dB` bands when the EQ owner is available;
- persistent mixer defaults from the current `MIXER_CHANNELS` authority when the mixer owner is available.

It does not serialize or overwrite raw `config.json`, EQ state files or ALSA state.

`POST /api/settings/reset/preview` is read-only and returns changed paths/counts plus a state-bound reset token. `POST /api/settings/reset/apply` requires explicit `confirm_reset: true`, rebuilds the server-owned target and delegates ACP application to the physically proven #90 restore planner/executor. That reuses stale-preview refusal, owner preflight, AirPlay restart confirmation where required, Unified Settings/EQ/mixer application, post-apply verification and reverse-order rollback.

### Real mixer round-trip boundary

The first commissioned-Pi ACP reset attempt reached mutation but failed during post-apply verification. The failure was rollback-protected.

Investigation proved that the existing restricted ALSA helper maps the nominal Music Master default of 80% through an integer `-51..0 dB` softvol range and reads the resulting state back as 79%. A fake mixer can round-trip 80 exactly; the real appliance cannot.

Reset therefore targets the **observable physical default** of 79% for Music Master while retaining 100% for Plexamp, AirPlay and Alarm. A regression test calls the real restricted mixer conversion helper so this hardware-facing contract cannot silently drift.

The commissioned-Pi corrected reset has completed successfully more than once and reported:

> Reset complete — Selected reset completed and verified. 27 changes applied across A Clockwork Plex.

The physically previewed changes covered EQ, all four persistent mixer values, AirPlay starting volume, alarm schedule/enabled state, display/theme/night/transition settings and Weather provider/location/card/history choices.

### Alarm sound safety switches

The two alarm-audio arming controls — `alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` — are **preserved deliberately**.

They are safety arming state rather than portable appliance personality. Reset therefore never silently arms or disarms scheduled alarm sound. Alarm schedules and their ordinary user choices can return to defaults while the owner's existing sound-safety state remains unchanged.

Alarm hardware/ALSA/helper fields are also outside the reset target.

## Plexamp commissioning reset owner

`app/plexamp_commissioning.py` is a separate appliance-local owner. `scripts/commission-plexamp.py` is its setup-owned command surface.

Its allowed setting set is deliberately only:

- `playerName`;
- `audioDeviceUuid`.

The owner talks only to Plexamp's loopback settings API on port `32500`; non-loopback base URLs are rejected. It does not receive Plex tokens, cookies, claim material or browser credentials and does not open unrelated Plexamp preferences.

### Player-name baseline

The reset baseline is stored in:

```text
~/.local/share/a-clockwork-plex/plexamp-commissioning.json
```

The file is atomic, mode `0600`, schema-versioned and contains only the commissioned **player name**. It does **not** contain a Plex token, account identifier, browser state or audio-device UUID.

For a fresh appliance, the player name entered during the interactive Plexamp claim becomes the baseline when `setup.sh` subsequently completes the commissioning step. Once captured, ordinary repeat `bash setup.sh` runs **do not replace that baseline** merely because the owner has since renamed the player. This is essential: a Reset target must not move every time setup is rerun.

For an appliance installed before this owner existed, Reset Preview does not silently invent/adopt a baseline. The migration is deliberate: run `bash setup.sh` once while the current Plexamp player name is the name that should become this appliance's Reset baseline. Later renames then remain resettable customisation rather than redefining the baseline.

### Managed audio output

The audio route is not stored as a baseline UUID. Each commission/Reset operation asks Plexamp for its current output/device catalogue and requires exactly one device whose display label is:

```text
A Clockwork Plex - Plexamp
```

The owner then uses that live device's UUID for the scoped `audioDeviceUuid` write. Missing or ambiguous matching devices fail closed. This avoids transplanting a stale machine-specific UUID and keeps the label/installer-created route as the durable appliance authority.

`Follows system output` is therefore not the supported commissioned target even though it remains a normal Plexamp choice the owner may temporarily select for testing.

### Preview, stale state and transaction behaviour

The commissioning plan exposes only bounded status, counts and a fingerprint. It never returns the actual player name or device UUID to the Reset UI.

The combined #93 reset token binds both:

- current ACP reset comparison/capability state; and
- current commissioning comparison/capability state.

A later player-name/output change invalidates the old Preview before mutation.

Apply sequencing is:

1. capture the exact pre-reset ACP backup and commissioning state;
2. apply/verify ACP through the existing #90 transaction when ACP work exists;
3. apply/verify the two-setting commissioning owner when commissioning work exists;
4. if the second Plexamp setting fails after the first succeeded, the commissioning owner restores its exact touched settings;
5. if commissioning still fails after ACP has already applied, the outer reset executor restores the exact pre-reset ACP backup as well.

A commissioning-only Reset is also supported and does not manufacture a pointless ACP restore transaction.

Automated fault injection covers the important late-failure shape: player-name write succeeds, audio-output write fails, the player-name write is rolled back, and earlier ACP mutation is also rolled back by the outer owner.

## Always-preserved ownership

A normal #93 Reset keeps all of the following intact:

- Weather Underground API key and other managed credentials;
- Plex/Plexamp login, claim, authentication and browser session state;
- Plex account/server/resource state and unrelated player/machine identity;
- all eight allow-listed Plexamp Headless portable preferences and every unknown Headless preference;
- Chromium profile/session/cache as a whole;
- Plexamp Home effective baseline state beyond the already-classified read-only inspection boundary;
- alarm sound master/scheduled safety arming switches;
- DAC, ALSA, mixer topology and installer-owned hardware configuration;
- installed runtimes, systemd units, sudo policies and appliance service ownership;
- Weather/News downloaded caches, rainfall history and other runtime/history state.

The **player label** and **managed Plexamp output selection** are no longer in this always-preserved list when a commissioning baseline exists; they are the narrowly resettable commissioning participant described above.

A deeper decommissioning/factory-wipe operation is a different product and is not implied by Reset to defaults.

## Plexamp Headless portable preferences remain a separate owner

The eight approved Headless scalar preferences discovered at checkpoint #88 remain part of **backup/restore**, not ordinary #93 Reset. Reset deliberately preserves them while the high-resolution-audio work remains a separate roadmap item.

A fresh read-only commissioned-Pi audit on 2 September 2026 reconfirmed all eight exact current values without opening any unknown/device/account/browser values:

| Preference | Current commissioned value | #93 Reset |
| --- | ---: | --- |
| `audioConversionBitrate` | `256` | Preserved |
| `autoPlayEnabled` | `false` | Preserved |
| `cacheSize` | `32768` | Preserved |
| `cachingWiFi` | `10` | Preserved |
| `loudnessLeveling` | `false` | Preserved |
| `precacheNetworkSpeed` | `0` | Preserved |
| `sampleRateConversionQuality` | `4` | Preserved |
| `sampleRateMatching` | `2` | Preserved |

These are **current commissioned values and the supported backup/restore allow-list**, not a claim that Plexamp factory defaults have been established. `premium` remains account/capability-derived and excluded. `playerName` and `audioDeviceUuid` are deliberately outside this portable Headless bundle and are owned only by the separate appliance-local commissioning boundary above.

The same audit still found **35** Plexamp Settings files in total, with **11** safe-looking candidate names and **24** deliberately unclassified/excluded files.

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
- require an exact fresh fingerprint before its classified restore mutation;
- restore exact raw values after an injected failure;
- inspect deliberately bounded key-name-only diagnostic shapes without opening their values.

Synthetic CI continues to prove stale-target refusal, scoped mutation, auth/cache/editor preservation, exact rollback and ambiguous-context refusal for the supported Backup/Restore Home owner.

### What physical testing disproved for Reset

Those safety properties do **not** prove the semantic claim “remove these records = Plexamp factory Home”.

On the commissioned Pi:

1. the Home bridge successfully loaded after Chromium was fully restarted;
2. the visible Home screen was a layout the owner had deliberately configured after installation;
3. Reset Preview reported **zero** allow-listed local `order` / `hidden` records;
4. after making a new visible Home change, the bridge could detect/remove the corresponding local override;
5. Plexamp then returned to the owner's existing configured Home layout, **not** Plexamp's original factory Home.

Therefore the known browser records are at least partly **delta overrides over another effective baseline**. The authority for that baseline may be another local Plexamp state family, account/library-derived state, or another owner; it is not established.

### Compact `:c` lead — ruled out as live Local Storage authority

A content-blind browser-key scan originally exposed:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/9:c
```

while the visible Home was the owner's configured baseline and the known `order` / `hidden` override count was zero. Because Chromium LevelDB can retain historical/deleted records, this was treated only as a lead.

A narrower live key-name-only probe then matched only that exact compact shape and deliberately continued before any `storage.getItem()` call. The 2 September commissioned-Pi follow-up reported:

> Live key-name inspection found no compact `:c` customization metadata key.

The visible Plexamp Home still remained the owner's configured post-install baseline and the known `order` / `hidden` override count remained zero. The earlier `:c` observation is therefore **historical LevelDB residue, not a current live Local Storage authority**. Its value was never opened.

Normal Plexamp playback was confirmed after that reboot/probe pass.

### Reset policy for Home

The UI continues to use truthful language:

- `No local overrides` means exactly that, not “Already default”;
- `N local overrides` reports the bounded known records;
- Plexamp Home remains disabled for Reset mutation while the effective factory baseline is unproven.

This does **not** affect the already-accepted #90 Backup/Restore Home owner, which restores a user's backed-up logical Home choices against the target's live context. “Restore my saved Home” is a proven target; “return to Plexamp factory Home” is a different semantic claim.

The remaining product decision is whether to continue bounded Home-baseline research or explicitly defer factory-Home Reset as optional scope. The commissioning owner does not resolve or weaken that decision.

## Reset presentation evidence — PHYSICALLY ACCEPTED

The first physical layout pass exposed that Reset reused Restore component markup without an equivalent Reset layout scope. A dedicated `settings-reset-defaults.css` fixed the overlapping/crowded target and status presentation.

A second physical pass exposed a separate CSS specificity bug: a Reset `.settings-card { display: grid; }` rule overrode the browser's native `[hidden]` behaviour, causing an empty Preview card to appear before Preview had been requested. The current stylesheet explicitly protects the hidden contract.

The owner also requested Review/Confirm to match the already-accepted Backup/Restore interaction hierarchy. The current Reset layout therefore presents:

**Preview result → Review reset action + Ready-to-confirm status → full-width Final confirmation card**

with the same visual staging philosophy as Backup/Restore.

The 2 September 1280×720 recheck physically accepted the completed presentation: Preview is absent until requested, the Home inspection target is visibly disabled, Preview details are readable, Review/Ready-to-confirm are adjacent, Final confirmation is full-width below them, and the persistent Reset-complete result remains clear after reload.

The commissioning participant extends the same guided flow; it does not add a second confirmation product. Its summary reports only availability/change counts and the managed output label, never the current/baseline player-name value or UUID. Its final visual/physical acceptance is still required.

## Automated evidence

Key green gates:

- implementation head `2944a876284535121f63e256b88696c860317fea` — **Tests #4452: 1005 tests, `OK`**;
- docs-synchronised pre-physical head `7e7c1ddf019f11813bcdcf31287c5c5aa57208a0` — **Tests #4456: 1005 tests, `OK`**;
- first physical-follow-up head `3e627472eaa73079d194ffc5aed4878d61c4f88b` — **Tests #4462: 1006 tests, `OK`**;
- baseline-safe UI head `c88377675e336a10267221b7dd73bb6e70c79179` — **Tests #4466: 1006 tests, `OK`**;
- exact physically rechecked source/docs head `526f580a4802c7c20dd00c96ab63b97a03d5122c` — **Tests #4468: 1006 tests, `OK`**;
- compact live-key probe head `ae26c9af57a37850f6ce5a55dedd5ff506c9401d` — **Tests #4471: compile, JavaScript/page wiring, shell and unit-test gates green**;
- commissioning implementation + catalogue-green head `fc1c9462957a6533e833a53d6d61e6453e133c14` — **Tests #4479: 1023 tests, `OK`**, with compile, JavaScript/page wiring and shell gates green.

The new commissioning regressions cover:

- first-run baseline capture and immutable repeat-setup baseline behaviour;
- exact managed-output label resolution with missing/ambiguous-route refusal;
- loopback-only API restriction;
- value-free Preview/public plan responses;
- stale-fingerprint refusal before mutation;
- successful two-setting convergence;
- injected second-write failure restoring the first Plexamp write;
- commissioning-only Reset;
- combined ACP + commissioning Reset and outer ACP rollback after a late commissioning failure;
- setup/dependency/Reset UI wiring and Python/shell/JavaScript syntax.

## Physical acceptance gate — OPEN

The ACP mutation boundary and base Reset presentation are physically proven. The commissioning implementation is CI-green but not yet physically proven. Before checkpoint #93 can close:

1. pull the exact final docs-synchronised candidate onto the commissioned Pi and confirm the dashboard/Plexamp services remain healthy;
2. **existing-appliance migration:** while Plexamp currently has the player name the owner wants as its long-term Reset baseline, run `bash setup.sh` once and confirm setup reports the baseline/output commissioning step as successful;
3. verify ordinary repeat setup does not recapture a later temporary player rename;
4. make a harmless temporary commissioning deviation — for example rename the player and select **Follows system output** — then run Reset Preview and confirm commissioning work is detected without exposing the old/new player name or device UUID;
5. **Review reset → Confirm & reset** and physically verify the original commissioned player name returns, the output returns to **`A Clockwork Plex - Plexamp`**, and normal Plexamp playback works;
6. run a fresh Preview and confirm the commissioning participant is at zero differences; when the owner is ready to leave ACP at shipped defaults, also confirm zero ACP differences and normal navigation/playback health;
7. make an explicit owner decision on optional **Plexamp factory-Home Reset** scope: either continue bounded semantic investigation and prove a safe target, or defer that optional feature while retaining the truthful inspection-only UI and already-supported Backup/Restore Home owner.

Only after those physical checks and the Home-scope decision can #93 move to **COMPLETE**.