# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** remains open only for the final commissioned-Pi combined physical acceptance.

Already physically accepted:

- the A Clockwork Plex (ACP) Reset transaction and rollback/verification semantics;
- the final 1280×720 Preview → Review → Confirm presentation;
- the same-appliance Plexamp commissioning Reset for player name and managed audio output.

The final combined candidate adds two browser-side owners:

1. Plexamp native ordinary-settings Reset, using Plexamp's own `settings.resetToDefaults()` authority;
2. Plexamp Home order/visibility Reset, using the bounded Local Storage records physically classified during #89/#90/#93.

The first commissioned-Pi Preview of that combined implementation correctly failed closed because the native owner could not locate Plexamp's real settings runtime. The Home bridge was live and correctly reported one deliberate order record plus one deliberate hidden record, while commissioning correctly reported two deliberate changes. Static inspection of the installed Plexamp 4.13.2 bundles then established the correct runtime authority: module `92895` exposes its `rootStore.settings` proxy through `global.app.rootStore.settings`. The browser owner now uses the application-global store directly rather than attempting webpack-cache discovery.

The same physical pass also corrected an ownership mistake: the eight safe Headless preferences are **portable Backup/Restore choices**, not ACP-owned Reset baselines. Native Reset now allows Plexamp's own `resetToDefaults()` to reset those ordinary preferences too. Their older commissioned values remain historical backup-audit evidence only.

PR #9 remains Draft and must not merge until the final physical transaction passes and the owner explicitly accepts it.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing flow is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Unsaved ACP Settings changes block Reset so staged work cannot be silently overwritten.

The complete Reset has four participants:

1. **A Clockwork Plex** — supported ACP user configuration generated from version-controlled defaults through production normalisers.
2. **Plexamp commissioning** — same-appliance owner for the captured player name plus managed `A Clockwork Plex - Plexamp` output.
3. **Plexamp native settings** — ordinary Plexamp settings reset by Plexamp's own application authority.
4. **Plexamp Home** — browser/device-local Home order and visibility returned to default state through bounded classified records.

Authentication, selected library, claim/session, account/machine identity, credentials, hardware topology, installed runtimes/services and unrelated Chromium state remain outside Reset.

## A Clockwork Plex owner

`app/configuration_reset.py` owns the ACP target. The browser never supplies default values.

`ConfigurationResetPlanner` reads version-controlled `config.example.json`, passes it through the production Settings normalisers and narrows it through established ownership boundaries. Specialist audio defaults are added only when their owners are available.

The supported ACP target includes:

- dashboard/display choices;
- Weather and News non-secret settings;
- alarm schedules and ordinary alarm choices;
- AirPlay user preferences;
- Master EQ enabled with neutral bands when the EQ owner is available;
- persistent mixer defaults from the current mixer authority.

It excludes credentials, hardware/topology, runtime/cache/history state and the two alarm-audio safety arming switches.

`POST /api/settings/reset/preview` is read-only and returns changed paths/counts plus a state-bound token. `POST /api/settings/reset/apply` requires `confirm_reset: true`, rebuilds the target and delegates to the physically accepted #90 restore transaction machinery for stale refusal, preflight, application, verification and reverse-order rollback.

### Physical mixer boundary

The commissioned Pi proved that nominal Music Master 80% quantises through the existing integer ALSA softvol mapping and reads back as **79%**. Reset therefore targets the physically observable 79% value for Music Master; Plexamp, AirPlay and Alarm persistent mixer defaults remain 100%.

### Alarm sound safety

`alarm_audio.master_enabled` and `alarm_audio.scheduled_enabled` are preserved deliberately. Reset never silently arms or disarms scheduled alarm sound.

## Plexamp commissioning owner — PHYSICALLY ACCEPTED

`app/plexamp_commissioning.py` and `scripts/commission-plexamp.py` own only:

- `playerName`;
- `audioDeviceUuid` as the live binding for the managed output.

The owner is loopback-only on Plexamp port 32500 and never reads Plex tokens/cookies/claim/session material or unrelated preferences.

The appliance-local baseline file is:

```text
~/.local/share/a-clockwork-plex/plexamp-commissioning.json
```

It is atomic, mode `0600`, schema-versioned and stores only the commissioned player name. The audio UUID is never stored as a baseline; every commission/Reset resolves exactly one live output labelled:

```text
A Clockwork Plex - Plexamp
```

Missing or ambiguous matches fail closed.

Physical acceptance on 3 September 2026 proved baseline capture, the real empty/unset audio-device representation, zero-difference convergence, deliberate two-difference Preview, guarded Reset and physical restoration of both player name and managed output.

`playerName` and `audioDeviceUuid` remain excluded from portable Backup/Restore.

## Plexamp native ordinary-settings owner

`browser/plexamp-bridge/native-reset.js` owns ordinary Plexamp application settings.

### Why Plexamp is the default authority

Disposable-profile testing established that Plexamp's own **Debugging → Reset to Defaults** preserves login and selected library while resetting ordinary settings. ACP therefore does not maintain a copied table of Plexamp defaults; it invokes Plexamp's own `settings.resetToDefaults()` method and verifies against a fresh instance of the live settings class.

### Live runtime discovery — physically corrected

The first commissioned-Pi combined Preview returned `runtime-unavailable`. That was a valid fail-closed result: the page-world script was present, but its original locator assumed a `webpackChunk*` runtime/cache that the real Plexamp 4.13.2 application does not expose.

A bounded read-only inspection of the installed static bundle established:

- module `92895` exports a `rootStore` proxy;
- its settings getter delegates to `global.app.rootStore.settings`;
- Plexamp's own Debugging button calls that proxy's `settings.resetToDefaults()`;
- the bundle is a closed webpack IIFE with no global module-cache authority required for this operation.

The native owner therefore locates only:

```text
window.app.rootStore.settings
```

with the browser-global compatibility form as fallback. It requires the resulting object to expose `resetToDefaults()` before Preview can become ready. It does not scan webpack modules, use `eval`, expose a generic JavaScript executor or automate arbitrary DOM controls.

### Preview

Preview constructs a fresh instance of the live settings class and compares bounded public settings against it.

Excluded from this native participant:

- keys beginning `_`;
- `premium` (account/capability-derived);
- `playerName` and `audioDeviceUuid` (owned by commissioning).

All other bounded non-function settings, including the eight safe Headless preferences used by Backup/Restore, participate normally in Plexamp's native Reset semantics.

Public Preview exposes only status, change count and a short fingerprint — never raw values.

### Apply, verification and rollback

Apply requires explicit confirmation and the exact fresh fingerprint. It then:

1. captures a bounded exact pre-reset snapshot for rollback;
2. calls Plexamp's own `settings.resetToDefaults()`;
3. verifies all native-owned settings against a fresh settings instance;
4. retains a rollback token until the outer multi-owner transaction succeeds.

If verification fails, the pre-reset snapshot is restored. If a later Home/server participant fails, the outer Reset client uses the retained token to restore the native prestate before reporting failure.

The native call may temporarily reset `playerName` and `audioDeviceUuid`; the already accepted commissioning participant subsequently returns them to this appliance's commissioned state.

## Eight safe Headless preferences: Backup/Restore vs Reset

Checkpoint #88 established this exact typed scalar allow-list for **portable Backup/Restore**:

- `audioConversionBitrate`
- `autoPlayEnabled`
- `cacheSize`
- `cachingWiFi`
- `loudnessLeveling`
- `precacheNetworkSpeed`
- `sampleRateConversionQuality`
- `sampleRateMatching`

That allow-list means ACP can safely export and version-aware restore those user choices. It does **not** make their current values appliance-owned Reset defaults.

Earlier commissioned audit values (`256`, `false`, `32768`, `10`, `false`, `0`, `4`, `2`) remain historical #88/#90 evidence. During the 4 September #93 physical pass the same real Pi reported different current values (`128`, `true`, `512`, `15`, `true`, `0`, `2`, `0`). Neither set is hard-coded by #93 as Plexamp defaults.

For Reset, Plexamp itself is authoritative: these eight ordinary preferences are allowed to follow `settings.resetToDefaults()` like other Plexamp settings. If later high-resolution-audio work intentionally commissions one of them as an ACP appliance policy, that future feature must establish and document its own ownership instead of #93 pre-empting it.

## Plexamp Home owner

The Home Reset owner recognises only the physically classified browser/device-local families:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:order
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:hidden
mmkv.default\discovery:customizations:order
mmkv.default\discovery:customizations:hidden
```

The last two are Plexamp's exact legacy migration keys.

It does not generalise to arbitrary `discovery:` data. `:editing`, auth/session, cached resources and unrelated browser state remain outside the owner.

Preview reports only bounded order/visibility record counts and a fingerprint. Apply requires the fresh fingerprint, captures exact raw bytes, removes only classified order/visibility records, verifies their absence and retains exact rollback state until the outer transaction finalizes.

### Why order and visibility are both required

A fresh disposable Chromium profile signed into the same account/library produced Plexamp's genuine default Home, including `Mixes for You` first in the physical test. Plexamp **Home Screen → Reset order** restored this default order, but a deliberately hidden section stayed hidden. A complete Home Reset therefore clears both order and hidden records.

The historical compact `:c` LevelDB lead was absent from live Local Storage during a bounded key-name-only probe and remains classified as historical/deleted residue, not a Reset authority.

## Browser isolation

The bridge remains deliberately narrow:

- Manifest V3;
- one isolated content-script entry (`content.js` + `reset.js`);
- matches only `http://localhost:32500/*` and `http://127.0.0.1:32500/*`;
- no extension `permissions` or `host_permissions`;
- no background worker;
- no cookies authority;
- no remote-debugging interface;
- `native-reset.js` is one loopback-scoped packaged web-accessible resource injected into Plexamp's page world by the isolated bridge.

No generic page-execution surface is exposed.

## Combined transaction sequencing

The browser and server owners cannot share one storage engine, so Reset composes retained rollback boundaries:

1. Preview obtains ACP/commissioning, native Plexamp and Home plans without mutation.
2. Review performs a fresh Preview and binds confirmation to fresh tokens/fingerprints.
3. Confirm applies native Plexamp settings when required and retains native rollback state.
4. It applies Home order/visibility when required and retains exact Home rollback state.
5. Before server mutation, a fresh server Preview must still match the reviewed ACP owner token.
6. The existing server transaction applies/verifies ACP + commissioning.
7. Only after all required participants succeed are browser rollback snapshots finalized.

If any browser participant fails, earlier browser work rolls back. If the later server transaction fails, retained browser owners roll back before failure is reported.

## Physical evidence and remaining gate

Automated milestones:

- `d8282a348cc701db1264a06b9abfcc46968d47d9` — Tests #4490, 1025 tests, `OK`; commissioning/presentation physically accepted afterwards.
- `01af4769ef2fbb21845c317e97f3d1851a2d9eed` — Tests #4509, 1027 tests, `OK`; first native/Home physical candidate.
- First physical Preview on `01af...` proved extension/Home/commissioning wiring but failed closed on native `runtime-unavailable`.
- Static Plexamp 4.13.2 bundle inspection identified `global.app.rootStore.settings` as the real native settings authority.
- `c2754171b6394485306df6aebf21df4d2c2e3e33` — **Tests #4512: 1027 tests in 49.344s, `OK`** after switching to the application-global runtime and returning the eight Headless preferences to normal native Reset semantics.

The current deliberate physical test state should remain in place for the next candidate:

- Artists hidden;
- Recently Added in Music moved to the top;
- temporary Plexamp player name;
- audio output set to Follows system output.

Remaining acceptance:

1. pull/reboot the final documentation-synchronised candidate so the updated extension script is loaded;
2. Preview must be complete and report bounded native/Home/commissioning work without raw values;
3. Review → Confirm & reset;
4. verify Plexamp ordinary defaults, genuine default Home order, Artists visible, commissioned player name, managed audio output, preserved login/library and normal playback/dashboard health;
5. verify the eight safe Headless preferences follow Plexamp's own defaults rather than an ACP hard-coded baseline;
6. fresh Preview must converge to zero native/Home/commissioning differences (and ACP zero when intentionally left at shipped ACP defaults);
7. obtain explicit owner acceptance before PR #9 leaves Draft or merges.
