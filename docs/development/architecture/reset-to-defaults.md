# Reset to defaults ownership

## Status

Checkpoint **#93 Reset to defaults** remains open for the final commissioned-Pi physical acceptance of the revised combined transaction.

Already physically accepted:

- the A Clockwork Plex (ACP) Reset transaction, verification and rollback model;
- the final 1280×720 Preview → Review → Confirm presentation;
- the same-appliance Plexamp commissioning Reset for player name and managed audio output.

The revised combined candidate adds two browser-side owners:

1. **Plexamp native ordinary-settings Reset** — Plexamp's own `settings.resetToDefaults()` authority, plus Plexamp player volume returning to 100%;
2. **Plexamp Home presentation Reset** — bounded per-section `viewSettings` only. Home order, visibility and custom-added sections are preserved.

PR #9 remains Draft and must not merge until the final physical transaction passes and the owner explicitly accepts it.

## Product boundary

Reset to defaults is deliberately **not a factory wipe** and is separate from Backup & restore.

The owner-facing flow is:

**Settings → Advanced → Reset to defaults → Preview reset → Review reset → Confirm & reset**

Preview and Review are read-only. Unsaved ACP Settings changes block Reset so staged work cannot be silently overwritten.

The complete Reset has four participants:

1. **A Clockwork Plex** — supported ACP user configuration generated from version-controlled defaults through production normalisers.
2. **Plexamp commissioning** — same-appliance owner for the captured player name plus managed `A Clockwork Plex - Plexamp` output.
3. **Plexamp native settings** — ordinary Plexamp settings reset by Plexamp's own application authority, with Plexamp player volume explicitly returned to 100%.
4. **Plexamp Home presentation** — per-section presentation/custom view settings returned to Plexamp defaults without changing section order, visibility or custom-added sections.

Authentication, selected library, claim/session, account/machine identity, credentials, hardware topology, installed runtimes/services and unrelated Chromium state remain outside Reset.

## A Clockwork Plex owner

`app/configuration_reset.py` owns the ACP target. The browser never supplies default values.

`ConfigurationResetPlanner` reads version-controlled `config.example.json`, passes it through the production Settings normalisers and narrows it through established ownership boundaries. Specialist audio defaults are added only when their owners are available.

The supported ACP target includes:

- dashboard/display choices;
- Weather and News non-secret settings;
- alarm schedules and ordinary alarm choices;
- AirPlay user preferences;
- Master EQ enabled with neutral Bass/Mid/Treble bands;
- persistent mixer levels returned to the current full-scale baseline when the mixer owner is available.

It excludes credentials, hardware/topology, runtime/cache/history state and the two alarm-audio safety arming switches.

`POST /api/settings/reset/preview` is read-only and returns changed paths/counts plus state-bound tokens. `POST /api/settings/reset/apply` requires `confirm_reset: true`, rebuilds the target and delegates to the physically accepted #90 restore transaction machinery for stale refusal, preflight, application, verification and reverse-order rollback.

### Browser/server stale-token ownership

The browser-native Plexamp participant runs before the server-owned ACP participant. That sequencing requires two deliberately different server fingerprints:

- `owner_tokens.a_clockwork_plex` fingerprints **only the ACP-owned target and current ACP-owned state**. The browser client uses this token immediately before server mutation to prove that ACP itself has not changed since Review.
- `restore_preview_token` is the broader #90 portable-Restore token used internally by the server executor. It may also fingerprint portable Plexamp Headless preferences because #90 Restore owns those preferences.

Those tokens must not be conflated. Native Plexamp Reset is explicitly allowed to change ordinary Headless preferences before the server step. Therefore a legitimate Headless change may invalidate the broader #90 restore token while the ACP-only owner token remains unchanged.

Physical testing on 5 September exposed the previous mistake: the first combined implementation reused the broader #90 token as the ACP hand-off token. A full-state Review contained 16 native Plexamp changes, including Headless preferences; native Reset changed them, the broader token changed, and the client falsely reported **“A Clockwork Plex settings changed after Review.”** The retained browser-native/Home rollback then restored the browser-owned prestate correctly. The fix gives ACP its own scoped token while retaining the full #90 token for the actual server transaction.

### Audio Reset baseline

Reset deliberately returns the persistent ACP audio controls to a neutral/full-scale baseline:

- Master EQ: enabled, Bass 0.0 dB, Mid 0.0 dB, Treble 0.0 dB;
- Music Master: 100%;
- Plexamp trim: 100%;
- AirPlay trim: 100%;
- Maximum Alarm Volume: 100%.

The earlier 80% Music Master / physically observed 79% round-trip was useful evidence about ALSA softvol quantisation, but it is no longer the Reset baseline.

AirPlay's **60% session-start volume** remains a separate user preference and runtime policy. It is not the persistent AirPlay trim baseline.

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

`browser/plexamp-bridge/native-reset.js` owns ordinary Plexamp application settings plus Plexamp's live music-player volume.

### Plexamp remains the default authority

Disposable-profile testing established that Plexamp's own **Debugging → Reset to Defaults** preserves login and selected library while resetting ordinary settings. ACP therefore does not maintain a copied table of Plexamp setting defaults; it invokes Plexamp's own `settings.resetToDefaults()` method and verifies against a fresh instance of the live settings class.

Read-only inspection of Plexamp 4.13.2 established the live authority at:

```text
global.app.rootStore.settings
```

with the browser-global compatibility form as fallback. The owner requires `resetToDefaults()` before Preview can become ready. It does not scan webpack modules, use `eval`, expose a generic JavaScript executor or automate arbitrary DOM controls.

### Preview diagnostics

Preview compares bounded public settings against a fresh settings instance.

Excluded from this native participant:

- keys beginning `_`;
- `premium` (account/capability-derived);
- `playerName` and `audioDeviceUuid` (owned by commissioning).

All other bounded non-function settings, including the eight safe Headless preferences used by Backup/Restore, participate normally in Plexamp's native Reset semantics.

Preview also reads Plexamp's live music-player volume through the same-origin player timeline API. A value below 100% contributes one logical native change named:

```text
playerVolume
```

Public Preview exposes bounded **setting names only** under Technical changed paths, together with count/fingerprint information. It never exposes old/new values. This deliberately makes residual post-reset differences diagnosable without turning Preview into a preference-value dump.

### Apply, verification and rollback

Apply requires explicit confirmation and the exact fresh fingerprint. It then:

1. captures a bounded exact pre-reset settings snapshot and the current Plexamp player volume;
2. calls Plexamp's own `settings.resetToDefaults()` when ordinary settings differ;
3. sets Plexamp player volume to **100%** through Plexamp's same-origin player parameter endpoint;
4. verifies settings against a fresh settings instance and verifies player volume at 100%;
5. retains a rollback token until the outer multi-owner transaction succeeds.

If verification fails, both settings and player volume are restored. If a later Home/server participant fails, the outer Reset client uses the retained token to restore the exact browser-native prestate.

The native call may temporarily reset `playerName` and `audioDeviceUuid`; the physically accepted commissioning participant subsequently returns them to this appliance's commissioned state.

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

Earlier commissioned audit values (`256`, `false`, `32768`, `10`, `false`, `0`, `4`, `2`) and later observed values (`128`, `true`, `512`, `15`, `true`, `0`, `2`, `0`) remain evidence of real appliance state, not Plexamp-default constants.

For Reset, Plexamp itself is authoritative: these eight ordinary preferences follow `settings.resetToDefaults()` like other Plexamp settings. If later high-resolution-audio work intentionally commissions one of them as an ACP appliance policy, that future feature must establish and document its own ownership.

## Plexamp Home presentation owner

The earlier investigation established an important product boundary: deleting Home order/visibility records does **not** reliably mean “factory Home”, because those records can be delta overrides over an existing effective Home baseline.

The revised #93 owner therefore does **not** attempt to reset Home order or visibility. It preserves:

- section order;
- hidden/visible state;
- custom-added sections;
- custom section titles;
- editor/auth/cache/unrelated browser state.

It recognises only current-context per-section records of the form:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

Real commissioned-profile evidence showed that both `<context>` and `<hub-id>` can contain bounded URL-like characters. The matcher therefore accepts only the established structural family plus a bounded identifier character envelope and exact final `:viewSettings` suffix. A key which clearly belongs to the family but cannot be classified fails Preview closed rather than being reported as zero changes.

For a built-in section, presentation-specific `viewSettings` are removed so Plexamp can use its own per-section default presentation. For a custom-added section, the owner strips presentation fields while retaining the validated custom `title` field so the section itself remains intact.

The owner fails closed on unsupported `viewSettings` encodings, unclassified family keys, ambiguous Home contexts or excessive bounded record counts. It does not open order, hidden, editor, auth or cache values while planning.

Preview reports only a bounded record count and fingerprint. Apply requires the fresh fingerprint, captures exact raw bytes, writes/removes only classified `viewSettings` records, verifies zero remaining presentation differences and retains exact rollback state until the outer transaction finalizes.

On exact physical-preview head `4e01b289fbfec352d41d345a50e22dcc30bf53a3`, the commissioned Pi successfully reported **15 Home presentation records** in one Preview and **14** after the state was recreated, with the technical UI collapsing them to `plexamp.home.view-settings · N` and exposing no raw Home identifiers or values.

The historical compact `:c` LevelDB lead remains classified as historical/deleted residue, not a Reset authority.

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

1. Preview obtains ACP/commissioning, native Plexamp and Home-presentation plans without mutation.
2. Review performs a fresh Preview and binds confirmation to fresh tokens/fingerprints.
3. Confirm applies native Plexamp settings/player volume when required and retains native rollback state.
4. It applies Home presentation `viewSettings` when required and retains exact Home rollback state.
5. Before server mutation, a fresh server Preview must still match the reviewed **ACP-only** owner token. Changes made legitimately by native Plexamp Reset to Headless preferences do not invalidate this ACP hand-off token.
6. The server executor still uses its separately retained broader #90 `restore_preview_token` to apply/verify the current ACP target, and commissioning uses its own fingerprint.
7. Only after all required participants succeed are browser rollback snapshots finalized.

If any browser participant fails, earlier browser work rolls back. If the later server transaction or hand-off check fails, retained browser owners roll back before failure is reported.

## Automated evidence and remaining gate

Current code evidence is green at `4a14205691ad320b7c6360fd06434fd26d1dc292` / **Tests #4559**. That run passed compile, JavaScript/page-wiring, shell checks and the full **1028-test** suite.

The added regression specifically proves that changing portable Plexamp Headless state and the underlying #90 restore token does **not** change `owner_tokens.a_clockwork_plex`, while an actual ACP-state change does. The complete reset token still changes with the broader server state, so the real apply boundary remains stale-protected.

Physical evidence through 5 September 2026:

- ACP Reset/rollback and presentation are accepted;
- commissioning rename/output round-trip is accepted;
- the native runtime fail-closed path led to the physically established `global.app.rootStore.settings` authority;
- the real Home `viewSettings` family is now classified on the commissioned profile and Preview is complete;
- exact head `4e01b289fbfec352d41d345a50e22dcc30bf53a3` physically reached **Preview ready** with bounded ACP/native/Home counts and names only;
- after recreating a fuller saved appliance state, Review reached **Ready to confirm** with 20 server-owned, 16 native Plexamp and 14 Home-presentation changes;
- Confirm then exposed the old false-stale ACP hand-off token bug because native Reset legitimately changed Headless preferences;
- the UI reported the failure and the retained browser-owned Plexamp changes were physically rolled back, which is positive rollback evidence;
- `4a14205691ad320b7c6360fd06434fd26d1dc292` fixes that token-scope defect and is automated-green; its final commissioned-Pi transaction remains to be retried.

The remaining physical acceptance is now deliberately narrow:

1. pull and reboot the final documentation-synchronised candidate;
2. Preview must again be complete and Review must reach Ready to confirm;
3. Confirm must cross the ACP-only hand-off without the false **“A Clockwork Plex settings changed after Review”** refusal;
4. verify ordinary Plexamp settings follow Plexamp defaults, Plexamp player volume becomes 100%, and Home section presentation returns to Plexamp per-section defaults while order/visibility/custom sections remain unchanged;
5. verify commissioned player name/output when deliberately changed, Plex login/library, playback and dashboard navigation remain healthy;
6. verify neutral ACP EQ and all four persistent mixer levels at 100%;
7. fresh Preview should converge to the supported baselines; any stable native runtime-normalised differences must be classified rather than repeatedly reset blindly;
8. obtain explicit owner acceptance before PR #9 leaves Draft or merges.
