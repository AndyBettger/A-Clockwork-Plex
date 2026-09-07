# Configuration backup and restore ownership

## Purpose

A Clockwork Plex needs a supported way to move useful appliance personality onto a rebuilt/replacement installation without cloning credentials, hardware identity, runtime caches or machine-specific implementation state.

The governing rule remains:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

Backup/Restore and Reset are deliberately different. A setting can be safe and portable enough to back up while still following its application's own defaults when Reset is requested.

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
| Plexamp live player volume | Exclude from portable backup | Runtime/player state; #93 explicitly returns live Plexamp music volume to 100% with rollback |
| Plexamp Home logical order/hidden choices | Include validated logical model | #90 restores target-context logical choices; fresh-profile #93 independently confirms both durable browser-local families |
| Plexamp Home per-section presentation (`viewSettings`) | **Not yet included in schema-v1 portable backup** | #93 physically confirms `viewSettings` as the durable presentation owner; portability follow-up remains open |
| Chromium profile wholesale | Never include | Never restore/copy wholesale |
| Weather/News caches/rainfall history | Exclude | Rebuild/refetch |
| Alarm/playback runtime | Exclude | Recreate from live state/current time |

## Portable ACP settings

Export is built from the **normalised Settings model**, not by serialising `config.json` directly.

Portable ACP state includes supported startup/idle, clock/display/night, Weather, alarms, AirPlay and safe user-facing audio choices. Installer/hardware integration does not migrate merely because a value happens to appear in configuration.

Credentials, raw hardware identity/topology, ALSA implementation state, service/runtime caches and machine identity remain excluded.

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

Known nonportable/separately owned fields remain:

- `playerName` — appliance-local commissioning label;
- `audioDeviceUuid` — target-specific output binding resolved live;
- `premium` — account/capability-derived.

Observed values from commissioned testing are evidence of real state, **not Reset defaults**. Backup/Restore means “restore the saved user's choices”; Reset means “return ordinary Plexamp settings to defaults defined by Plexamp itself”.

## ACP audio portability and Reset relationship

Backup stores logical EQ and mixer choices so a replacement appliance can restore the user's curve/calibration.

The current #93 Reset baseline is intentionally neutral/full-scale:

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

### Current schema-v1 Home model

The #89/#90 bridge currently owns only validated logical Home **order** and **hidden/visible** choices.

The portable model is:

```json
"home": {
  "order": [],
  "hidden": []
}
```

For export, the permission-free loopback browser bridge emits validated logical Home choices. The physically accepted commissioned export contained **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.

For restore, the bridge maps those logical choices onto the target's live Home context, requires a fresh fingerprint and explicit confirmation, captures exact target raw state, writes only classified Home records, verifies the logical result and reverses completed writes exactly on failure.

Checkpoint #90 is physically accepted for this schema-v1 order/hidden scope.

### Fresh-profile confirmation of schema-v1 owners

#93 disposable-profile testing independently supports the existing logical mapper rather than exposing alternate storage owners.

#### Order

Moving **Mixes for you** down two positions created the established browser-local `...:<section>:order` family. The move:

- survived page refresh;
- survived full Chromium process exit/relaunch;
- remained local to that browser profile when compared with another profile using the same Headless/account/library.

The corrected family probe reported exactly `order=1` on the order tracer.

#### Hidden/visible

A separate initially all-zero profile hid exactly **Recent Plays**. That created exactly one `hidden` record with `order=0`; the hide and family state survived page refresh and full Chromium restart.

Therefore the existing schema-v1 logical **order/hidden** abstraction is independently supported by fresh-profile physical evidence.

### Presentation (`viewSettings`) — confirmed owner, schema-v1 portability gap

Schema v1 does **not** currently export per-section `viewSettings`. A 5 September physical restore from a backup taken with Home presentation arranged as desired confirmed the consequence: order/hidden restored, but section presentation could not because it was never present in the backup.

That is a backup-schema completeness gap, not a restore-transaction failure.

Fresh #93 testing now independently confirms the durable presentation owner:

1. a third fresh profile started with all Home families zero;
2. changing exactly **Recent Plays → Carousel** produced `viewSettings=1` plus `editing=1` immediately after the edit;
3. a separate editor-only control profile opened/closed Home customisation without changes and remained completely all-zero;
4. after normal reload of the presentation tracer, Recent Plays remained Carousel while the probe became exactly `viewSettings=1`, `editing=0`;
5. after a full Chromium process exit/relaunch, Recent Plays still remained Carousel and the probe again reported exactly `viewSettings=1`, `editing=0`.

Therefore:

- `viewSettings` is the durable presentation owner;
- `editing` is transient edit bookkeeping, not durable Home personality;
- the missing schema-v1 presentation model should be built from validated logical `viewSettings` semantics, not raw Chromium storage.

### Custom sections/titles remain the final Home-family gap

Order, hidden/visible and built-in presentation persistence are now closed. Before declaring Home portability complete across replacement profiles, the remaining causal work is:

- classify custom-added section persistence on a fresh isolated profile;
- classify custom section title persistence one change at a time;
- decide which custom structure/title information is portable and how it should be represented logically;
- revalidate complete Home Backup/Restore after that model is implemented.

The schema-v1 order/hidden payload itself remains the correct abstraction and must not be replaced by copied browser files.

## #93 Home Reset relationship

The currently accepted production #93 Home Reset intentionally preserves:

- Home order;
- hidden/visible choices;
- custom-added sections;
- custom section titles.

It resets only presentation-specific records of the bounded family:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

For built-in sections, non-default `viewSettings` are removed so Plexamp uses its own per-section presentation defaults. For custom-added sections, the current owner strips presentation fields while retaining a validated title.

Order, hidden, `editing`, custom-hub, auth and cache values are not opened or mutated by this production owner.

This boundary is now strengthened by fresh-profile causal evidence: durable presentation is `viewSettings`; the `editing` family is transient across reload and is not required to preserve the visual choice.

## Why a clean Plexamp profile cannot simply be copied raw

A clean profile is useful as behavioural evidence but is not a portable backup artifact:

- browser profiles contain auth/session state;
- Home identifiers contain account/library/context-specific values;
- server/runtime-provided default sections can exist without local override records;
- custom sections need explicit product semantics;
- copied browser DB/MMKV bytes would couple portability to Chromium/Plexamp implementation details.

Portable Backup/Restore should therefore remain a logical model mapped through bounded live owners.

Likewise, a future full Home Reset should let Plexamp rebuild itself after clearing only narrowly proven Home-owned browser-profile-local persistence, not copy a clean profile's bytes or hard-code an observed default Home.

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

`plexamp.browser_preferences` is optional and merged only after a validated live bridge snapshot. Per-section presentation is not yet in schema v1. Commissioning state and live Plexamp player volume are intentionally absent.

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

Portable/nonportable boundaries, exact eight-value Headless allow-list and safe Home order/hidden ownership established.

### #89 configuration backup/export — CORE COMPLETE; HOME PRESENTATION FOLLOW-UP OPEN

Schema-v1 export of ACP logical settings/EQ/mixer, eight safe Headless preferences and validated Home order/hidden data is physically accepted. Per-section `viewSettings` remain the principal known schema-v1 completeness gap; their durable owner is now independently confirmed.

### #90 configuration import/restore — CORE COMPLETE; HOME PRESENTATION FOLLOW-UP OPEN

Read-only Preview, stale-protected transaction, exact-version Headless restore, target-context Home order/hidden restore/rollback and guided presentation are physically accepted. The remaining Home portability work is a logical `viewSettings` model plus custom-section/title classification.

### #93 Reset relationship — TRANSACTION ACCEPTED; FINAL HOME SCOPE OPEN

The combined Reset transaction is physically accepted. Home order, hidden/visible and built-in presentation persistence are now independently classified; full Home Reset remains open only for custom section/title semantics and the reversible scrub/rebuild proof.
