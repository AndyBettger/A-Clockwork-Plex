# Fresh appliance physical acceptance runbook

**Status:** Phase 7 spare-SD physical acceptance procedure  
**Branch under test:** `feature/alarm-engine`  
**Updated:** 16 August 2026

## Purpose

Prove that A Clockwork Plex can be built on a genuinely fresh Raspberry Pi OS
installation using the real bedroom Pi/HAT/display hardware **without touching the
accepted production SD card**.

The test covers:

- fresh package and paired Python-environment bootstrap;
- I2C/PN532 and Raspberry Pi DAC Pro commissioning;
- pinned Plexamp Headless + Node runtime and local interactive Plex claim;
- pinned NFC listener;
- dashboard/kiosk/AirPlay/alarm-safe Direct audio;
- EQ promotion using the exact accepted CamillaDSP 4.1.3 executable;
- reboot/resume and repeat-install idempotence;
- Weather Underground commissioning through Settings using the write-only secret path;
- historical rainfall acceptance for Today / Last 7 days / Current month / Current year, including cache reuse and live-observation isolation.

This is intentionally destructive **only to the spare SD card**. The accepted
production card is the rollback mechanism: remove it before this procedure and keep
it physically separate until testing is complete.

---

# 0. Stop rules and accepted identities

Stop on the first unexplained failure. Do not “fix forward” blindly during an
acceptance run; record what failed first.

- Power the Pi down before removing/reseating HATs, display cables or SD cards.
- Remove the accepted production SD card and label/store it somewhere safe before
  the spare card is inserted.
- Do not update Pi EEPROM/bootloader, audio-HAT EEPROM or hardware firmware during
  this run. The installer intentionally does not do those things.
- Run installers as the normal appliance user, never as root.
- Never paste the Weather Underground API key or Plex claim code into chat, evidence,
  `config.json` or a normal installer argument.
- Do not substitute an unverified Plexamp, Node or CamillaDSP artifact.
- A dashboard that merely opens is not acceptance. Both software verifiers and the
  physical audio/NFC/alarm/weather checks must pass.
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
| DAC | Raspberry Pi DAC Pro, accepted ALSA card id `Pro` |
| DAC fallback overlay | `rpi-dacpro` only when required by commissioning |
| Forecast provider | Open-Meteo |
| Root activation token | `APPLY-A-CLOCKWORK-PLEX` |

The historical Phase 6 Direct rollback `08d00093...` remains historical evidence;
it is deliberately not the fresh Direct target.

---

# 1. Rebuild the physical appliance and protect production state

1. Shut down the working appliance normally.
2. Disconnect power.
3. Remove the accepted production SD card.
4. Label/store that card safely. **Do not reformat it for this test.**
5. With the Pi still unpowered, carry out the intended physical tidy-up:
   - correct-length internal cables;
   - HATs properly seated;
   - proper standoffs/screws rather than temporary support;
   - display/audio/power wiring routed without strain.
6. Insert the spare SD card only after the physical rebuild is complete.

The test uses the same Pi/HAT/display hardware, which is desirable: it proves the
installer against the actual appliance hardware while the known-good software card
remains untouched.

---

# 2. Flash a genuinely fresh Raspberry Pi OS card

Use Raspberry Pi Imager and install a current **64-bit Raspberry Pi OS with Desktop**.
The desktop build is required because the finished appliance owns Chromium kiosk
startup as well as the headless services.

In Imager, preconfigure:

- the normal appliance username;
- a **test hostname** distinct from the production installation, for example
  `plexamp-test`;
- network/Wi-Fi as needed;
- locale/timezone;
- SSH if desired.

Do not preinstall Plexamp, Shairport Sync, NFC libraries, audio routing, CamillaDSP
or A Clockwork Plex services manually.

After first boot:

```bash
hostname -s
id
uname -m
cat /etc/os-release
```

Require `aarch64`/64-bit Raspberry Pi OS and record the test hostname.

---

# 3. Obtain the source tree — the only source-bootstrap exception

The repository must exist before its own installer can run. This is the one
unavoidable bootstrap boundary.

If `git` is already available on the fresh image:

```bash
cd ~
git clone --branch feature/alarm-engine https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
```

If `git` is not available, copy the exact `feature/alarm-engine` source tree from a
trusted development machine to `~/A-Clockwork-Plex`; do not manually install the
rest of the appliance dependencies. The guarded package stage owns `git` from then
on.

Record the exact source identity when `.git` is present:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
```

Require branch `feature/alarm-engine`, the latest green source head selected for the
acceptance run, and a clean tree. **Do not deliberately reset to historical checkpoint
#26; the physical spare-SD progress has moved beyond it.**

---

# 4. Create the acceptance evidence directory

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$HOME/acp-phase7-spare-sd-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE"
printf '%s\n' "$EVIDENCE" > "$HOME/.acp-phase7-evidence-path"
```

Capture the untouched fresh-card state:

```bash
{
  date --iso-8601=seconds
  hostnamectl || true
  uname -a
  cat /etc/os-release
  echo '--- source ---'
  git branch --show-current 2>/dev/null || true
  git rev-parse HEAD 2>/dev/null || true
  git status --short 2>/dev/null || true
  echo '--- cards before bootstrap ---'
  cat /proc/asound/cards 2>/dev/null || true
  echo '--- i2c before bootstrap ---'
  ls -l /dev/i2c-* 2>/dev/null || true
  echo '--- relevant services before bootstrap ---'
  for u in plexamp.service nfc-listener.service shairport-sync.service a-clockwork-plex.service; do
    systemctl show "$u" -p LoadState -p ActiveState -p UnitFileState 2>/dev/null || true
  done
} | tee "$EVIDENCE/00-fresh-baseline.txt"
```

It is completely acceptable — and expected — for Plexamp/NFC/application services
and even `CARD=Pro` to be absent on a genuinely new card. On the currently reused
spare acceptance card, previously accepted bootstrap state may already be present;
the installer must revalidate/converge it rather than assuming it.

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

Require the plan to show this order:

1. package/artifact check;
2. fresh stage-zero preflight;
3. package + paired main/NFC venv bootstrap;
4. Pi hardware commissioning;
5. player-pending gate;
6. pinned Plexamp runtime;
7. pinned NFC listener;
8. full host preflight;
9. application transaction/verifier.

The plan itself must make no production change.

---

# 6. Fresh Direct apply — controlled resume loop

Use `pipefail` so `tee` does not hide the installer's real exit code. Every rerun
gets its own timestamped log so earlier failed-attempt evidence is never overwritten:

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

There are three valid controlled outcomes.

## A. Exit `75` — reboot required

This is a **controlled checkpoint**, not a failure. Typical reasons are enabling
I2C or installing the reviewed DAC Pro boot block.

Require output containing:

```text
ROOT_INSTALL=REBOOT-REQUIRED
REBOOT_POLICY=OPERATOR-CONTROLLED
```

Then:

```bash
sudo reboot
```

After reconnecting:

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"
set -o pipefail
```

Recreate `DIRECT_CMD` and a new timestamped `DIRECT_LOG` from above and run it again.
Already-successful bootstrap stages are expected to revalidate/idempotently converge
rather than being blindly assumed.

## B. Exit `76` — Plexamp claim required

The pinned Node and Plexamp runtimes have been installed and verified, but no Plex
account/player state exists yet. This is the intended human authentication boundary.

Run Plexamp locally in the foreground:

```bash
cd ~/plexamp
/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node js/index.js
```

When Plexamp prompts:

1. obtain a **fresh** claim code from `https://plex.tv/claim` on your own device;
2. enter it directly into the local Plexamp prompt;
3. enter the desired player name;
4. wait until Plexamp reports that it has started successfully;
5. press `Ctrl-C` to stop the foreground process.

Do not save the claim code into evidence or pass it back to `install.sh`.

Return to the repository, recreate `DIRECT_CMD` plus a new timestamped `DIRECT_LOG`,
and run it again.

## C. Exit `0` — committed

Require:

```text
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=fresh-bootstrap
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

For the current reused spare-SD acceptance run, this is the expected next result
after the protected-sudoers verifier correction. Any other exit code is an
acceptance failure: stop and preserve the evidence before repairing anything.

---

# 7. Verify the completed fresh substrate and Direct appliance

Run both independent verifiers:

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

Also require the fresh Direct identity:

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/23-direct-route.sha256"
test ! -e /var/lib/a-clockwork-plex/split-bus/installed
```

Expected route SHA:

```text
654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9
```

Useful substrate spot checks:

```bash
systemctl --no-pager --full status plexamp.service nfc-listener.service || true
i2cdetect -y 1
aplay -l
```

PN532 must be visible at `0x24`; ALSA must expose `CARD=Pro`.

---

# 8. Physical Direct acceptance

## Dashboard / kiosk / Plexamp

- Dashboard, Settings and Clock render normally.
- Chromium kiosk launches once after a normal desktop login/restart.
- Embedded Plexamp UI loads and is usable.
- Play a familiar Plexamp track and require clean stable stereo playback.

## NFC

Scan a known Plexamp album tag.

Require all of the following:

- PN532 scan is detected;
- the tag triggers local Plexamp playback;
- the dashboard switches to the Plexamp display;
- repeated immediate scans are debounced rather than starting a storm of requests.

## AirPlay

- Connect from the normal sender/iPhone.
- Require clean stereo and the accepted PlaybackCoordinator takeover.
- End/pause AirPlay and require normal return without restarting the whole audio graph.

## Music Master / alarm isolation

1. Start music.
2. Set **Music Master = 0%**; music must become silent.
3. Trigger a real scheduled alarm; the alarm must remain audible.
4. Exercise Snooze/Dismiss.
5. Restore Music Master; music must return at the expected level.

## Direct-mode EQ truthfulness

Settings → Audio/EQ must show:

```text
Install required
```

Direct mode must not claim that EQ is installed/configured.

Record physical notes in `$EVIDENCE/24-direct-physical-notes.txt`.

---

# 9. Acquire the exact accepted CamillaDSP artifact

Do not manually hunt for a similarly named binary. Use the guarded repository
fetcher, which verifies both the official v4.1.3 aarch64 release archive and the
exact executable identity already accepted by A Clockwork Plex.

Plan:

```bash
bash scripts/fetch-camilladsp-4.1.3.sh \
  | tee "$EVIDENCE/30-camilladsp-plan.txt"
```

Acquire:

```bash
bash scripts/fetch-camilladsp-4.1.3.sh \
  --activate \
  --confirm FETCH-CAMILLADSP-4.1.3 \
  | tee "$EVIDENCE/31-camilladsp-fetch.txt"
```

Set the deterministic resulting path:

```bash
CAMILLA="$HOME/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp"
"$CAMILLA" --version
sha256sum "$CAMILLA"
```

Require version `4.1.3` and executable SHA:

```text
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

---

# 10. Promote the same fresh appliance to EQ

Plan:

```bash
bash install.sh \
  --fresh-bootstrap \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --non-interactive \
  | tee "$EVIDENCE/32-eq-plan.txt"
```

Apply:

```bash
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

Because hardware, Plexamp claim and NFC are already commissioned, no claim or
hardware reboot checkpoint should normally reappear here. If one does, stop and
understand why rather than bypassing it.

Verify:

```bash
bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/34-eq-bootstrap-verify.txt"

bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/35-eq-appliance-verify.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/36-eq-audio-verify.txt"
```

All three must pass.

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/37-eq-route.sha256"
test -f /var/lib/a-clockwork-plex/split-bus/installed
```

Expected EQ route SHA:

```text
1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9
```

---

# 11. Physical EQ acceptance

- Plexamp and AirPlay both play cleanly through the EQ graph.
- Change Bass/Mid/Treble one at a time using a familiar track and confirm plausible
  audible changes.
- Toggle EQ bypass and require processing to leave/return without changing alarm loudness.
- Music Master = 0% must silence music while a real alarm remains audible.
- **Maximum Alarm Volume** must independently govern the alarm ceiling.
- Snooze/Dismiss normally.
- Confirm NFC still starts Plexamp playback and switches the display after EQ promotion.

Do not manufacture another Camilla failure merely for drama; Phase 6 already proved
physical automatic failback. The fresh-install test is proving construction,
reboot and repeatability.

---

# 12. Reboot acceptance

```bash
sudo reboot
```

After reconnecting:

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"
CAMILLA="$HOME/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp"

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

Require all three to pass. Recheck kiosk startup, short Plexamp playback, one NFC
tag and one real alarm/Music Master isolation test.

---

# 13. Repeat the whole fresh-bootstrap install

Do this **before switching current observations to WU**, because the repeat install
intentionally reapplies the selected Ecowitt test profile. Historical WU rainfall is
commissioned afterwards and may then coexist with Ecowitt Push as the live source.

Recreate `EQ_CMD` from section 10 if this is a new shell, then:

```bash
set -o pipefail
"${EQ_CMD[@]}" 2>&1 | tee "$EVIDENCE/50-repeat-install.txt"
rc=${PIPESTATUS[0]}
test "$rc" -eq 0
```

Require normal commit markers, no reboot/claim prompt and no ownership drift.

Then repeat all three verifiers:

```bash
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

Require PASS from all three.

---

# 14. Commission Weather Underground through Settings

This section also performs the historical-rainfall acceptance. WU commissioning is
deliberately **not** a fresh-install command-line secret step. Do this on the local
dashboard after the repeat installer test has passed.

Open **Settings → Weather → Observation source**.

## 14.1 Current observation source and write-only WU commissioning

1. Confirm the top-right source chip truthfully matches the current live provider:
   **Ecowitt Push** when Ecowitt supplies live observations, or **WU Ready** after a
   healthy WU-current configuration.
2. The live provider may remain **Ecowitt custom push** for this acceptance. WU
   historical rainfall is independent of the current-observation choice.
3. Enter the real WU Station ID and save the ordinary Weather settings.
4. Use **Set API key** / **Replace API key** and type the key locally.
5. Press **Test connection** and require a sanitized success result.
6. After submission, the page must show only configured/not-configured status —
   never the stored key.

Do not paste the key into a terminal or evidence file.

Secret-storage metadata only:

```bash
sudo stat -c '%a %U:%G %n' /etc/default/a-clockwork-plex-weather \
  | tee "$EVIDENCE/60-wu-secret-metadata.txt"
```

Require root ownership and mode `600`.

Confirm `config.json` has no literal WU secret-like field:

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

Require:

```text
WU_CONFIG_SECRET_FIELDS=NONE
```

Inspect current-observation health without printing the key:

```bash
curl -fsS http://localhost:8088/api/weather/observations \
  | python3 -m json.tool \
  | tee "$EVIDENCE/62-wu-observation-health.json"
```

If WU is the live source, require a real recent observation. If Ecowitt remains the
live source, require healthy Ecowitt current observations while WU remains available
for history.

## 14.2 Exercise all four rainfall periods

In **Historical rainfall**, save and verify each option:

1. **Today** — must continue to use the current live station Rain Today value. It
   must not require a historical WU request merely to calculate today.
2. **Last 7 days** — six completed dates plus today's live total.
3. **Current month** — completed dates from the first of the month plus today live.
4. **Current year** — completed dates from 1 January plus today live.

After each save, inspect the sanitized history status:

```bash
curl -fsS http://localhost:8088/api/weather/rainfall \
  | python3 -m json.tool \
  | tee -a "$EVIDENCE/63-rainfall-history-health.json"
```

Require `complete: true` before accepting a displayed aggregate. If required dates
are unavailable, the UI/API must report incomplete history and must **not** show a
partial aggregate as though it were complete.

The Weather page's **Rainy Day Fund** must show the selected non-Today historical
aggregate while the existing Rain Today reading remains live and unchanged.

## 14.3 Prove cache reuse

With **Current year** selected and its first fill complete, explicitly request two
refreshes:

```bash
curl -fsS -X POST http://localhost:8088/api/weather/rainfall \
  | python3 -m json.tool \
  | tee "$EVIDENCE/64-rainfall-refresh-first.json"

curl -fsS -X POST http://localhost:8088/api/weather/rainfall \
  | python3 -m json.tool \
  | tee "$EVIDENCE/65-rainfall-refresh-second.json"
```

The second completed refresh must report:

```text
"fetched_ranges": 0
```

This proves completed dates are reused from the local cache rather than downloading
the year repeatedly. Today's live total is deliberately not persisted as a completed
historical day.

Inspect cache structure without exposing credentials:

```bash
python3 - <<'PY' | tee "$EVIDENCE/66-rainfall-cache-check.txt"
import json
from pathlib import Path

path = Path('weather-rainfall-history.json')
data = json.loads(path.read_text(encoding='utf-8'))
forbidden = {'api_key', 'apikey', 'password', 'secret', 'token'}
found = []

def walk(value, where='root'):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                found.append(f'{where}.{key}')
            walk(child, f'{where}.{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, f'{where}[{index}]')

walk(data)
stations = data.get('stations') if isinstance(data.get('stations'), dict) else {}
day_count = 0
for station in stations.values():
    if isinstance(station, dict) and isinstance(station.get('days'), dict):
        day_count += len(station['days'])
print(f'RAINFALL_CACHE_VERSION={data.get("version")}')
print(f'RAINFALL_CACHE_STATIONS={len(stations)}')
print(f'RAINFALL_CACHE_DAYS={day_count}')
print('RAINFALL_CACHE_SECRET_FIELDS=' + (','.join(found) if found else 'NONE'))
raise SystemExit(1 if found else 0)
PY
```

Require version `1`, at least one station/day after historical fill, and:

```text
RAINFALL_CACHE_SECRET_FIELDS=NONE
```

## 14.4 Supplemental-failure behaviour

Historical rainfall is supplementary. If a history request is unavailable during
acceptance, record that fact but require all of the following:

- current Ecowitt/WU observations still update normally;
- the normal Weather screen still renders current readings;
- no API key appears in the history error/status output;
- an incomplete historical period is marked incomplete and no misleading partial
  total is displayed.

Do not deliberately corrupt the real API key just to manufacture this failure if a
natural provider failure is not available; source/CI coverage already exercises the
failure path.

---

# 15. Final acceptance record

Create a short dated result document under `docs/` recording:

- spare-SD Raspberry Pi OS version and test hostname;
- exact `feature/alarm-engine` commit tested;
- whether DAC Pro was EEPROM-discovered or required the managed `rpi-dacpro` reboot;
- Plexamp claim checkpoint result;
- Direct verifier + physical result;
- EQ verifier + physical result;
- reboot result;
- repeat-install/idempotence result;
- NFC/AirPlay/alarm result;
- real WU Settings/Test Connection result;
- Observation Source/current-provider result and all four historical-rainfall period/cache results;
- any deviations or repairs required.

**Phase 7 does not close until that physical result is committed and reviewed.**
PR #2 remains Draft/open/unmerged until the owner separately approves release/merge.

---

## Recovery after the spare-SD experiment

If the test card fails catastrophically, that is still safe evidence:

1. power the Pi down;
2. remove the spare test card;
3. reinsert the untouched accepted production SD card;
4. power the rebuilt hardware back on;
5. verify the accepted production appliance normally.

Because this acceptance route does not update Pi EEPROM/bootloader or HAT firmware,
the software rollback boundary remains the SD card rather than hidden persistent
firmware state.
