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
| Master EQ | Include logical enabled/bands | Restore through EQ owner; #93 resets to enabled neutral 0/0/0 dB |
| Persistent mixer levels | Include logical percentages | Restore through mixer owner; #93 resets Music Master, Plexamp trim, AirPlay trim and Maximum Alarm Volume to 100% |
| Audio routes/CamillaDSP/systemd/sudoers/hardware | Exclude | Recreate from installer/hardware commissioning; #93 preserves topology |
| Plexamp runtime | Exclude | Reinstall through runtime owner; #93 does not replace runtime |
| Eight safe Plexamp Headless preferences | Include exact typed allow-list, version-aware | Restore saved values through restricted owner; **#93 lets Plexamp's own Reset to Defaults reset them normally** |
| Plexamp player name/audio output | Exclude from portable backup | Same-appliance #93 commissioning owner restores captured player name + dynamically resolved managed output |
| Plexamp live player volume | Exclude from portable backup | Runtime/player state rather than portable personality; #93 explicitly returns live Plexamp music volume to 100% with rollback |
| Plexamp Home logical order/hidden choices | Include validated logical model | #90 restores saved layout; #93 **preserves order/visibility/custom sections** and resets only per-section presentation `viewSettings` |
| Chromium profile wholesale | Never include | Never restore/copy wholesale; #93 touches only bounded native settings and Home presentation records |
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

Backup/Restore means “restore the saved user's choices”. Reset means “return Plexamp's ordinary settings to the defaults defined by Plexamp itself”. Therefore `browser/plexamp-bridge/native-reset.js` allows all eight safe Headless preferences to participate normally in Plexamp's own `settings.resetToDefaults()` method.

If later high-resolution-audio work deliberately makes one of these values an ACP appliance policy, that future work must establish and document its own commissioned ownership rather than inheriting an accidental #93 baseline.

## ACP audio portability and Reset relationship

Backup stores logical EQ and mixer values so a replacement appliance can restore the user's chosen curve and calibration.

Reset is different: the current #93 baseline is intentionally neutral/full-scale:

```text
Master EQ: enabled, Bass 0.0 dB, Mid 0.0 dB, Treble 0.0 dB
Music Master: 100%
Plexamp trim: 100%
AirPlay trim: 100%
Maximum Alarm Volume: 100%
```

The earlier nominal 80% / observed 79% Music Master result remains useful evidence about ALSA quantisation but is no longer a product default.

AirPlay's separate 60% **session-start volume** is a user preference/runtime policy, not the persistent AirPlay trim baseline.

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

### Backup/Restore Home bridge

The #89/#90 bridge classifies only validated Home order/hidden records under the local Plexamp origin. Auth/session, cache/resource, editor and unrelated values remain outside the owner.

For #89 export, the permission-free loopback-only bridge emits only validated logical Home order/hidden choices in browser memory. The final commissioned-Pi export physically contained **15 ordered Home identifiers + 1 hidden identifier**, with no browser omission and zero warnings.

For #90 restore, the bridge maps saved logical choices onto the target's live context, requires a fresh fingerprint and explicit confirmation, captures exact target raw state, writes only classified Home records, verifies the logical result and reverses completed writes exactly on failure.

Checkpoint #90 Home restore is physically accepted, including combined restore convergence back to zero differences.

### Separate #93 Home Reset — presentation only

The physical investigation showed that deleting order/visibility override records is not a reliable definition of “factory Home”. An appliance can have an already-customised effective Home while reporting no local order/hidden override records, so absence cannot truthfully be called default.

The #93 product boundary therefore changed:

- **preserve Home order**;
- **preserve hidden/visible choices**;
- **preserve custom-added sections**;
- **preserve custom section titles**;
- reset only each section's presentation-specific `viewSettings` back to Plexamp's own per-section defaults.

The current Reset owner recognises only:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

For built-in sections, a non-default `viewSettings` record is removed. For custom-added sections, presentation fields are stripped while a validated custom `title` is retained. Order, hidden, editor, custom-hub, auth and cache values are not opened or mutated by this Reset owner.

Preview reports only a count/fingerprint. Apply is stale-protected, snapshots exact raw bytes, writes/removes only classified `viewSettings`, verifies convergence and retains rollback state until the outer Reset finalizes.

The old compact `:c` LevelDB lead remains historical/deleted residue rather than a Reset authority.

## Native Plexamp Reset relationship

Plexamp's native Reset owner runs in the Plexamp page world while the extension remains permission-free and loopback-scoped.

Read-only inspection of the installed Plexamp 4.13.2 static bundle identified the real settings authority through `global.app.rootStore.settings`. The corrected owner calls Plexamp's real `settings.resetToDefaults()` method and compares against a fresh live settings instance.

The public Preview exposes only bounded setting **names**, counts and a fingerprint — never old/new values. This is intentionally enough to diagnose a residual “1 setting differs” case without broadening the preference-value surface.

The native owner also treats live Plexamp music-player volume as one bounded Reset choice:

- Preview reports `playerVolume` by name when it differs;
- target is 100%;
- apply uses Plexamp's same-origin player API;
- verification confirms 100%;
- rollback restores the exact pre-reset volume if this or a later Reset participant fails.

`playerName` and `audioDeviceUuid` remain excluded from native Preview diagnostics because commissioning owns their final appliance state.

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

`plexamp.browser_preferences` is optional and is merged only after a validated live bridge snapshot. The commissioning baseline and live Plexamp player volume are intentionally absent.

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

### #93 Reset relationship — FINAL REVISED PHYSICAL ACCEPTANCE OPEN

ACP Reset and commissioning Reset are already physically accepted. The revised browser-side contract is automated-green through `c1b98dc018b2e60d4ed8c6fba0999d022155eef9` / **Tests #4550** with 1027 tests passing: native setting-name diagnostics, Plexamp player-volume 100% Reset/rollback, Home `viewSettings` reset with order/visibility/custom-section preservation, and the new full-scale ACP mixer baseline.
