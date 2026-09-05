# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** has passed its revised combined multi-owner transaction on the commissioned Pi. Functional Reset is proven. The AirPlay session-start baseline is corrected to 100%; final product acceptance remains open while the owner decides whether the accepted presentation-only Home Reset should be extended to a full Home-customisation reset which lets Plexamp rebuild its own effective Home.

Physically accepted:

- the A Clockwork Plex (ACP) Reset transaction, verification and rollback model;
- the final 1280×720 Preview → Review → Confirm presentation;
- the same-appliance Plexamp commissioning Reset for player name and managed audio output;
- the Plexamp native ordinary-settings Reset, including Plexamp player volume returning to 100%;
- the Plexamp Home presentation Reset, with per-section presentation returned to Plexamp defaults while Home order and visibility remain intact;
- the corrected ACP-only browser/server stale-token hand-off inside the full combined transaction.

PR #9 remains Draft and must not merge until the final supported Home boundary is accepted explicitly.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing flow is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Unsaved ACP Settings changes block Reset so staged work cannot be silently overwritten.

The complete Reset has four participants:

1. **A Clockwork Plex** — supported ACP user configuration generated from version-controlled defaults through production normalisers.
2. **Plexamp commissioning** — same-appliance owner for the captured player name plus managed `A Clockwork Plex - Plexamp` output.
3. **Plexamp native settings** — ordinary Plexamp settings reset by Plexamp's own application authority, with Plexamp player volume explicitly returned to 100%.
4. **Plexamp Home presentation** — per-section presentation/custom view settings returned to Plexamp defaults without changing section order, visibility or custom-added sections.

Authentication, selected library, claim/session, account/machine identity, credentials, hardware topology, installed runtimes/services and unrelated Chromium state remain outside Reset.

## A Clockwork Plex owner

`app/configuration_reset.py` owns the ACP target. The browser never supplies default values.

`ConfigurationResetPlanner` reads version-controlled `config.example.json`, passes it through the production Settings normalisers and narrows it through established ownership boundaries. Specialist audio defaults are added only when their owners are available.

The supported ACP target includes:

- dashboard/display choices;
- Weather and News non-secret settings;
- alarm schedules and ordinary alarm choices;
- AirPlay user preferences;
- Master EQ enabled with neutral Bass/Mid/Treble bands;
- persistent mixer levels returned to the current full-scale baseline when the mixer owner is available.

It excludes credentials, hardware/topology, runtime/cache/history state and the two alarm-audio safety arming switches.

`POST /api/settings/reset/preview` is read-only and returns changed paths/counts plus state-bound tokens. `POST /api/settings/reset/apply` requires `confirm_reset: true`, rebuilds the target and delegates to the physically accepted #90 restore transaction machinery for stale refusal, preflight, application, verification and reverse-order rollback.

### Browser/server stale-token ownership

The browser-native Plexamp participant runs before the server-owned ACP participant. That sequencing requires two deliberately different server fingerprints:

- `owner_tokens.a_clockwork_plex` fingerprints **only the ACP-owned target and current ACP-owned state**. The browser client uses this token immediately before server mutation to prove that ACP itself has not changed since Review.
- `restore_preview_token` is the broader #90 portable-Restore token used internally by the server executor. It may also fingerprint portable Plexamp Headless preferences because #90 Restore owns those preferences.

Those tokens must not be conflated. Native Plexamp Reset is explicitly allowed to change ordinary Headless preferences before the server step. Therefore a legitimate Headless change may invalidate the broader #90 restore token while the ACP-only owner token remains unchanged.

Physical testing on 5 September exposed the previous mistake: the first combined implementation reused the broader #90 token as the ACP hand-off token. A full-state Review contained 16 native Plexamp changes, including Headless preferences; native Reset changed them, the broader token changed, and the client falsely reported **“A Clockwork Plex settings changed after Review.”** The retained browser-native/Home rollback then restored the browser-owned prestate correctly.

The fix gives ACP its own scoped token while retaining the full #90 token for the actual server transaction. The subsequent commissioned-Pi combined transaction physically crossed that hand-off and completed successfully.

### Audio and AirPlay Reset baseline

Reset deliberately returns the persistent ACP audio controls to a neutral/full-scale baseline:

- Master EQ: enabled, Bass 0.0 dB, Mid 0.0 dB, Treble 0.0 dB;
- Music Master: 100%;
- Plexamp trim: 100%;
- AirPlay trim: 100%;
- Maximum Alarm Volume: 100%;
- AirPlay session-start volume: 100%.

The earlier 80% Music Master / physically observed 79% round-trip was useful evidence about ALSA softvol quantisation, but it is no longer the Reset baseline.

AirPlay's session-start volume and persistent AirPlay trim are separate controls, but the intended shipped/reset value for both is **100%**. A short-lived 10% edit made during the 5 September follow-up was immediately identified by the owner as a typo and is not an accepted policy.

### Alarm sound safety

`alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` are preserved deliberately. Reset never silently arms or disarms scheduled alarm sound.

## Plexamp commissioning owner — PHYSICALLY ACCEPTED

`app/plexamp_commissioning.py` and `scripts/commission-plexamp.py` own only:

- `playerName`;
- `audioDeviceUuid` as the live binding for the managed output.

The owner is loopback-only on Plexamp port 32500 and never reads Plex tokens/cookies/claim/session material or unrelated preferences.

The appliance-local baseline file is:

```text
~/.local/share/a-clockwork-plex/plexamp-commissioning.json
```

It is atomic, mode `0600`, schema-versioned and stores only the commissioned player name. The audio UUID is never stored as a baseline; every commission/Reset resolves exactly one live output labelled:

```text
A Clockwork Plex - Plexamp
```

Missing or ambiguous matches fail closed.

Physical acceptance on 3 September 2026 proved baseline capture, the real empty/unset audio-device representation, zero-difference convergence, deliberate two-difference Preview, guarded Reset and physical restoration of both player name and managed output.

`playerName` and `audioDeviceUuid` remain excluded from portable Backup/Restore.

## Plexamp native ordinary-settings owner

`browser/plexamp-bridge/native-reset.js` owns ordinary Plexamp application settings plus Plexamp's live music-player volume.

### Plexamp remains the default authority

Disposable-profile testing established that Plexamp's own **Debugging → Reset to Defaults** preserves login and selected library while resetting ordinary settings. ACP therefore does not maintain a copied table of Plexamp setting defaults; it invokes Plexamp's own `settings.resetToDefaults()` method and verifies against a fresh instance of the live settings class.

Read-only inspection of Plexamp 4.13.2 established the live authority at:

```text
global.app.rootStore.settings
```

with the browser-global compatibility form as fallback. The owner requires `resetToDefaults()` before Preview can become ready. It does not scan webpack modules, use `eval`, expose a generic JavaScript executor or automate arbitrary DOM controls.

### Preview diagnostics and runtime-normalised exclusions

Preview compares bounded public settings against a fresh settings instance.

Excluded from the native changed-set/fingerprint are:

- keys beginning `_`;
- `premium` (account/capability-derived);
- `playerName` and `audioDeviceUuid` (owned by commissioning);
- `equalizerPresets`, because physical post-reset evidence showed Plexamp repopulates this catalogue after its own Reset, making it runtime-normalised/non-convergent state rather than a durable user-choice Reset target.

The `equalizerPresets` exclusion is deliberately narrow. It remains included in the exact pre-reset rollback snapshot, so if a later owner fails the transaction can still restore the precise runtime state that existed before Reset.

All other bounded non-function settings, including the eight safe Headless preferences used by Backup/Restore, participate normally in Plexamp's native Reset semantics.

Preview also reads Plexamp's live music-player volume through the same-origin player timeline API. A value below 100% contributes one logical native change named:

```text
playerVolume
```

Public Preview exposes bounded **setting names only** under Technical changed paths, together with count/fingerprint information. It never exposes old/new values. This made the post-reset convergence issue diagnosable without turning Preview into a preference-value dump.

### Apply, verification and rollback

Apply requires explicit confirmation and the exact fresh fingerprint. It then:

1. captures a bounded exact pre-reset settings snapshot and the current Plexamp player volume;
2. calls Plexamp's own `settings.resetToDefaults()` when ordinary settings differ;
3. sets Plexamp player volume to **100%** through Plexamp's same-origin player parameter endpoint;
4. verifies Reset-owned settings against a fresh settings instance and verifies player volume at 100%;
5. retains a rollback token until the outer multi-owner transaction succeeds.

If verification fails, both settings and player volume are restored. If a later Home/server participant fails, the outer Reset client uses the retained token to restore the exact browser-native prestate, including the runtime-normalised preset catalogue captured before Reset.

The native call may temporarily reset `playerName` and `audioDeviceUuid`; the physically accepted commissioning participant subsequently returns them to this appliance's commissioned state.

### Physical convergence evidence

After the corrected full Reset succeeded, a fresh Preview reported three native names:

- `activeTab`;
- `equalizerPresets`;
- `showFullScreenPlayerOnStart`.

A second native Reset converged `activeTab` and `showFullScreenPlayerOnStart`. A further Preview then reported only `equalizerPresets`. That repeatable 3 → 1 result is the physical basis for classifying `equalizerPresets` as runtime-populated state rather than repeatedly invoking Reset against it.

## Eight safe Headless preferences: Backup/Restore vs Reset

Checkpoint #88 established this exact typed scalar allow-list for **portable Backup/Restore**:

- `audioConversionBitrate`
- `autoPlayEnabled`
- `cacheSize`
- `cachingWiFi`
- `loudnessLeveling`
- `precacheNetworkSpeed`
- `sampleRateConversionQuality`
- `sampleRateMatching`

That allow-list means ACP can safely export and version-aware restore those user choices. It does **not** make their current values appliance-owned Reset defaults.

Earlier commissioned audit values (`256`, `false`, `32768`, `10`, `false`, `0`, `4`, `2`) and later observed values (`128`, `true`, `512`, `15`, `true`, `0`, `2`, `0`) remain evidence of real appliance state, not Plexamp-default constants.

For Reset, Plexamp itself is authoritative: these eight ordinary preferences follow `settings.resetToDefaults()` like other Plexamp settings. If later high-resolution-audio work intentionally commissions one of them as an ACP appliance policy, that future feature must establish and document its own ownership.

## Plexamp Home presentation owner

The earlier investigation established an important product boundary: deleting Home order/visibility records does **not** reliably mean “factory Home”, because those records can be delta overrides over an existing effective Home baseline.

The revised #93 owner therefore does **not** attempt to reset Home order or visibility. It preserves:

- section order;
- hidden/visible state;
- custom-added sections;
- custom section titles;
- editor/auth/cache/unrelated browser state.

It recognises only current-context per-section records of the form:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

Real commissioned-profile evidence showed that both `<context>` and `<hub-id>` can contain bounded URL-like characters. The matcher therefore accepts only the established structural family plus a bounded identifier character envelope and exact final `:viewSettings` suffix. A key which clearly belongs to the family but cannot be classified fails Preview closed rather than being reported as zero changes.

For a built-in section, presentation-specific `viewSettings` are removed so Plexamp can use its own per-section default presentation. For a custom-added section, the owner strips presentation fields while retaining the validated custom `title` field so the section itself remains intact.

The owner fails closed on unsupported `viewSettings` encodings, unclassified family keys, ambiguous Home contexts or excessive bounded record counts. It does not open order, hidden, editor, auth or cache values while planning.

Preview reports only a bounded record count and fingerprint. Apply requires the fresh fingerprint, captures exact raw bytes, writes/removes only classified `viewSettings` records, verifies zero remaining presentation differences and retains exact rollback state until the outer transaction finalizes.

On exact physical-preview head `4e01b289fbfec352d41d345a50e22dcc30bf53a3`, the commissioned Pi successfully reported **15 Home presentation records** in one Preview and **14** after the state was recreated, with the technical UI collapsing them to `plexamp.home.view-settings · N` and exposing no raw Home identifiers or values.

The corrected combined physical transaction subsequently proved that the Home presentation returned to Plexamp's per-section defaults while the owner's existing Home order and hidden/visible choices remained unchanged.

The historical compact `:c` LevelDB lead remains classified as historical/deleted residue, not a Reset authority.

### Full Home-customisation reset — native rebuild and persistence-authority investigation

The owner's suggestion to let Plexamp rebuild Home rather than replaying a copied baseline remains the preferred investigation path, but the persistence boundary is now explicitly **unclassified**.

A genuinely fresh disposable Chromium profile was launched with loopback-only DevTools on port 9224. Read-only runtime probes established:

- before Plex authentication/library selection, `rootStore.discovery` existed but its backing hub collection contained **0 hubs**;
- after signing in, selecting the intended library and making **no Home customisation**, the same profile contained **12 effective discovery hubs**;
- the visible untouched Home also contained **12 sections**;
- the narrow live authority is `rootStore.discovery.$mobx.values.hubs.value.$mobx.values`;
- those hub objects expose consistent logical shapes without requiring ACP to supply a copied template.

The important interpretation is that the pre-login 0-hub state is **not** a factory Home target. It is an unresolved account/library context. The useful positive evidence is the automatic 0 → 12 transition after account/library context became available.

The Local Storage investigation then established a separate and equally important persistence result:

- the untouched authenticated/library-selected 12-section Home had **zero** keys beneath `mmkv.default\discovery:customizations:*`;
- moving the default **Mixes for you** section down two places created no key-family delta there;
- the moved order survived a normal page refresh while the namespace remained empty;
- after fully exiting disposable Chromium, confirming the loopback DevTools endpoint had disappeared, and relaunching the **same disposable profile**, Mixes remained in the moved position;
- the same key-family probe still reported 0 `order`, 0 `hidden`, 0 `viewSettings`, 0 `editing`, 0 `customHubs`, 0 `other`, 0 contexts and 0 structurally invalid keys.

Therefore the known `mmkv.default\discovery:customizations:*` Local Storage family is **not the complete Home persistence authority**. The order change is durable browser-profile state rather than merely live MobX/session state, but its durable owner is not yet classified. IndexedDB or another browser-local persistence mechanism is a candidate, not a conclusion.

This also changes how the previously accepted Backup/Restore evidence must be interpreted: the real Local Storage `order`/`hidden` records observed and round-tripped on the commissioned profile remain valid evidence for that profile/state, but they are no longer assumed to be Plexamp's only or universal order/visibility representation.

The revised preferred full-reset architecture is therefore:

1. preserve authentication/session and selected library;
2. preserve the commissioned player name and managed audio output through their existing owner;
3. classify the **complete bounded Home-owned persistence authority** rather than assuming the known Local Storage family is exhaustive;
4. do **not** directly clear, populate or otherwise mutate `rootStore.discovery`'s transient hub array;
5. only after classification, capture the exact pre-reset state of narrowly proven Home-owned records for rollback;
6. remove/reset only those Home-owned records;
7. trigger the narrowest proven Plexamp Home reload/re-fetch mechanism, with a local page reload acceptable only if it is the safest proven trigger;
8. allow Plexamp to regenerate the effective Home from its own runtime sources;
9. verify the rebuilt logical Home and continued login/library state before finalising the rollback snapshot.

A production full-Home Reset **must not** simply delete the previously known Local Storage `order`/`hidden`/`viewSettings` families and claim completeness.

#### Current bounded browser-storage diagnostic

`scripts/inspect-plexamp-browser-storage.py` is a disposable-profile-only metadata diagnostic intended to classify the next persistence surface without reading stored user data or changing browser state.

It reports only:

- bounded Local Storage key-family counts, using key names only;
- bounded Session Storage key-family counts, using key names only;
- IndexedDB database metadata and object-store names.

It explicitly does **not**:

- call Web Storage `getItem()` or mutate Web Storage;
- open IndexedDB transactions;
- access object-store records, cursors, `get()`/`getAll()` data or values;
- accept arbitrary JavaScript, expressions or URLs;
- target the production kiosk profile.

For IndexedDB, it uses `indexedDB.databases()` to enumerate existing databases and opens an already listed database **without supplying a version** only long enough to read `objectStoreNames`, then closes it. It does not request a schema version, create/upgrade schemas, or open a transaction. Sensitive-looking metadata names are redacted and all inventories are bounded. Merely seeing an IndexedDB database/object-store name will not prove Home ownership; it will only identify a candidate surface for a still-narrower comparison.

The next disposable-profile sequence is now:

1. keep **Mixes for you** in its moved third-place tracer position and make no other Home changes;
2. run the bounded browser-storage metadata probe;
3. use that current metadata inventory only to identify candidate persistence surfaces; because there is no pre-edit baseline from this broader probe, do not attribute the order change from a single inventory alone;
4. if necessary, design a still-narrower read-only comparison or a second genuinely fresh disposable-profile baseline that exposes shapes/counts rather than auth/session/user values;
5. classify order ownership before changing visibility, presentation or custom sections;
6. only after all Home-owned persistence is bounded, build a disposable-only reversible scrub/rebuild experiment;
7. prove exact rollback restores the pre-scrub Home customisation if a later Reset participant fails.

Only if that passes should the production Home owner expand beyond the currently accepted presentation-only boundary. Authentication/session/browser databases unrelated to Home and unrelated caches remain out of scope throughout.

## Browser isolation

The production bridge remains deliberately narrow:

- Manifest V3;
- one isolated content-script entry (`content.js` + `reset.js`);
- matches only `http://localhost:32500/*` and `http://127.0.0.1:32500/*`;
- no extension `permissions` or `host_permissions`;
- no background worker;
- no cookies authority;
- no remote-debugging interface;
- `native-reset.js` is one loopback-scoped packaged web-accessible resource injected into Plexamp's page world by the isolated bridge.

No generic page-execution surface is exposed. The temporary DevTools probes used during the full-Home investigation are **developer diagnostics for the disposable Chromium profile only** and are not part of the production bridge or kiosk launch.

## Combined transaction sequencing

The browser and server owners cannot share one storage engine, so Reset composes retained rollback boundaries:

1. Preview obtains ACP/commissioning, native Plexamp and Home-presentation plans without mutation.
2. Review performs a fresh Preview and binds confirmation to fresh tokens/fingerprints.
3. Confirm applies native Plexamp settings/player volume when required and retains native rollback state.
4. It applies Home presentation `viewSettings` when required and retains exact Home rollback state.
5. Before server mutation, a fresh server Preview must still match the reviewed **ACP-only** owner token. Changes made legitimately by native Plexamp Reset to Headless preferences do not invalidate this ACP hand-off token.
6. The server executor still uses its separately retained broader #90 `restore_preview_token` to apply/verify the current ACP target, and commissioning uses its own fingerprint.
7. Only after all required participants succeed are browser rollback snapshots finalized.

If any browser participant fails, earlier browser work rolls back. If the later server transaction or hand-off check fails, retained browser owners roll back before failure is reported.

This complete sequence, including the corrected ACP-only hand-off, has passed on the commissioned Pi. Any future full Home-customisation owner must fit the same retained-rollback transaction model; the disposable experiment does not change production sequencing yet.

## Automated evidence and remaining gate

The combined production implementation was automated-green through **Tests #4575** on `07fec02c85a6871cc3a74160b7cd029ff7736f2c`: compile, JavaScript/page-wiring, shell checks and **1029 tests passed** in 53.364s.

The regression specifically proves that changing portable Plexamp Headless state and the underlying #90 restore token does **not** change `owner_tokens.a_clockwork_plex`, while an actual ACP-state change does. The complete reset token still changes with the broader server state, so the real apply boundary remains stale-protected.

The Home diagnostics now have separate bounded purposes:

- `inspect-plexamp-home-runtime.py` — broad live names/shapes discovery;
- `inspect-plexamp-home-hubs.py` — narrow effective discovery-hub shapes;
- `inspect-plexamp-home-customizations.py` — known Home Local Storage key-family names/counts only;
- `inspect-plexamp-browser-storage.py` — broader browser persistence **metadata only**, with no Web Storage values or IndexedDB records/transactions.

Physical evidence through 5 September 2026 now establishes:

- ACP Reset/rollback and presentation are accepted;
- commissioning rename/output round-trip is accepted;
- the native runtime fail-closed path established `global.app.rootStore.settings` as the live Plexamp settings authority;
- the real Home `viewSettings` family is classified on the commissioned profile;
- the earlier full-state Review reached **Ready to confirm** with 20 server-owned, 16 native Plexamp and 14 Home-presentation changes;
- the first full Confirm exposed the old false-stale ACP hand-off and physically proved browser-native/Home rollback;
- after the ACP-only token correction, the full multi-owner Confirm completed successfully;
- Plexamp player volume became 100%;
- Home presentation returned to Plexamp defaults while order and visibility were retained;
- ACP EQ became 0/0/0 dB and Music Master/Plexamp trim/AirPlay trim/Maximum Alarm Volume all became 100%;
- post-reset native diagnostics converged from `activeTab` + `equalizerPresets` + `showFullScreenPlayerOnStart` to only `equalizerPresets`, which is now classified as runtime-normalised state;
- regression coverage simulates that preset-catalogue repopulation and proves it no longer creates a false Reset difference while exact rollback still retains it;
- the AirPlay session-start baseline correction is 100%, matching the owner's intended full-scale baseline;
- a fresh disposable Chromium profile physically rebuilt its effective discovery hubs from **0 before login/library context to 12 after login/library selection with no Home edits**;
- the untouched 12-section Home required zero keys in the known Local Storage Home namespace;
- moving Mixes for you persisted across both page refresh and a full disposable Chromium process restart while that namespace remained empty.

The remaining acceptance is deliberately narrow:

1. get the broader browser-storage metadata probe candidate green in CI;
2. classify the durable Home order persistence authority before making more Home edits;
3. continue the one-change-at-a-time investigation only after that owner is understood;
4. build and physically prove the reversible full-Home scrub/rebuild path only after the complete Home-owned persistence surface is bounded;
5. decide from that evidence whether full Home structure belongs in #93 or a tightly scoped follow-up; presentation-only Reset is already physically accepted;
6. pull/reboot the eventual final accepted production head so the packaged bridge and corrected config are current;
7. confirm a fresh production Preview no longer reports `equalizerPresets`;
8. if the commissioned Pi is ever at the short-lived 10% AirPlay start value, ACP Preview should offer one change back to **100%**; apply it and verify AirPlay session-start volume and persistent AirPlay trim are both 100%;
9. keep the Home `viewSettings` backup/restore completeness gap and the newly exposed order-authority completeness gap open until implemented or explicitly deferred;
10. obtain explicit owner acceptance before PR #9 leaves Draft or merges.