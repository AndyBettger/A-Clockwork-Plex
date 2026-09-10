# Configuration backup and restore ownership

## Purpose

A Clockwork Plex needs a supported way to move useful appliance personality onto a rebuilt/replacement installation without cloning credentials, hardware identity, runtime caches or machine-specific implementation state.

The governing rule remains:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

Backup/Restore and Reset are deliberately different. A state family can be safe to clear and rebuild during same-profile Reset without being safe or meaningful to copy raw between appliances.

## Ownership matrix

| State | Backup policy | Restore / Reset relationship |
| --- | --- | --- |
| ACP user settings | Include normalised portable model, never raw `config.json` | Restore through production owners; #93 derives defaults from version-controlled example + normalisers |
| Alarm schedules/ordinary choices | Include | Restore normally; #93 resets ordinary choices but preserves alarm-audio arming switches |
| Display/theme/night/clock/startup | Include | Restore through Settings; #93 owns supported ACP defaults |
| Weather non-secret choices | Include | Restore through Weather Settings; #93 resets supported choices |
| Weather Underground API key | Never include | Recommission explicitly; #93 preserves credential |
| AirPlay user preferences | Include logical values | Restore through guarded owners; #93 resets supported defaults |
| Master EQ | Include logical enabled/bands | Restore through EQ owner; #93 resets to enabled neutral 0/0/0 dB |
| Persistent mixer levels | Include logical percentages | Restore through mixer owner; #93 resets Music Master, Plexamp trim, AirPlay trim and Maximum Alarm Volume to 100% |
| Audio routes/CamillaDSP/systemd/sudoers/hardware | Exclude | Recreate from installer/hardware commissioning; #93 preserves topology |
| Plexamp runtime | Exclude | Reinstall through runtime owner; #93 does not replace runtime |
| Schema-v1 eight safe Plexamp Headless preferences | Include exact typed allow-list, version-aware | Physically accepted schema-v1 compatibility Restore uses restricted owner; #93 lets Plexamp's own Reset reset them normally |
| Broader ordinary Plexamp settings personality | Include in production-wired schema-v2 logical model; commissioned-Pi acceptance pending | V2 restores only classified portable keys to saved deviation or constructor default; it never calls global Reset; retained rollback/finalize spans the coordinated transaction |
| Plexamp player name/audio output | Exclude from portable backup | Same-appliance #93 commissioning owner restores captured player name + dynamically resolved managed output |
| Plexamp live player volume | Exclude from portable backup | Runtime/player state; #93 returns live Plexamp music volume to 100% with rollback |
| Plexamp Home logical order/hidden choices | Include in schema-v1 compatibility and schema-v2 logical models | #90 schema-v1 physically restores target-context choices; v2 remaps logical state; #93 classifies both as durable resettable Home customisation |
| Plexamp Home per-section presentation (`viewSettings`) | Include in production-wired schema-v2 logical model; commissioned-Pi acceptance pending | #93 clears bounded same-profile presentation; v2 maps validated logical presentation to target-local context |
| Plexamp Home custom sections/titles | Include in production-wired schema-v2 logical model; commissioned-Pi acceptance pending | V2 serialises logical kind/query/title/presentation and remaps fresh target IDs/context/library with retained rollback |
| Chromium profile wholesale | Never include | Never restore/copy wholesale |
| Weather/News caches/rainfall history | Exclude | Rebuild/refetch |
| Alarm/playback runtime | Exclude | Recreate from live state/current time |

## Secrets and identity — hard exclusions

An ordinary backup must never contain:

- Weather Underground API key or future managed secrets;
- Plex authentication/claim/account/session credentials;
- browser cookies/login/session databases;
- passwords, bearer tokens, API keys or private-key material;
- target-specific player/machine/client identity;
- raw machine-specific audio/hardware topology.

A secret-safe backup can still contain household information such as alarm labels/times, station IDs or approximate forecast coordinates; it is portable, not anonymous.

The #93 commissioning baseline does not weaken these exclusions. Its player name remains appliance-local and never enters the portable backup; the audio UUID is resolved live and is not stored in the baseline.

## Plexamp settings portability boundary

The Plexamp Settings directory itself is **not** a supported backup unit.

### Supported schema-v1 Headless allow-list

Checkpoint #88 established this exact typed scalar portable allow-list:

- `audioConversionBitrate`
- `autoPlayEnabled`
- `cacheSize`
- `cachingWiFi`
- `loudnessLeveling`
- `precacheNetworkSpeed`
- `sampleRateConversionQuality`
- `sampleRateMatching`

The schema-v1 compatibility export/restore path uses only those exact names and expected types; malformed/unknown files are skipped rather than copied.

Known nonportable/separately owned fields include:

- `playerName` — appliance-local commissioning label;
- `audioDeviceUuid` — target-specific output binding resolved live;
- `premium` — account/capability-derived;
- authentication/session/credential values;
- runtime/navigation/internal-EQ catalogue state.

Observed values from commissioned testing are evidence of state, **not Reset defaults**. Backup/Restore means “restore saved user choices”; Reset means “return choices to defaults defined by their owners”.

### Broader native portability owner — ACTIVE, AUTOMATED GREEN; PHYSICAL ACCEPTANCE PENDING

The #89/#90 completeness follow-up has a separate bounded page-world owner based on the already-proven live `rootStore.settings` authority.

Its model is deliberately narrower than “clone Plexamp settings”:

- discover the constructor-default settings schema through the live Plexamp authority;
- export only bounded JSON-safe portable deviations from those defaults;
- exclude commissioning/identity/capability/runtime/auth/internal-EQ fields;
- bind Preview/Apply to an exact settings-schema fingerprint and a fresh target fingerprint;
- on Restore, assign **only classified portable keys**;
- restore a saved deviation when one exists, otherwise return that portable key to Plexamp's constructor default;
- never invoke Plexamp's broad `settings.resetToDefaults()` as part of portable Restore;
- capture/rollback only the same classified portable key set;
- retain rollback state until explicit finalize.

This “touch only what this owner owns” rule is stronger than temporarily performing a broad Reset and attempting to put unrelated state back afterwards.

Dedicated regression coverage uses a deliberately destructive fake `resetToDefaults()` and proves it is never called. Nonportable object identity/state stays untouched, stale targets fail closed and exact portable rollback succeeds.

Automated evidence:

- **Tests #4671** passed the native-owner gate on `eb061cc139acdd6649db2c56cccd062a7a05a614`;
- **Tests #4701** passed the real Settings integration gate on `bb47c8543ae9fe3d6abd2d4eb38c0d9dd66236ff`;
- **Tests #4704** passed the production bridge-activation/full-regression gate on `6a212689cd42dd96edcaf4e2869df51cde231689`.

Production bridge **1.5.0** now activates this owner through the bounded portability transport. Automated owner/transport proof is complete; commissioned-Pi Backup → Reset → Restore acceptance is still required before #89/#90 is closed.

## ACP audio portability and Reset relationship

Backup stores logical EQ and mixer choices so a replacement appliance can restore the user's curve/calibration.

The accepted #93 Reset baseline is:

```text
Master EQ: enabled
Bass: 0.0 dB
Mid: 0.0 dB
Treble: 0.0 dB
Music Master: 100%
Plexamp trim: 100%
AirPlay trim: 100%
Maximum Alarm Volume: 100%
AirPlay session-start volume: 100%
```

The earlier nominal 80% / observed 79% Music Master result remains useful ALSA quantisation evidence but is not a product default. The short-lived 10% AirPlay session-start value was a typo and is not accepted policy.

## Appliance-local Plexamp commissioning ownership

`app/plexamp_commissioning.py` and `scripts/commission-plexamp.py` own only `playerName` and the live managed-output binding.

The owner:

- accepts only Plexamp's loopback settings API;
- captures the intended player name into `~/.local/share/a-clockwork-plex/plexamp-commissioning.json` (mode `0600`);
- stores no audio UUID;
- dynamically requires exactly one output labelled **`A Clockwork Plex - Plexamp`**;
- fails closed on missing/ambiguous output;
- never serialises commissioning state into portable backup.

A temporary player rename plus **Follows system output** physically produced exactly two commissioning differences, and Reset restored both.

## Plexamp Home ownership

The kiosk Chromium profile contains authentication/session material as well as UI state, so **the profile must never be archived/restored wholesale**.

### Schema-v1 compatibility Home model — PHYSICALLY ACCEPTED

The physically accepted #89/#90 schema-v1 bridge exports/restores only validated logical Home **order** and **hidden/visible** choices:

```json
"home": {
  "order": [],
  "hidden": []
}
```

The commissioned export contained **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.

Restore maps those logical choices onto the target's live Home context, requires a fresh fingerprint and explicit confirmation, writes only classified Home records and verifies the logical result. Its schema-v1 write path self-rolls back a failed Home mutation, but it does **not** retain a browser rollback token across a later server participant. That historical limitation remains intentionally confined to old schema-v1 backups.

Checkpoint #90 remains physically accepted for this schema-v1 order/hidden scope.

### Complete persistence classification

Fresh-profile #93 work independently established the durable browser-local Home families used by the tested customisations:

```text
order
hidden
viewSettings
customHubs
```

Causal evidence established:

- moving **Mixes for you** survives reload/restart through `order`;
- hiding **Recent Plays** survives reload/restart through `hidden`;
- changing **Recent Plays → Carousel** survives through `viewSettings`; its companion `editing` state is transient and disappears after reload;
- opening/leaving the Home editor without changing anything creates no Home record;
- adding Artist-based **ACP Test Section** creates a durable coordinated `customHubs=1`, `order=1`, `viewSettings=1` bundle;
- renaming that section changes no family count; the validated title lives inside the same durable `viewSettings` record and survives reload/restart.

Persistence-family discovery is therefore closed.

### Structure/presentation context relationship — CLOSED

The preserved 9230 mixed state established two and only two relevant Home contexts:

- `customHubs`, `order` and `hidden` use the **structure context**;
- every captured `customHub.source` equals that structure context;
- built-in and custom `viewSettings` use the **presentation context**;
- both roles address the same selected library section.

Plexamp 4.13.2 source evidence explains the split:

- Discovery builds its structure settings key from live `rootStore.app.server` + `rootStore.app.library` as `discovery:customizations:${server}::${library}`;
- `useViewSettings()` prefixes that key with `discovery:customizations:` again, so the classified presentation context becomes `discovery:customizations:${server}`;
- the selected target library remains `/library/sections/<id>` in both roles.

This closes the clean-target routing problem: after #93 Reset there may be **zero** Home override records, but the v2 owner can derive both target contexts from the live authenticated Plexamp runtime rather than copying source context IDs or requiring a destination specimen.

### Home-v2 logical portability owner — ACTIVE, AUTOMATED GREEN; PHYSICAL ACCEPTANCE PENDING

`browser/plexamp-bridge/home-portability-v2.js` implements the bounded logical Home-v2 model and is active through production bridge **1.5.0**.

It never exports:

- generated custom-hub UUIDs;
- source structure/presentation/server context identifiers;
- source library section numbers;
- raw Local Storage keys;
- raw MMKV values;
- Chromium profile/LevelDB data;
- account capability/auth/session material.

Instead it exports validated semantics:

- Home order using built-in logical IDs plus backup-local custom references;
- hidden logical targets;
- built-in/custom presentation fields;
- custom section kind;
- library-query suffix relative to the selected library;
- custom title inside the validated presentation record.

Restore materialises those semantics using:

- target-local live structure/presentation contexts;
- target-local selected library section;
- fresh target-generated custom-hub UUIDs;
- `customHub.source` set to the target structure context;
- strict single-property MMKV JSON wrapper `{"_": value}`.

The owner deliberately canonicalises hidden/presentation logical collections independently of generated UUID/raw-key ordering while preserving the semantic Home `order` list. Every custom section must have a title-bearing presentation record. Live `premium` is consulted only as a target capability gate and is never serialised into the portable model.

It fails closed on:

- active `editing` state;
- unknown Home family;
- malformed/unsupported MMKV wrapper;
- duplicate/dangling custom references;
- invalid custom source/query/presentation/title shapes;
- unavailable custom-section target capability;
- stale Apply target;
- stale Rollback target;
- bounded record/size/count violations.

Apply retains exact pre-write raw records in memory, verifies the post-write **logical** model even though fresh UUIDs changed the physical keys, and retains a rollback token until explicit rollback/finalize.

`tests/test_plexamp_home_portability_v2.py` covers:

- completely empty post-Reset target context derivation;
- exact two-role structure/presentation construction;
- strict MMKV single-`_` wrapper;
- built-in presentation;
- multiple custom sections/titles;
- deliberately conflicting generated UUID/raw-key order vs stable logical order;
- target library/context/fresh UUID remapping;
- exact rollback to a previously empty target;
- exact rollback over pre-existing target Home records;
- stale Apply and stale Rollback refusal without collateral mutation;
- fail-closed classification/shape/capability cases.

Automated evidence:

- **Tests #4674** on `7bcd9efc825998da5d16951ad7f2187d80cee2b4` passed every Home-v2 behavioural case; the sole suite failure was the deliberately missing catalogue entry;
- **Tests #4675** passed completely on `92d2c20afdd4dd8fc6e4734fdccae18411d34102` after catalogue bookkeeping;
- **Tests #4701** passed the integrated Settings/controller gate;
- **Tests #4704** passed the active production-bridge security/full-regression gate.

Automated Home-v2 proof and production activation are complete. Commissioned-Pi export/restore acceptance remains the final product gate.

## Production bridge 1.5.0 boundary

The production extension manifest is now **1.5.0**. Its single loopback-only content-script block loads:

```text
content.js
reset.js
portability.js
```

Its single loopback-only web-accessible resource set is:

```text
native-reset.js
native-portability.js
home-portability-v2.js
```

The manifest adds no extension `permissions`, no `host_permissions` and no background authority. The launcher adds no DevTools/remote-debugging interface. The portability loader injects only the two bounded page-world owners above; there is no generic page-world evaluation surface.

The existing #93 Reset bridge remains present in the same package and is separately regression-protected. **Tests #4704** verifies both the new portability activation and continued #93 Reset/commissioning wiring under bridge 1.5.0.

## #93 full Home Reset relationship — PROVEN AND PHYSICALLY ACCEPTED

Same-profile Reset has a different goal from portable Backup/Restore. It can safely remove the bounded durable Home customisation records and let Plexamp rebuild its own effective Home from the still-authenticated account/library/runtime context.

The disposable 9230 experiment proved this end to end using a mixed state containing:

- custom **ACP Scrub Section**;
- moved **Mixes for you**;
- hidden **Recent Plays**;
- Carousel / Block / 180 px presentation on **Recently Added in Music**.

Before scrub, the bounded target had exactly five records:

```text
customHubs=1
order=1
hidden=1
viewSettings=2
editing=0
fingerprint=58ed4b28
```

After clearing only those five records, the bounded target was all-zero with fingerprint `741638a5`. A normal reload made Plexamp rebuild a default-looking Home while Plex login and the correct selected library remained intact.

Exact rollback restored all five raw records and returned the fingerprint to **`58ed4b28`**. After reload, all four deliberate Home customisations returned visually and the title/family probes matched the original state exactly.

The same bounded full-Home model subsequently passed the complete production Reset transaction on the commissioned bedroom Pi. After the final `activeTab` runtime-normalisation cleanup, exact head `477bf0fd0cd7090a4d434816611f35673d83851e` was pulled cleanly, the dashboard service restarted successfully, `/api/state` passed, and fresh Reset Preview reported **Already at baselines**, **0 Plexamp settings** and **0 Home** differences. The empty detailed Preview card also stayed hidden as intended.

This proves **Reset ownership**, not cross-installation portability. The production #93 Home owner may clear classified Home state in the current profile with exact rollback; #89/#90 separately maps a logical portable representation and still requires commissioned-Pi Backup → Reset → Restore acceptance.

## Why a clean Plexamp profile cannot be copied raw

A clean profile is useful behavioural evidence but is not a portable backup artifact:

- browser profiles contain auth/session state;
- Home identifiers contain account/library/context-specific values;
- server/runtime-provided default sections can exist without local override records;
- custom sections need explicit logical semantics across installations;
- copied browser DB/MMKV bytes would couple portability to Chromium/Plexamp implementation details.

Full Home Reset therefore clears only proven Home-owned browser-local overrides and lets Plexamp rebuild itself. Portable Backup/Restore remains a logical model mapped through bounded live owners.

## Backup envelopes

### Schema-v1 compatibility envelope — PHYSICALLY ACCEPTED

Existing schema-v1 backups remain supported:

```json
{
  "schema_version": 1,
  "source": {
    "application": "A Clockwork Plex",
    "app_version": "0.4.0",
    "release_tag": "v0.4.0"
  },
  "a_clockwork_plex": {
    "settings": {},
    "audio": {"eq": {}, "mixer": {}}
  },
  "plexamp": {
    "source_version": "4.13.2",
    "headless_preferences": {},
    "browser_preferences": {
      "schema_version": 1,
      "home": {"order": [], "hidden": []}
    }
  },
  "export_report": {"warnings": [], "omitted": []}
}
```

`plexamp.browser_preferences` is optional and merged only after a validated live bridge snapshot. Commissioning state and live Plexamp player volume are intentionally absent.

### Schema-v2 complete portable envelope — PRODUCTION WIRED; PHYSICAL ACCEPTANCE PENDING

The real Settings owner now assembles schema-v2 by combining the secret-safe server-owned ACP export with the live bounded native and Home-v2 snapshots. The portable Plexamp portion is structurally:

```json
{
  "schema_version": 2,
  "plexamp": {
    "source_version": "4.13.2",
    "portable_settings": {
      "schema_version": 1,
      "settings_schema_fingerprint": "........",
      "settings": {}
    },
    "browser_preferences": {
      "schema_version": 2,
      "home": {
        "schema_version": 2,
        "order": [],
        "hidden": [],
        "presentation": [],
        "custom_sections": []
      }
    }
  }
}
```

The live target fingerprints used to bind Preview/Apply are **not** exported into the portable file. Generated Home UUIDs, source server/context/library identifiers, raw MMKV keys/values, credentials, sessions, player/device identity and hardware topology remain excluded.

The server validator accepts schema 1 and schema 2, rejects mixed ownership, keeps recursive forbidden credential/machine-state checks and validates the logical v2 shapes without treating raw browser state as server-owned data.

## Restore transaction contract

### Schema-v1 compatibility flow — PHYSICALLY ACCEPTED

Schema-v1 remains conservative:

1. parse and validate without mutation;
2. reject forbidden credential/machine-owned fields;
3. Preview paths/counts rather than values;
4. preflight target owners;
5. restore selected browser Home order/hidden through the schema-v1 target-context owner when needed;
6. apply selected ACP Settings/EQ/mixer and compatible exact-version Headless preferences through server owners;
7. verify each supported owner;
8. roll back within each existing owner boundary on failure.

The owner-facing flow remains **Preview → choose A Clockwork Plex / Plexamp / both → Review selected restore → Confirm & restore**.

The schema-v1 Home owner self-rolls back a failed Home mutation but does not retain its previous raw target snapshot across a successful Home step followed by a later server failure. That compatibility behaviour is recorded rather than hidden.

### Schema-v2 complete transaction — IMPLEMENTED, ACTIVE, AUTOMATED GREEN

The v2 transaction strengthens the cross-owner boundary:

1. Preview/Review stay read-only and refresh all selected owner fingerprints;
2. after final confirmation, apply the native Plexamp owner and retain its rollback token;
3. apply Home-v2 and retain its rollback token;
4. apply selected server-owned ACP participants through the existing server transaction;
5. if any later participant fails, roll retained browser owners back in reverse order before reporting failure;
6. verify exact/logical rollback as appropriate;
7. finalize retained browser rollback state only after **all** selected participants verify;
8. only then perform the normal post-success reload that lets Plexamp rehydrate effective Home/runtime state.

Automation additionally proves browser-only restores do not enter the server participant, stale browser state fails closed, and post-commit finalize trouble is a cleanup warning rather than a false restore failure.

Schema-v2 server stale protection deliberately excludes the legacy Headless observer/capability participant from its transaction fingerprint because the earlier browser-owned native stage is allowed to change Plexamp settings. Schema-v1 retains the older Headless stale-protection contract.

This is the same commit-boundary lesson already physically proven by #93 Reset: do not reload or throw away browser rollback state before the whole transaction has committed.

## Checkpoint status

### #88 ownership audit — COMPLETE

Portable/nonportable boundaries, exact eight-value schema-v1 Headless allow-list and safe Home ownership established.

### #89 configuration backup/export — PRODUCTION BRIDGE ACTIVE AND AUTOMATED GREEN; PHYSICAL GATE OPEN

Schema-v1 export of ACP logical settings/EQ/mixer, eight safe Headless preferences and validated Home order/hidden data is physically accepted.

The broader native-settings owner, full Home-v2 logical owner, schema-v2 envelope assembly and real Settings Backup action are implemented. Production bridge **1.5.0** activates the bounded owners. **Tests #4704** passed the complete activation/security/full-regression gate and **Tests #4705** passed the subsequent roadmap checkpoint.

Remaining product work: physically create and inspect a complete schema-v2 export on the commissioned appliance before Reset.

### #90 configuration import/restore — PRODUCTION BRIDGE ACTIVE AND AUTOMATED GREEN; PHYSICAL GATE OPEN

Schema-v1 Preview, target-context order/hidden restore, exact-version Headless restore and guided presentation are physically accepted.

The complete v2 **native → Home → ACP/server** retained-rollback transaction is integrated into the real Settings Preview/Review/Confirm flow, schema-v1 compatibility remains intact, and production bridge 1.5.0 exposes the bounded browser participants. Automated stale/failure/reverse-rollback/commit-boundary coverage is green.

Remaining product work: physically validate **Backup → Reset → Restore** on the commissioned appliance using a deliberately recognisable normal-use configuration and verify post-restore convergence.

### #93 Reset relationship — COMPLETE

The full bounded Home Reset model is proven on disposable 9230 and physically accepted end to end on the commissioned bedroom Pi, including final zero-difference convergence after `activeTab` runtime-normalisation and the compact zero-change Preview presentation. Bridge 1.5.0 retains the accepted Reset resources and regression guards; #89/#90 physical portability acceptance remains separate.
