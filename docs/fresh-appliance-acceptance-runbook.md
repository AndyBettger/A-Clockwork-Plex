# Fresh appliance physical acceptance runbook

**Status:** Phase 7 physical acceptance procedure  
**Branch under test:** `feature/alarm-engine`  
**Prepared:** 11 August 2026

## Purpose

Prove that the guarded root installer can build a new A Clockwork Plex appliance on a fresh/disposable Raspberry Pi, promote it from Direct to EQ, accept real Weather Underground input, survive reboot and repeat the whole installation without ownership drift.

This is **not** a rehearsal on the accepted bedroom appliance. Phase 6 already supplied the physical EQ/failback evidence there.

## Stop rules

Stop on the first failed gate or unexplained difference.

- **Never run this procedure on `plexamp-bedroom`.**
- Run root `install.sh --apply` as the normal project user, never as root.
- Never put the WU API key in a literal shell argument, chat, `config.json`, browser state or evidence file.
- Never substitute an unverified CamillaDSP binary.
- Record a failed transaction before attempting repair/retry.
- A dashboard that opens is not an acceptance result; the verifier and physical audio tests must pass.
- WU history is inspection evidence only. Do not feed it into runtime barometer history during this run.

## Accepted identities

| Item | Required value |
|---|---|
| Fresh alarm-safe Direct route | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` |
| EQ split-bus route | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` |
| CamillaDSP | `4.1.3` aarch64 |
| CamillaDSP SHA-256 | `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |
| Forecast provider | Open-Meteo |
| Root activation token | `APPLY-A-CLOCKWORK-PLEX` |

The historical bedroom-Pi Direct rollback `08d00093...` is deliberately **not** the fresh Direct target.

---

# 1. Identify the disposable target

Use a fresh/disposable Raspberry Pi with the intended DAC/display hardware. The DAC must already be visible to ALSA as card id `Pro`; board-level/I2S commissioning is outside repository ownership.

```bash
hostname -s
id
uname -a
cat /etc/os-release

if [ "$(hostname -s)" = "plexamp-bedroom" ]; then
    echo 'STOP: this is the accepted bedroom appliance; do not run Phase 7 here.' >&2
    exit 1
fi
```

Record the target hostname and OS.

## External prerequisite: Plexamp Headless

Plexamp Headless remains external to this repository.

Before package bootstrap require at least:

```bash
systemctl cat plexamp.service
systemctl is-enabled plexamp.service || true
systemctl is-active plexamp.service || true
```

If `curl` already exists, the local API may also be checked now:

```bash
if command -v curl >/dev/null 2>&1; then
    curl -fsS http://localhost:32500/player/playback/pause >/dev/null
fi
```

Do not install `curl` manually just for this check; it is owned by the guarded package bootstrap. The full physical Plexamp/API check occurs after bootstrap.

## Source-tree bootstrap

The source tree must exist before its installer can own `git`. Prefer copying the exact checkout from a development host (`scp`/similar) to the disposable target, then let the guarded package owner establish its declared packages. If Git is already on the fresh image, a normal clone is also acceptable.

```bash
cd ~/A-Clockwork-Plex
git branch --show-current 2>/dev/null || true
git rev-parse HEAD 2>/dev/null || true
git status --short 2>/dev/null || true
```

When `.git` is present require branch `feature/alarm-engine` and record the exact commit. When the tree was transferred without `.git`, record the source commit before transfer.

---

# 2. Capture untouched baseline

Create an evidence directory outside the repository and persist its path so it survives reboot:

```bash
EVIDENCE="$HOME/acp-phase7-acceptance-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE"
printf '%s\n' "$EVIDENCE" > "$HOME/.acp-phase7-evidence-path"
printf '%s\n' "$EVIDENCE"
```

Host/audio baseline:

```bash
{
    date --iso-8601=seconds
    hostnamectl || true
    uname -a
    cat /etc/os-release
    echo '--- ALSA cards ---'
    cat /proc/asound/cards || true
    echo '--- aplay -l ---'
    aplay -l || true
    echo '--- Pro mixer ---'
    amixer -c Pro || true
} | tee "$EVIDENCE/00-host-baseline.txt"
```

Service baseline:

```bash
for unit in \
    plexamp.service \
    shairport-sync.service \
    a-clockwork-plex.service \
    a-clockwork-plex-airplay-metadata.service \
    a-clockwork-plex-audio-route.service \
    a-clockwork-plex-camilladsp.service \
    a-clockwork-plex-audio-failback.service
do
    printf '\n[%s]\n' "$unit"
    systemctl show "$unit" -p LoadState -p ActiveState -p UnitFileState 2>/dev/null || true
done | tee "$EVIDENCE/01-services-before.txt"
```

Managed-path baseline:

```bash
{
    route=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
    if [ -f "$route" ] && [ ! -L "$route" ]; then
        sha256sum "$route"
        stat -c '%a %u:%g %n' "$route"
    else
        echo 'active route absent/non-regular'
    fi

    if [ -e /var/lib/a-clockwork-plex/split-bus/installed ]; then
        echo 'EQ marker present before acceptance'
    else
        echo 'EQ marker absent before acceptance'
    fi
} | tee "$EVIDENCE/02-managed-before.txt"
```

**Pass:** target is not the bedroom Pi, card id `Pro` is present, Plexamp service exists and baseline evidence is saved.

---

# 3. Read-only fresh Direct gates

Start with **Direct + Ecowitt push** to prove the appliance installer/alarm-safe Direct graph before adding CamillaDSP or WU.

```bash
bash install.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --non-interactive \
  | tee "$EVIDENCE/10-direct-plan.txt"
```

Require a read-only plan showing package/artifact check → pre-bootstrap platform gate → package/venv bootstrap → full host preflight → application transaction.

Package/artifact gate:

```bash
bash scripts/check-appliance-packages.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  | tee "$EVIDENCE/11-direct-package-check.txt"
```

Require `APPLIANCE_PACKAGE_CHECK=PASS`. Installer-owned missing packages may be `READY` if available from APT.

Pre-bootstrap platform/external gate:

```bash
bash scripts/preflight-appliance.sh \
  --bootstrap-pending \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  | tee "$EVIDENCE/12-direct-platform-preflight.txt"
```

Require `APPLIANCE_PREFLIGHT=PLATFORM-PASS`. Python/venv, ALSA utilities, Shairport Sync and Chromium may be `READY`; platform/user/DAC/external Plexamp requirements must pass now.

---

# 4. Guarded fresh Direct install

```bash
bash install.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --non-interactive \
  --apply \
  --confirm APPLY-A-CLOCKWORK-PLEX \
  | tee "$EVIDENCE/20-direct-install.txt"
```

Required success markers:

```text
ROOT_INSTALL=COMMITTED
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

If the transaction fails, stop.

Standalone Direct verification:

```bash
bash scripts/verify-appliance.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/21-direct-verifier.txt"
```

Require `APPLIANCE_VERIFY=PASS`.

Check route/no-EQ state:

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/22-direct-route.sha256"
test ! -e /var/lib/a-clockwork-plex/split-bus/installed
```

Require route SHA `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`.

Now `curl` is installer-owned and available; confirm Plexamp local API reachability:

```bash
curl -fsS http://localhost:32500/player/playback/pause >/dev/null
```

---

# 5. Physical Direct acceptance

## Dashboard/kiosk

- Dashboard/Settings/Clock render normally.
- Kiosk does not duplicate windows after normal desktop/session restart.

## Plexamp and AirPlay

- Known Plexamp track: clean stable stereo playback and correct dashboard state/artwork.
- AirPlay from normal iPhone/sender: clean stereo, accepted PlaybackCoordinator takeover and metadata state.
- Pause/end AirPlay: ordinary handoff must not depend on restarting the audio graph.

## Music Master / alarm isolation

1. Play music.
2. Set **Music Master = 0%**; music must become silent.
3. Trigger a real scheduled alarm; alarm must remain audible.
4. Snooze/Dismiss normally.
5. Restore Music Master; music returns at expected level.

## Direct-mode EQ truthfulness

Settings → Audio/EQ must show:

```text
Install required
```

The Direct profile must not pretend EQ is installed/configured.

Record physical notes under the evidence directory.

---

# 6. Prepare pinned CamillaDSP

The repository never silently downloads/substitutes CamillaDSP. Supply the reviewed 4.1.3 aarch64 executable through the trusted acquisition path used for accepted EQ work.

```bash
CAMILLA=/path/to/camilladsp-4.1.3-aarch64

test -f "$CAMILLA" && test -x "$CAMILLA" && test ! -L "$CAMILLA"
"$CAMILLA" --version
sha256sum "$CAMILLA"
```

Require version `4.1.3` and SHA:

```text
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

Do not manually copy an unverified binary into managed locations.

---

# 7. Guarded EQ promotion

Plan:

```bash
bash install.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --non-interactive \
  | tee "$EVIDENCE/30-eq-plan.txt"
```

Require fresh EQ to request `--baseline alarm-safe-direct` while preserving the standalone historical default contract.

Apply:

```bash
bash install.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --non-interactive \
  --apply \
  --confirm APPLY-A-CLOCKWORK-PLEX \
  | tee "$EVIDENCE/31-eq-install.txt"
```

Require root/application commit markers and no rollback warning.

Whole-appliance + specialist verification:

```bash
bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/32-eq-appliance-verify.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/33-eq-audio-verify.txt"
```

Require both to pass.

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/34-eq-route.sha256"
test -f /var/lib/a-clockwork-plex/split-bus/installed
```

Require EQ route SHA `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`.

---

# 8. Physical EQ acceptance

## Music paths and EQ

- Plexamp and AirPlay both play cleanly through the EQ-capable graph.
- Change Bass/Mid/Treble one at a time using a familiar track and confirm credible audible changes.
- Toggle EQ bypass and require processing to leave/return without changing alarm loudness.
- Return controls to the desired acceptance state; do not use extreme boosts merely for drama.

## Music Master / alarm isolation

1. Music playing.
2. Music Master = 0%; music silent.
3. Real scheduled alarm remains audible.
4. Verify **Maximum Alarm Volume** independently governs the alarm ceiling.
5. Snooze/Dismiss normally.
6. Restore Music Master; music returns as expected.

## Guarded repair plan only

Do not manufacture another destructive failure; Phase 6 already supplied physical failback evidence. Confirm the installed profile has the accepted non-mutating repair plan:

```bash
bash scripts/audio/repair-audio.sh \
  --prepare-only \
  --binary "$CAMILLA" \
  --project-user "$USER" \
  | tee "$EVIDENCE/35-eq-repair-plan.txt"
```

Activate repair only if a genuine accepted recovery reason arises.

---

# 9. Reboot acceptance

```bash
sudo reboot
```

After reconnecting, restore the persisted evidence path:

```bash
EVIDENCE="$(cat "$HOME/.acp-phase7-evidence-path")"
test -d "$EVIDENCE"
cd ~/A-Clockwork-Plex
```

Re-establish the Camilla artifact path if necessary:

```bash
CAMILLA=/path/to/camilladsp-4.1.3-aarch64
```

Run both verifiers:

```bash
bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/40-eq-after-reboot-appliance.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/41-eq-after-reboot-audio.txt"
```

Require both to pass. Recheck dashboard kiosk startup, short Plexamp playback and a real alarm/Music Master isolation test.

---

# 10. Prepare WU host secret

Never type the literal API key into a shell command.

```bash
WU_DIR="$HOME/.config/a-clockwork-plex"
WU_KEY_FILE="$WU_DIR/wu-api-key"
install -d -m 700 "$WU_DIR"
install -m 600 /dev/null "$WU_KEY_FILE"
nano "$WU_KEY_FILE"
```

Enter one key line in the editor, save and close. Set the non-secret station ID:

```bash
WU_STATION_ID='YOUR_STATION_ID'
```

Check metadata only:

```bash
stat -c '%a %U:%G %n' "$WU_KEY_FILE"
```

Do not `cat`, `head`, `tail`, `sed` or command-substitute the key into evidence.

---

# 11. Read-only real WU current/history inspection

```bash
./venv/bin/python scripts/inspect-weather-underground-payloads.py \
  --station-id "$WU_STATION_ID" \
  --api-key-file "$WU_KEY_FILE" \
  | tee "$EVIDENCE/50-wu-payload-inspection.txt"
```

Require:

```text
WU_PAYLOAD_INSPECTION=PASS
State mutation: none
```

Record current/history keys, observation counts, timestamp evidence and pressure-related paths.

Interpretation:

- `Like-for-like history candidate: NO` → no instantaneous history contract.
- `YES — REVIEW REQUIRED` → evidence deserves design review only.
- Neither result authorises history ingestion during this acceptance.

The appliance continues to accumulate barometer history from real current observations.

---

# 12. Guarded WU appliance apply

Keep EQ selected. Existing EQ installation will delegate to the guarded repair lifecycle rather than create a second first-install backup.

Plan:

```bash
bash install.sh \
  --audio eq \
  --weather-observations weather-underground \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --wu-station-id "$WU_STATION_ID" \
  --wu-api-key-file "$WU_KEY_FILE" \
  --non-interactive \
  | tee "$EVIDENCE/51-wu-plan.txt"
```

Apply:

```bash
bash install.sh \
  --audio eq \
  --weather-observations weather-underground \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --wu-station-id "$WU_STATION_ID" \
  --wu-api-key-file "$WU_KEY_FILE" \
  --non-interactive \
  --apply \
  --confirm APPLY-A-CLOCKWORK-PLEX \
  | tee "$EVIDENCE/52-wu-install.txt"
```

Require commit markers.

Standalone verifier using the same key-file contract:

```bash
bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations weather-underground \
  --weather-api-key-file "$WU_KEY_FILE" \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/53-wu-verifier.txt"
```

Require `APPLIANCE_VERIFY=PASS`.

Inspect the credential-free runtime API:

```bash
curl -fsS http://localhost:8088/api/weather/observations \
  | python3 -m json.tool \
  | tee "$EVIDENCE/54-wu-runtime-observations.json"
```

Verifier semantics allow `ready`, `pending` or `degraded`, but physical acceptance must eventually see a genuine current observation and compare temperature/humidity/pressure plausibility with the selected PWS. Do not accept permanent `pending` as physical success.

Managed secret metadata only:

```bash
sudo stat -c '%a %U:%G %n' /etc/default/a-clockwork-plex-weather \
  | tee "$EVIDENCE/55-wu-secret-metadata.txt"
```

Do not save `/etc/default/a-clockwork-plex-weather` contents into evidence. Confirm `config.json` contains station ID + environment-variable name and no literal key.

---

# 13. Repeat whole-appliance installation

Repeat the already-configured EQ + WU root apply:

```bash
bash install.sh \
  --audio eq \
  --weather-observations weather-underground \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --wu-station-id "$WU_STATION_ID" \
  --wu-api-key-file "$WU_KEY_FILE" \
  --non-interactive \
  --apply \
  --confirm APPLY-A-CLOCKWORK-PLEX \
  | tee "$EVIDENCE/60-repeat-install.txt"
```

Require:

- package bootstrap is already satisfied or makes only legitimate additive corrections;
- existing EQ delegates to guarded repair and preserves the original uninstall baseline;
- no duplicate dashboard/kiosk/AirPlay/helper ownership;
- final verifier passes and commit markers appear;
- physical Plexamp/AirPlay/alarm behaviour is unchanged.

Final standalone verifier:

```bash
bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations weather-underground \
  --weather-api-key-file "$WU_KEY_FILE" \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/61-repeat-verifier.txt"
```

---

# 14. Final evidence

```bash
{
    date --iso-8601=seconds
    hostname -s
    echo '--- route ---'
    sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
    echo '--- EQ marker ---'
    stat /var/lib/a-clockwork-plex/split-bus/installed
    echo '--- service states ---'
    for unit in \
        plexamp.service \
        shairport-sync.service \
        a-clockwork-plex.service \
        a-clockwork-plex-airplay-metadata.service \
        a-clockwork-plex-audio-route.service \
        a-clockwork-plex-camilladsp.service \
        a-clockwork-plex-audio-failback.service
    do
        systemctl show "$unit" -p LoadState -p ActiveState -p UnitFileState 2>/dev/null || true
    done
} | tee "$EVIDENCE/70-final-state.txt"
```

Create a dated physical result document in `docs/` containing:

- target model/hostname and exact source commit;
- pre-install state;
- Direct installer/verifier/route result;
- Direct Plexamp/AirPlay/Music Master/alarm/UI result;
- EQ installer/verifier/route result;
- EQ/bypass/Music Master/alarm/reboot result;
- WU payload-inspector evidence and explicit history-semantics decision;
- WU runtime result without secret content;
- repeat-install result;
- deviations/failures and whether rollback occurred.

Do not close Phase 7 until that evidence exists and all required physical gates pass.

## Acceptance checklist

- [ ] Disposable target identified; it is not `plexamp-bedroom`.
- [ ] External Plexamp Headless prerequisite passes.
- [ ] ALSA card id `Pro` passes.
- [ ] Baseline evidence captured and evidence path persisted across reboot.
- [ ] Direct package availability + pre-bootstrap platform gate pass.
- [ ] Root Direct install commits.
- [ ] Direct route is exact `654ff170...`.
- [ ] Direct Plexamp/AirPlay playback passes.
- [ ] Music Master 0 silences music but not a real alarm.
- [ ] Direct EQ UI says **Install required**.
- [ ] Pinned CamillaDSP 4.1.3 artifact/hash passes.
- [ ] Root EQ install commits.
- [ ] EQ route is exact `1bc69f...`; both verifiers pass.
- [ ] Physical EQ/bypass + alarm isolation passes.
- [ ] Reboot verification passes.
- [ ] WU key remains host-file-only and absent from evidence.
- [ ] Real WU current/history inspector passes; history remains inspection-only.
- [ ] WU runtime current observation is physically/plausibly accepted.
- [ ] Repeat whole-appliance install commits without ownership drift.
- [ ] Final physical result document is committed.
- [ ] PR #2 remains Draft/open/unmerged pending explicit owner approval.
