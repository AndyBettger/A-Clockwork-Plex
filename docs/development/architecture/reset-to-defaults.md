# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** remains **physical acceptance open** only for the final combined Plexamp-native/Home path.

The commissioned 1280×720 Pi has already physically proved:

- the core **A Clockwork Plex reset transaction**;
- the final guided **Preview → Review → Confirm** presentation;
- the separate same-appliance **Plexamp commissioning Reset** for player name and managed audio output.

On 2 September 2026 the corrected ACP reset repeatedly applied and verified **27 supported changes**. The first physical pass exposed the real ALSA Music Master round-trip boundary: the nominal 80% request quantises through the existing integer softvol mapping and reads back as **79%**, so Reset now targets that physically observable value.

On 3 September 2026 the commissioning owner was physically accepted. A deliberate temporary player rename plus selection of **Follows system output** produced two commissioning differences; Reset restored the original commissioned player name and the managed **`A Clockwork Plex - Plexamp`** output without exposing the name values or device UUID in Preview.

A later disposable Chromium-profile investigation established Plexamp's real native reset semantics:

- a fresh browser profile signed into the same account/library shows Plexamp's genuine default Home, proving the commissioned Home layout is browser/device-local rather than account-synchronised;
- **Debugging → Reset to Defaults** restores ordinary Plexamp settings while preserving login and selected library;
- **Home Screen → Reset order** restores Plexamp's default Home ordering;
- Reset order alone does **not** restore deliberately hidden Home sections.

The branch now implements those semantics through a bounded native settings owner plus a bounded Home order/visibility owner. The exact code-side candidate `fe2409f36584d360afc05c474bfbea6e8ff4657a` passed **Tests #4506: 1027 tests in 51.242s, `OK`**, with Python compile, direct JavaScript syntax/page-wiring, shell, extension-security and unit-test gates green.

The remaining #93 gate is therefore physical verification of the **combined native Plexamp settings + Home order/visibility Reset** on the commissioned appliance. Until that passes, PR #9 remains Draft and must not be merged.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing path is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Ordinary unsaved Settings changes block Preview/Apply so Reset cannot silently overwrite staged work.

The current Reset has four deliberately separate participants:

1. **A Clockwork Plex** — always selected; resets supported ACP user configuration through the existing server-side transaction.
2. **Plexamp commissioning** — same-appliance owner for the commissioned `playerName` and managed audio output only.
3. **Plexamp native settings** — uses Plexamp's own `resetToDefaults()` authority for ordinary Plexamp settings while explicitly preserving ACP-owned Headless preferences and leaving commissioning identity to participant 2.
4. **Plexamp Home** — resets the bounded browser/device-local Home order and visibility records that physical testing associated with Plexamp's native Home reset behaviour.

Portable Backup & restore remains a different ownership model. A value can be **nonportable** yet still have a legitimate same-appliance Reset owner. `playerName` and `audioDeviceUuid`, for example, remain excluded from backup files even though the local commissioning owner can return them to this appliance's commissioned state.

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

Reset therefore targets the **observable physical default** of 79% for Music Master while retaining 100% for Plexamp, AirPlay and Alarm. Regression coverage calls the real restricted mixer conversion helper so this hardware-facing contract cannot silently drift.

The commissioned-Pi corrected reset has completed successfully more than once and reported:

> Reset complete — Selected reset completed and verified. 27 changes applied across A Clockwork Plex.

### Alarm sound safety switches

The two alarm-audio arming controls — `alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` — are **preserved deliberately**.

They are safety arming state rather than portable appliance personality. Reset therefore never silently arms or disarms scheduled alarm sound. Alarm schedules and their ordinary user choices can return to defaults while the owner's existing sound-safety state remains unchanged.

Alarm hardware/ALSA/helper fields are also outside the reset target.

## Plexamp commissioning reset owner — PHYSICALLY ACCEPTED

`app/plexamp_commissioning.py` is the separate appliance-local owner. `scripts/commission-plexamp.py` is its setup-owned command surface.

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

For a fresh appliance, the player name entered during the interactive Plexamp claim becomes the baseline when `setup.sh` subsequently completes commissioning. Once captured, ordinary repeat `bash setup.sh` runs **do not replace that baseline** merely because the player has since been renamed.

For an appliance installed before this owner existed, baseline migration is deliberate rather than implicit: run `bash setup.sh` once while Plexamp has the intended long-term commissioned player name.

### Managed audio output

The audio route is not stored as a baseline UUID. Each commission/Reset operation asks Plexamp for its live output/device catalogue and requires exactly one device whose display label is:

```text
A Clockwork Plex - Plexamp
```

The owner uses that live device's UUID for the scoped `audioDeviceUuid` write. Missing or ambiguous matching devices fail closed. `Follows system output` remains a normal Plexamp choice but is not the supported commissioned target.

### Physical evidence

On 3 September 2026 the real appliance proved the complete commissioning round-trip:

- one-time baseline capture succeeded;
- the managed output was dynamically resolved and selected;
- an immediate plan reported zero differences;
- a temporary player rename plus **Follows system output** produced exactly two differences;
- Settings Reset Preview exposed only `plexamp.commissioning.player_name` and `plexamp.commissioning.audio_output`, never the actual names or UUID;
- Reset completed and verified both changes;
- Plexamp directly showed the intended commissioned player name and **`A Clockwork Plex - Plexamp`** output afterwards.

This participant is therefore **physically accepted**.

## Plexamp native ordinary-settings reset owner

`browser/plexamp-bridge/native-reset.js` owns ordinary Plexamp application settings.

Physical disposable-profile testing established that Plexamp's own **Debugging → Reset to Defaults** is the correct semantic authority for ordinary Plexamp settings. The implementation therefore calls the same in-application `settings.resetToDefaults()` method rather than maintaining an ACP-authored table of guessed Plexamp defaults.

### Page-world boundary

The live Plexamp settings object belongs to Plexamp's page JavaScript world. ACP reaches it without broadening the extension's privileges:

- the existing Manifest V3 bridge still has exactly one isolated content-script entry: `content.js` + `reset.js`;
- the extension remains limited to `http://localhost:32500/*` and `http://127.0.0.1:32500/*`;
- it has no `permissions`, no `host_permissions`, no background worker, no cookie authority and no remote-debugging interface;
- `native-reset.js` is exposed as one loopback-scoped packaged web-accessible resource;
- the isolated reset bridge injects that one packaged script into the Plexamp page world.

The native owner locates the live Plexamp settings store from Plexamp's already-loaded webpack runtime and never sends raw setting values back to ACP.

### Read-only Preview

Preview constructs a fresh instance of the live settings class and compares bounded ordinary settings against that instance. Public output contains only:

- status;
- whether reset work exists;
- a change count;
- a short state fingerprint.

It deliberately excludes commissioning identity and the eight protected Headless preferences described below, so those values neither appear in the native change count nor become native Reset targets.

### Apply, verification and rollback

Apply requires the exact Preview fingerprint and explicit confirmation. A stale fingerprint refuses before mutation.

The native owner then:

1. captures a bounded exact pre-reset settings snapshot for rollback;
2. captures the eight protected Headless values and their presence/absence state;
3. calls Plexamp's own `settings.resetToDefaults()`;
4. immediately restores and verifies the eight protected Headless values;
5. verifies that the remaining Reset-owned ordinary settings now compare equal to a fresh Plexamp settings instance;
6. retains a rollback token until the complete outer #93 transaction succeeds.

If native verification fails, the pre-reset snapshot is restored. If a later Home/server participant fails, the outer Reset client uses the retained native rollback token before reporting failure.

`playerName` and `audioDeviceUuid` are intentionally allowed to take Plexamp's native defaults during this participant. They are not counted here and are subsequently returned to the physically accepted appliance values by the separate commissioning owner before the complete Reset can succeed.

## Protected Plexamp Headless preferences

The eight approved Headless scalar preferences discovered at checkpoint #88 remain a separate **portable Backup/Restore** owner and are deliberately preserved by ordinary #93 Reset:

| Preference | Current commissioned value | #93 native Reset |
| --- | ---: | --- |
| `audioConversionBitrate` | `256` | Preserved and re-applied |
| `autoPlayEnabled` | `false` | Preserved and re-applied |
| `cacheSize` | `32768` | Preserved and re-applied |
| `cachingWiFi` | `10` | Preserved and re-applied |
| `loudnessLeveling` | `false` | Preserved and re-applied |
| `precacheNetworkSpeed` | `0` | Preserved and re-applied |
| `sampleRateConversionQuality` | `4` | Preserved and re-applied |
| `sampleRateMatching` | `2` | Preserved and re-applied |

These values are the **current commissioned values and supported backup/restore allow-list**, not a claim that they are Plexamp factory defaults.

Calling Plexamp's native `resetToDefaults()` without this boundary could silently consume later high-resolution/audio policy work. The native owner therefore snapshots these eight immediately before Plexamp's reset, restores them immediately afterwards and verifies them before native Reset can report success.

`premium` remains account/capability-derived and excluded. Unknown Headless preferences are not promoted into ACP's portable ownership merely because the native settings object can see them.

## Plexamp Home reset owner

The existing browser bridge remains scoped to the physically classified Home Local Storage families:

- `mmkv.default\\discovery:customizations:<context>::/library/sections/<id>:order`
- `mmkv.default\\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden`

The final Reset owner additionally recognises the exact legacy keys used by Plexamp's Home customization layer:

- `mmkv.default\\discovery:customizations:order`
- `mmkv.default\\discovery:customizations:hidden`

It does not generalise to arbitrary `discovery:` data.

### Why this differs from the first Home experiment

The first commissioned-Pi experiment proved that merely deleting a newly created current-context `order`/`hidden` delta could return Plexamp to the owner's already-configured browser baseline rather than the original Plexamp Home. That correctly disproved the earlier claim that “no current-context override” always meant “factory Home”.

A later **disposable fresh Chromium profile** resolved the missing semantic question without risking the commissioned profile:

- same Plex account and selected library + fresh browser profile produced Plexamp's default Home, including `Mixes for You` first;
- therefore the commissioned Home baseline is browser/device-local rather than account-synchronised;
- Plexamp's native **Reset order** restores that default order;
- a deliberately hidden section remains hidden after Reset order, proving visibility needs a separate reset step.

The current bounded owner therefore resets both order and visibility records, including the exact legacy order/hidden records, rather than equating one current-context deletion with the whole factory semantic.

### Safety and rollback

The isolated bridge enumerates Local Storage **key names** and calls `getItem()` only after a key matches the exact reset/restore classification. It does not open auth/session, cache/resource or editor values.

Home Preview reports only bounded record counts plus a fingerprint. Apply requires the fresh fingerprint and explicit confirmation, captures exact raw record bytes, deletes only the classified order/hidden records, verifies their absence and retains exact rollback state until the outer Reset finalizes.

Synthetic regressions cover:

- modern current-context order + hidden reset;
- exact legacy order + hidden reset;
- stale-target refusal before mutation;
- exact raw rollback after injected failure;
- preservation of unrelated auth/cache/editor state;
- ambiguous modern-context refusal.

### Compact `:c` historical lead

Earlier LevelDB inspection had exposed a historical key-shaped residue ending in `:c`. A later live key-name-only probe found no matching live Local Storage key while the configured Home remained visible. Its value was never opened.

That lead remains classified as **historical/deleted LevelDB residue, not a live Reset authority**.

## Combined transaction sequencing

The browser and server owners cannot share one storage engine, so #93 composes them with retained rollback boundaries rather than pretending they are one database transaction.

The guided flow is:

1. **Preview** obtains the server ACP/commissioning plan plus native Plexamp and Home plans; no participant mutates state.
2. **Review reset** performs a fresh Preview and binds the confirmation UI to those fresh owner fingerprints/tokens.
3. **Confirm & reset** first applies native Plexamp ordinary settings when required and retains its rollback token.
4. It then applies Home order/visibility when required and retains its exact raw rollback token.
5. Before any server mutation, the client obtains a fresh server Preview and requires the reviewed ACP owner token to still match. Any intervening ACP/commissioning change causes refusal rather than applying against stale state.
6. The server applies the existing ACP + commissioning transaction. Its own owners verify and roll back their state on failure.
7. Only after all required server/browser participants report success are the retained native/Home rollback snapshots finalized and discarded.

If a browser owner fails, any earlier browser owner is rolled back. If a later server owner fails, the browser owners are also rolled back before the UI reports failure. The server transaction separately restores its own captured ACP/commissioning pre-state.

This keeps the user-facing product at **one Preview, one Review and one final confirmation** while preserving each storage owner's truthful verification/rollback boundary.

## Always-preserved ownership

A normal #93 Reset keeps all of the following intact:

- Weather Underground API key and other managed credentials;
- Plex/Plexamp login, claim, authentication and browser session state;
- selected Plex account/server/library state;
- the eight supported Headless portable preferences listed above;
- alarm sound master/scheduled safety arming switches;
- DAC, ALSA and installer-owned hardware/topology configuration;
- installed runtimes, systemd units, sudo policies and appliance service ownership;
- Weather/News downloaded caches, rainfall history and other runtime/history state;
- Chromium profile data outside the narrowly classified Plexamp Home reset records;
- unknown/unclassified Plexamp browser/Headless state that has not been deliberately promoted to a Reset owner.

The player label and managed Plexamp output selection are not “always preserved” when the commissioning baseline exists; they are deliberately returned to that appliance-local commissioned state.

A deeper decommissioning/factory-wipe operation is a different product and is not implied by Reset to defaults.

## Reset presentation evidence — PHYSICALLY ACCEPTED

The first physical layout pass exposed that Reset reused Restore component markup without an equivalent Reset layout scope. A dedicated `settings-reset-defaults.css` fixed the overlapping/crowded target and status presentation.

A second physical pass exposed a separate CSS specificity bug: a Reset `.settings-card { display: grid; }` rule overrode the browser's native `[hidden]` behaviour, causing an empty Preview card before Preview was requested. The stylesheet now explicitly protects the hidden contract.

A later 1280×720 pass exposed the commissioning-integrated Review card consuming too much width and compressing **Ready to confirm** into a word-per-line column. The repaired two-column review layout was physically rechecked on exact head `d8282a348cc701db1264a06b9abfcc46968d47d9` and accepted.

The accepted hierarchy remains:

**Preview result → Review reset action + Ready-to-confirm status → full-width Final confirmation card**

The native/Home participants reuse that same presentation and do not introduce additional confirmation products.

## Automated evidence

Important recent green gates:

- `526f580a4802c7c20dd00c96ab63b97a03d5122c` — **Tests #4468: 1006 tests, `OK`**; exact source physically rechecked for ACP Reset presentation.
- `fc1c9462957a6533e833a53d6d61e6453e133c14` — **Tests #4479: 1023 tests, `OK`**; commissioning implementation/catalogue baseline.
- `d8282a348cc701db1264a06b9abfcc46968d47d9` — **Tests #4490: 1025 tests in 41.235s, `OK`**; presentation reaccepted and commissioning physical acceptance subsequently completed.
- `b46209a3d250cc597e9c08d2b26e893dab62306e` — **Tests #4502: 1027 tests, `OK`**; isolated page-world native injection contract plus native/Home owner regressions.
- `fe2409f36584d360afc05c474bfbea6e8ff4657a` — **Tests #4506: 1027 tests in 51.242s, `OK`**; exact native/Home code candidate with direct syntax/wiring checks and explicit preservation of all eight Headless portable preferences.

The final native/Home automated coverage now includes:

- native comparison against Plexamp's own settings-class defaults;
- stale native fingerprint refusal;
- native retained rollback/finalize contract;
- all eight Headless values excluded from native change count and re-applied after `resetToDefaults()`;
- modern + legacy Home order/visibility reset;
- exact Home raw-state rollback;
- auth/cache/editor preservation;
- isolated extension manifest/resource injection security contract;
- ACP/commissioning token revalidation before server mutation;
- browser-owner rollback when a later participant fails.

## Physical acceptance gate — OPEN

ACP Reset, its presentation and Plexamp commissioning are already physically accepted. Before checkpoint #93 can close, the final native/Home candidate must be tested on the commissioned Pi:

1. pull the exact final docs-synchronised candidate and **fully restart Chromium/the kiosk** so the changed extension is reloaded;
2. record the current eight protected Headless values before mutation;
3. obtain Reset Preview and confirm only bounded counts/paths are exposed — no Plex credentials, player-name values, device UUID or raw Home values;
4. make harmless deliberate deviations in ordinary Plexamp settings, Home ordering and Home visibility; optionally repeat the already-accepted player-name/output deviation as an integration check;
5. Review → Confirm & reset;
6. verify Plexamp remains signed in with the selected library, ordinary settings return to Plexamp defaults, Home returns to the default order, the deliberately hidden section is visible again, the commissioned player name/output are correct, and all eight protected Headless values are unchanged;
7. confirm normal playback and dashboard navigation;
8. run a fresh Preview and confirm zero differences for the native Plexamp, Home and commissioning participants; when ACP is also intentionally left at shipped defaults, confirm zero ACP differences too.

Only after those physical checks and explicit owner approval can #93 move to **COMPLETE**, PR #9 leave Draft, and the next high-resolution-audio roadmap item begin.
