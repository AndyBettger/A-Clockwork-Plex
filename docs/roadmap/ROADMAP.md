# A Clockwork Plex Roadmap

**Last updated:** 31 August 2026  
**Active development branch:** `develop`  
**Stable branch:** `main`  
**PR #2:** merged into `main` on 23 August 2026.  
**Current release:** **`v0.4.0` — Unified Bedside Appliance — PUBLISHED 23 August 2026.**

> This roadmap began as the EQ/audio-installer plan. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, AirPlay acquired an arbitration layer, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation, release and future-product roadmap.

Detailed earlier chronology is preserved separately so completed engineering does not bury the useful bit:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — detailed early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — exact pre-consolidation roadmap snapshot through the original replacement-SD physical checkpoint;
- [`../development/evidence/final-clean-room-physical-progress-2026-08-21.md`](../development/evidence/final-clean-room-physical-progress-2026-08-21.md) — replacement-SD physical evidence;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/evidence/release-hygiene-audit-2026-08-19.md`](../development/evidence/release-hygiene-audit-2026-08-19.md) — repository/release-hygiene record.

Normal appliance owners do not need any of those files to install the clock. That job belongs to [`../INSTALL.md`](../INSTALL.md).

## Branch and release model

- `main` is the current supported stable appliance and the normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work may use short-lived `feature/<name>` branches created from `develop` and merged back to `develop` once validated.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- the next release version is intentionally **not assigned yet**; choose it when the actual next-release scope is clear rather than guessing from the first backlog item.
- the old `feature/alarm-engine` branch was retired after the v0.4.0 merge and deleted on 23 August 2026; its product history remains preserved by `main`, PR #2 and the immutable `v0.4.0` tag.

## Current `develop` cycle

### Development-cycle bootstrap — COMPLETE at checkpoint #84

- [x] Created `develop` from post-release `main` head `a2ccc85cbd1d264e7ebedcf50b82084a4289c09a`.
- [x] Switched GitHub Actions push validation from `feature/alarm-engine` to `develop`; `main` remains covered.
- [x] Established `v0.4.0` as the released baseline for all new work.
- [x] Added Events calendar, BBC News and Astronomy to the live product backlog.
- [x] Retired/deleted the old `feature/alarm-engine` branch ref after owner confirmation.

### High-resolution audio feasibility audit — COMPLETE at checkpoint #85; implementation OPEN

The post-v0.4.0 audio review confirmed that hi-res Plexamp playback is a genuine appliance audio-path feature rather than merely a Plexamp preference change.

- [x] The current managed EQ split-bus profile hard-codes the shared music bus and CamillaDSP capture/playback to **`S16_LE` / `44100` Hz**.
- [x] The current Direct/fallback profile also hard-codes its shared `dmix` path to **`S16_LE` / `44100` Hz**, so disabling/bypassing the managed EQ does not currently provide a native hi-res Plexamp path.
- [x] The Raspberry Pi DAC Pro hardware is capable of substantially higher resolution/sample rates than the present appliance bus. Exact accepted appliance formats/rates remain a later physical audit.
- [x] AirPlay remains a lower-rate source; a future higher-resolution internal bus must preserve AirPlay compatibility without making false hi-res claims.
- [x] Scheduled-alarm takeover, Maximum Alarm Volume authority and recovery remain non-negotiable.

No production audio format was changed by #85. Detailed implementation work remains under **High-resolution Plexamp audio / mixer-EQ path** below.

### Friendly forecast-location entry — COMPLETE at checkpoint #86

- [x] Added read-only `GET /api/weather/forecast/locations?q=...`: Open-Meteo for normal place searches plus Postcodes.io fallback for full UK postcodes when Open-Meteo has no match.
- [x] Added Settings → Weather → Online forecast friendly town/city/postcode selection while retaining exact latitude/longitude as advanced fallback.
- [x] Location lookup stages the existing forecast fields only; **Save Changes** remains the sole configuration persistence authority.
- [x] Physical town search passed with Milland on the development Pi.
- [x] Initial physical exact-postcode test exposed the real Open-Meteo gap for `GU30 7JS`; the Postcodes.io fallback subsequently resolved it successfully and drove the Weather forecast after Save Changes.
- [x] The same physical pass exposed far-future `Unknown conditions` daily cards. Both the seven-day foundation renderer and long-range completion renderer now suppress unusable unknown-condition days without shifting Today/Tomorrow labels or duplicating dates.
- [x] Final physical re-check showed the exact postcode forecast working and no remaining `Unknown conditions` daily card across the configured long range.
- [x] The owner confirmed the final synchronized `develop` Actions run green.

Initial location implementation/CI-wiring head: `fe118fb16ef282d6f55682699c1118e721c60b03`.  
Combined postcode/full-range follow-up code/test head: `a7fd2835c6f1bdb7a45591c6bfc1b17732e4f344`.  
Final #86 roadmap/acceptance head: `f901503e9ea4baaf32cc6b9ddcc474456f6745b2`.

### WU supplemental indoor expiry — COMPLETE at checkpoint #87

- [x] With Weather Underground selected, fresh Ecowitt indoor supplementation was deliberately withheld past the configured freshness window.
- [x] Weather removed the **Indoor** row instead of presenting stale values while WU outdoor/current observations remained available.
- [x] Clock retained its paired card layout but replaced expired indoor readings with **—**.
- [x] Re-enabling Ecowitt caused indoor temperature/humidity to reappear automatically on both Clock and Weather with no service restart.
- [x] Owner-supplied 1280×720 screenshots document the expired states.

**Weather priority #1 for the post-v0.4.0 cycle is complete.**

### Configuration ownership and backup-format audit — COMPLETE at checkpoint #88

The Settings/appliance-ownership cycle began by classifying persistent data before implementing backup or restore mutation. Governing rule:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

- [x] Added [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) with the ownership matrix, versioned envelope, restore transaction model and reset relationship.
- [x] Classified ordinary ACP settings as a **normalised portable model**, never raw `config.json` bytes.
- [x] Classified alarms, display/night choices, Weather non-secret choices, AirPlay preferences, logical EQ and four mixer percentages as portable user-owned state.
- [x] Established hard exclusions: WU/Plex credentials and claim/session material, browser cookies/session storage, player/machine identity, private keys, raw ALSA state, audio topology, installer state, caches and volatile runtime files.
- [x] Added `scripts/audit-plexamp-preferences.py`, content-blind by default and progressively narrowed through explicit safe audit modes; unknown/auth/device/browser values were never dumped.
- [x] Physical Plexamp 4.13.2 Headless inventory found **35 Settings files: 11 safe-looking candidate names and 24 unclassified/excluded files**.
- [x] Established the exact typed Headless portable allow-list from the commissioned Pi: `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `cachingWiFi`, `loudnessLeveling`, `precacheNetworkSpeed`, `sampleRateConversionQuality`, `sampleRateMatching`.
- [x] `audioDeviceUuid` is device-specific and must be recommissioned; `premium` is account/capability-derived and excluded; `playerName` remains a separate future device-label decision rather than an ordinary preference.
- [x] Browser discovery identified Plexamp at `http://localhost:32500` and MMKV web keys under `mmkv.default\<key>` without decoding their values.
- [x] `@Plexamp:resources`, all `*:cachedItems`, session/auth material and unrelated browser state are explicitly excluded.
- [x] A physical Home reorder experiment proved the contextual `discovery:customizations:...:order` family owns Home item ordering.
- [x] A real physical hide experiment created the complete per-hub `...:<hub-id>:hidden` key plus transient `...:<hub-id>:editing` state. `hidden` is the useful preference; `editing` is excluded.
- [x] Chromium LevelDB compaction changed which historical records were visible between samples. Therefore raw LevelDB/profile files are **discovery evidence only, never the production backup authority**.
- [x] Future browser Home export must operate through a live allow-listed Plexamp-browser authority and save logical order/hidden choices. Restore must discover the freshly claimed target account/library context instead of copying source context identifiers literally.

#88 is closed. No raw Plexamp profile or Chromium profile is a supported backup unit.

### Configuration backup/export — COMPLETE at checkpoint #89

The schema-v1 secret-safe export, Headless preference export and live Plexamp Home-layout bridge are physically accepted on the commissioned Pi and covered by synchronized green `develop` Actions validation.

- [x] Added `app/configuration_backup.py` with **schema version 1** and metadata sourced from `app/static/app-version.json`.
- [x] Export builds from the existing normalised Unified Settings authority and selects an explicit portable subset instead of serialising the public snapshot wholesale.
- [x] ACP export currently includes startup/idle choices, display/day/night presentation, Weather labels/units/cards/forecast/provider/rainfall settings, alarm configuration and AirPlay user preferences.
- [x] WU API credentials are never read by this exporter. The target-owned `api_key_env` implementation detail is also omitted; the ordinary station ID and timing choices remain portable.
- [x] Installer/hardware fields such as alarm ALSA/hardware device names and Plexamp localhost/pause/service plumbing are deliberately omitted.
- [x] EQ exports as the logical enabled/band model. Available shared mixer state exports as the four user-facing percentages (`master`, `plexamp`, `airplay`, `alarm`) rather than ALSA state files.
- [x] The exact eight #88 Plexamp Headless preferences export through strict name/type parsing. Unknown, malformed, device-identity and account/auth files are not copied.
- [x] Plexamp runtime version is taken from the ACP-owned `~/plexamp/.a-clockwork-plex-runtime` identity written/verified by the guarded Plexamp runtime installer; optional Plexamp `package.json` metadata is not a compatibility authority.
- [x] `GET /api/settings/backup` returns a pretty JSON attachment named `A-Clockwork-Plex-backup-YYYY-MM-DD_HHMMSS.json` with `Cache-Control: no-store`; it performs no configuration mutation.
- [x] Settings exposes **Advanced → Backup & restore → Download backup** and clearly states that credentials/authentication are excluded. Backup is an immediate read-only action and does not participate in staged **Save Changes**.
- [x] `export_report` records warnings and deliberate omissions. The server-only export continues to report browser Home preferences omitted unless the kiosk browser adds a validated live snapshot.
- [x] Regression coverage proves representative fake WU secrets, Plex auth/device/account state, hardware device fields and target-specific Plexamp plumbing do not enter the generated backup; endpoint attachment/no-store behaviour is also covered.
- [x] CI syntax/compile/page-wiring gates include the backup backend and download control.
- [x] The initial commissioned-Pi physical export passed on 24 August 2026: schema `1`; ACP domains `airplay, alarms, dashboard, display, weather`; audio sections `eq, mixer`; all eight approved Headless preferences; **0 warnings**; two deliberate omissions; and the structural forbidden-key checker reported **NONE**.
- [x] Corrected two CI-only regressions exposed during #89: the new architecture document is now catalogued and backup filenames preserve the source/appliance timezone rather than converting to the GitHub runner timezone.
- [x] Added `browser/plexamp-bridge/` as a Manifest V3 unpacked content extension with **no permissions, no background worker and no general browser-debug interface**. It is scoped only to Plexamp loopback origins on port `32500`.
- [x] The kiosk launcher loads that local extension from the repository when present. It does **not** expose a Chrome remote-debugging port; if bridge files are absent, normal kiosk launch remains available and backup fails safely back to the recorded omission.
- [x] The bridge reads host-page Local Storage only inside Plexamp and recognises only live `discovery:customizations:*:order` and per-hub `*:hidden` records. `editing`, caches, resources, session/auth state and unrelated preferences are not part of its output.
- [x] Added strict dashboard-side response validation. The Settings download flow fetches the existing server backup, requests the live Home snapshot using `postMessage`, merges only validated logical `order`/`hidden` data **inside the kiosk browser**, then creates the downloaded file locally. Browser preference values are not POSTed to the dashboard service or persisted as a server-side staging file.
- [x] Added automated bridge safety coverage: loopback-only manifest, no extension permissions/network/cookie authority, no remote-debugging launcher flag, and a Node-backed logical Home snapshot test that excludes editor/cache/auth fixtures.
- [x] First live-bridge physical probe on 24 August 2026 proved the extension/request path is active and fails closed: a fresh backup contained no `plexamp.browser_preferences`, retained the deliberate browser omission, and recorded exactly one warning: `browser bridge unsupported-hidden-format`. No unsupported value was exposed.
- [x] Hardened the bridge after that physical probe so it now calls `getItem()` **only after** a Local Storage key matches the exact `:order` / `:hidden` allow-list. Editor/cache/resource/auth-adjacent values are no longer merely excluded from output; they are not opened by the bridge at all. Added regression coverage for that read boundary.
- [x] Physical safe-shape probes established that both live values use one-property JSON wrappers: the hidden record wraps a boolean, while the order record wraps an array of **15 strings**. The opaque one-character wrapper key is intentionally not treated as part of ACP's compatibility contract.
- [x] Bridge `1.0.3` added strict singleton-wrapper parsing. The physical follow-up proved hidden state parses successfully.
- [x] Bridge `1.0.4` added a value-free rejected-order diagnostic. The commissioned Pi reported `items15-max77-empty0-over0-nonstring0-bad2f`: all 15 identifiers are bounded strings, and `/` (`0x2f`) was the only character required beyond the initial `[A-Za-z0-9_.-]` policy.
- [x] Bridge `1.0.5` and the dashboard-side validator therefore widened **only** to `[A-Za-z0-9_./-]`; `:` and other unobserved punctuation remain rejected. Slash-bearing per-hub `:hidden` keys are also supported, and the parent bridge asset was cache-busted.
- [x] Final live-layout physical export passed on 24 August 2026. Settings reported **“Backup downloaded, including Plexamp Home layout. Credentials and authentication were not included.”** Structural verification reported: browser preferences present; browser schema `1`; Home order captured with **15 items**; **1 hidden item**; browser omission **false**; warning count **0**.
- [x] Synchronized `develop` Actions remains green through **Tests #4347: 978 tests, `OK`** on 30 August 2026, including the production direct-import smoke gate added after the commissioned-Pi startup regression.

Initial #89 implementation sequence:
- backup service: `6497fb12c65c873daa866c67cd5ee8142287325f`;
- runner registration: `04437daa316da6a969bd982267b3f3d73daf4646`;
- secret-exclusion/API regression coverage: `6757619d3557c7c72d667bc626731010d519af70`;
- Settings download control: `4f8bc32878dd0dac58526aaa7bc5b719db79c42e`;
- ownership architecture synchronization: `2cb91d5ea57235ad5373f8f7489efc4f27dc0d04`;
- CI-gate wiring: `ec190533b8fe81ebf9cda3d062db7d41bcd85210`;
- CI catalogue/timezone corrections: `9a71c8da0998eb96900e9326e9c09b0c356c790f`, `7612c281531216beff10dfab3c411dadf067d994`;
- live bridge manifest/content/client/launcher/download integration: `e7c3b6ebe70038c86b23ecdffff937e9cd318abc` through `1f81d4381db6ad6d232452cc98f4a9a68df8c506`;
- bridge regression/CI gating: `93e8e5cb514af85beb5933758d7f575e9d2ab286`, `f0ca0fac67002d5ae580d793ed809433a8df6bc0`;
- fail-closed/read-boundary/shape diagnostics: `d19235465f91bc7569151626ec758bf556ea232f` through `4c2505ea3cee3f471395eb09f6a362bbbecff588`;
- singleton-wrapper parser: `b035d6d604823d2d2c476ccebac3b9c5b21a494e`, `014962eb02f0e3180643bdd5e1d4dac77c798cb3`, `f7858e306a671102fdd1caacb479c2ce0a30fee3`;
- rejected-order identifier diagnostic: `3a31ecf6d79586402aa3f73f4c14dd3cb41f9734`, `8057b7a3eb7e66d5f1ba7f28d0757d5dda633e66`, `d802ea734902ab1c0c221fc1775d024357a9397d`;
- final `/` identifier support/client validation/cache refresh: `99c0ede324ab5356a6d16b419e8cd50e5b5a7f05`, `8b37229cbdd579af69269586c7309298bdc7684f`, `9fe7c8350daf211fbd7a393ab72e9317ec996fcb`, `2657e86f937fd42669d1513ab2da65becf10bf01`, `a02592b25baa178cb10f775d461d1c44f7e21586`.

### Configuration import/restore — IN PROGRESS at checkpoint #90

#### Phase 1 — parse / validate / preview — PHYSICALLY ACCEPTED

- [x] Added `app/configuration_restore.py` with `ConfigurationRestorePlanner`, consuming the same schema-v1 portable model as export rather than raw appliance files.
- [x] Added read-only `POST /api/settings/restore/preview`; the preview operation itself has no mutation path.
- [x] Preview enforces a 1 MB request limit, schema/version and domain allow-lists, bounded JSON structure, exact mixer channels/ranges, exact typed Headless allow-list and the physically accepted `[A-Za-z0-9_./-]` Plexamp Home identifier policy.
- [x] Tampered credential/machine-owned fields such as API/auth/claim tokens, cookies, `audioDeviceUuid`, `playerName`, `premium`, ALSA/hardware fields and Plexamp service/pause plumbing are rejected before comparison.
- [x] Preview compares the normalized portable model against a fresh current backup and returns **changed paths/counts, never old/new values**. AirPlay receiver-name changes are flagged as requiring a restart confirmation.
- [x] Valid Plexamp Home order/hidden data is recognized and counted, but comparison/application is explicitly deferred to the future live-browser restore stage after Plexamp is commissioned.
- [x] Settings → Advanced → Backup & restore provides a JSON file selector and **Preview restore**. The selected file is parsed locally and sent in memory as JSON; there is no uploaded-file staging directory.
- [x] The preview API contract permanently keeps `read_only: true` and `apply_enabled: false`; separate `restore_available`, `server_restore_available` and `plexamp_headless_restore_available` fields describe supported work for the distinct confirmed restore phase so Preview never changes meaning.
- [x] Regression coverage protects read-only preview safety, changed-path/no-value output, rejection of tampered secret/machine fields and unsupported browser identifiers, plus `Cache-Control: no-store`.
- [x] Physical commissioned-Pi acceptance passed on 24 August 2026 with the just-created backup: **0 supported server-owned changes**, `read_only: true`, `apply_enabled: false`, Plexamp browser payload present with **15 ordered / 1 hidden**, and only the expected deferred-browser warning.
- [x] The Restore preview screen was physically checked at 1280×720 and remained readable/useful.

#### Phase 2 — transactional server-owned restore — PHYSICALLY ACCEPTED

Phase 2 deliberately restored only owners already controlled transactionally by the dashboard. Both the normal successful restore and stale-preview refusal paths are physically accepted on the commissioned Pi; Phase 3 subsequently added the separately guarded Plexamp Headless owner.

- [x] Added separate confirmed `POST /api/settings/restore/apply`; Preview itself remains non-mutating.
- [x] A 32-hex preview fingerprint binds Apply to the exact normalized backup and current server-owned comparison state. A stale preview refuses before owner mutation and requires a fresh Preview.
- [x] Apply requires explicit second confirmation. AirPlay receiver-name changes carry the existing restart confirmation forward.
- [x] Preflight refuses before mutation if a required Master EQ or persistent mixer authority is unavailable.
- [x] Rollback state is captured from the same normalised authorities before the first owner changes.
- [x] Application order is **Unified Settings → Master EQ → persistent four-channel mixer**; no raw config/EQ/ALSA state file is overwritten directly.
- [x] Post-apply verification re-runs the normalized comparison and requires all currently supported server-owned paths to match the requested backup.
- [x] Any required-stage failure rolls touched owners back in reverse order and reports rollback failures explicitly.
- [x] Restore rejects unsaved ordinary Settings changes in the UI before confirmation.
- [x] EQ restore validation is restricted to the production `-6…+6 dB` range in `0.5 dB` steps, and forbidden-key detection is case-insensitive.
- [x] Fake-backed regression coverage proves successful Settings/EQ/mixer restore, stale-preview refusal without mutation and an injected late mixer failure restoring mixer, EQ and Settings to their original logical state.
- [x] CI compile/JavaScript/source-contract gates require the separate apply registration/endpoint, immutable read-only Preview flag, `server_restore_available` and explicit confirmation control.
- [x] Physical harmless-change restore passed on 24 August 2026: one ordinary Settings value, one `0.5 dB` EQ value and one small persistent mixer value were deliberately changed; Preview reported exactly **3** restorable server-owned paths in `settings.dashboard`, `audio.eq` and `audio.mixer`; explicit two-step restore returned all three values to the backup state; re-selecting the same backup then reported **0** restorable items.
- [x] The successful physical restore confirmed rollback capture/verification and credential/Plexamp-deferred copy at 1280×720.
- [x] Scoped restore presentation polish now separates the Preview action from its result cards, spaces the result/confirmation blocks by 14px and vertically centres helper text beside Download/Preview actions. The 30 August screenshots confirmed the revised result/confirmation spacing is readable at 1280×720.
- [x] Physical stale-preview refusal passed on 30 August 2026: after Preview reported one Settings difference, Bass was changed by a further `0.5 dB`; the old preview was then rejected before mutation, both changed values remained changed, and a fresh Preview correctly reported **2** restorable paths (`settings.dashboard` and `audio.eq`).
- [x] Synchronized `develop` Actions **Tests #4311** and **#4312** passed the stale-warning UX logic and scoped warning CSS respectively.
- [x] The 30 August wording re-check exposed an ownership bug: the restore client's own catch handler overwrote the detailed stale-preview message with the generic retry line after the server had already returned the correct 409 detail. The owning `settings-about.js` path now renders the exact blocked message from the 409 `fresh_preview_required` response, clears the warning state when a new file/Preview starts, and has its asset URL cache-busted. The `settings-pass-a.js` observer remains defence-in-depth rather than the primary message owner.
- [x] The owning-client fix, cache refresh and source/syntax regression gate passed synchronized `develop` **Tests #4320/#4321**.
- [x] Final physical presentation re-check passed on 30 August 2026: the conspicuous blocked-restore wording is now correct, and the two-stage **Review restore → Confirm & restore** flow remains the accepted mutation boundary.

#### Phase 3 — version-aware Plexamp Headless preference restore — PHYSICALLY ACCEPTED

Phase 3 is the first Plexamp-owned mutation stage. It remains deliberately narrower than ordinary server restore and does not make the whole Plexamp Settings directory a backup/restore unit.

- [x] Restore eligibility is limited to the exact eight typed Headless allow-listed preferences established at #88/#89; unknown files, auth/session state, `audioDeviceUuid`, `playerName` and `premium` remain untouched.
- [x] A dedicated root-side owner `/usr/local/bin/a-clockwork-plex-plexamp-preferences` and unprivileged `PlexampPreferenceManager` are implemented. Preference values cross the privileged boundary as bounded JSON on stdin, never argv.
- [x] Backup/export and restore share the guarded installer's ACP-owned `~/plexamp/.a-clockwork-plex-runtime` manifest as the runtime-version authority. The backup, current runtime and helper-reported installed Plexamp versions must be an exact known match before Headless paths become restorable; `package.json` is not used as a fallback.
- [x] `sampleRateConversionQuality` and `sampleRateMatching` are additionally appliance-audio-generation aware and remain deferred when a backup comes from a different application/audio generation.
- [x] Each changed preference captures exact bytes, mode, ownership and timestamps; writes use atomic replacement/fsync, typed verification and post-restart verification. A late failure restores the original snapshots and service state.
- [x] Runtime coordination is narrowly scoped to the Plexamp preference owner: only `status` and `apply` are delegated, and the helper itself owns the required `plexamp.service` stop/restart plus loopback-port readiness check. The dashboard receives no broad `systemctl` authority.
- [x] The Preview fingerprint includes Headless readiness/version capability, so a target capability change after Preview is rejected before mutation.
- [x] The combined transaction order is **Unified Settings → Master EQ → persistent mixer → Plexamp Headless**. If the Headless owner fails, earlier touched ACP owners are rolled back in reverse order.
- [x] Preview/Settings now distinguishes **ACP/server**, **Plexamp Headless**, and **Plexamp Home layout** counts/availability without exposing preference values. Confirmation explicitly warns when Plexamp will briefly restart.
- [x] Fake/alternate-root regression coverage proves exact-version success, incompatible-version deferral, sample-rate audio-generation deferral, stale capability refusal, injected late-restart rollback and outer-transaction rollback.
- [x] Initial commissioned-Pi read-only status on 30 August physically proved the Settings directory, active `plexamp.service` and all **8/8** allow-listed typed preferences, but failed closed with `installed_version: null` / `restore_ready: false`. Read-only inspection then proved there is no installed `~/plexamp/package.json`; the verified 4.13.2 identity is the installer-owned `.a-clockwork-plex-runtime` manifest. No Plexamp preference was mutated during discovery.
- [x] Corrected backup/restore runtime identity and real-layout regression fixtures: `0240473a6f9f7c4ef45b0acfbc07f109c4fd4e37`, `a85c68e4d8818382d044110a9cf704821201af56`, `ebbbecdf0b831d21c1fb76eea2075a61775aee1d`, `84f3e256979dc429c4dbf3622f2bae98e197d116`. **Tests #4343 passed all 978 tests with `OK` on 30 August 2026.**
- [x] The first production reload on the corrected source exposed a direct-run import regression before any restore mutation: systemd launches `app/runner.py` directly, while the new Plexamp manager initially only supported package-relative import. `6c0f826288492ea44c473e03302a4c190fb31d46` added the direct-run fallback and `0ff222958659a63e041f6d4675ad7fb22dd38f27` added the matching CI smoke gate. **Tests #4347 passed all 978 tests with `OK`**; the commissioned dashboard/API/kiosk then physically recovered and survived reboot normally.
- [x] Corrected restricted-helper readiness physically passed with **8/8**, `installed_version: 4.13.2`, `restore_ready: true` and active `plexamp.service`.
- [x] A deliberately incompatible `4.13.3` copied backup with only `autoPlayEnabled` flipped physically produced **1 detected / 0 restorable / 1 deferred** Headless difference, `restore_available: false`, and before/after backups proved zero ACP, Headless or runtime-identity mutation.
- [x] The exact-version `4.13.2` physical round-trip changed only `autoPlayEnabled` from its original `false` to temporary `true`, applied/verified exactly one Headless path, then Previewed and restored the original `false` value with a second verified one-path apply. The final Preview returned **0 differences / 0 restorable changes**.
- [x] Post-round-trip invariants passed: both services active, restricted owner still `restore_ready: true`, clean repository, and Plexamp opened and played normally after the two controlled restarts.
- [x] The destructive late-restart rollback path remains covered by controlled automated fault injection and was deliberately not forced on the commissioned appliance.

#### Phase 4 — target-context-aware Plexamp Home order/hidden restore — IMPLEMENTED / CI ACCEPTED; PHYSICAL ACCEPTANCE NEXT

- [x] Extended the existing permission-free localhost-only Plexamp browser bridge from export to scoped `planHome` / `applyHome` operations for logical Home `order` / `hidden` state.
- [x] The browser owner discovers the **target's current** contextual customization keys from the live Plexamp Local Storage after commissioning. The source backup's account/library context is discarded and is never written literally to the target.
- [x] Read-only Home Preview maps the saved order/hidden choices onto the target catalogue, preserves target-only hubs, counts/skips saved hubs absent from the target and emits a target fingerprint. Preview performs no Local Storage write.
- [x] Home Apply requires explicit user confirmation and the exact fresh target fingerprint; a stale target/context is refused before any write.
- [x] Before mutation the owner captures exact raw Local Storage state for each changed target key. It writes only the target-context `order` / `hidden` keys, verifies the resulting logical layout and reverse-rolls exact raw state on failure. Rollback bookkeeping includes only writes that actually completed.
- [x] `editing`, caches, resources, auth/session and unrelated browser state remain outside both read and write allow-lists. The extension remains permission-free, has no background/network/cookie authority and the kiosk still exposes no remote-debugging port.
- [x] Settings presents Plexamp Home as a separate restore owner. The same selected backup/Preview can report Home work, but Home Apply is a separate explicit browser transaction from server/Headless Apply so a Plexamp service restart cannot invalidate frame-local rollback state.
- [x] Automated browser/Node contract coverage proves target-aware mapping, target-only preservation, safe skipping of source-only hubs, successful exact write/verification, stale Preview refusal before writes, injected mid-transaction failure with exact rollback and strict dashboard-side response validation.
- [x] CI source/wiring gates pin the Home restore controls, browser client, target fingerprint, fresh `20260831-home-restore-v1` Settings asset token and completed-write rollback invariant.
- [x] **Tests #4359** passed on exact implementation head `f010ae1b8700301bd4898e733ecdafd10bcfd480`: **983 tests, `OK`** on 31 August 2026.
- [ ] Physical acceptance remains: refresh the commissioned kiosk onto this source without broad browser changes; use a harmless Home reorder/hide candidate; prove read-only Preview and explicit Home confirmation; verify the target logical layout; restore the original layout; then confirm Plexamp login, selected library, player identity and normal playback remain unchanged.

- [ ] Final #90 closure requires synchronized CI plus full physical restore/rollback acceptance across all implemented owners.

Initial #90 implementation sequence:
- read-only planner/API: `95b557c1254921f706d0f7f9c9e7faebb549c08e`;
- runner registration: `0e67950b5dfc53c9123e836371030dcec245a5cd`;
- preview regression coverage: `4726dda3507b52218771c6956db51746280753e3`;
- compile/runner CI gate: `3a1143f27a338ebed71b68dec9dc95decebccab8`;
- Settings preview UI: `a99444333a56de1e577e7b8f330b9821957e57db`;
- preview-only UI contract gate: `bdff63df97b59e98027ab3aaab778636528cb1c0`;
- preview acceptance/restore contract documentation: `f0aafcf50519fc52cd6bbd3aff6331239fb199be`;
- transactional backend: `2c3f13234b30d1910748e466614962e5063ab593`;
- real Settings/EQ/mixer owner binding: `7067cdb28756117ef8aecbe62ce6795d3810ec0d`;
- confirmed restore UI: `4ffe8016570c675c80fb9c8a75ae41b4fd3f351f`;
- immutable Preview/separate restore-availability contract: `6445c93709b383bfd4a0087176ee3d7f1372299d`, `6136853e64c5dde279363c2fcc5314940cdbf781`;
- transactional regression coverage in the existing Settings test module: `15192d4f5949b47b1b20d5d1554f7929dad8b9ab`;
- phase-2 CI safety gates: `8007e20b60c5d88172cd0e85fd122161ee384037`;
- backup/restore visual polish: `ab9dc33400364f30c48c54cd63a96cf01761bf10`, `ac03f29584c8b4ea59d3efcf175548caed10db3f`, `da7035cfb60ba556b02eae07205180fec2ff2765`, `a2ee1372675bdb3dfb3afdc558c1f8d8d911aa7e`;
- stale-preview warning/control clarity follow-up: `4cd812843f0be7f8389e0cb8f35056cd6a1ba894`, `0710e30b2ad059b38ac1cb8a6acbb6e0a0ddfa85`;
- owning stale-warning source/cache/test fix: `2cb67e6ed34d67197871059eb7d2e9189b030544`, `fea3cfee3881279f70f5a77c670ebd688e7a14ab`, `196d7d0fae9182fc374d81d3476b5a1d382637c3`;
- Phase-2 physical acceptance / Phase-3 queue documentation: `68256ca355e42a101086072f1e35f65764af28ab`, `f173447a39aa1da56f13b63ad168ac839fa5fe0f`;
- Phase-3 restricted helper and app manager: `ebcad4d23e675039f1504e0be0d981d43cb7c5af`, `beb1fb364989d21ce2cba86764f97c7ce04f57bb`;
- Phase-3 helper packaging and transactional restore integration: `bb3d0f2cdd1028fefb001f409b35becb05246846`, `d6cd5f9a68021e2f4bc0d09e9b94eeac143641b5`, `f611337b5b729d36b61322123d4a833971837c8b`;
- helper catalogue/dependency closure and injected restart-failure coverage: `d3d23a2ae2e932ce9b0fcc3a5b68611d76c978f8`, `3467ec947c5e6fd67441d308ba5420f27768de79`, `e37d07d176fd1daad93a21b952568c927b1186c5`, `ac7020b14829c6d0e9892c139c974ebcc821c295`;
- Headless-aware Restore UI, transaction regressions and CI gates: `95c4b483c18fcc6c1ad142aeff862259032354a5`, `0d43cb47122df8242e153a435ce11604d32a3c7d`, `2fad5cebbf4e2e365b71b5b07573d124b7c9405`, `56c3624f416888249c74013f8097ab13b99af963`;
- Phase-3 ownership synchronization: `8eef583c690a9b3e6525305e65d5934a8e0cbcd8`;
- commissioned-runtime identity correction/coverage: `0240473a6f9f7c4ef45b0acfbc07f109c4fd4e37`, `a85c68e4d8818382d044110a9cf704821201af56`, `ebbbecdf0b831d21c1fb76eea2075a61775aee1d`, `84f3e256979dc429c4dbf3622f2bae98e197d116`;
- physical-finding ownership synchronization: `1fd58f5ff0f3508793db302285a068b44034b850`;
- production direct-run import fix/gate: `6c0f826288492ea44c473e03302a4c190fb31d46`, `0ff222958659a63e041f6d4675ad7fb22dd38f27`;
- Phase-3 physical acceptance ownership synchronization: `bfd6614d2e4c8b12d04c74199e6723a75b6f32bb`;
- Phase-4 completed-write rollback/cache/CI hardening and final implementation gate: `ac00bbf3c36c0e93d9557d26f3bdf9b6590ff439`, `63b1b643832505ba68b23164871661a8c7344a2c`, `edb833e2f0f2ba22a1f705d63c0627c0714e2ec3`, `f010ae1b8700301bd4898e733ecdafd10bcfd480`.

## Current supported release

**A Clockwork Plex `v0.4.0` — Unified Bedside Appliance** is the current published release.

- Accepted and merged `main` commit: `d5481b4d52627cbf57a2aa32f974d619fb38ee75`.
- GitHub Actions **Tests #4200** passed on that exact merged `main` commit.
- Published `v0.4.0` was verified identical to the merge commit (`ahead=0`, `behind=0`, no changed files).
- `main` is the normal supported installation/update channel.
- `v0.4.0` is immutable; later `main`/`develop` work is not part of that tag.

## Settled release invariants

### Audio

- Scheduled alarms **bypass Music Master** and music EQ.
- EQ music path: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm path: per-alarm start/target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- CamillaDSP is pinned to accepted `4.1.3`; canonical unit is `a-clockwork-plex-camilladsp.service`.
- The supported audio lifecycle is under `scripts/audio/`.
- `scripts/audio/preflight-eq.sh` is the historical read-only bedroom-Pi validation gate/diagnostic, not the normal installer path.

### Weather

- Open-Meteo supplies forecast data.
- Ecowitt Push or Weather Underground PWS may supply current observations; the selected current provider is authoritative for outdoor values.
- Fresh Ecowitt data may supplement WU indoor temperature/humidity only; stale supplementary values expire.
- WU selected-period rainfall history supplies Today / Last 7 days / Current month / Current year.
- A separate WU lifetime service discovers/backfills the full station archive independently of the selected rainfall period.
- WU secrets remain outside browser configuration, argv and logs under the restricted root-owned secret path.
- Repeat plain `setup.sh` preserves the commissioned Weather provider unless explicitly changed.

### Appliance/bootstrap

- `setup.sh` is the normal public installer; `appliance-installer.sh` is the guarded lower-level engine.
- Plexamp Headless `4.13.2`, appliance Node `20.20.2` arm64 and CamillaDSP `4.1.3` are the accepted v0.4.0 runtime identities.
- The accepted production SD remains protected; **a separate spare SD is the disposable acceptance target** for clean-room release validation.
- Validated hardware: Raspberry Pi Touch Display 2, PN532 I2C bus 1/address `0x24`, Raspberry Pi DAC Pro (`CARD=Pro`).
- Required boot mutation stops at an explicit reboot checkpoint.

### Presentation/runtime

- Seven daytime themes and accepted Classic/Astronomy night presentation are closed unless a real regression appears.
- Touch-to-wake, scheduled night dimming and burn-in shifting are implemented and are not future backlog items.
- Settings touch controls, alarm weekday/status presentation, clock-colon timing, AirPlay marquee/classification, navigation and EQ bypass presentation are accepted.

## v0.4.0 acceptance and release history

The detailed chronology remains in the history/evidence documents linked at the top of this file. Current release milestones:

- Physical clean-room appliance acceptance completed through #64 on the replacement spare SD; exact original tested runtime/source head `215bcedb43369844b5968ae24a7169e49636ef99`.
- Repository/release hygiene completed through #72; Tests #4103 and closing #4105 passed.
- Documentation/portability/branch polish completed through #77; #75 Tests #4127 passed **922/922**.
- #78 catalogued all **155** live `tests/test_*.py` modules and added two-way catalogue enforcement; Tests #4167 passed **925/925**.
- #79 added durable Settings → About release metadata; Tests #4173 passed **925/925**.
- #80 completed release-ready README/INSTALL and visual first-use guidance.
- #81 final post-polish validation Tests #4177 passed **925/925**.
- #82 final blank-Pi follow-up physically proved Weather full-history presentation, NFC and a real scheduled alarm ring → Snooze → re-ring → Dismiss. Follow-up Tests #4193 passed **927/927**, synchronization Tests #4197 also passed.
- #83 PR #2 merged to `main` as `d5481b4d52627cbf57a2aa32f974d619fb38ee75`; exact post-merge **Tests #4200** passed; `v0.4.0` was published and verified identical.

**All v0.4.0 release gates are complete.**

## Future product backlog — next development cycle

These are post-v0.4.0 ideas, not commitments to one release. Design/test independently before promotion to `main`.

### Agreed implementation order

Unless deliberately reprioritised, implementation proceeds in this order:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — IN PROGRESS at #90; #88 ownership COMPLETE, #89 export COMPLETE, Headless restore Phase 3 PHYSICALLY ACCEPTED, Home restore Phase 4 IMPLEMENTED / CI ACCEPTED
3. **Touchscreen Plexamp text entry**
4. **BBC News**
5. **Events calendar**
6. **High-resolution Plexamp audio / mixer-EQ path**
7. **Astronomy**

This priority list is authoritative. Detailed sections below are technical reference and do not imply a different order.

### Settings and appliance ownership

- [x] **Configuration backup/export — COMPLETE at #89.** Schema-v1 secret-free ACP/audio/Headless export plus the live browser Home bridge passed on the commissioned Pi with 15 ordered Home items, 1 hidden item, no browser omission and zero warnings; synchronized `develop` Actions is green.
- [x] **Plexamp preference backup feasibility/discovery — COMPLETE at #88.** Exact Headless allow-list and browser Home `order` / per-hub `hidden` key families are physically mapped. Auth/resource/caches/editor/device identity are excluded. Raw Plexamp/Chromium profiles and LevelDB are not backup units.
- [ ] **Configuration import/restore — IN PROGRESS at #90.** Read-only Preview, transactional ACP/server Phase 2 and version-aware allow-listed Plexamp Headless Phase 3 are physically accepted. Target-context-aware Plexamp Home Phase 4 is implemented and CI accepted; its harmless commissioned-Pi round-trip is the remaining Phase-4 physical gate.
- [ ] **Reset-to-defaults workflow.** Add an intentional confirmation-gated reset that distinguishes user configuration from appliance/runtime ownership instead of recommending manual JSON deletion.

### Touchscreen Plexamp text entry

- [ ] **Plexamp search keyboard/bridge.** The ACP Settings screen has its own touchscreen keyboard, but embedded Plexamp is a separate origin/surface. Investigate a safe touchscreen text-entry bridge that does not depend on the desktop OS on-screen keyboard. The permission-free localhost-only content bridge introduced by #89 is the preferred foundation if physical acceptance confirms it behaves reliably.

### News

- [ ] **BBC News headlines page.** Use BBC RSS/Atom feeds, assuming they remain publicly available at implementation time; do not scrape BBC HTML. Start with top headlines and optionally UK/World/Science/Technology where the feed catalogue supports it cleanly.
- [ ] **Cached/background feed handling.** Fetch outside render, cache the last successful feed, show update/source time and fail gracefully to stale-but-labelled content. News failure must never affect the appliance.
- [ ] **Safe headline presentation.** Sanitise feed markup, preserve BBC attribution and define kiosk-safe article opening.
- [ ] **Touch layout.** Favour a readable headline list/cards with clear age/source information and natural Touch Display 2 scrolling.

### Events calendar

- [ ] **Events calendar design spike.** Define the first data model: local-first storage and/or read-only iCalendar/ICS/CalDAV are preferable starting points; optional cloud-provider integrations remain separate.
- [ ] **Useful bedside views.** Today, upcoming events and a compact month/date browser; clearly distinguish all-day/timed events.
- [ ] **Calendar Settings/ownership.** Keep credentials/remote secrets out of browser-visible configuration and make offline/stale state explicit.
- [ ] **Reminders are separate.** Calendar events never silently become alarm-clock alarms; any future reminder needs explicit user policy and audio/priority semantics.

### High-resolution Plexamp audio / mixer-EQ path

The current v0.4.0 audio profiles intentionally use a fixed **16-bit / 44.1 kHz** shared bus. Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

- [ ] **Physical capability audit.** Use known 16/44.1, 24/48, 24/96 and 24/192 Plex files. Record Plexamp output mode/rate, DAC `aplay --dump-hw-params` and live ALSA `/proc/asound/.../hw_params` before selecting a production bus.
- [ ] **Choose the managed high-resolution bus.** Compare at least 24/96 and 24/192-class operation (appropriate ALSA container such as `S32_LE` where required) for CPU, stability, latency and CamillaDSP. Do not choose 192 kHz merely because the DAC advertises it.
- [ ] **Remove the 16/44.1 bottleneck from managed EQ.** Preserve source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → limiter and the post-EQ scheduled-alarm join.
- [ ] **EQ-active high-resolution plus native bypass.** Preferred UX: EQ active → accepted high-res DSP path; EQ bypass → source-rate-native Direct path and bit-perfect only where measured. If volume/reserve/limiting/resampling remain active, report managed bypass rather than falsely claiming bit-perfect.
- [ ] **Investigate source-rate-native Direct Plexamp.** Test 44.1/48/88.2/96/176.4/192 kHz direct-to-DAC and sample-rate matching. Existing Bypass EQ may become route selector only if alarm takeover, Maximum Alarm Volume, handoff and recovery stay deterministic; **appliance reliability outranks a bit-perfect badge**.
- [ ] **Define resampling policy.** If DSP uses one fixed high rate, choose deliberate high-quality conversion for other Plexamp rates and AirPlay rather than accidental ALSA `plug` conversion.
- [ ] **Preserve AirPlay compatibility.** Treat AirPlay according to its actual received format; do not advertise 96/192 kHz AirPlay merely because the internal bus can run there. Prove both handoff directions after high-rate playback.
- [ ] **Expose truthful diagnostics.** Report source format/rate, internal processing format/rate and final DAC format/rate separately.
- [ ] **Automated regression.** Protect route rendering/fallback, EQ active/bypass and scheduled-alarm authority.
- [ ] **Physical acceptance matrix.** Exercise all four source-rate classes through EQ/native modes, a real scheduled alarm during high-rate playback, then AirPlay takeover/return. Use “native/bit-perfect” only when measured ALSA/DAC parameters prove it.

### Astronomy — major new application area

Treat Astronomy as a **multi-screen touch section** with its own sub-navigation, in the spirit of Peter Duffett-Smith: useful numerical astronomy rather than decorative horoscope content. 🔭

- [ ] **Technical spike/calculation authority.** Prefer deterministic local/offline ephemeris. Compare a maintained astronomy library/ephemeris source with compact well-tested Duffett-Smith/Meeus-style calculations. Define reference fixtures/tolerances first.
- [ ] **Observer/location model.** Reuse existing latitude/longitude/timezone where sensible, with explicit Astronomy confirmation/override if needed.
- [ ] **Overview / Tonight.** Julian Date, local/Greenwich sidereal time, Sun/Moon headline state and notable current-night rise/set events.
- [ ] **Sun.** Sunrise/transit/sunset; civil/nautical/astronomical twilight; day length; RA/Dec; altitude/azimuth; useful seasonal events where reliable.
- [ ] **Moon.** Moonrise/transit/moonset; phase/age/illumination; next principal phases; distance/angular diameter; RA/Dec; altitude/azimuth.
- [ ] **Planets.** Mercury–Neptune rise/transit/set and useful position data; investigate magnitude, elongation, distance and constellation where reliable.
- [ ] **Navigation/presentation.** Touch-first 1280×720 sub-navigation, global drawer always reachable, night presentation designed from the outset.
- [ ] **Validation.** Reference dates/locations plus circumpolar/no-rise/no-set/polar/DST/local-date edge cases.

### Weather

- [x] Friendly forecast-location entry — COMPLETE #86.
- [x] WU-only supplemental-indoor expiry physical confirmation — COMPLETE #87.

**Weather is complete for the agreed next-cycle scope.**

## Deliberately not on the future list

Already implemented/accepted: scheduled alarms and real playback; night dimming/touch-to-wake; burn-in shifting; Weather history/provider selection; idle-return/dashboard behaviour; alarm Settings/status; AirPlay receiver naming; managed EQ and source/master/alarm gain controls; fresh-install/setup automation.

Keeping completed work off the future list matters. Otherwise the roadmap starts requesting features the appliance already has, which is an impressively inefficient form of time travel. 🕰️

## v0.4.0 release exit sequence

1. [x] Physical replacement-SD clean-room acceptance through #64.
2. [x] Repository/release hygiene through #72.
3. [x] Documentation/portability/branch hygiene through #77.
4. [x] Maintainer test-suite catalogue (#78).
5. [x] Settings → About/version contract (#79).
6. [x] Release-ready README/INSTALL and visual first-use material (#80).
7. [x] Pre-approval validation (#81).
8. [x] Final blank-Pi follow-up/spot-check (#82).
9. [x] Explicit owner approval for PR #2 merge — received 23 August 2026.
10. [x] PR #2 merged to `main`; exact merge `d5481b4d52627cbf57a2aa32f974d619fb38ee75` passed Tests #4200; `v0.4.0` published and verified identical (#83).

**All v0.4.0 release gates are complete.**
