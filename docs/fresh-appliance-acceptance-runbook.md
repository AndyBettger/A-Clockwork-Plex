# Fresh appliance physical acceptance runbook

**Status:** Phase 7 spare-SD physical acceptance procedure  
**Branch under test:** `feature/alarm-engine`  
**Updated:** 17 August 2026

## Purpose

Prove that A Clockwork Plex can be built and reconverged on the real bedroom Pi/HAT/display hardware using a **spare SD card** while the **accepted production SD card** remains removed and untouched.

The acceptance route covers fresh package/venv ownership, I2C/PN532, Raspberry Pi DAC Pro, pinned Plexamp Headless/Node, NFC, dashboard/kiosk, AirPlay, alarm-safe Direct audio, guarded EQ promotion, reboot/repeat-install, Weather Underground commissioning and historical rainfall.

**Current resumed spare-SD position (17 August 2026):** Sections 6 and 7 have completed successfully on `plexamp-test`. Guarded installed-EQ → requested-Direct convergence committed with root installer exit `0`; `FRESH_BOOTSTRAP_VERIFY=PASS`, `APPLIANCE_VERIFY=PASS`, the canonical Direct route SHA and clean EQ/loopback residue were independently verified. Evidence is recorded in `docs/eq-to-direct-physical-verification-2026-08-17.md`. Continue at **Section 8** for the remaining hands-on Direct checks; do not rerun Direct construction merely to regain context.

The focused Weather work may continue on that same Direct spare card without invalidating Sections 6–7. Settings presentation, WU write-only commissioning, Ecowitt/WU live-history independence, Ecowitt credential preservation and the selected-period Today / Last 7 days / Current month / Current year behavior have now passed physically. Current year naturally exposed three station-offline dates; these are accepted coverage gaps, not API failures, and the physical API correctly returned a 21.38-inch minimum-recorded total with zero repeat fetches. The remaining focused Weather gate is the corrected **Rainy Day Fund** projection: one-time previous-year backfill, six current/previous calendar gauges, optional station-lifetime Total and horizontal touch scrolling. Evidence is maintained in `docs/weather-physical-followup-2026-08-17.md`.

---

# 0. Stop rules and accepted identities

**Stop on the first unexplained failure.** Preserve evidence and diagnose the failed owner; do not fix forward blindly.

- Power down before reseating hardware or SD cards.
- Remove the accepted production SD card before the spare card is inserted.
- **Label/store that card safely. Do not reformat it for this test.**
- Do not update Pi EEPROM/bootloader, HAT EEPROM, audio-HAT firmware or other hardware firmware.
- Run installers as the normal appliance user, never as root.
- Never place a Weather Underground API key or Plex claim code in chat, evidence, `config.json`, installer argv or logs.
- Do not substitute unverified Plexamp, Node or CamillaDSP artifacts.
- PR #2 remains Draft/open/unmerged throughout this procedure.

| Item | Accepted value |
|---|---|
| Fresh alarm-safe Direct route | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` |
| EQ split-bus route | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` |
| CamillaDSP executable | `4.1.3` aarch64, SHA-256 `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |
| CamillaDSP official archive | SHA-256 `d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a` |
| Plexamp Headless | `4.13.2`, SHA-256 `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041` |
| Node | `20.20.2` linux-arm64, SHA-256 `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71` |
| PN532 | I2C bus `1`, address `0x24` |
| DAC | Raspberry Pi DAC Pro, ALSA `CARD=Pro` |
| DAC fallback overlay | `rpi-dacpro` only when commissioning requires it |
| Root activation token | `APPLY-A-CLOCKWORK-PLEX` |

The historical Phase 6 Direct rollback `08d00093...` is historical evidence, not the fresh Direct target.

---

# 1. Protect production state and prepare the appliance

1. Shut the working appliance down normally and disconnect power.
2. Remove the accepted production SD card.
3. Label/store that card safely; do not reformat it for this test.
4. Complete any intended cable/standoff tidy-up while unpowered.
5. Insert only the spare acceptance card.

The production card is the recovery boundary for this experiment.

---

# 2. Fresh Raspberry Pi OS baseline

For a genuinely fresh run, use current 64-bit Raspberry Pi OS with Desktop. In Raspberry Pi Imager configure the normal appliance username, network/locale/timezone, SSH if wanted, and a **test hostname** distinct from production such as `plexamp-test`.

Do not manually preinstall Plexamp, NFC libraries, Shairport routing, CamillaDSP or A Clockwork Plex services.

Record:

```bash
hostname -s
id
uname -m
cat /etc/os-release
```

Require 64-bit/aarch64 Raspberry Pi OS.

---

# 3. Obtain and verify the source tree

```bash
cd ~
git clone --branch feature/alarm-engine https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
git branch --show-current
git rev-parse HEAD
git status --short
```

If `git` is unavailable on a genuinely fresh image, copy the exact branch tree from a trusted machine only for this source-bootstrap boundary. Require `feature/alarm-engine`, the latest green head selected for acceptance, and a clean tree.

On the current reused spare card, fast-forward the existing checkout rather than cloning again.

---

# 4. Create or recover the acceptance evidence directory

For a new fresh-card experiment only:

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$HOME/acp-phase7-spare-sd-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE"
printf '%s\n' "$EVIDENCE" > "$HOME/.acp-phase7-evidence-path"
```

For every resumed attempt, including the current EQ → Direct retry, **reuse the existing evidence directory**:

```bash
EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"
printf 'EVIDENCE=%s\n' "$EVIDENCE"
test -d "$EVIDENCE" && echo EVIDENCE_OK || echo EVIDENCE_MISSING
```

Do not silently create a replacement directory if the saved path is missing.

---

# 5. Read-only fresh Direct plan

```bash
bash install.sh \
  --fresh-bootstrap \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --non-interactive \
  | tee "$EVIDENCE/10-direct-plan.txt"
```

Require the plan order to include package/artifact check, **fresh stage-zero preflight**, paired main/NFC venv bootstrap, hardware commissioning, player-pending gate, pinned Plexamp runtime, pinned NFC listener, full host preflight and application transaction/verifier. The plan must not mutate production state.

---

# 6. Fresh Direct apply — controlled resume loop

Use a new timestamped log on every attempt so prior failures remain evidence:

```bash
set -o pipefail
DIRECT_CMD=(
  bash install.sh
  --fresh-bootstrap
  --audio direct
  --weather-observations ecowitt-push
  --project-user "$USER"
  --non-interactive
  --apply
  --confirm APPLY-A-CLOCKWORK-PLEX
)

DIRECT_LOG="$EVIDENCE/20-direct-install-$(date +%Y%m%d-%H%M%S).txt"
"${DIRECT_CMD[@]}" 2>&1 | tee "$DIRECT_LOG"
rc=${PIPESTATUS[0]}
echo "installer exit=$rc"
echo "direct log=$DIRECT_LOG"
```

### Reused spare-SD EQ → Direct convergence

The spare card may already contain an accepted EQ appliance from an earlier Phase 7 attempt. That is now a **supported convergent source state** for a requested Direct install.

- Do **not** manually uninstall EQ before this run.
- The application transaction owns specialist EQ teardown, retained-backup handling, live loopback rollback state and canonical Direct installation.
- A failed transition must restore the prior EQ application state rather than requiring manual fix-forward.
- Preserve the timestamped log on any nonzero exit.

There are three controlled root-installer outcomes:

## A. Exit `75` — reboot required

Require:

```text
ROOT_INSTALL=REBOOT-REQUIRED
REBOOT_POLICY=OPERATOR-CONTROLLED
```

This is a controlled hardware checkpoint. Reboot manually, recover `$HOME/.acp-phase7-evidence-path`, and rerun the same command with a new timestamped log.

## B. Exit `76` — Plexamp claim required

Run the pinned player locally:

```bash
cd ~/plexamp
/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node js/index.js
```

Obtain a fresh code from `https://plex.tv/claim`, enter it only into the local Plexamp prompt, enter the player name, wait for successful sign-in, then `Ctrl-C`. Do not save the claim code. Return to the repository and rerun the same installer command.

## C. Exit `0` — committed

Require:

```text
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=fresh-bootstrap
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

For the current reused spare-SD retry, exit `0` is the expected success result after the source/CI-tested EQ → Direct convergence repair. Any other unexplained nonzero exit is an acceptance failure: stop, preserve the log, and do not manually fix forward.

---

# 7. Verify the completed Direct appliance

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"

bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/21-fresh-bootstrap-verify.txt"

bash scripts/verify-appliance.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/22-direct-appliance-verify.txt"
```

Require:

```text
FRESH_BOOTSTRAP_VERIFY=PASS
APPLIANCE_VERIFY=PASS
```

Check the Direct route and absence of the EQ marker:

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/23-direct-route.sha256"
test ! -e /var/lib/a-clockwork-plex/split-bus/installed
```

Expected SHA: `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`.

Spot-check hardware/runtime:

```bash
systemctl --no-pager --full status plexamp.service nfc-listener.service || true
i2cdetect -y 1
aplay -l
```

Require PN532 `0x24` and `CARD=Pro`.

**Current 17 August spare-SD result:** this section has passed and is recorded in `docs/eq-to-direct-physical-verification-2026-08-17.md`. Resume at Section 8 unless a later change specifically invalidates the Direct construction/verifier evidence.

---

# 8. Physical Direct acceptance

Record notes in `$EVIDENCE/24-direct-physical-notes.txt` and require:

- Dashboard, Settings and Clock render normally; Chromium kiosk starts normally.
- Plexamp plays stable stereo.
- A known NFC tag starts local Plexamp playback, switches the dashboard to Plexamp, and immediate repeated scans are debounced.
- AirPlay takes over cleanly through PlaybackCoordinator and returns normally.
- With music playing, **Music Master = 0%** silences music.
- A real scheduled alarm remains audible while Music Master is 0%; Snooze/Dismiss work.
- Settings → Audio/EQ shows **Install required** in Direct mode.

---

# 9. Acquire the exact accepted CamillaDSP artifact

```bash
bash scripts/fetch-camilladsp-4.1.3.sh \
  | tee "$EVIDENCE/30-camilladsp-plan.txt"

bash scripts/fetch-camilladsp-4.1.3.sh \
  --activate \
  --confirm FETCH-CAMILLADSP-4.1.3 \
  | tee "$EVIDENCE/31-camilladsp-fetch.txt"

CAMILLA="$HOME/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp"
"$CAMILLA" --version
sha256sum "$CAMILLA"
```

Require CamillaDSP 4.1.3 and executable SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`.

---

# 10. Promote the same appliance to EQ

Plan and apply using the guarded fresh-bootstrap owner:

```bash
bash install.sh \
  --fresh-bootstrap \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --non-interactive \
  | tee "$EVIDENCE/32-eq-plan.txt"

set -o pipefail
EQ_CMD=(
  bash install.sh
  --fresh-bootstrap
  --audio eq
  --weather-observations ecowitt-push
  --project-user "$USER"
  --camilladsp-binary "$CAMILLA"
  --non-interactive
  --apply
  --confirm APPLY-A-CLOCKWORK-PLEX
)
"${EQ_CMD[@]}" 2>&1 | tee "$EVIDENCE/33-eq-install.txt"
rc=${PIPESTATUS[0]}
test "$rc" -eq 0
```

Then run all three verifiers:

```bash
bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/34-eq-bootstrap-verify.txt"

bash scripts/verify-appliance.sh \
  --audio eq --weather-observations ecowitt-push \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/35-eq-appliance-verify.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/36-eq-audio-verify.txt"
```

Require all PASS and route SHA `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` with `/var/lib/a-clockwork-plex/split-bus/installed` present.

---

# 11. Physical EQ acceptance

Require clean Plexamp/AirPlay through EQ, plausible Bass/Mid/Treble changes, working bypass, Music Master = 0% music isolation with alarm still audible, independent **Maximum Alarm Volume**, working Snooze/Dismiss, and NFC playback/display handoff after EQ promotion.

Phase 6 already physically proved controlled Camilla failure/failback; do not manufacture another failure merely for this fresh-construction run.

---

# 12. Reboot acceptance

```bash
sudo reboot
```

After reconnecting, recover the source/evidence path and run:

```bash
bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/40-bootstrap-after-reboot.txt"

bash scripts/verify-appliance.sh \
  --audio eq --weather-observations ecowitt-push \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/41-appliance-after-reboot.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/42-audio-after-reboot.txt"
```

Require all three to pass, then recheck kiosk, brief Plexamp playback, one NFC tag and one real alarm/Music Master isolation test.

---

# 13. Repeat the whole fresh-bootstrap install

Do this **before switching current observations to WU**. Historical WU rainfall may later coexist with Ecowitt Push as the live source. This repeat-install gate proves ordinary appliance idempotence; Section 14.5 separately proves that a subsequently commissioned WU history credential survives Ecowitt weather reconvergence.

```bash
set -o pipefail
"${EQ_CMD[@]}" 2>&1 | tee "$EVIDENCE/50-repeat-install.txt"
rc=${PIPESTATUS[0]}
test "$rc" -eq 0

bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/51-repeat-bootstrap-verifier.txt"

bash scripts/verify-appliance.sh \
  --audio eq --weather-observations ecowitt-push \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/52-repeat-appliance-verifier.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/53-repeat-audio-verifier.txt"
```

Require normal commit markers, no renewed reboot/claim checkpoint, no ownership drift and PASS from all three verifiers.

---

# 14. Commission Weather Underground through Settings

Do this locally after the repeat installer gate for a full fresh-card run. WU credentials are write-only commissioning data, not fresh-install CLI material.

For the current focused Weather retest on the already-accepted Direct spare card, **14.1 through the selected-period portion of 14.3 and 14.5 have physically passed**. Do not rerun them merely to regain context. Continue with the Rainy Day Fund/backfill checks in **14.6**, then return to Section 8.

Open **Settings → Weather → Observation source**.

## 14.1 Current observation source and write-only credential commissioning

1. Confirm **Observation source** is a distinct Weather subpage rather than being mixed into Station settings.
2. Confirm the live-source state is a proper bordered badge at the **top-right of the Observation source card** and truthfully reports Ecowitt Push, WU Ready or an appropriate setup/degraded state.
3. Confirm Historical rainfall has its own bordered status badge at the **top-right of the Historical rainfall card**.
4. Confirm Observation source cards and their internal grids have clear touch-friendly separation on both supported landscape targets, including 1024×600.
5. Ecowitt may remain the current-observation provider while WU supplies historical rainfall.
6. Enter the real WU Station ID and save ordinary Weather settings.
7. Use **Set API key** / **Replace API key** and type the key only into the local Settings control.
8. If Weather Underground is selected as the **live** provider, press **Test connection** and require a sanitized success result. If Ecowitt remains live, do not switch providers merely to satisfy this button: prove the same commissioned WU credential through successful supplemental historical-rainfall requests.
9. After submission, only configured/not-configured status may be returned; never the stored key.

Check secret-file metadata without printing its contents:

```bash
sudo stat -c '%a %U:%G %n' /etc/default/a-clockwork-plex-weather \
  | tee "$EVIDENCE/60-wu-secret-metadata.txt"
```

Require root ownership and mode `600`.

Confirm `config.json` contains no literal WU secret field:

```bash
python3 - <<'PY' | tee "$EVIDENCE/61-wu-config-secret-check.txt"
import json
from pathlib import Path
cfg = json.loads(Path('config.json').read_text(encoding='utf-8'))
weather = cfg.get('weather') if isinstance(cfg.get('weather'), dict) else {}
wu = weather.get('weather_underground') if isinstance(weather.get('weather_underground'), dict) else {}
forbidden = {'api_key', 'apikey', 'password', 'secret', 'token'}
found = sorted(str(k) for k in wu if str(k).lower() in forbidden)
print('WU_CONFIG_SECRET_FIELDS=' + (','.join(found) if found else 'NONE'))
raise SystemExit(1 if found else 0)
PY
```

Require `WU_CONFIG_SECRET_FIELDS=NONE`.

**Current physical result:** PASS. The real credential is commissioned write-only, Ecowitt Push remains live, History ready is healthy, config contains no WU secret field, and the managed secret remains root-owned mode `600`.

## 14.2 Historical rainfall periods

Exercise and save all four supported configurable periods:

- **Today** — live station `dailyrainin`; no WU historical request required for this selected total.
- **Last 7 days** — completed days plus today live.
- **Current month** — completed month dates plus today live.
- **Current year** — completed year dates plus today live.

After each selection:

```bash
curl -fsS http://localhost:8088/api/weather/rainfall \
  | python3 -m json.tool \
  | tee -a "$EVIDENCE/63-rainfall-history-health.json"
```

Interpretation is now deliberately split between **calculation completeness** and **station coverage**:

- `complete: true` means every required completed date is either recorded or has been confirmed, by a successful targeted WU request, as having no station data.
- `coverage_complete: true` means every date actually has a recorded total.
- `complete: true` with `coverage_complete: false` is valid when confirmed station-offline dates exist. `total_in` remains numeric and is the **minimum recorded** rainfall; the UI must state how many days were not recorded.
- `pending_days > 0` means unresolved dates remain and the calculation is not complete.
- An actual provider/configuration/credential failure is a separate error state and must not take current observations down.

**Current physical result:** Today, Last 7 days, Current month and Current year are accepted. Current year physically returned 226 of 229 days with three confirmed station gaps (`2026-03-03`, `2026-03-05`, `2026-03-07`), `status: ready`, `complete: true`, `coverage_complete: false`, `pending_days: 0` and `total_in: 21.38`. Settings showed **History ready** and the explicit minimum-recorded coverage message.

## 14.3 Cache reuse, confirmed gaps and secret absence

For the selected Current-year calculation, refresh twice:

```bash
curl -fsS -X POST http://localhost:8088/api/weather/rainfall \
  | python3 -m json.tool \
  | tee "$EVIDENCE/64-rainfall-refresh-first.json"

curl -fsS -X POST http://localhost:8088/api/weather/rainfall \
  | python3 -m json.tool \
  | tee "$EVIDENCE/65-rainfall-refresh-second.json"
```

Once selected-period days are cached or confirmed as station gaps, repeated refreshes must report `"fetched_ranges": 0` and `"retried_dates": 0` unless a genuinely new completed day has appeared since the prior refresh.

The production service also prepares Rainy Day Fund comparison periods. On the **first refresh after enabling the expanded gauge history**, `gauge_fetched_ranges` may be nonzero while the previous calendar year is backfilled in ranges of at most 31 days. After that backfill has either recorded or gap-classified all returned dates, a second refresh must report `"gauge_fetched_ranges": 0` and `"gauge_retried_dates": 0`.

Inspect `weather-rainfall-history.json` structurally and require:

- cache version `1`;
- at least one cached station/day after fill;
- no keys named `api_key`, `apikey`, `password`, `secret` or `token`;
- every value under `days` is a finite non-negative numeric total;
- no `null` day markers;
- any accepted value under `gaps` is exactly `no_station_data`.

Retry/gap semantics are deliberate:

- a date omitted from a successful multi-day response is retried once as a single-day WU request;
- if that successful single-day request still has no usable daily record, the date becomes a confirmed station-data gap;
- confirmed gaps are retained separately from numeric totals and are not repeatedly fetched;
- they reduce coverage but do not turn an otherwise successful history calculation into an API error;
- if an old cache contains a legacy `null` day marker, it remains retryable and may be replaced by valid data;
- actual WU request/configuration/credential failures remain errors and are never silently relabelled as station gaps.

Do not corrupt the real provider or credential merely to manufacture an omission/failure. Source regression tests cover synthetic gap/recovery and provider-error paths.

**Current selected-period physical result:** PASS. Two Current-year POSTs both returned `fetched_ranges: 0`, `retried_dates: 0`, three stable confirmed gaps and the same numeric minimum-recorded total.

## 14.4 Supplemental failure behaviour

If a WU history request is naturally unavailable, require current Ecowitt/WU observations and the normal Weather page to remain operational, no credential material in error output, and the appropriate selected-period/gauge diagnostic to report the failure. Do not corrupt the real API key merely to manufacture a failure already covered by source tests.

The expanded Rainy Day Fund backfill uses separate `gauge_status` / `gauge_last_error` diagnostics so failure to fetch an older comparison period does not falsely turn an otherwise valid selected-period calculation into **History incomplete**.

## 14.5 Ecowitt reconvergence must preserve the commissioned WU history credential

This checkpoint deliberately exercises only the guarded Weather configuration owner, so it does **not** touch Direct/EQ routing, mixers, alarm behavior or playback services and it does not restart the dashboard.

With the WU key already commissioned and **Ecowitt Push** selected for live observations, compare the managed secret before/after without ever printing its contents or digest:

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"

test -f /etc/default/a-clockwork-plex-weather
WU_SECRET_BEFORE="$(sudo sha256sum /etc/default/a-clockwork-plex-weather | awk '{print $1}')"

sudo bash scripts/install-weather-config.sh \
  --activate \
  --confirm INSTALL-WEATHER-CONFIG \
  --provider ecowitt-push \
  | tee "$EVIDENCE/66-ecowitt-weather-reconvergence.txt"

WU_SECRET_AFTER="$(sudo sha256sum /etc/default/a-clockwork-plex-weather | awk '{print $1}')"
if [[ -n "$WU_SECRET_BEFORE" && "$WU_SECRET_BEFORE" == "$WU_SECRET_AFTER" ]]; then
  echo 'WU_HISTORY_CREDENTIAL_PRESERVED=PASS' \
    | tee "$EVIDENCE/67-wu-credential-preservation.txt"
else
  echo 'WU_HISTORY_CREDENTIAL_PRESERVED=FAIL' \
    | tee "$EVIDENCE/67-wu-credential-preservation.txt"
  unset WU_SECRET_BEFORE WU_SECRET_AFTER
  false
fi
unset WU_SECRET_BEFORE WU_SECRET_AFTER

sudo stat -c '%a %U:%G %n' /etc/default/a-clockwork-plex-weather \
  | tee -a "$EVIDENCE/67-wu-credential-preservation.txt"
```

Require:

```text
WEATHER_PROVIDER=ecowitt_push
WEATHER_FORECAST=OPEN-METEO-PRESERVED
WEATHER_SECRET_POLICY=ENV-FILE-ONLY
WU_HISTORY_CREDENTIAL_PRESERVED=PASS
```

The final `stat` must still report root ownership and mode `600`. The command output/evidence must contain no key material and no key digest. Source regression coverage separately proves that if no managed WU credential exists, Ecowitt activation preserves that absence rather than creating a file.

**Current physical result:** PASS and recorded in `docs/weather-physical-followup-2026-08-17.md`.

## 14.6 Rainy Day Fund historical gauges

This is the remaining focused Weather gate on the current Direct spare card.

The detailed Weather page must present independent historical summaries rather than merely mirroring whichever single period is selected in Settings:

- **Rain this week** — Monday through today;
- **Rain last week** — previous Monday through Sunday;
- **Rain this month**;
- **Rain last month**;
- **Rain this year**;
- **Rain last year**;
- **Total rain** only when Ecowitt actually supplies the station-lifetime `totalrainin` counter.

After loading the latest green source and restarting only `a-clockwork-plex.service`, force one rainfall refresh. Existing current-year data should remain cached; the first run may backfill the previous calendar year and therefore report nonzero `gauge_fetched_ranges` / `gauge_retried_dates`.

Force a second refresh after the first has completed. Require:

```text
fetched_ranges: 0
gauge_fetched_ranges: 0
gauge_retried_dates: 0
```

assuming no new completed date arrived between the two calls.

On the physical display require:

1. the six calendar gauges above are present once their data is resolved;
2. station-lifetime Total appears only if supplied by Ecowitt;
3. the Rainy Day Fund row scrolls horizontally by touch and remains readable at 1280×720 and 1024×600;
4. confirmed gaps add concise per-gauge copy such as **3 days not recorded** rather than suppressing the numeric gauge;
5. the Current-year gauge agrees with the selected-period API total for the same moment (physically 21.38 inches at the accepted checkpoint, subject only to subsequent live rainfall changing today’s contribution);
6. Ecowitt live observation remains healthy throughout.

The earlier physically blank Rainy Day Fund was traced to the rainfall wrapper patching the `app.main` facade while Flask's context processor resolved `dashboard_core.weather_detail_data`. Source commit `6316a63fbc109967ccd517a631796be01b859ba2` patches the actual core projection and has full CI coverage. Do not treat the old blank-gauge result as a WU data failure.

---

# 15. Final acceptance record

Commit/finalize a dated result document under `docs/` containing the spare-SD OS/test hostname, exact branch SHA, hardware/DAC result, Plexamp claim result, Direct result, NFC/AirPlay/alarm result, EQ result, reboot result, repeat-install result, WU Settings commissioning result, all four selected historical-rainfall results, any natural station gaps and minimum-recorded coverage, Rainy Day Fund current/previous week/month/year + optional lifetime Total result, horizontal-scroll result, Ecowitt credential-preservation result, cache structural/secret check and all deviations.

**Phase 7 does not close until that physical result is committed and reviewed.**
PR #2 remains Draft/open/unmerged until the owner separately approves release/merge.

---

## Recovery after the spare-SD experiment

If the test card fails catastrophically: power down, remove the spare card, reinsert the untouched accepted production SD card, power up, and verify the accepted production appliance. This acceptance route does not update Pi EEPROM/bootloader or HAT firmware, so the SD card remains the software recovery boundary.
