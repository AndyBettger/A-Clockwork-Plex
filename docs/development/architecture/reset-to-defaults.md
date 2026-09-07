# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** has passed its revised combined multi-owner transaction on the commissioned Pi. Functional Reset is physically proven. PR #9 remains **Draft and unmerged** while the final Plexamp Home scope is investigated.

The accepted production Reset currently has four participants:

1. **A Clockwork Plex (ACP)** — supported ACP user configuration generated from version-controlled defaults through production normalisers.
2. **Plexamp commissioning** — same-appliance owner for the captured player name plus managed `A Clockwork Plex - Plexamp` output.
3. **Plexamp native settings** — ordinary Plexamp settings reset by Plexamp's own application authority, with live Plexamp music volume returned to 100%.
4. **Plexamp Home presentation** — per-section `viewSettings` returned to Plexamp defaults while order, visibility and custom structure remain preserved.

Reset is deliberately **not a factory wipe**. Authentication, selected library, claim/session, account/machine identity, credentials, hardware topology, installed runtimes/services and unrelated Chromium state remain outside Reset.

## Owner-facing flow

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Unsaved ACP Settings changes block Reset so staged work cannot be silently overwritten.

## A Clockwork Plex owner

`app/configuration_reset.py` owns the ACP target. The browser never supplies defaults.

`ConfigurationResetPlanner` reads version-controlled `config.example.json`, passes it through the production Settings normalisers and narrows it through established ownership boundaries.

The current ACP Reset baseline includes:

- supported dashboard/display/Weather/News/alarm/AirPlay user choices;
- Master EQ enabled with Bass/Mid/Treble all **0.0 dB**;
- Music Master **100%**;
- Plexamp trim **100%**;
- AirPlay trim **100%**;
- Maximum Alarm Volume **100%**;
- AirPlay session-start volume **100%**.

`alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` are preserved deliberately so Reset never silently arms or disarms scheduled alarm sound.

### Browser/server stale-token ownership

The browser-native Plexamp participant runs before the server-owned ACP participant. Two different fingerprints are therefore required:

- `owner_tokens.a_clockwork_plex` fingerprints only ACP-owned target/current state and protects the browser→server hand-off;
- `restore_preview_token` is the broader #90 portable-Restore token used by the server restore transaction and may include portable Plexamp Headless preferences.

These must not be conflated. Physical testing exposed the previous false-stale failure when the broader #90 token was reused for the ACP hand-off. The corrected ACP-only token has passed the complete commissioned-Pi transaction.

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

A deliberate player rename plus **Follows system output** produced exactly two commissioning differences and Reset physically restored both without exposing the underlying values.

`playerName` and `audioDeviceUuid` remain excluded from portable Backup/Restore.

## Plexamp native ordinary-settings owner

`browser/plexamp-bridge/native-reset.js` owns ordinary Plexamp application settings plus live Plexamp music-player volume.

Disposable testing established the live authority at:

```text
global.app.rootStore.settings
```

The owner requires and invokes Plexamp's real `settings.resetToDefaults()` method. It does not scan webpack modules, use `eval`, expose generic JavaScript execution or automate arbitrary DOM controls.

### Native changed-set exclusions

Excluded from the Reset comparison/fingerprint are:

- keys beginning `_`;
- `premium`;
- `playerName` and `audioDeviceUuid` because commissioning owns their final appliance state;
- `equalizerPresets`, because physical post-reset evidence proved this catalogue is runtime-populated/non-convergent state rather than a durable Resettable user choice.

`equalizerPresets` remains inside the exact rollback snapshot.

The eight safe Headless preferences used by Backup/Restore participate normally in Plexamp's own Reset semantics; ACP does not hard-code their default values.

Preview exposes bounded setting **names only**, counts and fingerprints, never old/new values.

### Player volume

Plexamp live music-player volume is one native Reset choice:

- target: **100%**;
- same-origin Plexamp player API;
- verified apply;
- exact pre-reset rollback if this or a later participant fails.

## Accepted production Plexamp Home presentation owner

The current production Home owner deliberately preserves structure and resets only presentation.

It preserves:

- section order;
- hidden/visible choices;
- custom-added sections;
- custom section titles;
- editor/auth/cache/unrelated browser state.

It recognises only current-context records of the exact structural family:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

Real commissioned-profile evidence showed bounded URL-like characters in context/hub identifiers, so the matcher is structurally strict while allowing the physically observed identifier envelope. Unclassified `viewSettings`-looking keys fail Preview closed.

For a built-in section, non-default presentation-specific `viewSettings` are removed so Plexamp can use its own per-section defaults. For a custom-added section, the existing production owner strips presentation fields while retaining a validated custom `title` field so the section remains intact.

Preview reports only a bounded record count and fingerprint. Apply requires the fresh fingerprint, captures exact raw bytes, writes/removes only classified `viewSettings`, verifies convergence and retains exact rollback until the outer transaction finalises.

The commissioned Pi physically accepted this owner: Home presentation returned to Plexamp defaults while the user's order and visibility choices remained intact.

## Full Home-customisation reset — persistence authority investigation

The preferred future full-Home design is to **let Plexamp rebuild Home itself**, not replay a copied template or copy Chromium data.

A fresh disposable profile established that:

- before login/library selection, the live discovery-hub backing collection exists but contains **0 hubs**;
- after login and selecting the intended library, with no Home edits, Plexamp populated the effective Home itself;
- the narrow runtime authority is `rootStore.discovery.$mobx.values.hubs.value.$mobx.values`;
- the pre-login 0-hub state is unresolved context, not a factory Home target.

### Durable browser-profile-local owners now closed

Six isolated disposable profiles now cover five durable Home persistence cases plus one editor-only control:

```text
9224 order tracer
  Mixes for you moved to third
  durable: order=1, hidden=0

9225 hidden tracer
  Recent Plays hidden
  durable: hidden=1, order=0

9226 presentation tracer
  Recent Plays changed to Carousel
  durable after page refresh and full Chromium restart:
  viewSettings=1, editing=0

9227 editor-only control
  open Home editor, change nothing, exit
  all Home families remain zero

9228 custom-section tracer
  Artist-based custom Home section titled ACP Test Section
  durable after page refresh and full Chromium restart:
  customHubs=1, order=1, viewSettings=1
  hidden=0, editing=0, other=0
  context_count=2, section_context_count=2

9229 custom-title tracer
  same Artist-based custom section renamed
  ACP Test Section → ACP Renamed Section
  family inventory remains customHubs=1, order=1, viewSettings=1
  old title match 1→0; new title match 0→1
  renamed title + exact bundle survive page refresh
  and full Chromium process exit/relaunch
```

#### Order

Moving **Mixes for you** down two positions:

- survived normal page refresh;
- survived full Chromium process exit/relaunch using the same profile;
- remained different from a separate profile using the same Headless/account/library;
- produced an explicit browser-local key of the established `...:<section>:order` family;
- was reported by the corrected family probe as exactly `order=1`.

#### Hidden/visible

The initially clean second profile was repurposed as a hidden-only tracer. Hiding exactly **Recent Plays**:

- changed the all-zero Home-family inventory to exactly `hidden=1`, `order=0`;
- survived normal page refresh;
- survived full Chromium process exit/relaunch;
- left Mixes for you at the untouched top/default position.

#### Built-in presentation

A third fresh all-zero profile changed exactly one setting: **Recent Plays → Carousel**.

Immediately after the edit:

```text
viewSettings=1
editing=1
```

A fourth fresh profile proved that merely opening and leaving the Home editor without changing anything creates **no** Home record.

After a normal reload of the presentation tracer:

```text
viewSettings=1
editing=0
```

Recent Plays remained Carousel. After a full Chromium process exit/relaunch, the Carousel still remained and the family probe again returned exactly:

```text
viewSettings=1
editing=0
```

Therefore:

- `viewSettings` is the durable built-in presentation owner;
- `editing` is transient edit bookkeeping created during a committed customisation and cleared by reload;
- `editing` is not required to preserve the presentation choice;
- the current production Reset is correctly scoped to `viewSettings` and should continue leaving `editing` alone.

#### Custom-section creation and durability

A fifth fresh profile started with all Home persistence families at zero. Adding exactly one Artist-based custom Home section titled **ACP Test Section** changed the family inventory to:

```text
customHubs=1
order=1
viewSettings=1
hidden=0
editing=0
other=0
```

The three matching records span two classified structural contexts (`context_count=2`, `section_context_count=2`). The section remained present in the same position and the family inventory remained exactly unchanged after both a normal page refresh and a complete Chromium process exit/relaunch using the same profile.

Therefore custom-added section persistence is closed as a durable coordinated **custom-hub + ordering + presentation bundle**. A future full-Home scrub must treat that bundle atomically and retain exact rollback for all participating records rather than deleting `customHubs` in isolation.

#### Custom-title persistence and durability

A sixth fresh profile reproduced the same Artist-based **ACP Test Section** bundle after an all-zero baseline. The bounded title matcher found exactly one supported `viewSettings` record with exactly one title match and no unsupported/unclassified records.

Renaming only that section to **ACP Renamed Section** caused no family change:

```text
customHubs=1
order=1
viewSettings=1
hidden=0
editing=0
other=0
```

The old-title matcher changed from one match to zero while the new-title matcher changed from zero to one. Exactly one supported titled `viewSettings` record remained throughout. The renamed title and exact three-record bundle then survived both a normal page refresh and a complete Chromium process exit/relaunch using the same profile.

Therefore custom-title persistence is also closed. The validated title lives inside the existing durable `viewSettings` record; there is no separate title family. Any future full-Home scrub/rollback must therefore keep the custom section's `customHubs`, `order` and `viewSettings` state together as one atomic structural unit.

### Bounded custom-title diagnostic

The existing production Home Reset decoder already accepts and preserves only a validated `viewSettings.title` field: 1–240 characters, no control characters, direct/wrapped object codecs only. `scripts/inspect-plexamp-home-title.py` reuses that envelope as a developer-only disposable-profile diagnostic.

Unlike the key-family probe, the title diagnostic necessarily calls `getItem()` for structurally validated `viewSettings` keys. It then inspects only the optional validated `title` field and reports counts/matches against one caller-supplied expected title. It never emits stored titles, raw Local Storage values, raw keys, context identifiers or hub identifiers, and it never mutates storage. It exists solely to isolate a custom-title rename without broadening the production bridge.

### Diagnostic safety and corrected matcher

`scripts/inspect-plexamp-home-customizations.py` reports bounded Local Storage **key-family names/counts only**. It does not read stored values.

Earlier all-zero outputs are withdrawn because the developer probe initially generated a two-runtime-backslash namespace matcher. The production Backup/Restore bridge did not share that bug. The corrected diagnostic now matches Plexamp's real single-backslash namespace and is regression-covered, including a `SyntaxWarning`-as-error source compile check.

The broader disposable-profile browser-storage investigation also ruled out Session Storage and IndexedDB for the tested Home persistence cases. No browser databases or authentication/session material are mutated by these diagnostics.

## Preferred full-Home Reset architecture

A production full-Home Reset, if accepted, should:

1. preserve authentication/session and selected library;
2. preserve commissioned player name and managed output through their existing owner;
3. use the **complete bounded browser-profile-local Home persistence authority** now physically classified;
4. never directly clear/populate/mutate the transient `rootStore.discovery` hub array;
5. capture exact rollback state for narrowly proven Home-owned persistence;
6. remove/reset only those proven Home-owned records;
7. trigger the narrowest proven Plexamp Home reload/re-fetch mechanism;
8. allow Plexamp to regenerate its own effective Home;
9. verify logical Home plus continued login/library state;
10. retain rollback until the outer multi-owner transaction succeeds.

The observed default hub count is not a product invariant and must never be hard-coded.

## Remaining Home investigation

The browser-profile-local persistence surface is now fully classified for the tested Home customisation behaviours: order, hidden/visible, built-in presentation, custom-added section structure and custom titles are closed; `editing` is transient.

The remaining work is no longer persistence archaeology:

1. define exact full-Reset semantics for custom sections/titles from the completed classification;
2. build a disposable-only reversible scrub/rebuild experiment using the complete classified family set;
3. prove Plexamp rebuilds Home while login/library and unrelated browser state remain intact;
4. prove exact rollback restores the pre-scrub Home if a later Reset participant fails;
5. only then decide whether production expands beyond the accepted presentation-only Home owner.

## Browser isolation

The production bridge remains deliberately narrow:

- Manifest V3;
- loopback Plexamp origin only;
- no extension `permissions` or `host_permissions`;
- no cookies authority;
- no background worker;
- no production remote-debugging interface;
- no generic page-execution surface.

The DevTools probes used in this investigation are developer diagnostics for disposable Chromium profiles only and are not part of the production kiosk path.

## Combined transaction sequencing

The accepted Reset sequence is:

1. Preview obtains ACP/commissioning, native Plexamp and Home-presentation plans without mutation.
2. Review performs a fresh Preview and binds confirmation to fresh tokens/fingerprints.
3. Confirm applies native Plexamp settings/player volume and retains native rollback.
4. It applies Home presentation `viewSettings` and retains exact Home rollback.
5. A fresh server Preview must still match the reviewed **ACP-only** owner token.
6. The server executor uses its separate broader #90 `restore_preview_token`; commissioning uses its own fingerprint.
7. Only after all participants succeed are browser rollback snapshots finalised.

If a browser participant fails, earlier browser work rolls back. If the later server participant fails, retained browser owners roll back before failure is reported.

## Automated and physical evidence

Key green CI checkpoints:

- Tests #4575 — full combined implementation baseline;
- Tests #4586 — Home runtime/hub diagnostics;
- Tests #4601 — browser-storage diagnostic safety;
- Tests #4619 — corrected Home-family probe and warning regression;
- Tests #4620 — exact pre-hidden-acceptance state;
- Tests #4621 — hidden-acceptance roadmap state;
- Tests #4623 — post-presentation documentation/safety state;
- Tests #4625 — post-custom-section creation documentation state;
- Tests #4631 — bounded Home-title diagnostic + catalogues green.

Physical evidence through 7 September 2026 establishes:

- ACP Reset/rollback/presentation accepted;
- commissioning rename/output round-trip accepted;
- native Plexamp settings authority accepted;
- player volume Reset to 100% accepted;
- Home presentation Reset accepted;
- corrected ACP-only browser/server hand-off accepted;
- Home order persistence closed;
- Home hidden/visible persistence closed;
- built-in Home presentation persistence closed;
- transient `editing` separated from durable `viewSettings`;
- custom-added section persistence closed as a durable `customHubs=1`, `order=1`, `viewSettings=1` bundle across two classified contexts;
- custom-title persistence closed as a durable validated `viewSettings.title` field within that bundle, including page-refresh and full-process durability;
- the full Home persistence surface needed for the reversible scrub/rebuild proof is now bounded.

## Remaining gate before #93 can close

- [x] Close custom-title persistence one variable at a time.
- [ ] Complete the reversible full-Home scrub/rebuild experiment now that the persistence surface is fully bounded.
- [ ] Decide whether full Home structure belongs in #93 or a tightly scoped follow-up.
- [ ] Pull/reboot the eventual final production head so Chromium reloads the packaged bridge.
- [ ] Fresh production Preview must no longer report `equalizerPresets`.
- [ ] Verify any short-lived 10% AirPlay start value is returned to the accepted **100%** baseline if encountered.
- [ ] Keep the Home `viewSettings` Backup/Restore completeness gap open until implemented or explicitly deferred.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or merges.
