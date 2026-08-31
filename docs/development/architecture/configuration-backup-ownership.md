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
| Plexamp Headless persistent Settings store | `~/.local/share/Plexamp/Settings` | **Selective allow-list only; never copy directory wholesale** | Restore only the exact known typed non-auth preferences through the dedicated exact-version transactional owner; incompatible/unknown target state is deferred before mutation |
| A Clockwork Plex kiosk Chromium profile | `~/.config/a-clockwork-plex/chromium-profile` | **Never copy profile wholesale**; export only validated logical Plexamp Home state through the scoped live browser bridge | Restore only explicit logical Home choices through the live target-context browser owner after fresh Plexamp claim/library commissioning; never restore the Chromium profile |
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

The source customization key contains account/library context. The exported logical browser section deliberately discards that source context and retains only order/hidden choices. Phase 4 extends the same live bridge with the supported target-context restore authority rather than ever writing the source key literally:

- `planHome` discovers the live target's current Home customization context and catalogue from already allow-listed `:order` / `:hidden` records only;
- the saved logical order is mapped onto hubs that exist on the target, target-only hubs are preserved, and saved hubs absent from the target are counted/skipped rather than invented;
- plan is read-only and returns a target fingerprint binding confirmation to the current target context/raw state;
- `applyHome` requires explicit confirmation plus that exact fresh fingerprint and refuses a stale target before any Local Storage write;
- every changed target key is captured as exact raw Local Storage state before mutation; successful writes are tracked, the resulting logical layout is verified, and failures reverse-roll only writes that actually completed back to their exact raw state;
- `editing`, caches, resources, auth/session and unrelated state remain outside both the read and write boundary;
- this browser transaction never restarts Plexamp and does not depend on a copied Chromium profile, browser permissions or remote debugging.

The browser owner is intentionally a **separate transactional owner** from the Python/server/Headless restore chain. A Headless restore may restart Plexamp and therefore invalidate a frame-local browser rollback lease. The guided UI can preview both domains from one backup and offer one final confirmation, but that confirmation orchestrates **Home first → verify → server/Headless → verify** when both stages are selected. Each stage owns its own rollback; A Clockwork Plex does **not** claim one atomic transaction across Chromium Local Storage and a Plexamp service restart. If Home succeeds and a later server/Headless stage cannot complete, the result must report that partial outcome truthfully rather than invent a cross-owner rollback guarantee.

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

Release/version metadata is derived from `app/static/app-version.json`, not hard-coded into the exporter. Plexamp runtime compatibility identity comes from the ACP-owned `~/plexamp/.a-clockwork-plex-runtime` manifest written and verified by the guarded Plexamp runtime installer. Backup and restore do **not** infer compatibility from an optional Plexamp `package.json` packaging detail.

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

The #90 preview endpoint implements steps 1–3 without mutation. `POST /api/settings/restore/preview` accepts schema-v1 JSON in memory, rejects forbidden credential/machine-owned fields case-insensitively, validates bounded portable structures and compares the candidate to a fresh normalised current backup. EQ values are additionally constrained to the production `-6…+6 dB` / `0.5 dB` contract. Its response contains changed paths/counts rather than old/new values and permanently returns `read_only: true` and `apply_enabled: false`. Separate `restore_available`, `server_restore_available` and `plexamp_headless_restore_available` fields describe work available to the distinct confirmed restore endpoint; they never change the read-only meaning of Preview.

The commissioned Pi physically accepted this preview stage on 24 August 2026 using the just-created schema-v1 backup: **0 server-owned differences**, `read_only: true`, `apply_enabled: false`, browser schema `1`, **15 ordered** Home items and **1 hidden** item. The only warning was the expected notice that Plexamp Home comparison/application remained a future live-browser stage at that checkpoint. The 1280×720 Settings presentation was also physically checked.

The #90 transactional apply endpoint first reached physical acceptance for server-owned ACP state in Phase 2:

- `POST /api/settings/restore/apply` is a separate endpoint from Preview and requires an explicit `confirm_restore: true` request;
- a 32-hex preview fingerprint binds Apply to the exact normalized backup plus current comparison/capability state; if the appliance, selected backup or participating restore capability changes after Preview, Apply returns a conflict and requires a fresh preview before any owner is touched;
- required confirmations such as an AirPlay receiver restart are carried forward from the preview contract;
- preflight refuses the whole operation before mutation if a required owner is unavailable;
- rollback state is captured from the same normalised authorities before the first owner changes;
- server application order is **Unified Settings → Master EQ → persistent four-channel mixer**;
- verification re-runs the normalised comparison and requires all supported apply paths to match the requested backup;
- any required-stage failure rolls touched owners back in reverse order and reports rollback failures explicitly;
- Settings refuses the UI restore path while ordinary staged Settings changes are unsaved;
- automated fake-backed regression coverage injects late failures and verifies that previously touched owners return to their original logical state.

The normal Phase-2 successful path is physically accepted on the commissioned Pi. One harmless ordinary Settings value, one `0.5 dB` EQ value and one small persistent mixer value were deliberately changed after taking a baseline backup. Preview reported exactly three supported server-owned differences; the explicit two-stage restore returned all three values to the backed-up state; selecting the same backup again then reported **0** restorable server-owned items.

The stale-preview path is also physically accepted. After a Preview reported one Settings difference, a further `0.5 dB` Bass change was saved before Apply. The old preview was refused before mutation, both changed values remained changed, and a fresh Preview then reported both differences. This physically confirms the preview fingerprint is an optimistic-concurrency safety boundary rather than merely a UI hint.

The original owner-specific controls established the safe mutation boundaries but exposed too much implementation detail once Home restore joined the system. The current guided UI keeps the same safety contracts while presenting one owner-facing sequence: **Preview → choose A Clockwork Plex / Plexamp / both → Review selected restore → Confirm & restore**. Preview and Review are read-only. Review regenerates fresh plans for only the selected owners and exposes the sole mutating confirmation only when the selected work is still current. The A Clockwork Plex target covers Settings/alarms/EQ/mixer; the Plexamp target covers compatible Headless preferences plus Home order/hidden choices. The selective server candidate deliberately omits unselected domains so a visual choice cannot silently become an empty-value overwrite.

When both targets are selected, one confirmation may invoke two protected stages underneath. Browser Home is applied and verified first because a later Headless restart can invalidate a frame-local Home rollback lease; the server/Headless transaction then runs using its own fresh preview fingerprint and rollback state. This is guided orchestration, **not a claim of cross-owner atomicity**. Completion, conflict and failure feedback is kept next to the action path, and a server-involved successful restore persists the final status across the Settings reload so the result is not lost off-screen.

Plexamp Home therefore remains outside the Python transaction even though the user can select it as part of one guided restore operation. Its target fingerprint and exact raw Local Storage rollback snapshot remain browser-owned.

### Plexamp Headless restore boundary — PHYSICALLY ACCEPTED

Phase 3 extends the same confirmed restore transaction with a dedicated Plexamp-owned stage; it does **not** turn the Plexamp Settings directory into a generic file-copy unit:

- only the eight previously classified typed preferences are eligible;
- `app/plexamp_preferences.py` calls the installed restricted owner through `sudo -n`; preference values are supplied as bounded JSON on **stdin**, never argv;
- `/usr/local/bin/a-clockwork-plex-plexamp-preferences` is the narrow root-side owner. Its sudo policy exposes only `status` and `apply`, not unrestricted `systemctl` or filesystem access;
- backup/export and the privileged restore owner derive Plexamp runtime compatibility from the same ACP-owned `~/plexamp/.a-clockwork-plex-runtime` manifest. The backup Plexamp version, the current backup runtime version and the helper-reported installed runtime version must be an exact known match before a Headless path becomes restorable; there is no `package.json` compatibility fallback;
- the current target must expose all eight valid typed files and an active `plexamp.service`; missing/malformed target state fails closed rather than creating unknown preference files;
- `audioDeviceUuid`, `playerName`, `premium`, auth/session/resource state and every unknown Settings file remain untouched;
- `sampleRateConversionQuality` and `sampleRateMatching` are additionally appliance-audio-generation aware: when the backup application generation differs, those paths remain deferred even when ordinary exact-version Headless preferences can be restored;
- each changed key is snapshotted with exact bytes, mode, ownership and timestamps; replacement is atomic/fsync-backed and typed values are verified both before and after service restart;
- the helper quiesces only `plexamp.service`, restores its original active state, waits for systemd activity plus loopback port `32500`, and on a late failure restores the original preference snapshots before returning an explicit rollback result;
- the outer restore transaction applies **Unified Settings → Master EQ → persistent mixer → Plexamp Headless** and rolls earlier ACP owners back if the Headless stage fails;
- the Preview fingerprint includes Headless capability/version context, so an installed-version or readiness change between Preview and Apply invalidates the preview before mutation;
- Settings reports Headless availability as part of the Plexamp restore target without displaying old/new preference values;
- Plexamp Home remains a separate live-browser owner and does not use the Headless service-restart transaction.

The first commissioned-Pi Phase-3 status probe on 30 August 2026 was intentionally read-only and caught an ownership mismatch before any Plexamp preference mutation. It proved all **8/8** allow-listed preference files valid, the Settings directory present and `plexamp.service` active, while reporting `installed_version: null` / `restore_ready: false`. A second read-only inspection proved why: the commissioned runtime has no `~/plexamp/package.json`; its verified identity is the installer-owned `~/plexamp/.a-clockwork-plex-runtime` manifest with `kind=plexamp`, `version=4.13.2` and the pinned archive SHA-256. The helper correctly failed closed rather than guessing.

The compatibility authority was corrected in `0240473a6f9f7c4ef45b0acfbc07f109c4fd4e37` (backup), `a85c68e4d8818382d044110a9cf704821201af56` (restore owner), `ebbbecdf0b831d21c1fb76eea2075a61775aee1d` (commissioned-layout regressions) and `84f3e256979dc429c4dbf3622f2bae98e197d116` (remaining backup fixture). Fake/alternate-root coverage still proves exact-version round-trip, incompatible-version deferral, audio-generation deferral for sample-rate preferences, stale capability refusal and a deliberately injected **late Plexamp restart failure** that restores the original preference bytes/service state. It also proves the outer transaction rolls previously changed ACP owners back when the Headless owner fails. The corrected synchronized source/compile/JavaScript/unit gate was green at **develop Tests #4343: 978 tests, `OK`** on 30 August 2026.

The first attempt to reload the corrected dashboard source on the commissioned Pi then exposed a separate runtime-startup regression before the mismatch Preview could run. The systemd service launches `app/runner.py` directly, while the newly introduced `app/plexamp_preferences.py` initially imported `configuration_backup` only as a package-relative module. That combination compiled successfully but crashed in production direct-run import mode, leaving the dashboard in a restart loop and causing the kiosk launcher to time out. No restore Preview or Apply had run at that point and Plexamp remained healthy. Commit `6c0f826288492ea44c473e03302a4c190fb31d46` added the direct-run import fallback; `0ff222958659a63e041f6d4675ad7fb22dd38f27` added a `PYTHONPATH=app` direct-import smoke gate to CI. **Tests #4347 passed all 978 tests with `OK`**. Physical recovery then proved the production-style import check, `a-clockwork-plex.service`, `/api/state` and a rebooted kiosk all healthy again.

Commissioned-Pi Phase-3 acceptance completed on 31 August 2026:

- corrected restricted-helper status returned **8/8** allow-listed preferences, `installed_version: 4.13.2`, `restore_ready: true` and active `plexamp.service`;
- a deliberately incompatible copied backup (`4.13.3`) with only `autoPlayEnabled` flipped produced **1 detected / 0 restorable / 1 deferred** Headless difference, `restore_available: false`, and before/after backups proved ACP configuration, Headless preferences and runtime identity were unchanged;
- an exact-version `4.13.2` round-trip flipped only `autoPlayEnabled` from its original `false` to `true`, applied and verified exactly one Plexamp Headless path, then Previewed and restored the original `false` value with a second verified one-path apply;
- the final Preview of the original baseline returned **0 differences / 0 restorable changes**;
- `a-clockwork-plex.service` and `plexamp.service` remained active, the restricted owner remained `restore_ready: true`, the repository remained clean, and the owner physically confirmed Plexamp still opened and played normally after both controlled restarts.

The destructive late-restart rollback path remains intentionally covered by controlled automated fault injection rather than being forced on the commissioned appliance. Phase 3 is therefore **physically accepted**.

### Plexamp Home restore boundary — PHYSICALLY ACCEPTED; GUIDED RESTORE UX FOLLOW-UP IN ACCEPTANCE

Phase 4 adds the separately transactional browser-owned Home restore path without widening the #89 export/read boundary:

- the existing permission-free localhost-only content bridge exposes validated `planHome` and `applyHome` requests in addition to export;
- planning discovers the live target customization context, maps saved logical Home choices to the target catalogue, preserves target-only hubs and safely skips saved hubs that do not exist on the target;
- plan is read-only and returns counts plus a target fingerprint rather than exposing contextual key names or arbitrary browser values to Settings;
- Apply is available only after explicit confirmation and refuses a stale fingerprint before the first write;
- the bridge snapshots exact raw state for each changed target-context `order` / `hidden` key, performs only those allow-listed writes, verifies the effective logical layout and reverse-rolls successful writes to exact raw state on failure;
- rollback bookkeeping tracks a mutation only after its write completes successfully, so an exception on a write is not falsely treated as a completed mutation;
- auth/session/resource/cache/editor state and unrelated Local Storage remain outside both the read and write boundaries; no extension permissions, background worker, remote-debugging path or server-side browser-state staging was added;
- Node/browser contract tests cover target-aware mapping, target-only preservation, missing-source-hub skipping, successful write/verification, stale-target refusal before mutation, injected mid-transaction failure with exact raw rollback and strict parent-side response validation;
- source/wiring CI gates continue to pin the browser client, target fingerprint and completed-write rollback invariant.

The exact Phase-4 owner implementation head `f010ae1b8700301bd4898e733ecdafd10bcfd480` passed synchronized **develop Tests #4359: 983 tests, `OK`** on 31 August 2026.

The commissioned-Pi Home owner then passed harmless physical round-trips. A test with both an order change and a hidden-item change Previewed as **2 Plexamp Home changes**, restored the backed-up Home state, and converged to zero remaining Home differences. A later order-only test Previewed as **1 Home change**, restored successfully, visibly returned Plexamp Home to the backed-up ordering and again converged to zero. The owner confirmed Plexamp could still be opened and played normally afterwards. These results close the Home transaction's physical acceptance gate.

That same physical pass identified a **workflow UX issue, not a transaction failure**: the separate Home Review/Confirm controls looked like a second restore product beside the server restore, Review status was visually detached from the action, and final success feedback could appear far away from the button that caused it.

Commit `b0065a70ebc9e0a54d180869f15c87eb4627a169` therefore keeps the proven owners but replaces the implementation-shaped presentation with a guided target model:

- Preview reports the current safe differences and automatically selects each target that has restorable work;
- **A Clockwork Plex** selects Settings/alarms/EQ/mixer server-owned paths;
- **Plexamp** selects compatible Headless paths plus browser-owned Home paths;
- the owner may choose ACP only, Plexamp only or both before mutation;
- changing selection invalidates any previous Review;
- **Review selected restore** is read-only and obtains fresh selected-owner plans immediately before confirmation;
- **Confirm & restore** is the one user-facing mutating action;
- where both Home and server/Headless work exist, Home executes and verifies first, then server/Headless executes with its own transaction and verification;
- nearby status boxes own Preview, Review and final success/blocked/failure feedback; the successful server path persists the result across the Settings reload;
- the UI explicitly avoids promising global atomic rollback across browser Local Storage and a Plexamp service restart.

The guided-flow source, syntax and regression gates passed exact **develop Tests #4363** on `b0065a70ebc9e0a54d180869f15c87eb4627a169`: **985 tests, `OK`** on 31 August 2026. The remaining Phase-4 work is therefore a **1280×720 guided UX physical acceptance**, ideally with one harmless ACP + Plexamp Home difference restored together. The purpose of that pass is to verify clarity, target selection, adjacent Review/final status and the one-confirm orchestration; it is no longer proving that the Home transaction itself works.

Managed secrets remain a deliberate **post-restore commissioning step** throughout every phase.

## Reset-to-defaults relationship

The future reset workflow should use the same ownership classification rather than deleting files indiscriminately. It should be possible to reset ordinary user settings while leaving installer-owned hardware/audio topology and credentials alone unless the owner explicitly chooses a deeper decommissioning action.

## #88 audit status — COMPLETE

Checkpoint #88 is complete. Repository ownership classification, live Plexamp Headless inventory and browser-side Home-layout discovery have all established a narrow non-authentication backup boundary. No raw Plexamp profile, Chromium profile or LevelDB file is a supported backup unit.

The commissioned Pi physically proved the Headless allow-list and browser key families through staged read-only audits and before/after Home reorder/hide experiments. This closes discovery and moves the active Settings/appliance-ownership work to #89.

## #89 backup/export status — COMPLETE

The complete schema-v1 export path is physically accepted on the commissioned Pi and covered by synchronized green `develop` Actions:

- `app/configuration_backup.py` builds schema-version-1 JSON from the existing normalised Settings authority;
- portable field selection excludes installer/hardware values instead of serialising the whole public Settings snapshot;
- Weather observation export omits both the WU secret and target-owned `api_key_env` implementation detail;
- the exact eight typed Plexamp Headless preferences are read through a strict allow-list;
- Plexamp source-version metadata comes from the guarded installer's verified `.a-clockwork-plex-runtime` identity rather than optional runtime package metadata;
- EQ is exported as logical state and available shared-mixer levels as four percentages;
- `GET /api/settings/backup` is read-only, `Cache-Control: no-store`, and returns an attachment filename in the appliance/source timezone;
- Settings exposes **Advanced → Backup & restore → Download backup** without making backup part of the staged Save Changes transaction;
- the first physical download contained schema `1`, the expected five ACP settings domains, EQ + mixer, all eight approved Headless preferences, zero warnings and no forbidden credential/machine-state key paths;
- the scoped live Plexamp bridge physically added browser schema `1`, 15 Home-order identifiers and 1 hidden identifier; the browser omission was removed and warning count remained zero;
- the owner-facing success message explicitly states that Plexamp Home layout was included and credentials/authentication were not;
- synchronized `develop` validation remains green through **Tests #4347: 978 tests, `OK`** on 30 August 2026.

## #90 configuration restore status — IN PROGRESS

### Phase 1 — parse / validate / preview — PHYSICALLY ACCEPTED

- [x] Schema-v1 backup is parsed and bounded before comparison.
- [x] Credential, identity and target-machine fields are rejected without echoing values.
- [x] Preview remains read-only and exposes changed paths/counts rather than old/new values.
- [x] Plexamp Home data is validated and summarized without browser mutation.
- [x] Commissioned-Pi preview of the fresh backup returned **0** server-owned changes, `read_only: true`, `apply_enabled: false`, **15 ordered / 1 hidden**, and only the expected deferred-browser warning.
- [x] The 1280×720 Restore preview presentation was physically accepted.

### Phase 2 — transactional server-owned apply — PHYSICALLY ACCEPTED

- [x] Separate confirmed `POST /api/settings/restore/apply` endpoint implemented.
- [x] Fresh-preview fingerprint/stale-state refusal implemented and physically accepted without mutation.
- [x] Unified Settings, Master EQ and persistent mixer are applied through their existing owners only.
- [x] Reverse-order rollback and post-apply verification implemented.
- [x] EQ step/range and case-insensitive forbidden-key validation tightened before mutation was enabled.
- [x] Regression coverage includes success, stale-preview refusal and injected late-mixer-failure rollback.
- [x] CI source/syntax gates cover the separate apply endpoint and confirmation UI.
- [x] Physical harmless-change restore returned one Settings value, one `0.5 dB` EQ value and one small persistent mixer value to their backed-up state; a second preview of the same backup returned **0** supported server-owned differences.
- [x] Physical stale-preview refusal retained both post-preview changes and a subsequent fresh Preview correctly found both differences.
- [x] Scoped spacing/alignment polish was physically re-checked at 1280×720; the Preview/results and confirmation blocks are now clearly separated.
- [x] Tests #4311/#4312 passed the clearer blocked-warning/control-label logic and warning CSS.
- [x] The owning restore client now preserves the full stale-preview backend reason instead of overwriting it with a generic retry line; Tests #4320/#4321 passed the source/cache/syntax gates.
- [x] Final physical re-check accepted the **Review restore → Confirm & restore** labels and the conspicuous full blocked-restore warning.

### Phase 3 — version-aware Plexamp Headless apply — PHYSICALLY ACCEPTED

- [x] Dedicated exact-allow-list typed preference owner implemented with per-key snapshot, atomic write, typed verification and exact rollback state.
- [x] Commissioned-target readiness and exact Plexamp-version compatibility are preflight requirements before a Headless path becomes restorable.
- [x] Backup/export and restore use the guarded installer's ACP-owned `~/plexamp/.a-clockwork-plex-runtime` manifest as the shared version authority; optional Plexamp `package.json` metadata is not part of the compatibility contract.
- [x] Narrow runtime coordination is implemented: only `plexamp.service` can be quiesced/restarted by the restricted owner; the dashboard receives no broad service-control sudo authority.
- [x] The two sample-rate preferences are additionally appliance-audio-generation aware and remain deferred across a generation mismatch.
- [x] Preview/Settings reports ACP/server and Plexamp-owned work without exposing values.
- [x] Automated coverage proves exact-version success, incompatible-version deferral, audio-generation deferral, stale-capability refusal, injected late-restart rollback and outer-transaction rollback.
- [x] Initial commissioned-Pi read-only status physically proved all **8/8** allow-listed preferences and active `plexamp.service` but correctly failed closed with `installed_version: null`; read-only inspection then proved the installed 4.13.2 identity lives only in `.a-clockwork-plex-runtime`. No preference was mutated during discovery.
- [x] The shared runtime-authority correction and commissioned-layout regressions passed **Tests #4343: 978 tests, `OK` on 30 August 2026**.
- [x] Production reload exposed the direct-run import regression before restore mutation; `6c0f826288492ea44c473e03302a4c190fb31d46` fixed the import mode and `0ff222958659a63e041f6d4675ad7fb22dd38f27` added the matching CI smoke gate. **Tests #4347 passed 978 tests with `OK`**, and the commissioned dashboard/API/kiosk physically recovered.
- [x] Corrected owner readiness physically passed with `installed_version: 4.13.2`, `restore_ready: true`, all 8/8 preferences and active Plexamp.
- [x] Incompatible-version Preview physically passed with exactly one detected Headless difference deferred, zero restorable work and before/after proof of zero mutation.
- [x] Exact-version `autoPlayEnabled` round-trip physically passed: one verified apply to the temporary value, one verified apply back to the original value, final zero-difference Preview, healthy services and normal Plexamp playback.

### Phase 4 — target-context-aware Plexamp Home order/hidden apply — PHYSICALLY ACCEPTED; GUIDED RESTORE UX FOLLOW-UP IN ACCEPTANCE

- [x] Live localhost-only browser owner implements read-only Home planning and confirmed Home application against the target's current Plexamp customization context.
- [x] Saved logical Home choices are mapped to target hubs without transplanting source contextual keys; target-only hubs are preserved and unavailable source hubs are skipped/reported.
- [x] Home plan is read-only and target-fingerprinted; stale target state is refused before any write.
- [x] Home Apply snapshots exact raw target state, writes only allow-listed target-context `order` / `hidden` records, verifies the logical result and reverse-rolls completed writes exactly on failure.
- [x] Auth/session/resource/cache/editor and unrelated browser state remain outside the read/write boundary; extension permissions and kiosk debugging authority remain unchanged.
- [x] Automated target mapping, stale-preview, successful-apply, exact-rollback and client-validation coverage is in the synchronized suite.
- [x] **Tests #4359** passed on `f010ae1b8700301bd4898e733ecdafd10bcfd480`: **983 tests, `OK`** on 31 August 2026.
- [x] Commissioned-Pi Home round-trip acceptance passed with both two-change (order + hidden) and order-only cases; the backed-up Home layout returned, follow-up Preview converged to zero Home differences, and normal Plexamp browsing/playback remained available.
- [x] Guided target-selection/single-confirmation follow-up implemented in `b0065a70ebc9e0a54d180869f15c87eb4627a169` without changing the proven backend/browser owner boundaries.
- [x] **Tests #4363** passed the guided-flow source/syntax/regression gate: **985 tests, `OK`** on 31 August 2026.
- [ ] Remaining physical gate: at 1280×720 prove ACP/Plexamp/Both target selection, adjacent Review status, one Confirm orchestration and final status visibility using one harmless combined ACP + Plexamp Home restore, then confirm normal Plexamp identity/playback.

Final #90 closure remains gated on synchronized docs-inclusive CI plus that guided UX physical acceptance.
