# Fresh appliance physical acceptance runbook

**Status:** Phase 7 physical acceptance procedure  
**Branch under test:** `feature/alarm-engine`  
**Date prepared:** 11 August 2026

## Purpose

This runbook proves that the guarded root installer can build a new A Clockwork Plex appliance from a fresh/disposable Raspberry Pi target and then repeat that installation without ownership drift.

It is **not** a bedroom-Pi rehearsal. The accepted bedroom appliance already carries the Phase 6 physical EQ/failback evidence and must remain untouched while Phase 7 fresh-appliance acceptance is performed.

## Non-negotiable stop rules

Stop immediately on the first failed gate or unexplained difference. Do not carry on to collect a mixture of Direct, EQ and weather symptoms from a known-bad state.

- Do **not** run this procedure on `plexamp-bedroom`.
- Do not run root `install.sh --apply` as `root`; use the normal project user.
- Do not paste the Weather Underground API key into chat, shell command arguments, `config.json`, browser state or evidence documents.
- Do not improvise an alternate CamillaDSP binary if the exact pinned artifact is unavailable.
- Do not manually repair a failed transaction before recording its output and captured state.
- Do not treat a dashboard that merely opens as a successful appliance install; the profile verifier and physical audio checks must pass.
- Do not promote Weather Underground history into runtime barometer state during this acceptance. The history payload is inspection evidence only.

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

# 1. Choose and identify the disposable target

Use a fresh/disposable Raspberry Pi with the intended DAC/display hardware. The DAC must already be visible to ALSA as card id `Pro`; the repository does not own board-level/I2S commissioning.

From the target, as the normal project user:

```bash
hostname -s
id
uname -a
cat /etc/os-release
```

Hard stop guard:

```bash
if [ "$(hostname -s)" = "plexamp-bedroom" ]; then
    echo 'STOP: this is the accepted bedroom appliance; do not run Phase 7 here.' >&2
    exit 1
fi
```

Record the chosen target hostname in the eventual physical result document.

## External prerequisite: Plexamp Headless

Plexamp Headless remains an external prerequisite rather than an installer-owned package. Before appliance installation:

```bash
systemctl cat plexamp.service
systemctl is-enabled plexamp.service || true
systemctl is-active plexamp.service || true
curl -fsS http://localhost:32500/player/playback/pause >/dev/null
```

The pause request is only a reachability check; restore/confirm the desired idle state before physical playback testing.

**Pass:** `plexamp.service` exists and the local Plexamp control endpoint is reachable.

## Source-tree bootstrap

The installer can own `git` as a host package only after its own source tree exists. Therefore source delivery is a bootstrap transport concern, not an excuse to create a second package owner.

Preferred acceptance approach: copy the exact repository working tree/checkout to the disposable target from a development machine (for example via `scp`/`rsync` over SSH), then let the guarded package bootstrap establish/verify its declared host packages. If Git is already present on the fresh image, a normal clone is also acceptable.

Once the repository is present:

```bash
cd ~/A-Clockwork-Plex
git branch --show-current 2>/dev/null || true
git rev-parse HEAD 2>/dev/null || true
git status --short 2>/dev/null || true
```

If using a Git checkout, require branch `feature/alarm-engine` and record the exact commit under test. If the source was transferred without `.git`, record the source commit separately before transfer.

---

# 2. Capture the untouched target baseline

Create an evidence directory outside the repository:

```bash
EVIDENCE="$HOME/acp-phase7-acceptance-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE"
printf '%s\n' "$EVIDENCE"
```

Capture read-only host/audio state:

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

Capture relevant service state without changing it:

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

Capture prior managed-path identity/absence:

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

**Pass:** target is not the bedroom Pi, ALSA card `Pro` is present, Plexamp external prerequisite exists, and the baseline is recorded.

---

# 3. Read-only fresh Direct gates

Start with the least complex appliance profile: **Direct + Ecowitt push**. This proves the full installer and alarm-safe Direct graph before adding CamillaDSP or WU.

## Root plan

```bash
bash install.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --non-interactive \
  | tee "$EVIDENCE/10-direct-plan.txt"
```

**Pass:** plan is read-only, names the two-stage preflight/package sequence and selects alarm-safe Direct.

## Package/artifact availability

```bash
bash scripts/check-appliance-packages.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  | tee "$EVIDENCE/11-direct-package-check.txt"
```

**Pass:** `APPLIANCE_PACKAGE_CHECK=PASS`. Missing installer-owned packages may be reported `READY` if available from the host package manager.

## Pre-bootstrap platform/external preflight

```bash
bash scripts/preflight-appliance.sh \
  --bootstrap-pending \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  | tee "$EVIDENCE/12-direct-platform-preflight.txt"
```

**Pass:** `APPLIANCE_PREFLIGHT=PLATFORM-PASS`.

At this stage installer-owned Python/venv, ALSA utilities, Shairport Sync and Chromium may be `READY`; platform, user, physical DAC and external Plexamp requirements must already pass.

---

# 4. Guarded fresh Direct install

Run as the normal project user:

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

The root installer will repeat the package check/platform gate, establish the additive package + verified-venv baseline, run full host preflight, then enter one application transaction.

**Required terminal success markers:**

```text
ROOT_INSTALL=COMMITTED
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

If the transaction fails, stop and preserve output. Do not continue to physical audio checks.

## Verify Direct end state

```bash
bash scripts/verify-appliance.sh \
  --audio direct \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/21-direct-verifier.txt"
```

Require:

```text
APPLIANCE_VERIFY=PASS
```

Check exact Direct route:

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/22-direct-route.sha256"
```

Require SHA:

```text
654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9
```

Require no EQ installed marker:

```bash
test ! -e /var/lib/a-clockwork-plex/split-bus/installed
```

---

# 5. Physical Direct acceptance

Use the real DAC/speakers and dashboard UI.

## Dashboard/kiosk

- Dashboard loads normally at the appliance display.
- Settings and Clock surfaces render correctly.
- Reopening/restarting the desktop session must not create duplicate kiosk windows.

## Plexamp

- Start known music through Plexamp.
- Confirm clean stereo playback with no obvious distortion/chopping.
- Confirm dashboard playback state/artwork behaves normally.

## AirPlay

- Start AirPlay from the iPhone/normal sender.
- Confirm it takes audio ownership according to the accepted PlaybackCoordinator behaviour.
- Confirm stable stereo output and metadata/dashboard state.
- End/pause AirPlay and confirm no unnecessary service restart is involved in ordinary handoff.

## Music Master / alarm isolation

With music playing:

1. set **Music Master = 0%**;
2. require Plexamp/AirPlay music to become silent;
3. trigger a real scheduled alarm through the normal alarm engine;
4. require the alarm to remain audible;
5. Snooze/Dismiss using the real UI;
6. restore Music Master and require normal music level to return.

**Pass:** the fresh Direct graph proves alarm bypass of Music Master through the physical DAC.

## Direct-mode EQ truthfulness

Open Settings → Audio/EQ while Direct is installed.

**Required UI health text:**

```text
Install required
```

EQ controls must not pretend that an EQ runtime is installed/configured.

Record physical result notes in `$EVIDENCE/23-direct-physical-notes.txt` or the final result document.

---

# 6. Prepare the pinned CamillaDSP artifact

The repository deliberately does not silently download CamillaDSP. Supply the reviewed aarch64 4.1.3 executable through the same trusted acquisition method used for the accepted Phase 6 work.

Set only a path variable; do not modify the binary:

```bash
CAMILLA=/path/to/camilladsp-4.1.3-aarch64
```

Require a regular executable, not a symlink:

```bash
test -f "$CAMILLA" && test -x "$CAMILLA" && test ! -L "$CAMILLA"
"$CAMILLA" --version
sha256sum "$CAMILLA"
```

Require version `4.1.3` and SHA:

```text
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

Store only the path and hash in evidence; do not copy an unverified binary into managed locations manually.

---

# 7. Guarded EQ promotion

## Read-only EQ plan

```bash
bash install.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA" \
  --non-interactive \
  | tee "$EVIDENCE/30-eq-plan.txt"
```

Require that fresh EQ explicitly uses the `alarm-safe-direct` baseline while preserving the standalone historical default contract.

## Root EQ apply

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

## Whole-appliance + specialist verification

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

Require both verifiers to pass.

Record active route identity:

```bash
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf \
  | tee "$EVIDENCE/34-eq-route.sha256"
```

Require EQ split-bus SHA:

```text
1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9
```

Require installed marker:

```bash
test -f /var/lib/a-clockwork-plex/split-bus/installed
```

---

# 8. Physical EQ acceptance

## Music paths

- Plexamp plays normally through the EQ-capable graph.
- AirPlay plays normally through the same music processing path.
- Source handoff remains governed by PlaybackCoordinator; ordinary handoff does not restart the audio graph.

## EQ/bypass

Using a familiar music track:

- change Bass and confirm an audible/credible tonal change;
- change Mid and confirm an audible/credible tonal change;
- change Treble and confirm an audible/credible tonal change;
- toggle EQ bypass and require the tonal processing to leave/return without changing alarm loudness;
- return controls to the desired acceptance state.

Do not use extreme boosts simply to make the test obvious; limiter/headroom behaviour is already an accepted invariant.

## Music Master / alarm isolation under EQ

Repeat the Direct isolation test:

1. music playing;
2. Music Master = 0%;
3. music must be silent;
4. real scheduled alarm must remain audible;
5. change/inspect **Maximum Alarm Volume** and require it to govern the alarm ceiling independently of Music Master/EQ;
6. Snooze/Dismiss normally;
7. restore Music Master and confirm music returns at the expected level.

**Pass:** physical split-bus isolation matches the accepted architecture.

## Guarded repair plan

Without manufacturing a fault, confirm the installed profile can produce the accepted repair plan:

```bash
bash scripts/audio/repair-audio.sh \
  --prepare-only \
  --binary "$CAMILLA" \
  --project-user "$USER" \
  | tee "$EVIDENCE/35-eq-repair-plan.txt"
```

This command must remain non-mutating. Do **not** activate repair unless an actual accepted recovery reason exists during the test.

---

# 9. Reboot acceptance

Capture current service/route state, then reboot the disposable target normally:

```bash
sudo reboot
```

After reconnect/login:

```bash
cd ~/A-Clockwork-Plex

bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/40-eq-after-reboot-appliance.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/41-eq-after-reboot-audio.txt"
```

Recheck physical Plexamp and a short real alarm test. Require dashboard kiosk startup, music playback, EQ state and alarm isolation to survive reboot.

---

# 10. Weather Underground secret preparation

Keep the WU key on the test host only. Do **not** put the literal secret into a shell command because shell history is evidence too.

```bash
WU_DIR="$HOME/.config/a-clockwork-plex"
WU_KEY_FILE="$WU_DIR/wu-api-key"
install -d -m 700 "$WU_DIR"
install -m 600 /dev/null "$WU_KEY_FILE"
nano "$WU_KEY_FILE"
```

Paste/type the key into the editor as one line, save and close. Do not show it in the terminal afterward.

Set the non-secret station ID:

```bash
WU_STATION_ID='YOUR_STATION_ID'
```

Check **metadata only**:

```bash
stat -c '%a %U:%G %n' "$WU_KEY_FILE"
```

Do not run `cat`, `sed`, `head`, `tail` or `echo $(...)` on the key file for evidence.

---

# 11. Read-only real WU current/history inspection

Before allowing history semantics to influence any future design decision, inspect the real station payloads with the dedicated diagnostic tool:

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

Record:

- current observation keys and pressure-related paths;
- history observation count;
- history timestamp evidence;
- history pressure-related paths;
- the tool's like-for-like history assessment.

Interpretation rule:

- `NO` means history is not suitable for instantaneous pressure samples under the current contract;
- `YES — REVIEW REQUIRED` means only that the live payload deserves design review;
- neither result authorises this acceptance run to write WU history into dashboard pressure history.

The new appliance continues to build pressure history from real current observations normally.

---

# 12. Guarded WU appliance apply

Keep the accepted EQ profile while changing the observation provider. Because EQ is already installed, the EQ lifecycle will use its guarded repair path rather than creating a second first-install backup.

## Plan

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

## Apply

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

Require the same root/application commit markers.

## Standalone verification using the same key-file contract

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

Inspect live observation API without exposing credentials:

```bash
curl -fsS http://localhost:8088/api/weather/observations \
  | python3 -m json.tool \
  | tee "$EVIDENCE/54-wu-runtime-observations.json"
```

Require provider `weather-underground`/runtime-equivalent and an acceptable `ready`, `pending` or `degraded` state according to current verifier semantics. For physical acceptance, wait for/require a real current observation to become visible and compare its temperature/humidity/pressure plausibility with the PWS rather than accepting `pending` forever.

Check managed secret **metadata only**:

```bash
sudo stat -c '%a %U:%G %n' /etc/default/a-clockwork-plex-weather \
  | tee "$EVIDENCE/55-wu-secret-metadata.txt"
```

Do not save the file contents into evidence.

Confirm `config.json` contains station ID + environment-variable name but **not** the API key value.

---

# 13. Repeat whole-appliance installation

This is the idempotency/ownership-drift acceptance gate. Run the same already-configured EQ + WU root apply again:

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

- package bootstrap reports already-satisfied prerequisites or otherwise makes only legitimate additive corrections;
- EQ existing-install path delegates to guarded repair rather than replacing the original uninstall baseline;
- no duplicate dashboard/kiosk/AirPlay/helper ownership appears;
- final whole-appliance verifier passes;
- root/application commit markers appear;
- physical Plexamp/AirPlay/alarm behaviour remains unchanged.

Run the standalone verifier again:

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

# 14. Final acceptance evidence

Capture final state:

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

Create a dated physical result document in `docs/` summarising:

- target model/hostname and source commit;
- pre-install state;
- Direct installer/verifier/route result;
- Direct Plexamp/AirPlay/Music Master/alarm/UI result;
- EQ installer/verifier/route result;
- EQ/bypass/Music Master/alarm/reboot result;
- WU payload-inspector evidence and explicit decision about history semantics;
- WU runtime result without secret content;
- repeat-install result;
- any deviations or failures and whether rollback occurred.

Do not mark Phase 7 complete until that evidence exists and all required physical gates pass.

## Acceptance summary checklist

- [ ] Disposable/fresh target identified; target is not `plexamp-bedroom`.
- [ ] External Plexamp Headless prerequisite passes.
- [ ] DAC card id `Pro` passes.
- [ ] Baseline evidence captured.
- [ ] Direct package availability + pre-bootstrap platform gate pass.
- [ ] Root Direct install commits.
- [ ] Direct route is exact `654ff170...`.
- [ ] Direct Plexamp/AirPlay playback passes.
- [ ] Music Master 0 silences music but not a real alarm.
- [ ] Direct EQ UI says **Install required**.
- [ ] Pinned CamillaDSP 4.1.3 artifact/hash passes.
- [ ] Root EQ install commits.
- [ ] EQ route is exact `1bc69f...` and both verifiers pass.
- [ ] Physical EQ/bypass + alarm isolation passes.
- [ ] Reboot verification passes.
- [ ] WU key remains host-file-only and is never exposed in evidence.
- [ ] Real WU current/history inspector passes; history remains inspection-only.
- [ ] WU runtime current observation is physically/plausibly accepted.
- [ ] Repeat whole-appliance install commits with no ownership drift.
- [ ] Final physical result document is committed.
- [ ] PR #2 remains Draft/open/unmerged pending explicit owner approval.
