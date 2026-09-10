# Commissioned Pi Backup/Restore acceptance — 10 September 2026

## Scope

Physical acceptance for checkpoints #89/#90 schema-v2 portable Backup/Restore on the commissioned `plexamp-bedroom` appliance.

This record is intentionally chronological. PR #10 remains Draft/unmerged until the complete Backup → Reset → Restore cycle passes and the owner explicitly approves promotion/merge.

## Starting state

- Previous physically accepted #93 implementation head: `477bf0fd0cd7090a4d434816611f35673d83851e` on `feature/reset-defaults`.
- Working tree was clean.
- Appliance switched cleanly to `feature/backup-restore-completeness` at `fb5e77c3a3c8caf6e23ab9def68110dd9636be5e`.

## Repeat setup / production convergence — PASS

Normal `bash setup.sh` completed successfully.

Key evidence:

- CamillaDSP 4.1.3 reused with `CAMILLA_ARTIFACT=PASS-EXISTING` and accepted executable SHA-256;
- commissioned Weather Underground profile and managed credential preserved;
- no APT package mutation required;
- paired main/NFC venv bootstrap passed;
- PN532 passed at I2C bus 1 / address `0x24`;
- DAC `CARD=Pro` passed with existing EEPROM/config; no firmware update;
- pinned Plexamp Headless 4.13.2 + Node 20.20.2 runtime owner passed while persistent Plexamp user state remained outside runtime replacement;
- NFC listener, restricted helpers and AirPlay integration converged successfully;
- existing EQ path remained on accepted split-bus route `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` and verified successfully;
- final whole-appliance verifier: **0 failures / 0 warnings**, `APPLIANCE_VERIFY=PASS`;
- application transaction committed with `APPLICATION_TRANSACTION=COMMITTED`, `ROOT_INSTALL=COMMITTED`, `APPLICATION_VERIFY=PASS`;
- Plexamp commissioning verification reported `changed_count: 0`, existing player-name baseline present, and managed `A Clockwork Plex - Plexamp` output already correct.

One transient dashboard `curl: (7)` occurred during the guarded service replacement/restart window; the dashboard owner subsequently verified successfully and the final independent verifier reported `dashboard-api PASS`, so this is not a final verification failure.

## Genuine reboot / bridge 1.5 production load — PASS

After a real `sudo reboot`:

- dashboard and embedded Plexamp appeared normal;
- branch remained `feature/backup-restore-completeness` at `fb5e77c3a3c8caf6e23ab9def68110dd9636be5e` with a clean working tree;
- complete `scripts/verify-appliance.sh --audio eq --weather-observations weather-underground ...` passed again with **0 failures / 0 warnings**;
- bridge manifest reported version **1.5.0**;
- content scripts were exactly `content.js`, `reset.js`, `portability.js`;
- web-accessible resources were exactly `native-reset.js`, `native-portability.js`, `home-portability-v2.js`;
- manifest contained no `permissions`, `host_permissions` or `background` authority;
- running Chromium kiosk used `/home/andy/.config/a-clockwork-plex/chromium-profile`;
- Chromium loaded the repository Plexamp bridge and Plexamp Search bridge through `--load-extension`;
- no Chromium `--remote-debugging-port` or `--remote-debugging-address` flags were present.

## Documentation / CI checkpoint — PASS

The physical reboot checkpoint was added to the live roadmap and this chronological acceptance record. The first documentation run, Tests #4708, correctly found one catalogue-only omission: this newly created testing record had not yet been added to the deliberately classified `docs/development/testing` set. No functional source, compile, JavaScript/page/shell or portability test failed.

The testing classification guard and Development documentation index were updated. **Tests #4710 passed completely** on `0cc6e43affe0e2dd45664bcd7073316277ce2421`, including compile, JavaScript/page/shell checks and the complete unit/regression suite.

## Deliberate pre-backup acceptance specimen — READY

The appliance fast-forwarded cleanly to `59ae3eb8431e682b61d07bdfded5478c047c460e`; the working tree remained clean. Only documentation/test-catalogue files changed from the physically accepted runtime head, so no setup rerun, service restart or reboot was required.

A deliberately conspicuous user-owned configuration was then created for the Backup → Reset → Restore proof:

- A Clockwork Plex daytime theme: **Crimson Glow**;
- Master EQ: **Bass +2.0 dB, Mid -1.0 dB, Treble +1.5 dB**;
- persistent output levels settled at **Music Master 79%, Plexamp trim 89%, AirPlay trim 93%, Maximum Alarm Volume 63%**;
- AirPlay session-start volume: **74%**, apply-on-start enabled;
- Plexamp live player volume deliberately remained a separate runtime value and is not part of portable Backup/Restore;
- Plexamp ordinary portable settings were deliberately changed, including **Show Full Player when starting playback**, Autoplay and other constructor-default deviations captured by the native-v2 owner;
- Plexamp Home: **Recent Plays** hidden;
- Plexamp Home: **Recently Added in Music** presentation changed to **Carousel / Block / 180 px**;
- Plexamp Home: an **Artist** custom section was added and titled **`ACP Backup Restore Test`**;
- Plexamp Home ordering was then moved far enough to force a complete durable `order` record rather than only custom-section placement.

The Plexamp UI label physically present on this Headless/kiosk build is **Show Full Player when starting playback**; that is the intended setting. The earlier acceptance instruction used imprecise wording, not a kiosk-mode-specific missing option.

The requested 87% Plexamp persistent trim settled and read back as 89% because the calibrated human percentage is mapped through dB onto ALSA softvol's finite raw steps. The confirmed 89% value is therefore the correct portable acceptance target.

The physical Settings control used for AirPlay session-start volume autosaves when the slider is released. An earlier acceptance instruction incorrectly referred to a separate explicit Save action; the observed current UI and the resulting backup prove that no extra Save button is required for this control.

## Schema-v2 export exercise — BLOCKER FOUND BEFORE RESET

The Settings page successfully reported a **complete schema-v2 backup**, and repeated exports contained the expected logical ACP/native/Home-v2 envelope. The final pre-fix specimen included:

- top-level schema version **2**;
- Crimson Glow theme;
- EQ **+2.0 / -1.0 / +1.5 dB**;
- persistent mixer **79 / 89 / 93 / 63%**;
- AirPlay starting volume **74%**, apply-on-start enabled;
- Plexamp 4.13.2 native deviations including `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `gridSize`, `sampleRateConversionQuality` and `showFullScreenPlayerOnPlay`;
- Home-v2 hidden count **1**;
- Home-v2 presentation count **2**;
- Home-v2 custom-section count **1**, with portable relative Artist query and title `ACP Backup Restore Test`;
- after the deliberate second Home move, a complete Home order of **13 entries**.

A recursive inspection found no forbidden credential/auth/player-identity key names.

The full order exposed a previously unrepresented Plexamp identifier family: the final built-in row used a target-scoped Recent Played identifier shaped like:

```text
music.recent.played.<source-context>./hubs/sections/9
```

The exact source-context value is deliberately not recorded here. This identifier embeds both target context and the source library section number, contradicting the Home-v2 portability contract that portable files must not carry source context/library identity. The existing browser owner and Python envelope validator had treated it as an ordinary safe-character built-in identifier, so synthetic tests had missed the problem.

**Reset was deliberately not run.** Physical acceptance correctly stopped at the export boundary rather than testing Restore with a known source-bound backup.

## Target-scoped Recent Played portability fix — AUTOMATED GREEN

`browser/plexamp-bridge/home-portability-v2.js` now recognises only the proven target-scoped Recent Played form and requires its embedded context/section to match the live source scope. Export converts that physical identifier to the source-free logical marker:

```text
target-library.music.recent.played
```

Restore materialises that marker from the destination's live target context and selected library section. A raw target-scoped Recent Played identifier supplied as a supposedly portable logical built-in is rejected by the Home-v2 browser owner.

Implementation commits:

- `2ac1e0569270c3544ba249c68f89b637cf4482d7` — target-scoped Home hub portability owner fix;
- `ee66d3356baa38b148f98fc852c7109bfbe3f62b` — regression proving source → logical marker → different target remap and rejection of raw source-bound input.

**Tests #4714 passed completely** on `ee66d3356baa38b148f98fc852c7109bfbe3f62b`, including Python compile, JavaScript/page/shell checks and the complete unit/regression suite. The documentation follow-up **Tests #4715** also passed completely.

## Post-fix schema-v2 re-export — PASS

The corrected Home-v2 owner was pulled onto the commissioned appliance, Chromium was genuinely restarted through a reboot so the production extension loaded the new JavaScript, and a fresh backup was created from the unchanged recognisable specimen.

Backup `A-Clockwork-Plex-backup-2026-09-10_051035.json` reported:

- top-level schema version **2**;
- Crimson Glow theme;
- EQ enabled at **Bass +2.0 dB / Mid -1.0 dB / Treble +1.5 dB**;
- persistent mixer **Music Master 79% / Plexamp trim 89% / AirPlay trim 93% / Maximum Alarm Volume 63%**;
- AirPlay session-start volume **74%**;
- Plexamp 4.13.2 portable deviations remained present;
- Home order contained **13 logical entries**;
- `Recent Plays` remained represented as hidden;
- `Recently Added in Music` retained **Carousel / Block / 180 px** presentation;
- custom Artist section `ACP Backup Restore Test` retained its portable relative query and title.

Most importantly, the final target-scoped Recent Played row exported as exactly:

```text
target-library.music.recent.played
```

The physical inspection then passed all three portability assertions:

```text
logical Recent Played marker: PASS
raw target-scoped Recent Played absent: PASS
raw library section path absent: PASS
```

The portable Home model therefore contains no source Recent Played context/hash and no raw source library section path. This closes the physical export blocker that the first full-order specimen exposed.

**#89 schema-v2 Backup/export physical gate: PASS.** The remaining product gate is #90: accepted #93 Reset followed by schema-v2 Preview → Review → Confirm Restore and post-restore physical/logical convergence.

## Accepted #93 Reset Preview for #90 — PASS (read-only)

With the accepted schema-v2 backup safely retained, the commissioned appliance opened **Settings → Advanced → Reset to defaults** and ran only **Preview reset**. The preview remained read-only and explicitly reported that nothing had changed yet.

Observed owner accounting:

```text
26 server-owned
7 Plexamp native settings
5 Plexamp Home customisation records
38 selected changes total
```

The 26 server-owned paths broke down as:

- `audio.eq` — 3;
- `audio.mixer` — 4;
- `settings.airplay` — 1;
- `settings.alarms` — 4;
- `settings.display` — 3;
- `settings.weather` — 11.

The native owner reported seven changes: the six ordinary Plexamp setting deviations represented by the accepted backup specimen plus `playerVolume`, which #93 Reset deliberately returns to 100% but portable Restore does not own.

The Home owner reported exactly **5** bounded durable records: **1 order, 1 visibility, 2 presentation/title, 1 custom section**. Plexamp commissioning reported that the captured player-name baseline and managed **A Clockwork Plex - Plexamp** audio output already matched, so no commissioning repair was required.

The Preview presented no warning/incomplete state, kept the documented preserved owners visible, and enabled **Review selected reset**. No mutation had yet occurred.

**Disposition:** the #93 Reset Preview gate for the #90 physical transaction is accepted. The next step is Review → one Confirm & reset, followed by post-Reset commissioning/baseline checks before any Restore mutation.