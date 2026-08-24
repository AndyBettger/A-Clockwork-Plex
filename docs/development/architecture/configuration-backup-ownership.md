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
| A Clockwork Plex kiosk Chromium profile | `~/.config/a-clockwork-plex/chromium-profile` | **Never copy profile wholesale**; export only validated logical Plexamp Home state through the scoped live browser bridge | Restore only explicit logical Home choices after fresh Plexamp claim/library commissioning; never restore the Chromium profile |
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
- `@Plexamp:settings:radioIncludeExternal` — ordinary browser preference candidate, not currently in the Home-layout bridge allow-list;
- `mmkv.default\...:cachedItems` — generated cache content, exclude;
- `mmkv.default\discovery:customizations:<context>::/library/sections/<id>:order` — physically proven Home-item ordering authority;
- `mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden` — physically proven per-item hidden/shown customization state;
- matching `...:<hub-id>:editing` records — transient customiser/editor state, exclude.

A physical differential test moved one Home item and only the contextual `:order` record acquired new state. A separate real hide action created the complete per-hub `:hidden` key and transient `:editing` records for the affected Home hub.

The raw Chromium LevelDB files are **discovery evidence only, not the production backup authority**. Chromium compacted the database between snapshots, changing which historical records were visible. Production Home-layout export therefore executes against the live Plexamp browser origin and never scrapes/copies the LevelDB files.

The #89 live bridge is deliberately narrow:

- `browser/plexamp-bridge/` is an unpacked Manifest V3 content extension loaded only by the dedicated kiosk launcher;
- the manifest requests no Chrome permissions, has no background/service worker and matches only Plexamp loopback origins on port `32500`;
- the kiosk does **not** expose a remote-debugging port;
- inside Plexamp, the bridge reads only the live Local Storage key families already physically classified as Home `order` / per-hub `hidden` state;
- `editing`, caches, resources, auth/session state and unrelated browser preferences are not emitted and their values are not opened;
- the bridge responds only to the A Clockwork Plex dashboard parent origins on port `8088` and uses a request nonce;
- the dashboard parent validates origin, frame source, schema, status, item counts and conservative hub-ID syntax before accepting the snapshot;
- physical discovery narrowed accepted Home identifiers to **`[A-Za-z0-9_./-]`** with a 220-character bound; `/` was the only additional character observed beyond the original conservative set, while `:` remains rejected;
- the accepted browser snapshot is merged into the already secret-free server backup **in browser memory**; it is not POSTed to the dashboard service or written to a temporary server-side file;
- if the extension is unavailable or an observed Plexamp value uses an unsupported format, export fails closed for this optional section and records an omission/warning instead of broadening the read boundary.

The final commissioned-Pi #89 export physically returned browser schema `1`, **15 ordered Home identifiers**, **1 hidden identifier**, no browser omission and **zero warnings**. This establishes the live browser bridge as the supported export authority for Home order/hidden state.

The source customization key contains account/library context. The exported logical browser section deliberately discards that source context and retains only order/hidden choices. Restore must not write a source key literally to a replacement appliance. After Plexamp has been freshly claimed and the target library selected, the future restore path must discover the target's live customization context and translate the saved logical ordering/hidden choices into it.

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
  "created_at": "2026-08-24T00:35:02+01:00",
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
    "headless_preferences": {},
    "browser_preferences": {
      "schema_version": 1,
      "home": {
        "order": [],
        "hidden": []
      }
    }
  },
  "export_report": {
    "warnings": [],
    "omitted": []
  }
}
```

`plexamp.browser_preferences` is optional. It is present only when the live browser bridge returns a validated `ready`/`empty` snapshot; otherwise the export report keeps the browser section explicitly omitted and may include a safe bridge-status warning.

Release/version metadata is derived from `app/static/app-version.json`, not hard-coded into the exporter. Plexamp runtime version is read from non-sensitive local runtime package metadata when available.

Sections may be omitted when their owner/backend is unavailable. Export reports what was deliberately skipped.

## Restore contract

Restore is a separate operation from export and remains conservative:

1. parse and validate the schema without changing anything;
2. reject malformed/unsupported required data and bound all values;
3. present a summary/preview, including unavailable optional sections and confirmation requirements;
4. establish that the target appliance/runtime/audio owners are installed and healthy;
5. capture rollback state for every owner that will change;
6. apply ordinary ACP configuration through its Settings authorities;
7. apply guarded specialist state (AirPlay receiver name, EQ, mixer) through those specialist owners;
8. apply supported Plexamp allow-listed preferences only after Plexamp is installed/claimed and version compatibility is known;
9. verify the resulting Settings/specialist snapshots;
10. roll back changed owners if a required restore stage fails.

The #90 preview endpoint implements steps 1–3 without mutation. `POST /api/settings/restore/preview` accepts schema-v1 JSON in memory, rejects forbidden credential/machine-owned fields case-insensitively, validates bounded portable structures and compares the candidate to a fresh normalised current backup. EQ values are additionally constrained to the production `-6…+6 dB` / `0.5 dB` contract. Its response contains changed paths/counts rather than old/new values and permanently returns `read_only: true` and `apply_enabled: false`. A separate `server_restore_available` flag says whether the distinct confirmed server-restore endpoint has supported work to do; it never changes the read-only meaning of Preview.

The commissioned Pi physically accepted this preview stage on 24 August 2026 using the just-created schema-v1 backup: **0 server-owned differences**, `read_only: true`, `apply_enabled: false`, browser schema `1`, **15 ordered** Home items and **1 hidden** item. The only warning was the expected notice that Plexamp Home comparison/application remains a live-browser stage. The 1280×720 Settings presentation was also physically checked.

The #90 server-owned phase implements steps 4–7, 9 and 10 for **server-owned ACP state only**:

- `POST /api/settings/restore/apply` is a separate endpoint from Preview and requires an explicit `confirm_restore: true` request;
- a 32-hex preview fingerprint binds Apply to the exact normalized backup plus current server-owned comparison state; if the appliance or selected backup changes after Preview, Apply returns a conflict and requires a fresh preview before any owner is touched;
- required confirmations such as an AirPlay receiver restart are carried forward from the preview contract;
- preflight refuses the whole operation before mutation if a required EQ or persistent-mixer authority is unavailable;
- rollback state is captured from the same normalised Settings/EQ/mixer authorities before the first owner changes;
- application order is **Unified Settings → Master EQ → persistent four-channel mixer**;
- verification re-runs the normalised comparison and requires all supported server-owned paths to match the requested backup;
- any required-stage failure rolls touched owners back in reverse order and reports rollback failures explicitly;
- Settings refuses the UI restore path while ordinary staged Settings changes are unsaved;
- automated fake-backed regression coverage injects a late mixer failure after Settings and EQ have changed and verifies that mixer, EQ and Settings all return to their original logical state.

The normal successful path is physically accepted on the commissioned Pi. One harmless ordinary Settings value, one `0.5 dB` EQ value and one small persistent mixer value were deliberately changed after taking a baseline backup. Preview reported exactly three supported server-owned differences; **Restore server settings → Confirm restore** returned all three values to the backed-up state; selecting the same backup again then reported **0** restorable server-owned items. The remaining live safety check for this phase is stale-preview refusal, while injected failure/rollback remains covered automatically rather than by intentionally breaking the appliance.

This server-owned phase does **not** write Plexamp Headless preference files or Plexamp Home Local Storage. Headless preferences remain deferred to a later version-aware Plexamp-owner stage; Home order/hidden remains deferred until a target live browser context can be discovered and rolled back safely. Managed secrets likewise remain a deliberate **post-restore commissioning step**.

## Reset-to-defaults relationship

The future reset workflow should use the same ownership classification rather than deleting files indiscriminately. It should be possible to reset ordinary user settings while leaving installer-owned hardware/audio topology and credentials alone unless the owner explicitly chooses a deeper decommissioning action.

## #88 audit status — COMPLETE

Checkpoint #88 is complete. Repository ownership classification, live Plexamp Headless inventory and browser-side Home-layout discovery have all established a narrow non-authentication backup boundary. No raw Plexamp profile, Chromium profile or LevelDB file is a supported backup unit.

The commissioned Pi physically proved the Headless allow-list and browser key families through staged read-only audits and before/after Home reorder/hide experiments. This closes discovery and moves the active Settings/appliance-ownership work to #89.

## #89 backup/export status — PHYSICALLY ACCEPTED

The complete schema-v1 export path is physically accepted on the commissioned Pi:

- `app/configuration_backup.py` builds schema-version-1 JSON from the existing normalised Settings authority;
- portable field selection excludes installer/hardware values instead of serialising the whole public Settings snapshot;
- Weather observation export omits both the WU secret and target-owned `api_key_env` implementation detail;
- the exact eight typed Plexamp Headless preferences are read through a strict allow-list;
- EQ is exported as logical state and available shared-mixer levels as four percentages;
- `GET /api/settings/backup` is read-only, `Cache-Control: no-store`, and returns an attachment filename in the appliance/source timezone;
- Settings exposes **Advanced → Backup & restore → Download backup** without making backup part of the staged Save Changes transaction;
- the first physical download contained schema `1`, the expected five ACP settings domains, EQ + mixer, all eight approved Headless preferences, zero warnings and no forbidden credential/machine-state key paths;
- the scoped live Plexamp bridge physically added browser schema `1`, 15 Home-order identifiers and 1 hidden identifier; the browser omission was removed and warning count remained zero;
- the owner-facing success message explicitly states that Plexamp Home layout was included and credentials/authentication were not;
- the remaining #89 administrative gate is a synchronized green GitHub Actions run on the accepted implementation/documentation head.

## #90 configuration restore status — IN PROGRESS

### Phase 1 — parse / validate / preview — PHYSICALLY ACCEPTED

- [x] Schema-v1 backup is parsed and bounded before comparison.
- [x] Credential, identity and target-machine fields are rejected without echoing values.
- [x] Preview remains read-only and exposes changed paths/counts rather than old/new values.
- [x] Plexamp Home data is validated and summarized without browser mutation.
- [x] Commissioned-Pi preview of the fresh backup returned **0** server-owned changes, `read_only: true`, `apply_enabled: false`, **15 ordered / 1 hidden**, and only the expected deferred-browser warning.
- [x] The 1280×720 Restore preview presentation was physically accepted.

### Phase 2 — transactional server-owned apply — PHYSICALLY ACCEPTED; STALE-PREVIEW CHECK PENDING

- [x] Separate confirmed `POST /api/settings/restore/apply` endpoint implemented.
- [x] Fresh-preview fingerprint/stale-state refusal implemented.
- [x] Unified Settings, Master EQ and persistent mixer are applied through their existing owners only.
- [x] Reverse-order rollback and post-apply verification implemented.
- [x] EQ step/range and case-insensitive forbidden-key validation tightened before mutation was enabled.
- [x] Regression coverage includes success, stale-preview refusal and injected late-mixer-failure rollback.
- [x] CI source/syntax gates cover the separate apply endpoint and confirmation UI.
- [x] Physical harmless-change restore returned one Settings value, one `0.5 dB` EQ value and one small persistent mixer value to their backed-up state; a second preview of the same backup returned **0** supported server-owned differences.
- [x] Physical review confirmed the two-step restore interaction at 1280×720 and identified only cosmetic spacing/alignment follow-up, now isolated in scoped backup/restore CSS.
- [ ] Final synchronized Actions result for the current phase-2/polish head must be green.
- [ ] Physical visual re-check of the scoped spacing/alignment follow-up.
- [ ] Physical stale-preview refusal: change/save one supported value after Preview and prove Apply refuses the stale fingerprint without restoring anything.

Plexamp Headless and live-browser Home application remain later #90 phases, not part of phase 2.
