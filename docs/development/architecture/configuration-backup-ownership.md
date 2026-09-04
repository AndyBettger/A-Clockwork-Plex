# Configuration backup and restore ownership

## Purpose

A Clockwork Plex needs a supported way to move useful appliance personality onto a rebuilt/replacement installation without cloning credentials, hardware identity, runtime caches or machine-specific implementation state.

The governing rule remains:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

Backup/Restore and Reset are deliberately different operations. A setting can be safe and portable enough to back up while still following its application's own defaults when Reset is requested.

## Ownership matrix

| State | Backup policy | Restore / Reset relationship |
| --- | --- | --- |
| ACP user settings | Include normalised portable model, never raw `config.json` | Restore through production owners; #93 derives ACP defaults from version-controlled example + normalisers |
| Alarm schedules/ordinary choices | Include | Restore normally; #93 resets ordinary choices but preserves alarm-audio arming switches |
| Display/theme/night/clock/startup | Include | Restore through Settings; #93 owns supported ACP defaults |
| Weather non-secret choices | Include | Restore through Weather Settings; #93 resets supported choices |
| Weather Underground API key | Never include | Recommission explicitly; #93 preserves credential |
| AirPlay user preferences | Include logical values | Restore through guarded owners; #93 resets supported user defaults |
| Master EQ | Include logical enabled/bands | Restore through EQ owner; #93 resets to neutral/default logical state |
| Persistent mixer levels | Include logical percentages | Restore through mixer owner; #93 uses physically observable mixer defaults |
| Audio routes/CamillaDSP/systemd/sudoers/hardware | Exclude | Recreate from installer/hardware commissioning; #93 preserves topology |
| Plexamp runtime | Exclude | Reinstall through runtime owner; #93 does not replace runtime |
| Eight safe Plexamp Headless preferences | Include exact typed allow-list, version-aware | Restore saved values through restricted owner; **#93 lets Plexamp's own Reset to Defaults reset them normally** |
| Plexamp player name/audio output | Exclude from portable backup | Same-appliance #93 commissioning owner restores captured player name + dynamically resolved managed output |
| Plexamp Home logical order/hidden choices | Include validated logical model | #90 restores saved layout; #93 separately returns bounded order/visibility to Plexamp default state |
| Chromium profile wholesale | Never include | Never restore/copy wholesale; #93 touches only classified Home records |
| Weather/News caches/rainfall history | Exclude | Rebuild/refetch; #93 preserves runtime/history |
| Alarm/playback runtime | Exclude | Recreate from live state/current time |

## Portable ACP settings

Export is built from the **normalised Settings model**, not by serialising `config.json` directly.

Portable ACP state includes startup/idle choices, clock/display/night preferences, Weather labels/units/cards/providers/forecast settings, alarms, AirPlay preferences and safe user-facing audio choices. Installer/hardware integration does not migrate merely because a value happens to appear in configuration.

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

The #93 commissioning baseline does not weaken these exclusions. Its player name remains local to the appliance and never enters the portable backup envelope; the audio UUID is not stored in the baseline at all.

## Plexamp Headless portable preference boundary

The Plexamp Settings directory is preserved by the guarded runtime installer across runtime replacement, but the directory itself is **not** a supported backup unit.

Checkpoint #88 established this exact typed scalar portable allow-list:

| Preference | Backup/Restore |
| --- | --- |
| `audioConversionBitrate` | Include, version-aware |
| `autoPlayEnabled` | Include, version-aware |
| `cacheSize` | Include, version-aware |
| `cachingWiFi` | Include, version-aware |
| `loudnessLeveling` | Include, version-aware |
| `precacheNetworkSpeed` | Include, version-aware |
| `sampleRateConversionQuality` | Include, version/audio-policy aware |
| `sampleRateMatching` | Include, version/audio-policy aware |

The audit uses Plexamp's typed scalar encodings (`Btrue` / `Bfalse`, `N<number>`). Only exact allow-listed names and expected types are exported/restored; malformed/unknown files are skipped rather than copied.

Known nonportable/separately owned fields remain:

- `playerName` — appliance-local commissioning label;
- `audioDeviceUuid` — target-specific output binding, dynamically resolved by commissioning;
- `premium` — account/capability-derived.

### Observed values are evidence, not defaults

Earlier #88/#90 commissioned-Pi auditing observed:

```text
256 / false / 32768 / 10 / false / 0 / 4 / 2
```

for the eight keys above.

During the 4 September #93 physical pass the same appliance instead reported:

```text
128 / true / 512 / 15 / true / 0 / 2 / 0
```

Those observations are useful forensic/commissioning evidence, but **neither set is a #93 Reset baseline**.

Backup/Restore means “restore the saved user's choices”. Reset means “return Plexamp's ordinary settings to the defaults defined by Plexamp itself”. Therefore `browser/plexamp-bridge/native-reset.js` now allows all eight safe Headless preferences to participate normally in Plexamp's own `settings.resetToDefaults()` method.

If later high-resolution-audio work deliberately makes one of these values an ACP appliance policy, that future work must establish and document its own commissioned ownership rather than inheriting an accidental #93 baseline.

## Appliance-local Plexamp commissioning ownership — PHYSICALLY ACCEPTED

`app/plexamp_commissioning.py` and `scripts/commission-plexamp.py` own only:

- `playerName`;
- `audioDeviceUuid` as the live binding for the managed output.

The owner:

- accepts only Plexamp's loopback settings API on port 32500;
- captures the intended player name once into `~/.local/share/a-clockwork-plex/plexamp-commissioning.json` (mode `0600`);
- never recaptures a later rename during ordinary repeat setup;
- stores no audio UUID;
- dynamically requires exactly one output labelled **`A Clockwork Plex - Plexamp`**;
- fails closed on missing/ambiguous managed output;
- returns only bounded status/count/fingerprint information to Reset Preview;
- never serialises this state into portable backup.

Physical acceptance completed on 3 September 2026: a temporary player rename and **Follows system output** produced exactly two commissioning differences, and Reset returned both to the commissioned appliance state without exposing the values.

## Plexamp Home ownership

The kiosk Chromium profile contains authentication/session material as well as UI state, so **the profile must never be archived/restored wholesale**.

The live #89/#90 bridge classifies only Plexamp Home order/hidden records under the local Plexamp origin. Auth/session, cache/resource, editor and unrelated values remain outside the owner.

### Backup/Restore Home bridge

For #89 export, the permission-free loopback-only bridge emits only validated logical Home order/hidden choices in browser memory. The final commissioned-Pi export physically contained **15 ordered Home identifiers + 1 hidden identifier**, with no browser omission and zero warnings.

For #90 restore, the bridge maps saved logical choices onto the target's live context, requires a fresh fingerprint and explicit confirmation, captures exact target raw state, writes only classified Home records, verifies the logical result and reverses completed writes exactly on failure.

Checkpoint #90 Home restore is physically accepted, including combined restore convergence back to zero differences.

### Separate #93 Home Reset

Backup/Restore means “return to this saved layout”. Reset means “return to Plexamp's browser/device-local default Home”.

A disposable fresh Chromium profile using the same Plex account/library established the default Home independently; `Mixes for You` appeared first in the physical test. Plexamp **Home Screen → Reset order** restored this default order, but did not unhide a deliberately hidden section.

The #93 Home owner therefore resets both order and visibility across only these bounded families:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:order
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden
mmkv.default\discovery:customizations:order
mmkv.default\discovery:customizations:hidden
```

Preview reports only counts/fingerprint. Apply is stale-protected, snapshots exact raw bytes, removes only classified reset records, verifies absence and retains rollback state until the outer Reset finalizes.

The old compact `:c` LevelDB lead was absent from live Local Storage during a bounded key-name-only probe and remains historical/deleted residue rather than a Reset authority.

## Native Plexamp Reset runtime relationship

Plexamp's native Reset owner runs in the Plexamp page world while the extension remains permission-free and loopback-scoped.

The first physical combined Preview on 4 September 2026 correctly failed closed with native `runtime-unavailable`: the original implementation assumed a webpack chunk/cache export not present on the real app. Read-only inspection of the installed Plexamp 4.13.2 static bundle identified module `92895` and its proxy getter to `global.app.rootStore.settings`.

The corrected owner therefore uses Plexamp's application-global settings store directly and calls Plexamp's real `settings.resetToDefaults()` method. It neither exposes raw setting values nor adds generic page execution, remote debugging, cookies or network authority.

## Backup envelope

The supported portable format remains schema-versioned JSON with these logical domains:

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

`plexamp.browser_preferences` is optional and is merged only after a validated live bridge snapshot. The commissioning baseline is intentionally absent.

## Restore contract

Restore remains conservative:

1. parse and validate without mutation;
2. reject forbidden credential/machine-owned fields;
3. Preview paths/counts rather than values;
4. preflight target owners;
5. capture rollback state;
6. apply ACP Settings/EQ/mixer/AirPlay through their owners;
7. restore exact-version safe Headless preferences through the restricted owner;
8. restore Home through the target-context browser owner when selected;
9. verify resulting logical state;
10. roll back within each supported owner boundary on failure.

The guided owner-facing flow remains **Preview → choose A Clockwork Plex / Plexamp / both → Review selected restore → Confirm & restore**.

## Accepted checkpoints

### #88 ownership audit — COMPLETE

Established the portable/nonportable boundaries, exact eight-value Headless allow-list and safe Home order/hidden families while unknown/auth/device/browser values remained unopened.

### #89 configuration backup/export — COMPLETE

Physically accepted schema-v1 export of ACP logical settings/EQ/mixer, all eight safe Headless preferences and validated logical Home data, with secrets/device identity/runtime state excluded.

### #90 configuration import/restore — COMPLETE

Physically accepted read-only Preview, stale-protected server transaction, exact-version Headless restore, Home restore/rollback and guided owner-facing presentation. Final combined physical restore converged back to zero differences.

### #93 Reset relationship — PHYSICAL ACCEPTANCE STILL OPEN FOR FINAL NATIVE/HOME COMBINATION

ACP Reset and commissioning Reset are already physically accepted. The corrected native Plexamp settings + Home implementation is automated-green at `c2754171b6394485306df6aebf21df4d2c2e3e33` / **Tests #4512: 1027 tests in 49.344s, `OK`** after the live runtime locator and Headless Reset ownership corrections.
