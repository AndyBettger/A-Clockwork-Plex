# Configuration backup and restore ownership

## Purpose

A Clockwork Plex needs a supported way to move the useful personality of a commissioned appliance onto a rebuilt or replacement installation without accidentally cloning credentials, hardware identity, volatile runtime state or stale machine-specific files.

The backup contract therefore follows the same ownership rule as the rest of the appliance:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

This document records the post-v0.4.0 ownership audit that precedes the backup/export and restore/import implementation.

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
| A Clockwork Plex kiosk Chromium profile | `~/.config/a-clockwork-plex/chromium-profile` | **Never copy profile wholesale** | If safe Plexamp UI preferences can be identified, export/restore only explicit allow-listed values |
| WU selected-period/full-station rainfall caches | `weather-rainfall-history.json`, `weather-rainfall-lifetime.json` | **Exclude** | Rebuild/backfill from the commissioned Weather source |
| Forecast cache | `weather-forecast-cache.json` | **Exclude** | Re-fetch from Open-Meteo |
| Dashboard/weather live state and pressure/extreme history | `state.json` | **Exclude** | Rebuild from live observations |
| Alarm runtime/audio runtime | `alarm-runtime.json`, `alarm-audio-runtime.json` | **Exclude** | Recreate from configuration and current time; never resurrect an old ringing/snoozed occurrence |
| Playback/handoff runtime | `playback-runtime.json` and application-state runtime | **Exclude** | Recreate from live Plexamp/AirPlay state |
| EQ route state, install markers, pre-EQ rollback backup and installer transactions | `/var/lib/a-clockwork-plex/...` | **Exclude** | Owned by installation/repair lifecycle only |
| Generated assets, logs and caches | project/runtime cache paths | **Exclude** | Regenerate |

## Portable A Clockwork Plex settings

The export should be built from the **normalised Settings model**, not by serialising `config.json` directly. The current public Settings authority already knows how to normalise and validate the appliance domains.

Portable candidates include:

- startup/idle screen and idle timeout;
- clock format, transition preferences, daytime theme and alarm-indicator policy;
- night dim schedule/levels, night clock style and burn-in shifting preference;
- Weather labels, units, clock-card selection/order, provider choice, Ecowitt freshness/path, WU station ID/timing, selected rainfall period and Open-Meteo forecast settings;
- alarm schedules, labels, recurrence, tones, volumes, fade, Snooze and Dismiss/ring policy;
- AirPlay receiver name, default starting volume and hold behaviour;
- safe user-facing audio preferences;
- safe Plexamp connection preferences only where they are genuinely portable.

Installer/hardware integration values should not silently migrate merely because they happen to appear in `config.json`. Examples include fixed ALSA hardware device names, installer-owned service paths and compatibility plumbing. A restore should use the target installation's commissioned hardware/runtime values unless a field has deliberately been classified as portable.

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

The guarded Plexamp installer already treats:

```text
~/.local/share/Plexamp/Settings
```

as persistent state outside the replaceable `~/plexamp` runtime. That directory is intentionally preserved across Plexamp runtime repairs/updates, but it is **not safe as a backup unit**.

Known categories in or associated with this store include harmless preferences, audio-device selection, current player state/queue, connection resources and player/account identity. Copying the whole directory to a replacement Pi could therefore clone identity or authentication alongside the desired settings.

The safe model is:

1. inventory the actual Plexamp 4.13.2 Settings filenames on the commissioned development Pi **without reading values**;
2. identify candidate `@Plexamp:settings:*` preference keys;
3. inspect only candidate values that are needed to classify a setting and are not credential/identity material;
4. establish an exact allow-list in source/tests;
5. export those values under an explicitly versioned `plexamp.headless_preferences` section;
6. restore them only when the target Plexamp version/setting semantics are supported.

Current queue/state, resources, tokens and identity remain excluded even if technically easy to copy.

### Browser-side Plexamp experience settings

The A Clockwork Plex kiosk uses its own Chromium profile:

```text
~/.config/a-clockwork-plex/chromium-profile
```

The same browser profile renders the dashboard and the Plexamp web UI. Plexamp experience/UI choices such as Home layout may therefore live in Chromium Local Storage/IndexedDB rather than Headless's server-side Settings store.

That profile also contains browser session and authentication data, so **the Chromium profile must never be archived/restored wholesale**.

Support for Plexamp Home/layout preferences is conditional on finding a stable, narrowly extractable set of non-auth storage keys. If that cannot be made robust and safe, the backup feature should explicitly say that those browser-side Plexamp preferences require manual reconfiguration rather than weakening the credential boundary.

## Audio preferences

### EQ

`MasterEqualizer` is the authority for persisted Bass/Mid/Treble and bypass state. The backup should carry only the logical model, for example:

```json
{
  "bypassed": false,
  "bands": {
    "bass": 1.0,
    "mid": 0.0,
    "treble": -0.5
  }
}
```

Restore calls the EQ authority after the audio backend has been installed and verified. It must not write `master-eq.json` directly.

### Mixer

Persistent mixer levels are currently stored by ALSA, but ALSA's state file is tied to a particular card/control graph. The backup therefore stores the four user-facing percentages instead:

```json
{
  "master": 80,
  "plexamp": 100,
  "airplay": 100,
  "alarm": 85
}
```

Restore invokes the existing restricted mixer helper after the target audio profile is ready. This makes the backup portable even if the underlying raw softvol percentages or device identity change.

## Proposed backup envelope

The first supported format should be JSON and explicitly versioned. A conceptual schema is:

```json
{
  "schema_version": 1,
  "created_at": "2026-08-23T20:00:00+01:00",
  "source": {
    "application": "A Clockwork Plex",
    "app_version": "0.4.0",
    "release_tag": "v0.4.0"
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
    "headless_preferences": {},
    "browser_preferences": {}
  }
}
```

The real implementation should derive release/version metadata from `app/static/app-version.json` rather than hard-coding it in the exporter.

Sections may be omitted when their owner/backend is unavailable. Export should report what was included and what was deliberately skipped.

## Restore contract

Restore is a separate operation from export and should be conservative:

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

## #88 audit status

Repository-side ownership classification is complete enough to define the backup envelope and hard exclusions. The remaining discovery gate before implementation is a **read-only inventory of the actual Plexamp Headless preference-key filenames on the commissioned Pi**, followed by a separate assessment of whether Home/layout browser preferences can be extracted safely from the dedicated Chromium profile.
