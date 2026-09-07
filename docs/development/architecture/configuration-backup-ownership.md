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
| Eight safe Plexamp Headless preferences | Include exact typed allow-list, version-aware | Restore saved values through restricted owner; #93 lets Plexamp's own Reset reset them normally |
| Plexamp player name/audio output | Exclude from portable backup | Same-appliance #93 commissioning owner restores captured player name + dynamically resolved managed output |
| Plexamp live player volume | Exclude from portable backup | Runtime/player state; #93 returns live Plexamp music volume to 100% with rollback |
| Plexamp Home logical order/hidden choices | Include validated logical model | #90 restores target-context choices; #93 also classifies both as durable resettable Home customisation |
| Plexamp Home per-section presentation (`viewSettings`) | **Not yet included in schema-v1 portable backup** | #93 confirms durable ownership and now clears it during bounded full-Home Reset; portable logical model remains open |
| Plexamp Home custom sections/titles | **Not yet included in schema-v1 portable backup** | #93 confirms custom sections as `customHubs + order + viewSettings`, title inside `viewSettings`, and clears the bounded bundle during Reset; portable model remains open |
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

## Plexamp Headless portable preference boundary

The Plexamp Settings directory itself is **not** a supported backup unit.

Checkpoint #88 established this exact typed scalar portable allow-list:

- `audioConversionBitrate`
- `autoPlayEnabled`
- `cacheSize`
- `cachingWiFi`
- `loudnessLeveling`
- `precacheNetworkSpeed`
- `sampleRateConversionQuality`
- `sampleRateMatching`

Only exact allow-listed names and expected types are exported/restored; malformed/unknown files are skipped rather than copied.

Known nonportable/separately owned fields include:

- `playerName` — appliance-local commissioning label;
- `audioDeviceUuid` — target-specific output binding resolved live;
- `premium` — account/capability-derived.

Observed values from commissioned testing are evidence of state, **not Reset defaults**. Backup/Restore means “restore saved user choices”; Reset means “return choices to defaults defined by their owners”.

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

### Current schema-v1 portable Home model

The #89/#90 bridge currently exports/restores only validated logical Home **order** and **hidden/visible** choices:

```json
"home": {
  "order": [],
  "hidden": []
}
```

The physically accepted commissioned export contained **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.

Restore maps those logical choices onto the target's live Home context, requires a fresh fingerprint and explicit confirmation, captures exact target rollback state, writes only classified Home records, verifies the logical result and reverses completed writes exactly on failure.

Checkpoint #90 is physically accepted for this schema-v1 order/hidden scope.

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

Therefore the remaining Backup/Restore work is **logical-model design and implementation**, not storage-family discovery.

### Presentation/custom-section portability gap

Schema v1 does **not** export per-section `viewSettings`, custom-section structure or custom titles. Physical restore testing on 5 September demonstrated the consequence: supported order/hidden choices restore, but presentation cannot restore when it was never present in the backup.

That is a backup-schema completeness gap, not a restore-transaction failure.

A future portable model must describe validated logical presentation/custom-section/title semantics and map them through the target's live context. It must **not** serialize raw Chromium Local Storage keys/values or copy a profile.

## #93 full Home Reset relationship — PROVEN

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

This proves **Reset ownership**, not **portability**. The production #93 Home owner may clear classified Home state in the current profile with exact rollback, while #89/#90 must still develop a logical cross-installation representation for presentation/custom sections/titles.

## Why a clean Plexamp profile cannot be copied raw

A clean profile is useful behavioural evidence but is not a portable backup artifact:

- browser profiles contain auth/session state;
- Home identifiers contain account/library/context-specific values;
- server/runtime-provided default sections can exist without local override records;
- custom sections need explicit logical semantics across installations;
- copied browser DB/MMKV bytes would couple portability to Chromium/Plexamp implementation details.

Full Home Reset therefore clears only proven Home-owned browser-local overrides and lets Plexamp rebuild itself. Portable Backup/Restore remains a logical model mapped through bounded live owners.

## Backup envelope

The supported schema-v1 envelope remains:

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

`plexamp.browser_preferences` is optional and merged only after a validated live bridge snapshot. Per-section presentation/custom-section/title semantics are not yet in schema v1. Commissioning state and live Plexamp player volume are intentionally absent.

## Restore contract

Restore remains conservative:

1. parse and validate without mutation;
2. reject forbidden credential/machine-owned fields;
3. Preview paths/counts rather than values;
4. preflight target owners;
5. capture rollback state;
6. apply ACP Settings/EQ/mixer/AirPlay through their owners;
7. restore exact-version safe Headless preferences through the restricted owner;
8. restore current schema-v1 Home order/hidden through the target-context browser owner when selected;
9. verify resulting logical state;
10. roll back within each supported owner boundary on failure.

The owner-facing flow remains **Preview → choose A Clockwork Plex / Plexamp / both → Review selected restore → Confirm & restore**.

## Checkpoint status

### #88 ownership audit — COMPLETE

Portable/nonportable boundaries, exact eight-value Headless allow-list and safe Home ownership established.

### #89 configuration backup/export — CORE COMPLETE; HOME PRESENTATION/CUSTOM MODEL FOLLOW-UP OPEN

Schema-v1 export of ACP logical settings/EQ/mixer, eight safe Headless preferences and validated Home order/hidden data is physically accepted. Presentation/custom-section/title persistence is fully classified, but the validated portable logical model is not yet implemented.

### #90 configuration import/restore — CORE COMPLETE; HOME PRESENTATION/CUSTOM MODEL FOLLOW-UP OPEN

Read-only Preview, stale-protected transaction, exact-version Headless restore, target-context Home order/hidden restore/rollback and guided presentation are physically accepted. Remaining Home portability work is logical-model implementation and physical revalidation.

### #93 Reset relationship — FULL HOME ARCHITECTURE PROVEN; PRODUCTION ACCEPTANCE PENDING

The full bounded Home Reset model is physically proven on disposable 9230 and implemented on `feature/reset-defaults`. This does not close the #89/#90 portability gap. #93 now awaits a final green branch head, commissioned-Pi production Preview/Review/Confirm acceptance, and explicit owner approval before PR #9 may leave Draft or merge.
