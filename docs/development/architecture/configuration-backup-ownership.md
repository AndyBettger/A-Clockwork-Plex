# Configuration backup and restore ownership

## Purpose

A Clockwork Plex needs a supported way to move the useful personality of a commissioned appliance onto a rebuilt or replacement installation without accidentally cloning credentials, hardware identity, volatile runtime state or stale machine-specific files.

The backup contract therefore follows the same ownership rule as the rest of the appliance:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

This document records the post-v0.4.0 ownership audit and the contract now used by the backup/export implementation.

## Design goals

A normal appliance backup should:

- preserve settings the owner would reasonably expect to survive a rebuild;
- be inspectable, versioned and portable between supported A Clockwork Plex installations;
- contain **no authentication or managed secrets**;
- avoid machine-specific paths, generated caches and transient runtime state;
- restore through the same validated authorities used by Settings rather than overwriting arbitrary files;
- tolerate a newer appliance/Plexamp version by validating known fields and ignoring or reporting unsupported optional preferences;
- provide a preview before a restore can change the live appliance.

A backup is **not** intended to be a disk image or a forensic copy of the Pi.

## Ownership matrix

| State | Current owner/location | Ordinary backup policy | Restore policy |
| --- | --- | --- | --- |
| A Clockwork Plex user settings | `config.json`, exposed/validated through `UnifiedSettingsService` and specialist Settings extensions | **Include as a normalised portable settings model**, not as raw `config.json` bytes | Validate and apply through the unified/specialist settings authorities |
| Alarm schedules and user alarm choices | `config.json` / alarm configuration authority | **Include** | Preview enabled alarms and validate before applying; never copy alarm runtime state |
| Display themes, night behaviour, clock layout and idle/startup choices | `config.json` / Unified Settings | **Include** | Apply through Settings validation |
| Weather station labels, units, clock cards, observation provider settings and forecast location | `config.json` / Weather Settings authorities | **Include non-secret values** | Apply through Weather Settings validation; remote credentials remain a separate commissioning step |
| Weather Underground API key | `/etc/default/a-clockwork-plex-weather`, root-owned, mode `0600` | **Never include** | Recommission explicitly through the managed credential owner |
| AirPlay receiver name and ordinary handoff/default-volume preferences | configuration plus `ShairportNameManager` | **Include logical values** | Apply receiver name through its guarded helper and other preferences through Settings |
| Master EQ Bass/Mid/Treble and bypass state | `/var/lib/a-clockwork-plex/split-bus/master-eq.json`, owned by the restricted EQ helper | **Include as normalised logical values** | Apply through `MasterEqualizer`; never replace the root-owned state file directly |
| Persistent shared mixer levels | ALSA control state persisted by `alsactl store` | **Include four normalised percentages** (`master`, `plexamp`, `airplay`, `alarm`) | Apply through the restricted mixer helper after the accepted audio route exists; never copy ALSA state files |
| Audio routes, CamillaDSP configuration/binary, systemd units, sudoers and hardware bindings | guarded installer/audio lifecycle | **Exclude** | Recreate from the installed release and hardware commissioning, not from user backup |
| Plexamp Headless runtime | `~/plexamp`, installed from pinned release archive | **Exclude** | Reinstall through the guarded Plexamp runtime owner |
| Plexamp Headless persistent Settings store | `~/.local/share/Plexamp/Settings` | **Selective allow-list only; never copy directory wholesale** | Restore only known non-auth preference keys, version-aware and best-effort |
| A Clockwork Plex kiosk Chromium profile | `~/.config/a-clockwork-plex/chromium-profile` | **Never copy profile wholesale** | Export/restore only explicit allow-listed current Plexamp UI values through a live browser-side authority |
| WU selected-period/full-station rainfall caches | `weather-rainfall-history.json`, `weather-rainfall-lifetime.json` | **Exclude** | Rebuild/backfill from the commissioned Weather source |
| Forecast cache | `weather-forecast-cache.json` | **Exclude** | Re-fetch from Open-Meteo |
| Dashboard/weather live state and pressure/extreme history | `state.json` | **Exclude** | Rebuild from live observations |
| Alarm runtime/audio runtime | `alarm-runtime.json`, `alarm-audio-runtime.json` | **Exclude** | Recreate from configuration and current time; never resurrect an old ringing/snoozed occurrence |
| Playback/handoff runtime | `playback-runtime.json` and application-state runtime | **Exclude** | Recreate from live Plexamp/AirPlay state |
| EQ route state, install markers, pre-EQ rollback backup and installer transactions | `/var/lib/a-clockwork-plex/...` | **Exclude** | Owned by installation/repair lifecycle only |
| Generated assets, logs and caches | project/runtime cache paths | **Exclude** | Regenerate |

## Portable A Clockwork Plex settings

The export is built from the **normalised Settings model**, not by serialising `config.json` directly. The public Settings authority already knows how to normalise and validate the appliance domains.

Portable settings include:

- startup/idle screen and idle timeout;
- clock format, transition preferences, daytime theme and alarm-indicator policy;
- night dim schedule/levels, night clock style and burn-in shifting preference;
- Weather labels, units, clock-card selection/order, provider choice, Ecowitt freshness/path, WU station ID/timing, selected rainfall period and Open-Meteo forecast settings;
- alarm schedules, labels, recurrence, tones, volumes, fade, Snooze and Dismiss/ring policy;
- AirPlay receiver name, default starting volume and hold behaviour;
- safe user-facing audio preferences.

Installer/hardware integration values do not migrate merely because they happen to appear in `config.json`. Examples include fixed ALSA hardware device names, installer-owned service paths, Plexamp localhost/service plumbing and compatibility fields. A restore uses the target installation's commissioned hardware/runtime values unless a field has deliberately been classified as portable.

The Weather Underground `api_key_env` setting is also target-owned implementation detail and is omitted from the portable backup. The actual API key is already outside normal Settings and remains a hard exclusion.

## Secrets and identity: hard exclusions

An ordinary backup must never contain:

- Weather Underground API key or any future managed Weather secret;
- Plex account authentication token, claim token or account/session credentials;
- Plexamp player/machine/client identity intended to distinguish one player from another;
- Chromium cookies, login data, session storage or authentication databases;
- passwords, bearer tokens, API keys or other values matching a managed-secret class;
- private key material.

A non-credential backup can still contain personal household information such as alarm times, station IDs, labels and approximate forecast coordinates. The UI/documentation should make that distinction clear rather than describing the file as anonymous.

## Plexamp ownership boundary

The guarded Plexamp installer treats:

```text
~/.local/share/Plexamp/Settings
```

as persistent state outside the replaceable `~/plexamp` runtime. That directory is intentionally preserved across Plexamp runtime repairs/updates, but it is **not safe as a backup unit**.

The commissioned Plexamp 4.13.2 development Pi physically exposed 35 files in this store. Eleven safe-looking `@Plexamp:settings:*` names were visible to the content-blind audit and 24 files remained deliberately unclassified. The exact ordinary typed scalar allow-list established from that live inventory is:

| Preference | Observed value | Backup policy |
| --- | ---: | --- |
| `audioConversionBitrate` | `256` | Include, version-aware |
| `autoPlayEnabled` | `false` | Include, version-aware |
| `cacheSize` | `32768` | Include, version-aware |
| `cachingWiFi` | `10` | Include, version-aware |
| `loudnessLeveling` | `false` | Include, version-aware |
| `precacheNetworkSpeed` | `0` | Include, version-aware |
| `sampleRateConversionQuality` | `4` | Include, version/audio-policy aware |
| `sampleRateMatching` | `2` | Include, version/audio-policy aware |
| `audioDeviceUuid` | value deliberately not read | **Exclude**; recommission the target output device |
| `premium` | value deliberately not read | **Exclude**; derived account/capability state |
| `playerName` | value deliberately not read | Keep outside the ordinary preference bundle; handle separately only if a future device-label restore is explicitly designed |

Plexamp's typed scalar files use `Btrue` / `Bfalse` and `N<number>` encodings for these observed settings. Export code accepts only the exact allow-listed names and expected scalar type; unknown files and malformed values are skipped rather than copied.

Current queue/state, resources, tokens and identity remain excluded even if technically easy to copy.

### Browser-side Plexamp Home customisation

The A Clockwork Plex kiosk uses its own Chromium profile:

```text
~/.config/a-clockwork-plex/chromium-profile
```

The same browser profile renders the dashboard and Plexamp web UI. The profile also contains browser session/authentication state, therefore **the Chromium profile must never be archived/restored wholesale**.

Read-only physical discovery on the commissioned Pi established the Plexamp origin as `http://localhost:32500` and identified React Native MMKV-style Local Storage keys under the `mmkv.default\<key>` namespace. The discovery helper deliberately read names/fingerprints only, never browser values.

The useful ownership findings are:

- `@Plexamp:resources` — **exclude**; server/resource identity;
- `@Plexamp:settings:activeTab` — transient navigation state, exclude from ordinary backup;
- `@Plexamp:settings:radioIncludeExternal` — ordinary browser preference candidate;
- `mmkv.default\...:cachedItems` — generated cache content, exclude;
- `mmkv.default\discovery:customizations:<context>::/library/sections/<id>:order` — physically proven Home-item ordering authority;
- `mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden` — physically proven per-item hidden/shown customization state;
- matching `...:<hub-id>:editing` records — transient customiser/editor state, exclude.

A physical differential test moved one Home item and only the contextual `:order` record acquired new state. A separate real hide action created the complete per-hub `:hidden` key and transient `:editing` records for the affected Home hub.

The raw Chromium LevelDB files are **discovery evidence only, not the production backup authority**. Chromium compacted the database between snapshots, changing which historical records were visible. Production Home-layout export must therefore execute against the live Plexamp browser origin and read only the allow-listed current `order` / `hidden` preference families. It must never scrape/copy the LevelDB files.

The source customization key also contains account/library context. Restore must not write the source key literally to a replacement appliance. After Plexamp has been freshly claimed and the target library selected, the restore path must discover the target's live customization context and translate the saved logical ordering/hidden choices into that context.

## Audio preferences

### EQ

`MasterEqualizer` is the authority for persisted Bass/Mid/Treble and bypass state. The backup carries only the logical model, for example:

```json
{
  "enabled": true,
  "bands": {
    "bass": 1.0,
    "mid": 0.0,
    "treble": -0.5
  }
}
```

Restore calls the EQ authority after the audio backend has been installed and verified. It must not write `master-eq.json` directly.

### Mixer

Persistent mixer levels are stored by ALSA, but ALSA's state file is tied to a particular card/control graph. The backup stores the four user-facing percentages instead:

```json
{
  "master": 80,
  "plexamp": 100,
  "airplay": 100,
  "alarm": 85
}
```

Restore invokes the existing restricted mixer helper after the target audio profile is ready. This makes the backup portable even if the underlying raw softvol percentages or device identity change.

## Backup envelope

The first supported format is JSON and explicitly versioned:

```json
{
  "schema_version": 1,
  "created_at": "2026-08-23T23:59:00+01:00",
  "source": {
    "application": "A Clockwork Plex",
    "app_version": "0.4.0",
    "release_tag": "v0.4.0",
    "release_name": "Unified Bedside Appliance"
  },
  "a_clockwork_plex": {
    "settings": {},
    "audio": {
      "eq": {},
      "mixer": {}
    }
  },
  "plexamp": {
    "source_version": "4.13.2",
    "headless_preferences": {}
  },
  "export_report": {
    "warnings": [],
    "omitted": []
  }
}
```

Release/version metadata is derived from `app/static/app-version.json`, not hard-coded into the exporter. Plexamp runtime version is read from non-sensitive local runtime package metadata when available.

Sections may be omitted when their owner/backend is unavailable. Export reports what was deliberately skipped. Browser Home preferences are intentionally reported as omitted until the live browser-side allow-listed bridge is implemented.

## Restore contract

Restore is a separate operation from export and remains conservative:

1. parse and validate the schema without changing anything;
2. reject malformed/unsupported required data and bound all values;
3. present a summary/preview, including enabled alarm count and unavailable optional sections;
4. establish that the target appliance/runtime/audio owners are installed and healthy;
5. capture rollback state for every owner that will change;
6. apply ordinary ACP configuration through its Settings authorities;
7. apply guarded specialist state (AirPlay receiver name, EQ, mixer) through those specialist owners;
8. apply supported Plexamp allow-listed preferences only after Plexamp is installed/claimed and version compatibility is known;
9. verify the resulting Settings/specialist snapshots;
10. roll back changed owners if a required restore stage fails.

Managed secrets remain a deliberate **post-restore commissioning step**. A successful restore must not claim that WU/Plex authentication was restored when those credentials were intentionally excluded.

## Reset-to-defaults relationship

The future reset workflow should use the same ownership classification rather than deleting files indiscriminately. It should be possible to reset ordinary user settings while leaving installer-owned hardware/audio topology and credentials alone unless the owner explicitly chooses a deeper decommissioning action.

## #88 audit status — COMPLETE

Checkpoint #88 is complete. Repository ownership classification, live Plexamp Headless inventory and browser-side Home-layout discovery have all established a narrow non-authentication backup boundary. No raw Plexamp profile, Chromium profile or LevelDB file is a supported backup unit.

The commissioned Pi physically proved the Headless allow-list and browser key families through staged read-only audits and before/after Home reorder/hide experiments. This closes discovery and moves the active Settings/appliance-ownership work to #89.

## #89 backup/export status — IN PROGRESS

The first export slice is implemented on `develop`:

- `app/configuration_backup.py` builds schema-version-1 JSON from the existing normalised Settings authority;
- portable field selection excludes installer/hardware values instead of serialising the whole public Settings snapshot;
- Weather observation export omits both the WU secret and target-owned `api_key_env` implementation detail;
- the exact eight typed Plexamp Headless preferences are read through a strict allow-list;
- EQ is exported as logical state and available shared-mixer levels as four percentages;
- browser Home preferences remain explicitly omitted pending the live browser-side bridge;
- `GET /api/settings/backup` is read-only, `Cache-Control: no-store`, and returns an attachment filename;
- Settings exposes **Advanced → Backup & restore → Download backup** without making backup part of the staged Save Changes transaction;
- restore/import is intentionally not enabled by this slice.
