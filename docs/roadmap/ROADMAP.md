# A Clockwork Plex Roadmap

**Last updated:** 11 September 2026  
**Active integration branch:** `develop`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This began as the EQ/audio-installer roadmap. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation/release/future-product roadmap. Detailed engineering chronology belongs in development/history documents rather than burying the useful current plan.

Specialist authorities:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership and Home completeness;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and physical/product gate;
- [`../development/architecture/bbc-news.md`](../development/architecture/bbc-news.md) — #92 BBC News plus the physically accepted article-QR hand-off follow-up;
- [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md) — queued resilience design.

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not this development roadmap.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop`.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- the next release version is intentionally not assigned until its real scope is clear.

## Current development cycle

### #84 Development-cycle bootstrap — COMPLETE

- [x] Created `develop` from the post-v0.4.0 baseline.
- [x] GitHub Actions validates `develop` and `main`.
- [x] Established the feature-branch → `develop` → accepted release model.

### #85 High-resolution audio feasibility audit — COMPLETE; implementation queued

The current managed EQ and Direct/fallback profiles still use a fixed **S16_LE / 44100 Hz** shared music path. The Settings/appliance-ownership engineering track (#88–#93) is now physically complete **and integrated into `develop`**, and the bounded #92 article-QR follow-up is physically accepted. High-resolution implementation is therefore the next major product feature.

Before production mutation, use `scripts/audio/preflight-eq.sh` as the **read-only bedroom-Pi validation gate**. The **accepted production SD remains protected**; **a separate spare SD is the disposable acceptance target** for destructive route/lifecycle experiments.

Accepted constraints:

- AirPlay compatibility must remain truthful to the received source format;
- scheduled-alarm takeover, Maximum Alarm Volume and recovery are non-negotiable;
- bypass/native/bit-perfect claims must be based on measured ALSA/DAC state;
- appliance reliability outranks a bit-perfect badge.

### #86 Friendly forecast-location entry — COMPLETE

- [x] Read-only town/city/postcode lookup using Open-Meteo plus Postcodes.io fallback for full UK postcodes.
- [x] Friendly location stages exact forecast coordinates while retaining precise manual latitude/longitude fallback.
- [x] Physical Milland and `GU30 7JS` tests passed.

### #87 WU supplemental indoor expiry — COMPLETE

- [x] Stale Ecowitt indoor supplementation expires while WU outdoor observations remain live.
- [x] Weather removes expired indoor values; Clock retains paired geometry with placeholders.
- [x] Re-enabling Ecowitt restores indoor data without service restart.

### #88 Configuration ownership and backup-format audit — COMPLETE

- [x] Portable ACP settings are a normalised logical model, never raw `config.json` bytes.
- [x] Credentials/auth/session, hardware identity/topology, raw ALSA, caches and machine identity are excluded.
- [x] Exact eight-value Plexamp Headless portable allow-list established: `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `cachingWiFi`, `loudnessLeveling`, `precacheNetworkSpeed`, `sampleRateConversionQuality`, `sampleRateMatching`.
- [x] `playerName` and `audioDeviceUuid` classified nonportable.
- [x] Plexamp Home browser-local persistence families physically classified without treating the Chromium profile as a backup unit.

### #89 Configuration backup/export — COMPLETE

- [x] Schema-v1 backup/export physically accepted.
- [x] Export contains normalised ACP settings, logical EQ/mixer, exact eight typed Headless preferences and logical Home order/hidden choices.
- [x] Credentials, browser auth/session, player/device identity, hardware topology and runtime/cache state excluded.
- [x] Physical export captured **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.
- [x] Fresh-profile #93 evidence independently confirms durable `order`, `hidden`, `viewSettings`, custom-section and custom-title persistence.
- [x] Full Home-v2 logical owner implemented for order/hidden/presentation/custom sections/custom titles without exporting source UUIDs, context IDs, library section numbers or raw browser records.
- [x] Broader native Plexamp settings owner implemented using the proven live settings authority; only classified portable keys are written and global Plexamp Reset is never invoked by portable Restore.
- [x] Clean post-Reset Home target can derive structure/presentation contexts from live Plexamp server/library state even with zero local Home override records.
- [x] Top-level schema-v2 import envelope is explicit: `plexamp.portable_settings` + Home-v2 logical browser preferences. Schema-v1 remains accepted and mixed v1/v2 Plexamp ownership is rejected rather than guessed.
- [x] Schema-v2 validation exposes only safe counts/status, keeps recursive credential/machine-state rejection, and rejects source-bound Home context including `/library/sections/<id>/...` masquerading as a relative custom query.
- [x] Settings-browser orchestration assembles a complete schema-v2 export from the secret-safe schema-v1 ACP server export + live native portability snapshot + live Home-v2 snapshot, replacing rather than duplicating legacy Headless/Home ownership and excluding target fingerprints from the portable file.
- [x] Dedicated `settings-backup-restore.js` now owns the real Settings Backup/Restore page; `settings-about.js` is only the thin Settings bootstrap for that owner.
- [x] Schema-v2 export is wired into the real Settings Backup action with schema-v1 import compatibility and a safe compatibility fallback.
- [x] Production bridge **1.5.0** activates the bounded native/Home-v2 portability transport while retaining #93 Reset assets, loopback-only scope and a permission/background-free extension manifest.
- [x] Automated gates: native **Tests #4671**; Home-v2/full catalogue **Tests #4675**; schema-v2 validator **Tests #4680**; JavaScript query hardening **Tests #4681**; direct Python/JavaScript parity **Tests #4682**; dormant dual-owner transport **Tests #4688**; complete dormant export/transaction orchestration **Tests #4691**; cross-owner v2 stale-token boundary **Tests #4694**; result-counter refinement **Tests #4695**; dedicated Settings-controller contract **Tests #4697**; activated Settings ownership/full suite **Tests #4701** on `bb47c8543ae9fe3d6abd2d4eb38c0d9dd66236ff`; bridge-activation safety/full suite **Tests #4704** on `6a212689cd42dd96edcaf4e2869df51cde231689`.
- [x] Commissioned-Pi bridge-activation gate passed on `fb5e77c3a3c8caf6e23ab9def68110dd9636be5e`: repeat `bash setup.sh` converged with `APPLIANCE_VERIFY=PASS` (0 failures / 0 warnings), preserved commissioned Weather Underground/EQ/Plexamp state, and a genuine reboot returned a normal dashboard/Plexamp kiosk.
- [x] Post-reboot production proof confirmed bridge **1.5.0** resources, dedicated `a-clockwork-plex/chromium-profile`, repository `--load-extension` wiring, and **no Chromium remote-debugging flags**; a fresh whole-appliance verifier again passed 0/0.
- [x] Complete schema-v2 export physically accepted on the commissioned Pi after a full-order specimen exposed and then closed a target-scoped Recent Played portability leak. The accepted re-export carries the logical `target-library.music.recent.played` marker, no source context/hash or raw library-section path, the full 13-entry logical Home order, hidden/presentation/custom-title/custom-section state, six native Plexamp deviations and the deliberate ACP/EQ/mixer/AirPlay specimen.
- [x] A second real-use export from the owner's preferred configuration also passed structural/portability inspection: schema-v2, 11 native Plexamp deviations, 15-entry logical Home order, 15 presentation records, three custom Home sections/titles, source-free Recent Played remapping and no credential/auth export.

### #90 Configuration import/restore — COMPLETE

- [x] Read-only parse/validate/Preview with paths/counts rather than values.
- [x] Stale-protected ACP Settings/EQ/mixer restore with reverse rollback.
- [x] Exact-version eight-value Plexamp Headless restore through the restricted schema-v1 owner.
- [x] Target-context-aware schema-v1 Home order/hidden restore with exact local write rollback.
- [x] Guided **Preview → choose ACP / Plexamp / both → Review → Confirm & restore** presentation physically accepted at 1280×720.
- [x] Final combined physical restore converged to zero differences for the supported schema-v1 scope.
- [x] New native portability owner has fresh schema/target fingerprints plus retained rollback/finalize and touches only classified portable settings.
- [x] New Home-v2 owner remaps target context/library/fresh custom IDs, verifies logical convergence despite changed physical IDs, and retains exact rollback/finalize.
- [x] Home-v2 fails closed on active editing, unknown families, malformed wrappers, dangling/wrong-source custom records, invalid presentation/title/query state, unavailable target capability and stale Apply/Rollback.
- [x] Schema-v2 server validation is backward compatible with v1, rejects ambiguous mixed ownership, validates native/Home logical shapes without reading raw browser state and keeps Preview browser-owned comparison deferred to the live owners.
- [x] Server and Home-v2 owner independently reject source-library-bound custom queries; relative `/all?...` style queries remain portable.
- [x] V2 transaction integrates native → Home → server with browser rollback tokens retained until every selected participant commits, and finalizes them only after successful server verification.
- [x] Injected-failure automation proves a later server failure rolls Home then native back in reverse order; Home/stale failures after native also restore native before returning, browser-only restores do not enter the server participant, and post-commit finalize trouble is reported as cleanup warning rather than a false restore failure.
- [x] Schema-v2 server stale protection no longer fingerprints the legacy Headless observer/capability participant, so legitimate browser-owned native changes before ACP cannot create a false stale conflict; schema-v1 keeps its original Headless stale protection.
- [x] The automated-green v2 transaction is wired into the real Settings **Preview → choose target → Review → Confirm** path while old schema-v1 backups retain their accepted compatibility path.
- [x] Production bridge **1.5.0** loads `portability.js` plus only the bounded `native-portability.js` and `home-portability-v2.js` page-world resources alongside the existing Reset bridge; no extension permissions, host permissions, background authority, DevTools or remote-debug surface were added.
- [x] **Tests #4704** passed the complete bridge-activation gate on `6a212689cd42dd96edcaf4e2869df51cde231689`: compile, JavaScript/page wiring/shell checks, activation/security guards, #93 Reset/commissioning regressions and full unit/regression suite all green.
- [x] Commissioned-Pi repeat-install + genuine-reboot precondition passed on `fb5e77c3a3c8caf6e23ab9def68110dd9636be5e`; bridge 1.5.0 is physically loaded by the normal production kiosk with no remote-debugging interface and the post-reboot appliance verifier is green.
- [x] Canonical schema-v2 physical restore specimen accepted before Reset: Crimson Glow, EQ +2/-1/+1.5 dB, persistent mixer 79/89/93/63%, AirPlay start 74%, six native deviations and full logical Home-v2 state including source-free target-library Recent Played remapping.
- [x] Accepted #93 Reset Preview physically passed against that specimen: **26 server-owned + 7 Plexamp native + 5 Home = 38 selected changes**, no warning/incomplete state, commissioning already matched the captured player-name baseline and managed output, and Preview remained read-only.
- [x] Commissioned-Pi **Review → Confirm reset → post-Reset verification → schema-v2 Preview → Review → Confirm restore → convergence** passed. Reset returned the appliance to verified baselines while preserving login/library/commissioning; Restore applied **33 changes** (26 ACP + 6 portable Plexamp settings + 1 logical Home change); the same backup then Previewed at **0 changes**.
- [x] Long Restore technical paths now wrap within the 1280×720 Preview detail column rather than overflowing the viewport; physical follow-up passed and **Tests #4723** passed the corresponding layout/catalogue regression on `e42a35d08b3aedbb10aa79a094c9a9ec7a287f94`.
- [x] A second real-use round trip using the owner's preferred configuration passed: after verified Reset baselines, the inspected schema-v2 backup Previewed **30 changes** (18 ACP + 11 portable Plexamp settings + 1 logical Home change), Review remained current, Confirm restored both ACP and Plexamp, and the same backup then reported **“No supported portable settings differ” / 0 selected**.

The accepted schema-v1 compatibility flow still applies Home before the later server stage and does not retain a browser rollback token across a successful Home write followed by a server failure. That limitation is deliberately preserved only for old schema-v1 files. **Schema-v2 #89 Backup/export and #90 Restore are both physically accepted on the commissioned Pi.**

### #91 Touchscreen Plexamp text entry — COMPLETE

- [x] Shared Settings keyboard uses true one-shot Shift and theme-aware presentation.
- [x] Plexamp Search keyboard/bridge physically accepted.
- [x] General Plexamp text fields physically accepted for Home title, Smart Playlist name/description, Home Screen section title and Player Name.
- [x] Bridge remains permission-free, loopback-only and excludes login/password fields.

### #92 BBC News — COMPLETE; ARTICLE QR FOLLOW-UP PHYSICALLY ACCEPTED

- [x] BBC RSS-only feed/cache authority for Top Stories, UK, World, Science and Technology.
- [x] `/api/news` public story model remains link-free; no outbound article navigation from kiosk Chromium.
- [x] Last-good cache, stale/degraded presentation and Top Stories ticker physically accepted.
- [x] Settings, News page, touch scrolling, startup/idle-return and Wi-Fi-loss recovery physically accepted.
- [x] Article hand-off retains the absolute HTTPS destination supplied by the fixed BBC RSS item in the private cache, using `<link>` first and a valid HTTPS `<guid>` fallback; there is deliberately no `/news/` path restriction.
- [x] QR SVG is generated locally on the appliance; no third-party QR service receives the selected article URL and the browser accepts no arbitrary URL-to-QR input.
- [x] Touch detail modal shows the QR hand-off only after a valid local QR loads; a missing/rejected article link leaves the existing local story detail intact.
- [x] Initial automated compile, JavaScript/page/shell checks and full unit/regression suite passed in **Tests #4732** on `4d38a5d0eb8d69d180b1517c2e910fcc454804a1`; trusted-RSS destination/GUID-fallback refinement passed the complete gate in **Tests #4749** on `40becde8815e5051efc24c61ca50a3abb5806c9c`.
- [x] Commissioned 1280×720 + iPhone acceptance passed on 11 September 2026: repeat `bash setup.sh` converged with `APPLIANCE_VERIFY=PASS` (**0 failures / 0 warnings**), QR codes rendered and scanned from the Touch Display 2, normal BBC News URLs continued to open directly in the installed BBC News iOS app, and the live **“El Niño likely to cause wetter and warmer-than-normal autumn”** BBC Weather destination gained a QR and opened correctly in Chrome; kiosk Chromium retained ACP throughout.

### #93 Reset-to-defaults workflow — COMPLETE

The complete four-owner Reset transaction, bounded full Home customisation Reset, post-reset convergence and zero-change owner-facing presentation are now physically accepted on the commissioned bedroom Pi. The disposable 9230 scrub/rebuild/rollback rehearsal remains the reversible architecture proof.

Repository integration completed on 10 September 2026 in dependency order: **PR #9** (`feature/reset-defaults`) merged into `develop` as `f6ff3291041f6044a3ea89737a8f06bbdb964736`, then **PR #10** (`feature/backup-restore-completeness`) was retargeted to `develop` and merged as `5baddf318d5ecbe66ca68d16e68819448b2dd6bd`. The resulting `develop` push passed **Tests #4728**.

#### Accepted transaction foundations

- [x] ACP Reset target generated from version-controlled defaults through production normalisers.
- [x] ACP stale-preview, verification and rollback semantics physically accepted.
- [x] 1280×720 Preview/Review/Ready/Confirm presentation physically accepted.
- [x] Same-appliance commissioning restores captured Plexamp player name + dynamically resolved **`A Clockwork Plex - Plexamp`** output.
- [x] Plexamp native owner calls real `global.app.rootStore.settings.resetToDefaults()`.
- [x] Plexamp live music-player volume resets to **100%** with verification and exact rollback.
- [x] `equalizerPresets` excluded from native changed-set/fingerprint as runtime-normalised catalogue state while remaining rollback-covered.
- [x] `activeTab` classified as runtime/navigation residue and excluded from the native changed-set/fingerprint through the same runtime-normalised mechanism while remaining rollback-covered.
- [x] ACP EQ returns to 0/0/0 dB; Music Master, Plexamp trim, AirPlay trim, Maximum Alarm Volume and AirPlay session-start volume use the accepted **100%** baseline.
- [x] Full multi-owner Confirm crosses the corrected ACP-only browser/server stale-token boundary successfully.

#### Complete Home persistence classification — CLOSED

Preserved causal specimens:

```text
9224  order tracer
9225  hidden tracer
9226  built-in presentation tracer
9227  editor-only control
9228  durable custom-section tracer
9229  durable custom-title tracer
9230  mixed reversible full-Home tracer
```

Established durable families:

```text
order
hidden
viewSettings
customHubs
```

Established interpretation:

- [x] `order` is durable and browser-profile-local.
- [x] `hidden` is durable and browser-profile-local.
- [x] `viewSettings` owns durable built-in presentation.
- [x] `editing` is transient edit bookkeeping; editor entry/exit alone creates no Home state.
- [x] custom-added sections are coordinated `customHubs + order + viewSettings` bundles.
- [x] validated custom titles live inside the custom section `viewSettings` record.
- [x] Session Storage/IndexedDB were ruled out for the tested Home persistence cases.

The observed effective/default hub count is evidence, not a product invariant, and is never hard-coded.

#### 9230 full reversible proof — PASSED

9230 deliberately combined:

- custom Artist section **ACP Scrub Section**;
- moved **Mixes for you**;
- hidden **Recent Plays**;
- **Recently Added in Music** set to Carousel / Block / 180 px.

Settled bounded state:

```text
customHubs=1
order=1
hidden=1
viewSettings=2
editing=0
other=0
matching records=5
context_count=2
section_context_count=2
fingerprint=58ed4b28
```

Confirmed scrub:

- [x] exact five Home records captured to a no-overwrite mode-0600 disposable snapshot;
- [x] exactly those five classified records removed;
- [x] bounded Home state verified all-zero;
- [x] empty/customisation-free fingerprint `741638a5`;
- [x] after normal reload Plexamp rebuilt a populated default-looking Home itself;
- [x] custom section/order/hidden/presentation overrides disappeared;
- [x] Plex login remained intact;
- [x] correct library remained selected.

Confirmed rollback:

- [x] restored exactly five records into the empty bounded target;
- [x] original fingerprint **`58ed4b28`** returned exactly;
- [x] independent family probe returned the original `customHubs=1`, `order=1`, `hidden=1`, `viewSettings=2` inventory;
- [x] title matcher again found exactly one `ACP Scrub Section`;
- [x] after reload the custom section, moved order, hidden Recent Plays and Carousel/Block/180 px presentation all returned visually;
- [x] Plex login and correct library remained intact throughout.

This proves the intended production model: clear only bounded Home-owned customisation state and let Plexamp rebuild itself; do not synthesize runtime hubs or copy a clean Chromium profile.

#### Commissioned-Pi production acceptance — PASSED

On the accepted branch carrying bridge **1.4.0**, normal `bash setup.sh` convergence and the required reboot passed with a clean working tree, all critical services active, healthy dashboard API, correct Plex login/library, and the production kiosk loading the bounded bridge without remote-debugging flags.

Fresh production Preview reported:

```text
19 server-owned
8 Plexamp native settings
5 bounded Home customisation records
```

The production Home set was classified as `order=1`, `hidden=0`, `viewSettings=3`, `customHubs=1`, with no warnings. `equalizerPresets` was absent. Review refreshed the same protected plan and reported **Ready to confirm**.

Production Confirm then completed and verified **34 applied changes** across ACP, Plexamp native settings, Home customisation and commissioning. After the automatic completion reload:

- [x] Plexamp remained signed in;
- [x] the correct music library remained selected;
- [x] Home rebuilt into default order/style and the custom section/presentation overrides disappeared;
- [x] player name remained the commissioned value;
- [x] managed audio output remained **A Clockwork Plex - Plexamp**;
- [x] ACP reported **Already at baselines** on fresh Preview;
- [x] Home reported **0** bounded customisation overrides on fresh Preview;
- [x] commissioning still matched the player-name baseline and managed output.

The sole initial post-reset Preview residue was `plexamp.native-settings.activeTab`, created by normal Plexamp UI/navigation state rather than meaningful user configuration. Commit `09488072ad204d9a7c0f984d8a4a2a64e92387dd` excluded it through the same runtime-normalised comparison boundary already used for `equalizerPresets`; exact rollback snapshots still include it.

The final production cleanup was physically accepted on head `477bf0fd0cd7090a4d434816611f35673d83851e`: the commissioned Pi fast-forwarded cleanly, `a-clockwork-plex.service` restarted, `/api/state` returned **PASS**, and a fresh **Preview reset** reported **Already at baselines**, **0 Plexamp settings** and **0 Home** changes. The zero-change result now remains compact: the detailed Preview card stays hidden when every owner is ready and there is nothing to reset, while warning/incomplete previews can still reveal diagnostic detail.

#### Production full-Home semantics — IMPLEMENTED AND PHYSICALLY ACCEPTED

The Home owner now:

- [x] recognises only bounded durable `order`, `hidden`, `viewSettings`, `customHubs` records;
- [x] fails closed on active `editing`, unknown/malformed families, stale targets and bounded-size/count violations;
- [x] snapshots exact raw Home records in memory before mutation;
- [x] removes records individually, never `localStorage.clear()`;
- [x] verifies the bounded Home target is empty after apply;
- [x] retains exact rollback through the later server participant;
- [x] refuses rollback into a non-empty bounded Home target;
- [x] finalises rollback state only after the complete transaction succeeds;
- [x] uses the existing post-success dashboard reload as Plexamp's Home rebuild trigger;
- [x] leaves auth/session/library/account/device identity and unrelated browser/cache state outside the Home owner;
- [x] uses no DevTools, remote-debug production interface, generic `eval`, raw profile copying or transient runtime-hub mutation.

The ordering is deliberate: Home must **not** reload immediately after clearing because that would discard the in-memory rollback token before the later server participant committed. The existing outer transaction already supplies the correct commit boundary.

#### Automated evidence

- [x] Tests #4623 passed on `8db7c9907675ec416681b0d72676594c4781f960`.
- [x] Tests #4625 passed on `136f6fc5e14b0734f0d9ff5ca8f4d02951418450`.
- [x] Tests #4631 passed on `9457a4413611e506bfab0cbf73cd4ef01a07184f`.
- [x] Tests #4632 passed on `1b0fccf26887b708417a24974df92d87ff093553`.
- [x] Tests #4633 passed on `54600624add3af758dd38d564daf1a4a7868d7eb`.
- [x] Tests #4638 passed on `96f06e09544fafed3475f3416ac28650b040c580`: widened full-Home production owner + five-record safety/rollback smoke + full suite green.
- [x] Tests #4647 passed on `88d69c9b8310f0bd82acfefff11c393053f8106f`: final full-Home production implementation gate after Reset UI/cache/bridge-version and regression updates.
- [x] Tests #4649 passed on `1f077b28ad453b90409ea91f24da0773c3a0ba90`: exact commissioned-Pi acceptance head, including documentation bookkeeping.
- [x] Tests #4650 passed on `09488072ad204d9a7c0f984d8a4a2a64e92387dd`: `activeTab` runtime-normalisation cleanup; compile, JavaScript/page wiring/shell checks and full unit suite green.
- [x] Tests #4662 passed on `3165f832bb8cae5277e727ee08f68b9143cba790`: zero-change Preview logic plus cache/client regression green.
- [x] Tests #4663 passed on `477bf0fd0cd7090a4d434816611f35673d83851e`: final cache-safe physical-acceptance head; compile, JavaScript/page wiring/shell checks and full unit suite green.

#### #93 closure

- [x] Home persistence classification complete.
- [x] Full disposable scrub/rebuild/rollback proof complete.
- [x] Full bounded Home customisation joins #93 rather than becoming a separate Reset follow-up.
- [x] Production owner widened and bridge 1.4.0 physically loaded.
- [x] Commissioned-Pi Preview → Review → Confirm physically passed; Home rebuilt while login/library/player identity/output remained correct.
- [x] Fresh post-reset Preview no longer reports `equalizerPresets` and reports ACP/Home at baseline.
- [x] The commissioned Pi did not contain the short-lived 10% AirPlay session-start residue; no AirPlay-owned change appeared in the accepted Preview.
- [x] `activeTab` post-reset navigation residue classified and excluded on the feature branch.
- [x] Final production pull/restart physically verified **0 meaningful Reset differences** and the compact zero-change Preview presentation.

The #89/#90 complete portable Plexamp Backup/Restore follow-up is physically accepted and now integrated into `develop` together with #93 Reset. The Settings/appliance-ownership track is therefore closed on the integration branch.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

**High-resolution audio is the next major implementation area.** Continue to protect the commissioned production SD; destructive route/lifecycle experiments belong on the spare SD.

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — COMPLETE through #93, including schema-v2 Backup/Restore
3. **Touchscreen Plexamp text entry** — COMPLETE #91
4. **BBC News** — COMPLETE #92, including physically accepted article-QR hand-off
5. **High-resolution Plexamp audio / mixer-EQ path** — NEXT
6. **Astronomy**
7. **Appliance resilience**
8. **Events calendar**

This priority list is authoritative.

## Future product backlog

### BBC News configurable sections

Goal: extend the accepted News screen from the fixed five-section starter set to a user-owned ordered set of BBC RSS sections without turning ACP into an unrestricted RSS reader.

- [ ] Preserve Top Stories, UK, World, Science and Technology as the out-of-box defaults.
- [ ] Provide a friendly built-in catalogue for additional BBC feeds plus an advanced way to add a BBC-owned HTTPS RSS URL that is not yet catalogued.
- [ ] Validate a candidate feed before saving it, derive a sensible default title, and retain a stable internal section id separate from the displayed label.
- [ ] Allow sections to be enabled/disabled, reordered and optionally renamed; the default News section must remain one of the enabled entries.
- [ ] Keep the existing Top Stories ticker source independent initially rather than coupling ticker behaviour to section customisation.
- [ ] Include logical section configuration in portable Backup/Restore while continuing to exclude downloaded RSS/cache state.
- [ ] Preserve cache-first/stale behaviour and the accepted link-free public story model/phone-owned QR hand-off boundary.
- [ ] Add 1280×720 Settings/News physical acceptance for a mixed default + added-section configuration.

### High-resolution Plexamp audio / mixer-EQ path

Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

- [ ] Physical capability audit with known 16/44.1, 24/48, 24/96 and 24/192 Plex files.
- [ ] Choose a managed high-resolution bus by measured CPU/stability/latency.
- [ ] Remove the managed 16/44.1 bottleneck while preserving trims → Music Master → reserve → EQ → limiter → alarm join.
- [ ] Define truthful EQ-active high-resolution and native-bypass behaviour.
- [ ] Investigate source-rate-native Direct Plexamp across 44.1/48/88.2/96/176.4/192 kHz.
- [ ] Define deliberate resampling policy for Plexamp and AirPlay sources.
- [ ] Expose source, processing and final DAC format/rate separately in diagnostics.
- [ ] Regression/physical acceptance: route/fallback, EQ active/bypass, alarm takeover, AirPlay both directions and recovery.

### Astronomy

- [ ] Deterministic local/offline calculation authority with reference fixtures and tolerances.
- [ ] Observer/location model reusing existing coordinates/timezone where sensible.
- [ ] Overview/Tonight: Julian Date, sidereal time, Sun/Moon headline state and useful events.
- [ ] Sun: rise/transit/set, twilight classes, day length, RA/Dec and altitude/azimuth.
- [ ] Moon: rise/transit/set, phase/age/illumination, principal phases, distance/angular diameter, RA/Dec and altitude/azimuth.
- [ ] Planets Mercury–Neptune: rise/transit/set and useful position/magnitude/elongation data where reliable.
- [ ] Touch-first 1280×720 navigation plus night presentation.
- [ ] Validate circumpolar/no-rise/no-set/polar/DST/local-date edge cases.

### Appliance resilience

Detailed design/security constraints: [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md).

- [ ] Investigate intermittent read-only root-filesystem/SD behaviour observed during commissioned-Pi testing.
- [ ] Reduce avoidable appliance writes where this does not weaken rollback/history/recovery.
- [ ] Design kiosk-safe Wi-Fi recovery with a bounded temporary NetworkManager-backed recovery AP and local QR/captive-portal-style setup.
- [ ] Keep Wi-Fi credentials out of query strings, argv, logs, browser history and persistent recovery pages.
- [ ] Define recovery timeout/rollback so failed reconfiguration cannot strand the appliance indefinitely.
- [ ] Add truthful health/status for storage, network and critical appliance services without automatic mutation.

### Events calendar

- [ ] Define source/credential ownership before implementation.
- [ ] Build a cache-first, touch-friendly upcoming-events model.
- [ ] Reuse global date/time formatting and existing screen/idle ownership.
- [ ] Design stale/offline behaviour.
- [ ] Keep external event links/navigation out of the kiosk unless explicitly designed and safely owned.

## Release gate for the next version

Before promoting the next development cycle to `main`:

- all included feature branches must be merged into `develop` only after automated and physical acceptance;
- the clean-room installer/runbook must still pass on supported hardware;
- repeat `bash setup.sh` must remain safe/idempotent;
- repository/docs catalogues and this live roadmap must describe the actual shipped state;
- the accepted production appliance must not be used as the disposable target for destructive audio/storage experiments;
- release version/tag/name is assigned only after final scope and acceptance are known.
