# Configuration backup and restore ownership

## Purpose

A Clockwork Plex needs a supported way to move the useful personality of a commissioned appliance onto a rebuilt or replacement installation without cloning credentials, hardware identity, volatile runtime state or stale machine-specific files.

The governing rule remains:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

A backup is not a disk image or forensic copy of the Pi. A separate same-appliance Reset owner may legitimately own **nonportable commissioning state** without making that state portable.

## Ownership matrix

| State | Current owner/location | Ordinary backup policy | Restore / Reset relationship |
| --- | --- | --- | --- |
| A Clockwork Plex user settings | `config.json` through `UnifiedSettingsService` and specialist Settings owners | **Include as normalised portable settings**, never raw bytes | Restore through validated owners; #93 Reset derives ACP defaults from `config.example.json` through the same normalisers |
| Alarm schedules and user alarm choices | alarm configuration authority | **Include** | Restore normally; #93 Reset restores ordinary alarm choices but preserves alarm-audio arming switches |
| Display/theme/night/clock/startup choices | Unified Settings | **Include** | Restore through Settings; #93 Reset owns supported defaults |
| Weather non-secret choices | Weather Settings authorities | **Include** | Restore through Weather Settings; credentials remain separate commissioning |
| Weather Underground API key | `/etc/default/a-clockwork-plex-weather` | **Never include** | Recommission explicitly; #93 Reset preserves it |
| AirPlay receiver and user preferences | configuration + `ShairportNameManager` | **Include logical values** | Restore through guarded owners; #93 Reset owns supported user defaults |
| Master EQ | restricted EQ owner | **Include logical enabled/band state** | Restore through `MasterEqualizer`; #93 Reset owns neutral/default logical state |
| Persistent mixer levels | ALSA control state through restricted mixer helper | **Include four logical percentages** | Restore through mixer helper; #93 Reset uses physically observable mixer defaults |
| Audio routes/CamillaDSP/systemd/sudoers/hardware | guarded installer/audio lifecycle | **Exclude** | Recreate from release/hardware commissioning; #93 Reset preserves topology |
| Plexamp Headless runtime | guarded Plexamp runtime owner | **Exclude** | Reinstall through runtime owner; #93 Reset does not replace runtime |
| Plexamp Headless persistent Settings | `~/.local/share/Plexamp/Settings` | **Selective eight-value allow-list only** | Exact-version transactional restore; #93 native Reset preserves/re-applies those same eight values |
| Plexamp appliance-local commissioning baseline | `~/.local/share/a-clockwork-plex/plexamp-commissioning.json` + live loopback output catalogue | **Exclude** | #93 same-appliance commissioning Reset owns `playerName` + managed output only |
| Plexamp Home logical choices | live kiosk browser origin | **Include validated logical order/hidden choices**, never Chromium profile | #90 restores backed-up logical layout; #93 separately resets bounded Home order/visibility to Plexamp defaults |
| Chromium profile wholesale | `~/.config/a-clockwork-plex/chromium-profile` | **Never include** | Never restore/copy wholesale; #93 touches only classified Home records |
| Weather/News caches and rainfall history | runtime cache files | **Exclude** | Rebuild/refetch; #93 preserves runtime/history state |
| Alarm/playback runtime | runtime state files | **Exclude** | Recreate from live state/current time |
| EQ route/install rollback state | `/var/lib/a-clockwork-plex/...` | **Exclude** | Installer/repair lifecycle only |

## Portable A Clockwork Plex settings

The export is built from the **normalised Settings model**, not by serialising `config.json` directly.

Portable settings include:

- startup/idle screen and idle timeout;
- clock format, transition preferences, daytime theme and alarm-indicator policy;
- night dim schedule/levels, night clock style and burn-in shifting preference;
- Weather labels, units, clock-card selection/order, provider choice, Ecowitt freshness/path, WU station ID/timing, selected rainfall period and Open-Meteo forecast settings;
- alarm schedules, labels, recurrence, tones, volumes, fade, Snooze and Dismiss/ring policy;
- AirPlay receiver name, default starting volume and hold behaviour;
- safe user-facing audio preferences.

Installer/hardware integration values do not migrate merely because they happen to appear in `config.json`. The Weather Underground `api_key_env` field is target-owned implementation detail and is omitted; the real API key remains a hard exclusion.

## Secrets and identity: hard exclusions

An ordinary backup must never contain:

- Weather Underground API key or future managed Weather secrets;
- Plex authentication/claim/account/session credentials;
- Plexamp player/machine/client identity intended to distinguish one appliance from another;
- Chromium cookies, login data, session storage or authentication databases;
- passwords, bearer tokens, API keys or private-key material;
- raw machine-specific audio/hardware topology.

A non-credential backup can still contain personal household information such as alarm times, labels, station IDs and approximate forecast coordinates. It is therefore portable and secret-safe, not anonymous.

The #93 commissioning baseline does **not** weaken these exclusions. Its player label remains local to the appliance and never enters schema-v1 backup. The audio output UUID is not stored in that baseline at all.

## Plexamp Headless portable preference boundary

The guarded installer preserves:

```text
~/.local/share/Plexamp/Settings
```

across Plexamp runtime replacement, but the directory is **not** a supported backup unit.

The commissioned Plexamp 4.13.2 Pi physically exposed 35 files. Eleven safe-looking `@Plexamp:settings:*` names were visible to content-blind audit and 24 files remained deliberately unclassified. The exact typed scalar portable allow-list is:

| Preference | Observed commissioned value | Backup/Restore | #93 Reset |
| --- | ---: | --- | --- |
| `audioConversionBitrate` | `256` | Include, version-aware | Preserve/re-apply |
| `autoPlayEnabled` | `false` | Include, version-aware | Preserve/re-apply |
| `cacheSize` | `32768` | Include, version-aware | Preserve/re-apply |
| `cachingWiFi` | `10` | Include, version-aware | Preserve/re-apply |
| `loudnessLeveling` | `false` | Include, version-aware | Preserve/re-apply |
| `precacheNetworkSpeed` | `0` | Include, version-aware | Preserve/re-apply |
| `sampleRateConversionQuality` | `4` | Include, version/audio-policy aware | Preserve/re-apply |
| `sampleRateMatching` | `2` | Include, version/audio-policy aware | Preserve/re-apply |
| `audioDeviceUuid` | deliberately not read by backup audit | **Exclude** | Same-appliance commissioning owner resolves managed output dynamically |
| `premium` | deliberately not read | **Exclude** | Account/capability-derived; preserved |
| `playerName` | deliberately not read by backup audit | **Exclude** | Same-appliance commissioning owner restores local baseline |

The eight portable values use Plexamp's typed scalar encodings such as `Btrue` / `Bfalse` and `N<number>`. Export accepts only exact allow-listed names and expected types; malformed/unknown files are skipped rather than copied.

These eight observed values are **commissioned values and the supported Backup/Restore allow-list**, not a statement of Plexamp factory defaults.

### Relationship to native #93 Plexamp Reset

Checkpoint #93 now calls Plexamp's own in-application `settings.resetToDefaults()` for ordinary Plexamp settings. That native method is deliberately prevented from consuming the portable Headless ownership boundary.

`browser/plexamp-bridge/native-reset.js` therefore:

1. excludes all eight allow-listed Headless keys from native Reset Preview/counting;
2. captures their current values and present/absent state immediately before `resetToDefaults()`;
3. calls Plexamp's native reset method;
4. immediately restores the eight captured values;
5. verifies them before native Reset can report success;
6. includes them in the retained full rollback verification.

This is important for the queued high-resolution-audio work: #93 does **not** redefine current Headless sample-rate/audio-policy choices as Plexamp Reset defaults.

Unknown Headless values remain unclassified rather than becoming portable merely because the page-world settings object can see them.

## Appliance-local Plexamp commissioning ownership — PHYSICALLY ACCEPTED

`app/plexamp_commissioning.py` and `scripts/commission-plexamp.py` may operate only on:

- `playerName`;
- `audioDeviceUuid`.

Their contract is deliberately local and narrow:

- only Plexamp's loopback settings API on port `32500` is accepted;
- first successful `setup.sh` commissioning captures the claimed player name into `~/.local/share/a-clockwork-plex/plexamp-commissioning.json` with mode `0600`;
- repeat setup does not recapture a later rename;
- an older appliance acquires the baseline only through deliberate one-time setup migration;
- the baseline stores no audio UUID;
- each commission/Reset operation dynamically requires exactly one output labelled **`A Clockwork Plex - Plexamp`** and uses its current UUID;
- missing/ambiguous matching outputs fail closed;
- public Reset planning returns bounded status/count/fingerprint information, never player-name values or UUID;
- authentication, claim/account/resource state and unrelated Plexamp settings remain outside this owner;
- the owner is never serialized into the portable backup envelope.

Physical acceptance completed on 3 September 2026: a temporary player rename and **Follows system output** produced exactly two commissioning differences, and Reset returned both to the commissioned appliance state without leaking values.

## Browser-side Plexamp Home ownership

The kiosk Chromium profile is:

```text
~/.config/a-clockwork-plex/chromium-profile
```

It contains authentication/session state as well as Plexamp UI preferences, so **the profile must never be archived/restored wholesale**.

Physical discovery established Plexamp at `http://localhost:32500` and identified MMKV-style Local Storage state. Useful classified families are:

- contextual `mmkv.default\discovery:customizations:<context>::/library/sections/<id>:order` — Home ordering;
- contextual `mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden` — Home visibility;
- corresponding `:editing` records — transient editor state, excluded;
- `*:cachedItems`, resources, auth/session and unrelated state — excluded.

The live #89/#90 browser bridge remains the supported Backup/Restore authority. Raw Chromium LevelDB is discovery evidence only because browser compaction changes historical records.

### Backup/Restore Home bridge

`browser/plexamp-bridge/` is an unpacked Manifest V3 bridge loaded only by the dedicated kiosk launcher. It remains:

- loopback-only on Plexamp port `32500`;
- permission-free;
- without a background/service worker;
- without remote-debugging authority;
- without general network/cookie access.

For export, the bridge opens values only after keys match the exact Home `order` / `hidden` allow-list. It emits logical Home choices only. The dashboard validates schema, origin, source frame, request nonce, bounded counts and conservative hub identifiers before merging the optional browser section **in browser memory** into the server-generated secret-free backup.

The final commissioned-Pi #89 export physically returned browser schema `1`, **15 ordered Home identifiers**, **1 hidden identifier**, no browser omission and zero warnings.

For #90 restore, `planHome` discovers the target's live current context and maps saved logical choices onto hubs that exist there. `applyHome` requires explicit confirmation plus an exact fresh fingerprint, captures exact raw target state, writes only classified target-context `order` / `hidden` records, verifies the logical layout and reverses completed writes exactly on failure.

Checkpoint #90 Phase 4 is physically accepted: both order+hidden and order-only round trips restored the backed-up Home layout, converged to zero Home differences and left Plexamp browsing/playback healthy.

### Separate #93 Home Reset owner

Backup/Restore means “return to this saved logical Home layout”. Reset means “return to Plexamp's browser/device-local default Home”. Those are different operations.

An early #93 experiment proved that deleting one newly created contextual override could merely return Plexamp to the owner's already-configured browser baseline; absence of that one override was therefore **not** enough to prove factory/default Home.

A later disposable fresh Chromium profile resolved the semantic boundary safely:

- same Plex account/library + fresh browser profile produced the genuine default Home (`Mixes for You` first in the physical test);
- therefore the commissioned Home baseline is browser/device-local, not account-synchronised;
- Plexamp **Home Screen → Reset order** restores the default ordering;
- Reset order does not unhide a deliberately hidden section.

The #93 Home owner therefore resets both ordering and visibility across the bounded modern contextual records plus the exact legacy keys:

- `mmkv.default\discovery:customizations:order`;
- `mmkv.default\discovery:customizations:hidden`.

It does not generalise to arbitrary `discovery:` state. Preview reports only counts/fingerprint; apply is stale-protected, snapshots exact raw bytes, deletes only classified reset records, verifies absence and retains rollback state until the outer Reset finalizes. Auth/cache/editor values remain unopened and untouched.

The old compact `:c` LevelDB lead was later absent from live Local Storage and remains historical/deleted residue rather than a Reset authority.

The full native/Home Reset implementation is automated-green at `fe2409f36584d360afc05c474bfbea6e8ff4657a` / **Tests #4506: 1027 tests in 51.242s, `OK`**. Combined native/Home physical acceptance is still open.

## Audio preferences

### EQ

`MasterEqualizer` is the authority for persisted Bass/Mid/Treble and bypass state. Backups carry only the logical model. Restore calls that authority after the audio backend is installed/verified and never writes `master-eq.json` directly.

### Mixer

Persistent mixer levels are stored by ALSA, but raw ALSA state is tied to a card/control graph. Backups therefore store the four user-facing percentages (`master`, `plexamp`, `airplay`, `alarm`) and restore them through the restricted mixer helper.

The physically proven #93 default for Music Master is **79% observable**, not the nominal 80%, because of integer softvol quantisation. The other three Reset mixer defaults remain 100%.

## Backup envelope

The supported format is explicitly versioned JSON:

```json
{
  "schema_version": 1,
  "source": {
    "application": "A Clockwork Plex",
    "app_version": "0.4.0",
    "release_tag": "v0.4.0",
    "release_name": "Unified Bedside Appliance"
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

`plexamp.browser_preferences` is optional and present only after a validated live bridge snapshot. The commissioning baseline is intentionally absent.

Release identity comes from `app/static/app-version.json`. Plexamp runtime compatibility comes from the ACP-owned `~/plexamp/.a-clockwork-plex-runtime` manifest rather than optional `package.json` packaging details.

## Restore contract

Restore remains conservative:

1. parse/validate schema without mutation;
2. reject malformed/forbidden credential or machine-owned fields;
3. Preview changed paths/counts without values;
4. preflight required target owners;
5. capture rollback state;
6. apply ACP Settings and specialist EQ/mixer/AirPlay through their owners;
7. apply exact-version supported Plexamp Headless preferences only through their restricted owner;
8. apply/verify browser Home through its separate target-context owner when selected;
9. verify resulting logical state;
10. roll back within each supported owner boundary on failure.

The guided owner-facing flow is **Preview → choose A Clockwork Plex / Plexamp / both → Review selected restore → Confirm & restore**. Review refreshes selected-owner plans immediately before confirmation. Browser Home and server/Headless storage remain separate transactional owners; the UI does not invent a global atomic filesystem/browser transaction.

## #88 ownership audit — COMPLETE

Checkpoint #88 established the portable/nonportable boundaries described above. The commissioned Pi physically proved the eight Headless allow-list and Home order/hidden browser families while unknown/auth/device/browser values remained unopened. No raw Plexamp Settings directory, Chromium profile or LevelDB file is a supported backup unit.

## #89 configuration backup/export — COMPLETE

The complete schema-v1 export is physically accepted:

- ACP normalised portable settings, logical EQ/mixer and all eight approved Headless values are exported;
- secrets, player/device identity, hardware topology, runtime/caches are excluded;
- the live permission-free browser bridge adds validated logical Plexamp Home data in browser memory;
- physical export contained 15 ordered Home identifiers and 1 hidden identifier with zero warnings;
- the owner-facing download explicitly states credentials/authentication are not included.

## #90 configuration restore — COMPLETE

All four restore phases are physically accepted:

- **Phase 1:** parse/validate/read-only Preview;
- **Phase 2:** transactional ACP Settings/EQ/mixer apply with stale-preview refusal and rollback;
- **Phase 3:** exact-version eight-value Plexamp Headless apply with restricted helper, service coordination, compatibility checks and rollback;
- **Phase 4:** target-context-aware Plexamp Home order/hidden restore with exact raw browser rollback.

Physical acceptance included harmless ACP/EQ/mixer round trips, stale-preview refusal, incompatible Plexamp-version deferral, exact-version `autoPlayEnabled` round trip, Home order+hidden/order-only round trips and final zero-difference previews. Normal Plexamp playback remained healthy.

The accepted guided UI presents one Preview/Review/Confirm flow while preserving the actual distinct transaction owners underneath.

## #93 Reset-to-defaults relationship — IN PHYSICAL ACCEPTANCE

Checkpoint #93 deliberately reuses these ownership classifications without turning Reset into deletion or machine cloning:

- ACP defaults are server-owned and normalized from version-controlled defaults;
- Plexamp commissioning returns the local player name/output to the physically accepted appliance baseline;
- Plexamp ordinary settings use Plexamp's own `resetToDefaults()` authority;
- all eight portable Headless preferences are protected/re-applied around that native reset;
- Plexamp Home order and visibility use a separate bounded browser/device-local Reset owner derived from physical disposable-profile evidence;
- credentials/authentication, login/library selection, alarm arming, hardware/topology, runtimes and caches/history remain preserved.

Detailed #93 sequencing, rollback and remaining physical acceptance are maintained in [`reset-to-defaults.md`](reset-to-defaults.md).
