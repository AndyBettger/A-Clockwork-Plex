# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** has passed the combined multi-owner transaction on the commissioned Pi and the disposable **9230 full-Home scrub → Plexamp rebuild → exact rollback** rehearsal. PR #9 remains **Draft and unmerged** until the widened production Home owner is physically accepted on the commissioned appliance and the owner explicitly approves merge.

Reset is deliberately **not a factory wipe**. Authentication, selected library, claim/session, account/machine identity, credentials, hardware topology, installed runtimes/services and unrelated Chromium state remain outside Reset.

The production transaction has four participants:

1. **A Clockwork Plex (ACP)** — supported ACP user configuration generated from version-controlled defaults through production normalisers.
2. **Plexamp commissioning** — same-appliance owner for the captured player name plus managed `A Clockwork Plex - Plexamp` output.
3. **Plexamp native settings** — ordinary Plexamp settings reset by Plexamp's own application authority, with live Plexamp music volume returned to 100%.
4. **Plexamp Home customisation** — the complete bounded durable browser-local Home customisation set is cleared and Plexamp rebuilds its own effective Home on the normal post-commit dashboard reload.

## Owner-facing flow

**Settings → Advanced → Reset to defaults → Preview reset → Review selected reset → Confirm & reset**

Preview and Review are read-only. Unsaved ACP Settings changes block Reset so staged work cannot be silently overwritten. Browser owners are stale-protected and retain exact rollback state until the server-owned participant succeeds.

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
- `equalizerPresets`, because physical evidence proved it is runtime-populated/non-convergent catalogue state rather than a durable resettable user choice.

`equalizerPresets` remains inside the exact rollback snapshot.

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
- Tests #4638 on `96f06e09544fafed3475f3416ac28650b040c580` — widened production full-Home owner, five-record workflow smoke, JavaScript/page wiring, shell checks and full unit suite all green.

Later branch heads must also be green before commissioned-Pi production acceptance.

## Remaining gate before #93 can close

- [x] Complete the Home persistence classification.
- [x] Complete disposable mixed scrub → Plexamp rebuild → exact rollback with auth/library preserved.
- [x] Decide that bounded full Home customisation belongs in #93.
- [x] Implement the widened production Home owner and automated five-record rollback/safety coverage.
- [ ] Obtain a complete green CI run on the final production/docs head.
- [ ] Pull/reboot that exact head on the commissioned Pi so Chromium loads the packaged bridge version carrying full-Home semantics.
- [ ] Physically accept production Preview → Review → Confirm, including Home rebuild, retained login/library, commissioning restoration and accepted ACP defaults.
- [ ] Verify a fresh production Preview no longer reports `equalizerPresets` as a native Reset difference.
- [ ] If the commissioned Pi contains the short-lived 10% AirPlay start value, verify Reset returns AirPlay session-start and persistent AirPlay trim to **100%**.
- [ ] Keep the #89/#90 Home presentation/custom-structure portable Backup/Restore follow-up open until implemented or deliberately deferred.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or merges.
