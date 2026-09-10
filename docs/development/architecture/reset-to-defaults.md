# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults is COMPLETE**. The full production **Preview → Review → Confirm** transaction passed on the commissioned bedroom Pi, including bounded full-Home rebuild, retained Plex login/library, commissioned player identity/output and accepted ACP defaults. The disposable **9230 full-Home scrub → Plexamp rebuild → exact rollback** rehearsal remains the reversible architecture proof.

The final cleanup gate also passed physically on production head `477bf0fd0cd7090a4d434816611f35673d83851e`: after the commissioned Pi fast-forwarded cleanly and `a-clockwork-plex.service` restarted, `/api/state` returned success and a fresh Reset Preview reported **Already at baselines**, **0 Plexamp settings** and **0 Home** changes. The zero-change result now remains compact, with the detailed Preview card hidden when every owner is ready and there is nothing to reset.

PR #9 remains **Draft and unmerged** pending explicit owner approval to leave Draft or merge. That repository decision is no longer an outstanding #93 engineering gate. The #89/#90 portable Home presentation/custom-section/title model remains a separate open follow-up.

Reset is deliberately **not a factory wipe**. Authentication, selected library, claim/session, account/machine identity, credentials, hardware topology, installed runtimes/services and unrelated Chromium state remain outside Reset.

The production transaction has four participants:

1. **A Clockwork Plex (ACP)** — supported ACP user configuration generated from version-controlled defaults through production normalisers.
2. **Plexamp commissioning** — same-appliance owner for the captured player name plus managed `A Clockwork Plex - Plexamp` output.
3. **Plexamp native settings** — ordinary Plexamp settings reset by Plexamp's own application authority, with live Plexamp music volume returned to 100%.
4. **Plexamp Home customisation** — the complete bounded durable browser-local Home customisation set is cleared and Plexamp rebuilds its own effective Home on the normal post-commit dashboard reload.

## Owner-facing flow

**Settings → Advanced → Reset to defaults → Preview reset → Review selected reset → Confirm & reset**

Preview and Review are read-only. Unsaved ACP Settings changes block Reset so staged work cannot be silently overwritten. Browser owners are stale-protected and retain exact rollback state until the server-owned participant succeeds.

When every owner is ready and the selected change count is zero, Preview now shows only the compact **Already at baselines** status. The large detailed Preview card remains hidden because there is nothing to review. Warning/incomplete previews may still reveal the detailed card because diagnostic explanation is then useful. This exact zero-change presentation was physically accepted on the commissioned Pi.

## A Clockwork Plex owner

`app/configuration_reset.py` owns the ACP target. The browser never supplies defaults.

`ConfigurationResetPlanner` reads version-controlled `config.example.json`, passes it through production Settings normalisers and narrows it through established ownership boundaries.

The accepted ACP Reset baseline includes:

- supported dashboard/display/Weather/News/alarm/AirPlay user choices;
- Master EQ enabled with Bass/Mid/Treble all **0.0 dB**;
- Music Master **100%**;
- Plexamp trim **100%**;
- AirPlay trim **100%**;
- Maximum Alarm Volume **100%**;
- AirPlay session-start volume **100%**.

`alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` are preserved deliberately so Reset never silently arms or disarms scheduled alarm sound.

### Browser/server stale-token ownership

Two fingerprints have different jobs and must remain separate:

- `owner_tokens.a_clockwork_plex` fingerprints only ACP-owned target/current state and protects the browser→server hand-off;
- `restore_preview_token` is the broader #90 portable-Restore token and may include portable Plexamp Headless preferences.

Physical testing exposed the false-stale failure caused by reusing the broader token. The corrected ACP-only hand-off passed the commissioned-Pi transaction.

## Plexamp commissioning owner — PHYSICALLY ACCEPTED

`app/plexamp_commissioning.py` and `scripts/commission-plexamp.py` own only:

- `playerName`;
- `audioDeviceUuid` as the live binding for the managed output.

The appliance-local baseline is:

```text
~/.local/share/a-clockwork-plex/plexamp-commissioning.json
```

It is atomic, mode `0600`, schema-versioned and stores only the commissioned player name. The audio UUID is resolved live each time by requiring exactly one output labelled:

```text
A Clockwork Plex - Plexamp
```

A deliberate player rename plus **Follows system output** produced exactly two commissioning differences and Reset physically restored both. `playerName` and `audioDeviceUuid` remain excluded from portable Backup/Restore.

## Plexamp native ordinary-settings owner

`browser/plexamp-bridge/native-reset.js` owns ordinary Plexamp application settings plus live Plexamp music-player volume.

The live authority is:

```text
global.app.rootStore.settings
```

The owner invokes Plexamp's real `settings.resetToDefaults()` method. It does not scan webpack modules, use `eval`, expose generic JavaScript execution or automate arbitrary DOM controls.

Excluded from the native changed-set/fingerprint are:

- keys beginning `_`;
- `premium`;
- `playerName` and `audioDeviceUuid`, because commissioning owns their final appliance state;
- `equalizerPresets`, because physical evidence proved it is runtime-populated/non-convergent catalogue state rather than a durable resettable user choice;
- `activeTab`, because the commissioned production Reset returned every meaningful owner to baseline but normal Plexamp UI/navigation then repopulated `activeTab` as the sole fresh-Preview difference. It is navigation residue, not durable user configuration.

Both `equalizerPresets` and `activeTab` remain inside the exact rollback snapshot. The exclusion applies only to changed-set/fingerprint convergence semantics.

The `activeTab` classification was physically revalidated after the cleanup landed: fresh production Preview then reported zero Plexamp native differences rather than repeatedly offering runtime navigation residue as reset work.

Plexamp live music-player volume is explicitly returned to **100%**, verified, and exact-rollback covered.

## Plexamp Home customisation owner

### Durable ownership boundary

Fresh isolated profiles established the complete durable browser-profile-local Home customisation families used by the tested behaviours:

```text
order
hidden
viewSettings
customHubs
```

`editing` is transient edit bookkeeping. It is **not** durable Home personality; however, if an active `editing` record is present, production Preview fails closed rather than mutating Home through an unsettled edit.

The production owner recognises only structurally classified records under the bounded Plexamp customisation namespace. Unknown terminal families, malformed keys, oversized records, stale fingerprints or excessive record counts also fail closed.

It never calls `localStorage.clear()`, never copies a Chromium profile, never touches cookies/Session Storage/IndexedDB, and never directly manipulates Plexamp's transient runtime hub array.

### Causal persistence evidence

The preserved disposable evidence matrix is:

```text
9224 order tracer
  Mixes for you moved to third
  durable: order=1

9225 hidden tracer
  Recent Plays hidden
  durable: hidden=1

9226 presentation tracer
  Recent Plays → Carousel
  durable after reload/restart: viewSettings=1, editing=0

9227 editor-only control
  open/close Home editor without changes
  all Home families remain zero

9228 custom-section tracer
  Artist-based ACP Test Section
  durable: customHubs=1, order=1, viewSettings=1

9229 custom-title tracer
  ACP Test Section → ACP Renamed Section
  same family inventory; title moves inside validated viewSettings
  durable through reload + full Chromium restart

9230 mixed reversible tracer
  custom section + moved order + hidden section + built-in presentation override
  durable target: customHubs=1, order=1, hidden=1, viewSettings=2
```

These tests establish:

- Home order is durable browser-local state;
- hidden/visible choices are durable browser-local state;
- `viewSettings` owns durable built-in presentation;
- custom-added sections are coordinated `customHubs + order + viewSettings` bundles;
- validated custom titles live inside the custom section's `viewSettings` record;
- `editing` disappears across reload and is not required for persistence.

The observed default/effective hub count is not a product invariant and must never be hard-coded.

## 9230 reversible full-Home proof — PASSED

The final disposable rehearsal deliberately created four independent customisations on port **9230**:

- Artist custom section **ACP Scrub Section**;
- **Mixes for you** moved further down;
- **Recent Plays** hidden;
- **Recently Added in Music** changed to Carousel / Block / 180 px.

After Plexamp settled, the bounded family inventory was exactly:

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
```

The exact pre-scrub fingerprint was:

```text
58ed4b28
```

Confirmed rehearsal `apply` captured those five raw Home-owned records into the mode-0600 disposable snapshot, removed exactly those five records, and verified the bounded target was empty. The empty/customisation-free fingerprint was:

```text
741638a5
```

After a normal Plexamp reload:

- Plexamp rebuilt a normally populated default-looking Home itself;
- the custom section, moved order, hidden choice and presentation override were gone;
- Plex login remained intact;
- the correct music library remained selected;
- no runtime-hub synthesis or clean-profile copying was used.

Confirmed rehearsal `rollback` then restored exactly five records into the still-empty bounded target and verified the original fingerprint returned:

```text
58ed4b28
```

After reload, the complete mixed Home returned visually: **ACP Scrub Section**, moved **Mixes for you**, hidden **Recent Plays**, and the Carousel / Block / 180 px presentation. The title matcher again found exactly one `ACP Scrub Section`; the independent family probe again returned exactly the original five-record inventory. Login and the selected library still remained intact.

This closes the architectural question: clearing only classified durable Home customisation records is sufficient for Plexamp to rebuild its own effective Home, and exact raw rollback can reconstruct the previous Home without touching authentication or unrelated browser state.

## Production full-Home transaction semantics

The existing multi-owner orchestration already provides the required commit boundary, so no new Plexamp reload API is needed.

The production sequence is:

1. Preview obtains ACP/commissioning, native Plexamp and bounded Home plans without mutation.
2. Review performs a fresh Preview and binds confirmation to fresh tokens/fingerprints.
3. Confirm applies native Plexamp settings/player volume and retains native rollback.
4. It snapshots and clears the complete classified durable Home set (`order`, `hidden`, `viewSettings`, `customHubs`), verifies the bounded target is empty, and retains the exact Home rollback token.
5. A fresh server Preview must still match the reviewed **ACP-only** owner token.
6. The server executor applies ACP-owned defaults and commissioning through their own stale/rollback boundaries.
7. If any later participant fails, browser owners roll back **before any page reload**. Home rollback requires the bounded target to remain empty and then verifies the exact original fingerprint.
8. Only after every participant succeeds are browser rollback snapshots finalised.
9. The already-existing dashboard reload then occurs. That reload is the narrow Plexamp rebuild trigger: Plexamp regenerates its own effective Home from account/library/runtime context.

The ordering is important. Reloading immediately after the Home clear would destroy the in-memory production rollback token before the later server participant had committed. The existing post-success reload avoids that problem cleanly.

## Commissioned-Pi production acceptance — PASSED

The first complete production acceptance head `1f077b28ad453b90409ea91f24da0773c3a0ba90` was converged through normal `bash setup.sh`, followed by the supported reboot. Post-reboot verification confirmed:

- clean Git working tree at the exact accepted head;
- packaged bridge 1.4.0 loaded by the production kiosk;
- no remote-debugging flags;
- dashboard, Plexamp, Shairport, NFC and CamillaDSP services active;
- dashboard API healthy;
- Plex still signed in with the correct library.

Fresh production Preview reported **19 server-owned + 8 Plexamp native + 5 Home customisation** changes, with no warnings. The Home records were classified as `order=1`, `hidden=0`, `viewSettings=3`, `customHubs=1`. `equalizerPresets` was absent. Review refreshed the same scope and reported **Ready to confirm**.

Production Confirm completed and verified **34 applied changes**. After the automatic completion reload:

- Plexamp Home was back in default order/style;
- the custom section and stored presentation/title overrides were gone;
- Plex remained signed in to the correct library;
- player name remained correct;
- managed output remained **A Clockwork Plex - Plexamp**;
- ACP fresh Preview reported **Already at baselines**;
- Home fresh Preview reported **0** bounded customisation overrides;
- commissioning remained correct.

The only initial fresh-Preview difference was `plexamp.native-settings.activeTab`. This appeared only after normal UI/navigation use and was therefore classified as runtime-normalised navigation state rather than meaningful resettable configuration. Commit `09488072ad204d9a7c0f984d8a4a2a64e92387dd` added it to `RUNTIME_NORMALIZED_KEYS`.

Final convergence/UX acceptance then ran on exact head:

```text
477bf0fd0cd7090a4d434816611f35673d83851e
```

The commissioned Pi fast-forwarded cleanly with an empty `git status --short`. Restarting `a-clockwork-plex.service` succeeded and the guarded `/api/state` probe returned **Dashboard API: PASS**. A normal Settings refresh followed by **Preview reset** then showed:

```text
A Clockwork Plex + managed Plexamp: Already at baselines
Plexamp settings + Home customisation: 0 settings · 0 Home
```

The compact **Already at baselines** status remained visible and the large detailed Preview card stayed hidden. This proves both final `activeTab` convergence and the intended zero-change owner-facing presentation on the real appliance.

## Browser isolation

The production bridge remains deliberately narrow:

- Manifest V3;
- loopback Plexamp origin only;
- no extension `permissions` or `host_permissions`;
- no cookies authority;
- no background worker;
- no production remote-debugging interface;
- no generic page-execution surface.

The DevTools probes and `scripts/rehearse-plexamp-home-scrub.py` are developer tooling for disposable Chromium profiles only and are not part of the production kiosk path.

## Backup/Restore relationship

Full-Home Reset ownership does **not** make raw Home Local Storage portable.

Schema-v1 Backup/Restore still carries only validated logical Home `order` and `hidden` choices. Per-section presentation, custom-section structure and custom-title semantics remain an open #89/#90 logical-model follow-up. That future work must map validated logical choices through live target context rather than archive raw browser keys/values.

See [`configuration-backup-ownership.md`](configuration-backup-ownership.md).

## Automated evidence

Selected green CI checkpoints:

- Tests #4619 — corrected Home-family probe and warning regression;
- Tests #4621 — hidden persistence documentation state;
- Tests #4623 — presentation documentation/safety state;
- Tests #4625 — custom-section evidence state;
- Tests #4631 — bounded title diagnostic/catalogues;
- Tests #4632 — custom-title closure;
- Tests #4633 — reversible scrub rehearsal tooling;
- Tests #4638 on `96f06e09544fafed3475f3416ac28650b040c580` — widened production full-Home owner, five-record workflow smoke, JavaScript/page wiring, shell checks and full unit suite all green;
- Tests #4647 on `88d69c9b8310f0bd82acfefff11c393053f8106f` — final production full-Home implementation gate after UI/cache/version and stale-regression updates;
- Tests #4649 on `1f077b28ad453b90409ea91f24da0773c3a0ba90` — exact commissioned-Pi acceptance head including documentation bookkeeping;
- Tests #4650 on `09488072ad204d9a7c0f984d8a4a2a64e92387dd` — `activeTab` runtime-normalisation cleanup; compile, JavaScript/page wiring/shell checks and full unit suite green;
- Tests #4662 on `3165f832bb8cae5277e727ee08f68b9143cba790` — zero-change Preview logic/cache regression green;
- Tests #4663 on `477bf0fd0cd7090a4d434816611f35673d83851e` — final cache-safe physical-acceptance head; compile, JavaScript/page wiring/shell checks and full unit suite green.

## #93 closure state

- [x] Complete the Home persistence classification.
- [x] Complete disposable mixed scrub → Plexamp rebuild → exact rollback with auth/library preserved.
- [x] Decide that bounded full Home customisation belongs in #93.
- [x] Implement the widened production Home owner and automated five-record rollback/safety coverage.
- [x] Obtain complete green CI on the accepted production implementation/bookkeeping heads.
- [x] Pull/converge/reboot the commissioned Pi with bridge 1.4.0.
- [x] Physically accept production Preview → Review → Confirm, including Home rebuild, retained login/library, commissioning restoration and accepted ACP defaults.
- [x] Verify fresh production Preview no longer reports `equalizerPresets` and reports ACP/Home at baseline.
- [x] Confirm the commissioned Pi did not contain the short-lived 10% AirPlay start residue at the accepted Preview checkpoint.
- [x] Classify and exclude the sole post-reset `activeTab` navigation residue.
- [x] Pull/restart the final cleanup head and physically verify fresh Preview reports **0 meaningful Reset differences** with the zero-change details card hidden.

#93 is therefore complete. The #89/#90 Home presentation/custom-structure portable Backup/Restore follow-up remains open as a separate portability task. PR #9 remains Draft and unmerged until the owner explicitly decides to move it into review/merge.
