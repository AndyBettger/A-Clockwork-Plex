# A Clockwork Plex Roadmap

**Last updated:** 29 September 2026  
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
- [`../development/testing/airplay-hi-res-buffer-investigation.md`](../development/testing/airplay-hi-res-buffer-investigation.md) — active #85 AirPlay/192 kHz timing and buffer investigation;
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

The commissioned managed EQ profile now runs a physically accepted fixed **S32_LE / 192 kHz** processing/output path, while the conservative Direct/fallback profile deliberately remains **S16_LE / 44.1 kHz**. High-resolution implementation remains active on `feature/hi-res-audio-eq` until the final stability/diagnostic gates and merge boundary are complete.

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
- [x] **Provisional managed candidate:** advance **S32_LE / 192 kHz** to the wider functional gate, retaining **S32_LE / 96 kHz** as fallback if the broader stability/compatibility evidence favours it. This is explicitly provisional until the wider gate passes.
- [x] First wider-gate AirPlay pass: Shairport acquired the fixed S32_LE/192 kHz managed path but playback was persistently choppy. Repository tracing confirms AirPlay leaves Shairport through ALSA `acp_airplay` → `plug`/softvol/`dmix` → loopback → CamillaDSP; **PipeWire is not in the current AirPlay path**.
- [x] **AirPlay timing diagnosis and fixed-192 correction physically complete:** the unchanged 192 kHz frame geometry reproduced persistent choppiness with repeated CamillaDSP underrun/overrun/stall recovery. Time-scaled ALSA/CamillaDSP geometry removed the sustained fault, and the final physically proven candidate keeps S32_LE/192 kHz with ALSA period/buffer **4096/32768**, CamillaDSP chunksize **4096**, queuelimit 4 and `target_level=12288` (~64 ms).
- [x] **Receiver-owned AirPlay fixed-192 gate physically passed:** the final high-target candidate passed separately bounded activation, idle, AirPlay startup, five-minute steady playback, EQ/volume/trim control and a later deliberate disconnect/reconnect with no audible choppiness and no filtered CamillaDSP/Shairport timing or error events. Exact recovery to S16_LE/44.1 passed after every rehearsal.
- [x] Keep **CamillaDSP Controller Adapt deferred**: the fixed 192 kHz graph has now passed the AirPlay stability/control/transition evidence that originally motivated the fallback design, so dynamic source-rate topology is not currently justified.
- [x] **Promoted production profile deployed and physically accepted on 29 September 2026:** guarded repair on the commissioned bedroom Pi installed split-route SHA-256 `9de505b8e9ef326558fd317f22afaba2006d056efb0c34c79457c43ec9881fec` and Direct/failback SHA-256 `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb`; `verify-audio.sh` passed during and after repair; route status reported `split-bus-active`; the live ACP bus, CamillaDSP capture and physical DAC were all S32_LE/192 kHz. Plexamp and AirPlay both played correctly, all three EQ bands worked, Plexamp/AirPlay trims and live/source volume controls behaved correctly, and Music Master worked as designed.
- [x] **Promoted Direct failback → split-bus recovery physically passed on 29 September 2026:** the normal route owner selected the exact promoted Direct hash `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb`, stopped CamillaDSP as intended and drove the physical DAC at S16_LE/44.1 with 1024/8192 geometry. AirPlay playback was clean and AirPlay Live, AirPlay Trim and Music Master all worked. The normal `activate-split-bus` path then restored the production split hash `9de505b8e9ef326558fd317f22afaba2006d056efb0c34c79457c43ec9881fec`, restarted CamillaDSP, passed `verify-audio.sh`, returned ACP/CamillaDSP/DAC to S32_LE/192 kHz, and the bounded transition error filter was empty.
- [x] **Truthful audio-path diagnostics physically accepted on 30 September 2026:** the API passed in both production split and Direct modes, and the corrected **Settings → Audio → Hardware** presentation is now physically visible at the commissioned 1280×720 UI. Split reports Source format/rate **Not reported**, Processing S32_LE/192 kHz/4ch and live DAC S32_LE/192 kHz/2ch; Direct independently changes Processing and DAC to S16_LE/44.1 kHz/2ch; normal return restores 192 kHz. Source remains deliberately unreported because current Plexamp/AirPlay observers expose no trustworthy source format/rate. In the normal split topology CamillaDSP continuously owns the physical DAC, so the DAC legitimately remains open at S32_LE/192 kHz even when neither source is actively playing; `Idle / closed` is only a representable exceptional ALSA state, not the expected silence state.
- [ ] **Active final #85 gate:** run the longer ordinary mixed-source production stability soak with XRUN/stall journal inspection before merge.

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

### #94 Native Plexamp desktop / visualiser migration feasibility — QUEUED INVESTIGATION

Goal: investigate replacing the legacy Plexamp Headless + embedded browser UI with the current ARM64 Linux desktop Plexamp so the bedside appliance can use the native visualisers **without sacrificing NFC launch, the managed ACP audio graph, alarm/AirPlay ownership, recovery or touchscreen navigation**.

This is deliberately queued **after #85 closes**. It is a feasibility/rehearsal track first, not permission to remove the accepted Headless runtime.

- [ ] Install the current supported ARM64 Linux Plexamp **alongside the accepted appliance only in a reversible test boundary**. Prefer the official 4.50.x Flatpak/AppImage path; do not replace the pinned Headless service during discovery.
- [ ] Confirm the native app can render its visualisers correctly on the commissioned Raspberry Pi GPU/display at the real 1280×720 touchscreen geometry and acceptable CPU/GPU load.
- [ ] Prove native Plexamp can select the existing ACP virtual output **`acp_plexamp`** (or an equivalently controlled host ALSA endpoint) so the accepted downstream chain remains Plexamp source → Plexamp trim → Music Master → reserve → EQ → limiter → alarm join → DAC. Do not bypass CamillaDSP or invent a second volume authority merely to gain the visualiser.
- [ ] Classify the Flatpak/AppImage audio boundary on the Pi. The current Linux 4.50 line supports direct ALSA output; prefer direct use of the existing ACP PCM over adding PipeWire/PulseAudio translation unless direct ALSA is physically unsuitable.
- [ ] Determine whether the native Linux app exposes the same local Plex Companion receiver surface used today by Headless on port 32500, especially `/player/playback/playMedia` and timeline/status endpoints. If compatible, reuse that boundary rather than rewriting NFC media selection.
- [ ] Run an NFC proof with the existing tag format. A successful scan must launch the intended Plex item in the **native local player**, not a separate Headless instance, and must preserve queue semantics used by ACP playback observation.
- [ ] Verify alarm takeover/dismissal/manual-resume, AirPlay takeover, Plexamp/AirPlay arbitration and route/failback behaviour with native Plexamp as the local player.
- [ ] Design a proper display owner for **Chromium dashboard ↔ native Plexamp**. The existing NFC display-switch script is the natural policy boundary, but current dashboard navigation assumes one Chromium kiosk window. Evaluate compositor/window-focus control plus a reliable touchscreen path back to ACP; do not depend on fragile coordinate automation.
- [ ] Confirm the native app can be raised/focused reliably on the current Raspberry Pi OS desktop/compositor after boot, after screen changes and after an NFC scan. Linux Plexamp 4.50 exposes native MPRIS including `Raise`, which may help one half of the transition; ACP still needs a deterministic way to return Chromium to the foreground.
- [ ] Decide whether an always-available ACP edge handle/overlay is required while native Plexamp is foreground so alarms, Settings and dashboard pages remain reachable without a keyboard.
- [ ] Audit settings/backup/reset ownership. Current browser bridges and Headless/Home storage contracts must not silently be assumed to apply to the rewritten desktop app; classify native Plexamp identity, preferences, Home customisation and claim state before migration.
- [ ] Keep Plexamp Headless as rollback until a native-player candidate passes reboot/autostart, NFC, audio, alarms, AirPlay, display switching, backup/reset and longer stability gates.
- [ ] Only after physical acceptance decide whether Headless is retired entirely. A two-player design where native Plexamp merely remote-controls Headless is **not the preferred visualiser path**, because Plex visualisers require locally decoded audio data.

Research notes recorded when queued:
- Plexamp 4.50.12 is on the stable desktop channel; Flathub's beta repository carries the current stable ARM64 Linux build while the normal Flathub listing still exposes the older 4.13 generation.
- Plex has stated Plexamp Headless will no longer be supported going forward, making this investigation useful for lifecycle reasons as well as the visualiser.
- The full Linux Plexamp is explicitly confirmed by Plex to provide visualisers on a Raspberry Pi when playback is local.

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — COMPLETE through #93, including schema-v2 Backup/Restore
3. **Touchscreen Plexamp text entry** — COMPLETE #91
4. **BBC News** — COMPLETE, including article QR and configurable sections
5. **High-resolution Plexamp audio / mixer-EQ path** — ACTIVE
6. **Native Plexamp desktop / visualiser migration feasibility** — QUEUED after #85
7. **Astronomy**
8. **Appliance resilience**
9. **Events calendar**

This priority list is authoritative.

## Future product backlog

### High-resolution Plexamp audio / mixer-EQ path

Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

Active branch: `feature/hi-res-audio-eq`

- [x] Measure the Raspberry Pi DAC Pro's exact supported format/rate combinations on the real appliance with the audio graph deliberately quiesced and restored: `S16_LE`, `S24_LE` and `S32_LE` accept 44.1–192 kHz; packed `S24_3LE` does not. This proves ALSA hardware constraints, not yet sustained hi-res playback.
- [x] Physical capability audit with known **16/44.1, 24/48, 24/96 and 24/192** Plex files: Plexamp remains native-rate through its source stream/mixer and prefers 48/96/192 for the managed device, while the current ACP device opens at 44.1 and the downstream path remains **S16_LE / 44.1 kHz**. The managed ACP output-device chain is the measured bottleneck.
- [x] **S32_LE / 96 kHz** managed-bus rehearsal physically passed end-to-end with known 24/96 Plex material: device 9, loopback, CamillaDSP and the physical DAC all ran at 96 kHz, CamillaDSP used about 1.2% CPU, and exact restore returned the accepted S16/44.1 graph with verifier success.
- [x] **S32_LE / 192 kHz** managed-bus rehearsal also physically passed; a deliberate reboot repeat proved the hardened recovery copies remain durable without manual `sync`, device 9 and the full managed path return at 192 kHz after boot, and normal restore still returns the accepted S16/44.1 graph. **192 kHz is the provisional managed candidate; 96 kHz remains the fallback.**
- [x] First AirPlay test on the fixed 192 kHz candidate acquired the managed path but was persistently choppy; the active AirPlay route is Shairport → ALSA `acp_airplay`/`plug` → fixed `dmix` → loopback → CamillaDSP, not PipeWire.
- [x] Captured the unchanged 192 kHz failing AirPlay graph on 29 September 2026. The live path was genuinely S32_LE/192 kHz, but CamillaDSP repeatedly logged playback underruns, capture overruns and capture/processing stalls; live capture/DAC ALSA geometry was only 512/4096 frames and CamillaDSP CPU was ~2.9%. Exact restore returned the accepted 16/44.1 graph with verifier success.
- [x] **Time-scaled fixed-192 AirPlay candidate physically passed on 29 September 2026:** ALSA period/buffer 4096/32768, CamillaDSP chunksize 4096, target_level 8192, same S32_LE/192 route and queuelimit=4. The same choppiness-sensitive audiobook theme was played twice with no audible fault; two snapshots showed no underrun/overrun/stall evidence, live capture/DAC geometry was 2048/16384, CamillaDSP used ~1.9% CPU, and exact restore returned the accepted 16/44.1 graph.
- [ ] Keep CamillaDSP Controller Adapt as a **deferred fallback**, not the active design: source-rate ALSA capture, adapted `capture_samplerate`/format, asynchronous SRC + rate adjustment, fixed S32_LE/192 kHz processing/output. Revisit only if the wider fixed-192 gate exposes a limitation.
- [x] **Fixed-192 Plex source-rate matrix physically passed on 29 September 2026:** known 16/44.1, 24/48, 24/96 and 24/192 sources all played correctly. Plexamp retained source-rate pipeline/mixer/source-stream behaviour; fresh 48/96/192 transitions reported their source rate as preferred/best while Device 9 opened at 192 kHz, and the loopback → CamillaDSP → DAC path remained S32_LE/192 kHz throughout. The 44.1 case reused the already-open 192 kHz device. CamillaDSP stayed ~1.7–1.8% CPU and exact restore again returned the accepted 16/44.1 graph.
- [x] **Plexamp-side fixed-192 live-control pass physically passed on 29 September 2026:** Bass changes were audibly effective and Music Master/Plexamp trim changed level as intended. CamillaDSP retained PID 68242 across the exercise, the loopback → CamillaDSP → DAC path remained S32_LE/192 kHz, CPU was ~1.6%, no underrun/overrun/stall/xrun/error lines were found, starting EQ/mixer values were restored, and exact 16/44.1 recovery passed. The pass exposed a metadata-only defect where the mixer API still reported 44.1 kHz; the helper now follows managed split-bus DAC/rate metadata with legacy fallback.
- [ ] **AirPlay-side fixed-192 control gate — partial pass / fault under correction (29 September 2026):** EQ, Music Master and AirPlay trim worked and the mixer API truthfully tracked 44.1 → 192 → 44.1 kHz, but the main AirPlay sender-volume slider had no audible effect and configured starting volume was not reliably applied on reconnect. The longer reconnect/control run also contained two isolated CamillaDSP playback-buffer underrun recoveries. ACP's sender-volume adapter was traced to Shairport MPRIS SetVolume; the active fix moves reads/writes to native RemoteControl AirplayVolume/SetAirplayVolume and keeps observed sender state authoritative until confirmed.
- [x] **AirPlay 2 sender-volume capability classified on 29 September 2026:** native `RemoteControl.AirplayVolume` readback physically works and reported the connected iPhone at **-20 dB / 33% sender scale**, but receiver-originated writes are not honoured on the commissioned AirPlay 2 path. After the negative-`busctl` argument bug was fixed, established-session ACP slider moves produced no audible change, no iPhone slider movement and no native readback change; a delayed direct `SetAirplayVolume d 0.0` call was also accepted locally while `AirplayVolume` remained **-20 dB**. This matches current Shairport Sync master documentation: AirPlay 2 remote-control facilities are not implemented; D-Bus/MPRIS remote control is for Classic AirPlay, with experimental AirPlay 2 work only on the development branch.
- [x] **AirPlay volume authority selected and implemented in software, 29 September 2026:** use **receiver-owned AirPlay volume**. The physical `pvol` trace proved the iPhone continuously emits sender-volume metadata from mute (**-144 dB**) through **0 dB**, but that value is now diagnostic only. Shairport is rendered with `ignore_volume_control = "yes"`, so sender attenuation no longer enters the gain path. ACP adds a dedicated runtime-only `A Clockwork AirPlay Live` ALSA softvol upstream of the persistent AirPlay Trim and Music Master; the main AirPlay fader controls that local stage. The old Starting volume setting/Start knob, `/api/audio/defaults` endpoint, sender-scale browser conversion and `SetAirplayVolume` writer are retired. The new live stage is deliberately excluded from portable mixer backup/reset state.
- [x] **First receiver-owned deployment attempt failed safely on 29 September 2026:** the guarded EQ repair was given the already-installed verified CamillaDSP binary and GNU `install` rejected the source/destination self-copy. The transaction restored the previous installed state and the existing 44.1 kHz verifier remained the accepted baseline. The repair owner now safely reuses an exact managed binary instead of self-copying, with regression coverage. CI also protected the pinned Direct/failback invariant: the physically proven alarm-safe Direct route remains byte-identical and unchanged rather than being silently modified for the new live fader.
- [x] **Receiver-owned AirPlay functional gate physically passed at 44.1 kHz on 29 September 2026:** guarded repair/helper/AirPlay activation succeeded and the verifier passed after installation. Shairport's `ignore_volume_control = "yes"` made a deliberately quiet iPhone sender play at ACP's receiver-owned level; the ACP AirPlay live fader, persistent AirPlay Trim, Music Master and EQ all changed the audible result as intended; moving the iPhone slider continued to update read-only `pvol` metadata from mute through 0 dB without changing audible level; reconnecting did not change ACP's live level; and the obsolete Starting volume control/setting is absent. The installed helper reports AirPlay Live, AirPlay Trim, Plexamp Trim and Music Master on the same ACP `perceptual-amplitude` scale (50% = -6.02 dB, 25% = -12.04 dB, 10% = -20 dB); the old AirPlay sender-scale conversion is retired. Plexamp's main live fader remains Plexamp Headless's native 0–100 player-volume API, so exact acoustic equivalence of its 50% point to ACP's local 50% point is not claimed without measurement.
- [ ] **44.1 kHz stability check narrowed on 29 September 2026:** a fresh accepted-baseline playback run was audibly clean and a journal window starting immediately before that run contained no underrun/overrun/stall/xrun/Broken pipe/error/fail lines. This materially separates ordinary steady playback from the earlier reconnect/control exercise that produced recovery warnings. Keep the wider transition/control stability gate open until one deliberately timestamped reconnect repeat confirms the distinction.
- [ ] **Fixed-192 receiver-owned stability pass failed audibly on 29 September 2026:** all AirPlay Live/Trim/Music Master/EQ controls and reconnect semantics worked, but the time-scaled S32_LE/192 kHz run became audibly skippy. The new CamillaDSP PID logged repeated playback-buffer underruns throughout active playback while CPU remained ~2.1%; the graph was still exactly 4096/32768 managed ALSA, chunksize 4096, target_level 8192, with DAC/capture 2048/16384. Exact restore returned the accepted 16/44.1 baseline and verifier passed.
- [x] **High-target fixed-192 stability/control/transition gate physically passed on 29 September 2026:** the exact `time-scaled-high-target` candidate (S32_LE/192 kHz, ALSA 4096/32768, CamillaDSP chunksize 4096, `target_level=12288`, capture/DAC 2048/16384) completed separately timestamped activation, one-minute idle, AirPlay startup, five-minute untouched steady playback and live EQ/volume/trim-control phases with no audible choppiness or filtered errors. A targeted follow-up then deliberately disconnected and reconnected AirPlay; receiver-owned AirPlay Live level plus EQ/Trim/Music Master semantics remained correct, the bounded transition error filter was empty, and the subsequent snapshot contained only normal service/start informational lines. CamillaDSP remained ~2.0–2.2% CPU. Exact restore returned S16_LE/44.1 and verification passed after both runs.
- [x] **Direct/failback receiver-owned AirPlay + alarm gate physically passed on 29 September 2026:** candidate SHA-256 `0166bd73e3e9a34dbdebff995de9fa6e39d2cd344dca574c891d46dd1a6aacfb` ran as genuine Direct/failback with CamillaDSP inactive and S16_LE/44.1 DAC geometry. AirPlay Live/Trim/Music Master behaved correctly; the controlled Classic Klaxon preview remained audible with Music Master at 0%, proving alarm-lane independence; a real scheduled alarm took the screen, paused AirPlay exactly once, remained independent of music controls, released to the deliberate manual-resume policy, and AirPlay resumed correctly from both Pi and iPhone. The bounded error filter was empty and exact restoration to the accepted split bus passed verification. The tested Direct bytes are now the pinned first-class Direct and EQ-failback profile.
- [x] **Managed 16/44.1 production bottleneck removed in source:** the EQ split profile now pins the physically accepted S32_LE/192 kHz route with ALSA 4096/32768, CamillaDSP chunksize 4096 and target_level 12288 while preserving trims → Music Master → reserve → EQ → limiter → alarm join. Guarded deployment/installed-state verification is still required on the commissioned Pi before this source promotion is considered operationally accepted.
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

- [ ] **System-time/NTP authority:** add an explicit NTP/time-synchronisation setting and health check; verify the Pi is actually synchronized after boot and network recovery, expose truthful synchronized/unsynchronized state, and define sensible configurable/default time sources. This owns wall-clock accuracy for the bedside clock, alarms, timestamps and future astronomy calculations and is deliberately separate from audio sample-clock drift correction.
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
