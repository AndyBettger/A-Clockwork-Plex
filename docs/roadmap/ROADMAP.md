# A Clockwork Plex Roadmap

**Last updated:** 16 September 2026  
**Active integration branch:** `develop`  
**Active feature branch:** `feature/hi-res-audio-eq`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This began as the EQ/audio-installer roadmap. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide live roadmap.

## Roadmap authority and history

This file is the single live implementation/release/future-product roadmap. Detailed engineering chronology belongs in the development/history documents rather than turning the roadmap into a commit diary.

Specialist authorities:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership and Plexamp Home completeness;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and physical/product gate;
- [`../development/architecture/bbc-news.md`](../development/architecture/bbc-news.md) — #92 BBC News, article QR hand-off and configurable sections;
- [`../development/architecture/high-resolution-audio.md`](../development/architecture/high-resolution-audio.md) — active #85 hi-res/EQ architecture, test-appliance policy and acceptance boundary;
- [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md) — queued resilience design.

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not this development roadmap.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop`.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- feature branches do not merge merely because CI is green: relevant Raspberry Pi/touchscreen behaviour must pass its physical acceptance gate first.
- the next release version is intentionally not assigned until its real scope is clear.

## Current development cycle

### #84 Development-cycle bootstrap — COMPLETE

- [x] Created `develop` from the post-v0.4.0 baseline.
- [x] GitHub Actions validates `develop` and `main`.
- [x] Established the feature-branch → `develop` → accepted release model.

### #85 High-resolution audio feasibility audit — COMPLETE; IMPLEMENTATION ACTIVE

The current accepted managed EQ and Direct/fallback profiles still use a fixed **S16_LE / 44100 Hz** shared music path. High-resolution implementation is now active on `feature/hi-res-audio-eq`, branched from the accepted post-PR-#12 `develop` state.

The historical `scripts/audio/preflight-eq.sh` is the old pre-EQ-install gate and is **not** the baseline for this phase: it intentionally expects the managed EQ files to be absent and the previous direct route to be active. The current installed-stack baseline instead uses read-only `scripts/audio/verify-audio.sh` plus `scripts/audio/audit-hi-res-audio.sh`. The bedroom Pi is the development/test appliance for this work: controlled route, sample-format and lifecycle experiments may be performed directly on it. Recovery is provided by committed feature-branch checkpoints plus the known-good `develop` and `main` rebuild baselines; a separate spare SD card is not a project requirement.

- [x] Created `feature/hi-res-audio-eq` from accepted `develop` after PR #12 merged.
- [x] Documented the development-appliance/recovery policy in `docs/development/architecture/high-resolution-audio.md`.
- [x] Added a read-only installed-stack hi-res audit separate from the historical pre-install EQ gate.
- [x] Captured the first physical read-only baseline on 14 September 2026: `verify-audio.sh` passed; the DAC was live at **S16_LE / 44.1 kHz stereo**; the ALSA split bus, installed profile and CamillaDSP independently fix the current processing path to **S16_LE / 44.1 kHz**; route/EQ/services were healthy and CamillaDSP used about **0.6% CPU** at the snapshot.
- [x] Recorded two audit corrections from that run: repository verifier scripts must be invoked through `bash`, and loopback procfs inspection must follow card index 7 (`/proc/asound/card7`) rather than the configured module id string. The Raspberry Pi DAC Pro is I2S, so the absent USB-style `/proc/asound/Pro/stream0` descriptor is expected rather than a hardware failure.
- [x] Physically measured the idle Raspberry Pi DAC Pro on 14 September 2026 with the guarded capability probe: exact stereo `RW_INTERLEAVED` `S16_LE`, `S24_LE` and `S32_LE` constraints were accepted at **44.1/48/88.2/96/176.4/192 kHz**; packed `S24_3LE` was rejected at every tested rate. The probe restored CamillaDSP → Plexamp → AirPlay → dashboard, `verify-audio.sh` passed after restoration, and the route returned to `split-bus-active` without Direct failback.
- [x] Completed the known-source Plex baseline on 15 September 2026 with **16/44.1, 24/48, 24/96 and 24/192** material. The 44.1 kHz control stays 44.1 throughout. For the 48/96/192 sources, Plexamp direct-plays and keeps its source stream/internal mixer at the native rate and explicitly prefers that rate for device 9 (`A Clockwork Plex - Plexamp`), but the managed device opens at **44.1 kHz** and the ACP loopback → CamillaDSP → physical DAC path remains **S16_LE / 44.1 kHz**. The fixed ACP managed output-device chain is therefore the measured rate/sample-format bottleneck; Plexamp's decoder/mixer is not. CamillaDSP remained about **0.6–0.7% CPU** on the accepted 44.1 kHz graph.
- [x] Added guarded `scripts/audio/rehearse-hi-res-bus.py` for the first reversible managed-bus experiments. It is plan-only by default, supports only **S32_LE / 96 kHz** and **S32_LE / 192 kHz**, requires the exact accepted S16/44.1 baseline before mutation, delegates the service/route transition to the accepted route owner, provides a normal-user read-only snapshot, and requires explicit verified restore.
- [x] First 96 kHz attempt exposed a reboot/interruption recovery weakness: the candidate and `state.json` persisted but both old `shutil.copy2` recovery files returned as zero-length files. Normal restore correctly refused; checksum-gated recovery reconstructed only from repository baseline files whose hashes exactly matched the recorded originals, restored `split-bus-active`, passed `verify-audio.sh` twice and returned the physical DAC to S16_LE/44.1. The rehearsal tool was hardened with atomic writes, file/directory `fsync`, pre-mutation checksum verification, explicit durable-backup state and candidate-hash verification.
- [x] Hardened **S32_LE / 96 kHz** rehearsal physically passed on 15 September 2026: with known 24/96 Plex material, device 9 opened at **96000 Hz**, the ACP loopback and CamillaDSP capture were **S32_LE / 96000 Hz / 4 channels**, the Raspberry Pi DAC Pro was **S32_LE / 96000 Hz / 2 channels**, and CamillaDSP used about **1.2% CPU**. Explicit restore returned the exact accepted route, `verify-audio.sh` passed, a second verifier pass also passed, and the DAC was independently confirmed back at **S16_LE / 44100 Hz**.
- [x] Hardened **S32_LE / 192 kHz** rehearsal physically passed on 16 September 2026: known 24/192 Plex material traversed the ACP loopback, CamillaDSP and Raspberry Pi DAC Pro at **S32_LE / 192000 Hz**. CamillaDSP used about **2.2–2.4% CPU**, and normal restore returned the accepted S16/44.1 graph with verifier success.
- [x] Deliberate reboot durability repeat passed at 192 kHz: the fsynced split-route/default recovery files retained their exact accepted SHA-256 hashes across a reboot performed without manual `sync`; after boot Plexamp device 9 opened at **192000 Hz** with preferred/best 192000, the full managed path remained S32/192, normal `--restore` worked without the exceptional recovery tool, verification passed twice and the DAC returned to S16/44.1.
- [x] **Provisional managed candidate:** advance **S32_LE / 192 kHz** to the wider functional gate, retaining **S32_LE / 96 kHz** as fallback if the broader stability/compatibility evidence favours it.
- [ ] Wider selected-candidate gate: measure lower-rate Plex/resampling truthfulness, live EQ changes/bypass, Plexamp/source trims and Music Master ownership, AirPlay, alarm preview/scheduled takeover, latency/long-duration stability and recovery before selecting a production managed-bus policy.

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

- [x] Portable ACP settings are a normalised logical model rather than raw `config.json` bytes.
- [x] Credentials/auth/session, hardware identity/topology, raw ALSA, caches and machine identity are excluded.
- [x] Plexamp native/Home ownership and portability boundaries are classified and documented.

Detailed authority: [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md).

### #89 Configuration backup/export — COMPLETE

- [x] Schema-v1 compatibility export remains supported.
- [x] Schema-v2 export carries portable ACP state, broader classified Plexamp native settings and complete logical Home-v2 state without source machine identifiers.
- [x] Production bridge 1.5.0 activates the bounded native/Home-v2 portability transport with no extension permissions, background authority or production DevTools interface.
- [x] Commissioned-Pi export specimens and real-use backups passed structural/portability inspection.

### #90 Configuration import/restore — COMPLETE

- [x] Read-only Preview → choose target → Review → Confirm flow accepted at 1280×720.
- [x] Schema-v2 multi-owner transaction preserves stale protection, verification and reverse rollback across native Plexamp → Home → ACP server owners.
- [x] Commissioned-Pi Reset/Restore round trips converged to zero supported differences.
- [x] Schema-v1 backups retain their accepted compatibility path.

#89/#90 and #93 are integrated into `develop`; the Settings/appliance-ownership engineering track is closed.

### #91 Touchscreen Plexamp text entry — COMPLETE

- [x] Shared Settings keyboard uses true one-shot Shift and theme-aware presentation.
- [x] Plexamp Search keyboard/bridge physically accepted.
- [x] General Plexamp text fields physically accepted for Home title, Smart Playlist metadata, Home Screen section title and Player Name.
- [x] Bridge remains permission-free, loopback-only and excludes login/password fields.

### #92 BBC News — CORE + ARTICLE QR + CONFIGURABLE SECTIONS COMPLETE

#### Accepted core

- [x] BBC RSS feed/cache authority, link-free `/api/news` story model, last-good cache and stale/degraded presentation physically accepted.
- [x] Touch News page, category rail, synchronized scrollbar, local detail modal, Settings workspace and Top Stories ticker physically accepted.
- [x] News as manual, Startup and Idle-return screen physically accepted, including a real reboot into News.
- [x] Real Wi-Fi-loss test retained cached stories/ticker and recovered normally.

#### Accepted article QR hand-off

- [x] Article hand-off retains the absolute HTTPS destination supplied by the trusted BBC RSS item, using `<link>` first and a valid HTTPS `<guid>` fallback.
- [x] QR SVG is generated locally; the kiosk exposes no article anchor and no arbitrary URL-to-QR input.
- [x] Initial full automated gate passed in **Tests #4732**; trusted-RSS destination/GUID refinement passed **Tests #4749**.
- [x] Commissioned 1280×720 + iPhone acceptance passed on 11 September 2026: normal BBC News destinations opened the installed BBC News app, the live BBC Weather destination from the Science feed gained a QR and opened correctly in Chrome, and kiosk Chromium remained in ACP.

#### Configurable sections follow-up — COMPLETE / PHYSICALLY ACCEPTED

Implementation branch: `feature/news-custom-feeds`  
PR: **#12 — Add configurable BBC News feeds**

- [x] Preserve the original five sections — Top Stories, UK, World, Science & Environment and Technology — as the out-of-box enabled set.
- [x] Expand the friendly built-in catalogue with England, Scotland, Wales, Northern Ireland, Business, Politics, Health, Education and Entertainment & Arts.
- [x] Allow sections to be enabled/disabled and reordered; the default News section must remain enabled. Built-in section names and source URLs are fixed/canonical in the finished UI, while custom-feed display names remain editable.
- [x] Add **News → News feeds** for bounded custom BBC News sources; the first physical pass established that this belongs with ordinary News configuration rather than under Advanced.
- [x] Custom source authority remains exact HTTPS `feeds.bbci.co.uk/news/.../rss.xml`; arbitrary hosts, HTTP, credentials, non-News paths and redirect escapes are rejected.
- [x] Friendly custom-source entry may also accept an ordinary HTTPS BBC News section page on `bbc.co.uk`/`bbc.com`. The browser converts its `/news/...` path to the corresponding `https://feeds.bbci.co.uk/news/.../rss.xml` candidate and then uses the existing strict RSS **Check feed and add** gate; ACP does not scrape or store BBC page HTML.
- [x] New/changed custom feeds use a read-only **Check feed and add** preflight before the custom source can become usable; the server parses the candidate, derives a sensible label and deterministic stable id, and returns no source URL in the validation response.
- [x] A changed source cannot reuse cached content belonging to the previous URL as if it came from the replacement source.
- [x] `/api/news` remains source-URL/article-link/GUID free; the accepted phone-owned QR boundary remains unchanged.
- [x] Top Stories remains the independent ticker source even if another section is active/default or Top Stories is hidden from the rail.
- [x] `feed_order` and `custom_feeds` are portable News state; downloaded RSS/cache state remains excluded. The in-flight `feed_labels` compatibility field remains tolerated internally but built-in renaming is no longer exposed by the finished Settings UI.
- [x] **Tests #4753** passed the first complete implementation gate on `58e47e800ff13ed98f0834a7f429d958b7927ac0`.
- [x] **Tests #4765** passed compile, JavaScript/page/shell and full regression CI on commissioned-test head `2ea286211cb8712553dce3e131598c06b2d6aa4c`.
- [x] Commissioned-Pi repeat `bash setup.sh` on that head passed with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings**.
- [x] First 1280×720 functional pass proved the enlarged catalogue plus Business enable → temporary **Business Test** rename → reorder → default selection → saved News rendering, with the Top Stories ticker still independent. The commissioned feed was later returned to canonical **Business** before the final custom-only feed-manager decision.
- [x] Physical findings were folded back into the branch: the section rail gained a bounded touch-scroll region, feed-editor cards gained explicit vertical separation, and the feed editor moved into Settings → News.
- [x] **Tests #4774** passed compile, JavaScript/page wiring/shell and the full regression suite on the first post-physical-follow-up implementation/catalogue head `bc2f5b7c7a4e49bec9376fa49e1c73b279051e8a`.
- [x] Commissioned-Pi repeat `bash setup.sh` on follow-up head `8106ab5e91bcc4498cd1fca41959ed231c9e8815` again passed with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings** and preserved the existing commissioned News configuration.
- [x] Second 1280×720 pass confirmed that the enlarged News rail now scrolls, **News feeds** is correctly owned by Settings → News, and feed-editor cards have useful visual separation.
- [x] That second pass identified two presentation-copy refinements: stop presenting the bare `feeds.bbci.co.uk` host as though it were a useful browser destination, and make the rail scrollbar visually match the existing story-list control. Full-feed guidance was added and the first scrollbar styling attempt passed **Tests #4779/#4780**.
- [x] Third 1280×720 pass proved the Europe URL itself passes **Check feed**, but also showed Chromium still drew native rail-scrollbar arrow buttons, the checked feed retained the generic **Custom BBC feed** label, and helper copy still referred to a nonexistent **Save Changes** step. The branch replaced the native rail scrollbar with the same custom synchronized track/thumb presentation used by the story list, derives labels from useful RSS channel metadata (`BBC News` title + `BBC News - Europe` description → **Europe**), and describes Check feed without an explicit-save instruction.
- [x] The next commissioned 1280×720 pass confirmed the left rail and story scrollbars now visually match, the Europe feed is automatically named **Europe** after Check feed, Europe can be enabled and its real stories render in the mixed built-in/custom rail, while the bottom ticker remains visibly tied to Top Stories.
- [x] That pass identified the remaining Settings usability refinement: the large feed-editor cards are sensible for editing but poor for long-distance ordering, and the Add BBC feed control/new-row location were not obvious. The branch separated **News feeds** from a compact **News → Feed order** page with a touch drag grip and Enabled/Disabled control per row; Add BBC feed uses a normal button footprint and scrolls/highlights the newly created editor.
- [x] The same shared touch-first reorder helper now enhances **Weather → Clock weather cards**: the visible arrow controls are replaced by a drag grip while the established `ACPClockCards` state owner and unified Settings transaction remain authoritative.
- [x] **Tests #4801** passed Python compilation, JavaScript/page/shell checks and the full regression suite on touch-order implementation head `92cb656452fb546f20f078d6ee76f0e72b31fc6b`, including direct syntax/contract coverage for the shared reorder helper, News Feed order and Clock-card drag enhancer.
- [x] The following commissioned pass confirmed Feed order long-distance drag plus edge auto-scroll, the Enabled/Disabled control, and Weather Clock-card reordering all work physically. The smaller Add BBC feed button was also accepted visually.
- [x] That pass exposed two final touch-polish faults: Add BBC feed created the editor but did not move the Settings scroller to it, and the font-rendered 2×3 grip looked off-centre. The screenshot also showed that shared Settings display rules were defeating native `[hidden]` on the News editor's Enabled and Move buttons. The branch captures the pre-add editor ids before the original click handler runs, explicitly scrolls the Settings detail pane to the new card, draws a centred CSS dot matrix for the grip, and enforces the editor-only hidden controls with `display: none !important`.
- [x] **Tests #4807** passed Python compilation, JavaScript/page/shell checks and the full regression suite on follow-up head `e5828a7205394019f4fb6d24e1c8ef46547beec3`.
- [x] Commissioned recheck on `1e98c49bf8b661a17a5d4de5715d820be487cdbe` confirmed the centred 2×3 grips on both News Feed order and Weather Clock weather cards, confirmed Add BBC feed scrolls to its new editor, and confirmed the duplicate Enabled/Move controls are absent from News feeds.
- [x] Product simplification agreed after that pass: **News feeds is now custom-source management only**. Built-in feed editor cards are hidden completely there and retain fixed canonical names/URLs; Feed order and Sections remain the places to enable, disable, order and choose the default section. The page shows a friendly empty state when no custom feeds exist.
- [x] **Tests #4824** passed the full automated gate for the custom-only manager implementation on `90a4eee0f66c63bf7e3f5ba6272279ac177e2aa0`.
- [x] The next commissioned 1280×720 pass confirmed the custom-only News feeds presentation and empty state, confirmed Europe story QR hand-off still works, and physically proved that a non-BBC custom source is rejected before it can become usable.
- [x] That rejection pass exposed one usability fault: Check-feed success/failure was reported in the page-level intro card and could be off-screen. Validation feedback is now rendered beside the custom feed's own Check feed controls instead.
- [x] Inspection of a live BBC Sussex section page established the useful ordinary-page pattern `/news/england/sussex` → `/news/england/sussex/rss.xml`. The Settings helper now accepts such BBC News page URLs and locally derives the RSS candidate before the unchanged strict server preflight; **Tests #4834** passed Python compilation, JavaScript/page/shell checks and the full regression suite on implementation head `81fd4798d7954baf46e17cbd8f28f22868f6bd67`.
- [x] The first commissioned load of that helper exposed a browser-runtime regression missed by syntax/unit CI: its subtree `MutationObserver` reacted to the helper's own caption/help/status DOM writes, creating a self-sustaining mutation loop that starved the Settings page event loop. The observer is now restricted to direct editor-card additions/replacements, DOM decoration is idempotent, a dedicated regression assertion prevents restoring subtree observation, and the script cache key was bumped. **Tests #4839** passed compile, JavaScript/page/shell checks and the full regression suite on fix head `708296f0d3d84c0218541c79ad436ec8e93062d6`.
- [x] Commissioned recheck confirmed Settings loads normally after the observer fix. Ordinary BBC page URLs physically added **Sussex, Surrey and Hampshire & The Isle of Wight**, each converted to the expected `feeds.bbci.co.uk` RSS source; QR hand-off also works from those custom sections. A non-BBC source still fails locally beside its own controls as intended.
- [x] Final validation-control polish adds explicit spacing below the action row and relabels the successful action to **Check feed and add**. **Tests #4844** passed Python compilation, JavaScript/page/shell checks and the full regression suite on implementation head `a0466bf605515078961e7110f81f9942cd473094`.
- [x] Commissioned recheck confirmed the final **Check feed and add** label/message spacing is comfortable at 1280×720 and the custom-feed Settings interaction remains usable.
- [x] Changed-source/cache isolation is physically accepted: a commissioned **Cache Test** custom feed first populated Kent stories, then the same feed record was changed to the Essex source and populated Essex content without presenting stale Kent stories under the replacement source. The temporary feed was then removed.
- [x] Portable Backup/Reset/Restore ownership passed the bounded commissioned-appliance read-only gate on 14 September 2026: a fresh **schema-v2** backup contained logical News state including Business as default plus the Europe, Sussex, Hampshire & Isle of Wight and Surrey custom-feed records with canonical BBC RSS URLs; Reset Preview reported **`settings.news · 4`** and exactly `custom_feeds`, `default_category`, `enabled_categories` and `feed_order` as changed News paths without Confirm; Restore Preview of that fresh backup correctly reported **No changes** against the unchanged live appliance. Generated RSS/cache/private article state remains outside the portable model.

Detailed authority and the physical checklist: [`../development/architecture/bbc-news.md`](../development/architecture/bbc-news.md).

### #93 Reset-to-defaults workflow — COMPLETE

- [x] Full ACP + Plexamp native + bounded Home + commissioning transaction physically accepted.
- [x] Reset uses version-controlled ACP defaults through production normalisers; EQ/mixer/audio baselines are verified.
- [x] Plexamp login/library/identity and managed output survive Reset correctly.
- [x] Full Home customisation ownership (`order`, `hidden`, `viewSettings`, `customHubs`) was classified through disposable-profile evidence and a reversible scrub/rebuild/rollback proof.
- [x] Commissioned-Pi Preview → Review → Confirm and fresh post-reset zero-change Preview passed.
- [x] #93 merged to `develop` via PR #9; #89/#90 completeness then merged via PR #10.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — COMPLETE through #93, including schema-v2 Backup/Restore
3. **Touchscreen Plexamp text entry** — COMPLETE #91
4. **BBC News** — COMPLETE, including article QR and configurable sections
5. **High-resolution Plexamp audio / mixer-EQ path** — ACTIVE
6. **Astronomy**
7. **Appliance resilience**
8. **Events calendar**

This priority list is authoritative.

## Future product backlog

### High-resolution Plexamp audio / mixer-EQ path

Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

Active branch: `feature/hi-res-audio-eq`

- [x] Measure the Raspberry Pi DAC Pro's exact supported format/rate combinations on the real appliance with the audio graph deliberately quiesced and restored: `S16_LE`, `S24_LE` and `S32_LE` accept 44.1–192 kHz; packed `S24_3LE` does not. This proves ALSA hardware constraints, not yet sustained hi-res playback.
- [x] Physical capability audit with known **16/44.1, 24/48, 24/96 and 24/192** Plex files: Plexamp remains native-rate through its source stream/mixer and prefers 48/96/192 for the managed device, while the current ACP device opens at 44.1 and the downstream path remains **S16_LE / 44.1 kHz**. The managed ACP output-device chain is the measured bottleneck.
- [x] **S32_LE / 96 kHz** managed-bus rehearsal physically passed end-to-end with known 24/96 Plex material: device 9, loopback, CamillaDSP and the physical DAC all ran at 96 kHz, CamillaDSP used about 1.2% CPU, and exact restore returned the accepted S16/44.1 graph with verifier success.
- [x] **S32_LE / 192 kHz** managed-bus rehearsal also physically passed; a deliberate reboot repeat proved the hardened recovery copies remain durable without manual `sync`, device 9 and the full managed path return at 192 kHz after boot, and normal restore still returns the accepted S16/44.1 graph. **192 kHz is the provisional managed candidate; 96 kHz remains the fallback.**
- [ ] Run the wider 192 kHz candidate gate: lower-rate Plex/resampling truthfulness, live EQ/bypass, trims/Music Master, AirPlay, alarm takeover, latency/long-run stability and recovery.
- [ ] Remove the managed 16/44.1 bottleneck in the production profile while preserving trims → Music Master → reserve → EQ → limiter → alarm join.
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

- all included feature branches must be merged into `develop` only after automated and relevant physical acceptance;
- the clean-room installer/runbook must still pass on supported hardware;
- repeat `bash setup.sh` must remain safe/idempotent;
- repository/docs catalogues and this live roadmap must describe the actual shipped state;
- materially risky audio/storage experiments must remain isolated to feature branches with a known-good rollback/rebuild path through `develop` or `main`;
- release version/tag/name is assigned only after final scope and acceptance are known.
