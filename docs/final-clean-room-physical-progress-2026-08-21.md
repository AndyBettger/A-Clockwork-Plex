# Final clean-room physical progress — 21 August 2026

**Status:** in progress — initial replacement-SD clean-room installation/identity baseline plus Plexamp/EQ, focused WU rainfall-history race retest, AirPlay handoff/EQ, NFC functional/debounce, real scheduled-alarm functional/safety path, representative post-commissioning reboot/formal verifier pass, and repeat public `setup.sh` plus repeat-verifier idempotence proof are complete; clean-checkout proof, final release hygiene and final acceptance remain pending.  
**Branch under test:** `feature/alarm-engine`  
**PR:** #2 remains Draft/open/unmerged pending explicit owner approval.

## Initial replacement-SD clean-room result

A newly imaged SD card was prepared with the current 64-bit Raspberry Pi OS/Desktop path, normal OS updates were applied, and the Raspberry Pi Touch Display 2 settings from `docs/INSTALL.md` were configured. The current production-candidate branch was then installed using the public command:

```bash
bash setup.sh
```

The installation returned to a fresh working A Clockwork Plex dashboard without manual component fixes. This is the first clean-room run on the replacement SD after the previous test card developed intermittent read-only behaviour.

### Tested source / checkout

The post-install evidence captured on the appliance was:

```text
HOSTNAME=plexamp-test
ARCH=aarch64
BRANCH=feature/alarm-engine
HEAD=097d11a6eb8e552df58769cbe1400e999058a1ac
GIT-STATUS-BEGIN
GIT-STATUS-END
```

So the clean-room appliance was initially installed from the exact selected green source head and the repository checkout was clean immediately after installation.

The OS userspace reported:

```text
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
VERSION_ID="13"
VERSION="13 (trixie)"
VERSION_CODENAME=trixie
DEBIAN_VERSION_FULL=13.6
```

Architecture is the required `aarch64`.

### CamillaDSP identity

The integrated setup-owned artifact at:

```text
~/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp
```

reported:

```text
CamillaDSP 4.1.3 (05e9cfc)
```

and SHA-256:

```text
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

This exactly matches the accepted CamillaDSP 4.1.3 executable identity.

### Plexamp commissioning and EQ functional PASS

Plexamp was opened, the Plex account sign-in completed, the intended music library selected, and **`A Clockwork Plex - Plexamp`** selected as the Plexamp audio output rather than `Follows system output`.

Physical playback acceptance on the replacement SD then passed all focused checks:

- Plexamp played stable audio through the managed output;
- Music Master audibly controlled Plexamp loudness;
- Bass, Mid and Treble each produced the expected audible tonal change;
- EQ bypass removed the EQ tonal effect while retaining Music Master control;
- Return to normal restored the EQ effect;
- `systemctl is-active a-clockwork-plex-camilladsp.service` returned `active`.

This closes the Plexamp/EQ functional slice of the final clean-room run.

## Weather commissioning / rainfall-history race follow-up — PASS

During initial Weather Underground commissioning on the replacement card, concurrent rainfall-history refresh owners exposed a collision on the shared atomic `weather-rainfall-history.json.tmp` cache path. Source checkpoint #58 introduced a dedicated refresh mutex around the complete cache read/fetch/merge/write transaction and added deterministic overlapping-refresh regression coverage.

The replacement appliance was then updated from `097d11a6...` to the documentation/current branch head with a clean fast-forward:

```text
git status --short
# no output

Updating 097d11a..dcb4433
Fast-forward
...

git rev-parse HEAD
dcb4433e8c72350f4c11de2f643f83a4ffa6a1a9
```

The dashboard service was restarted only for the source update and returned:

```text
systemctl is-active a-clockwork-plex.service
active
```

The focused physical retest then exercised the previously failing path: **Current year**, **Test Connection**, period switching to **Last 7 days**, switching back to **Current year**, and revisiting/reloading the Weather Settings surface. The operations completed normally and the historical-rainfall status remained healthy; the previous atomic-cache rename failure did not recur.

A focused journal check after the retest showed only successful rainfall API requests, including:

```text
POST /api/weather/rainfall HTTP/1.1 200
GET /api/weather/rainfall HTTP/1.1 200
```

There was no rainfall-history traceback, exception, atomic rename error or other matching error output. This closes the physical half of checkpoint #58 and allows the replacement-SD clean-room sequence to continue.

## AirPlay handoff / EQ functional PASS

The replacement-SD clean-room run then exercised AirPlay from a real sender while Plexamp was already playing.

Physical behaviour passed all focused checks:

- selecting the A Clockwork Plex AirPlay receiver paused Plexamp and transferred the dashboard to the AirPlay surface;
- AirPlay audio was clean and stable through the managed output;
- changing the managed EQ produced an audible tonal change on AirPlay audio;
- **Bypass EQ** removed the tonal EQ effect and **Return to normal** restored it;
- disconnecting AirPlay returned the dashboard to the Clock page rather than spuriously restarting/resuming another source;
- Plexamp could then be manually played successfully again.

Service identity was captured before and after the ordinary AirPlay handoff. The values were identical at both points:

```text
plexamp.service
MainPID=1909
NRestarts=0
ActiveState=active

shairport-sync.service
MainPID=5082
NRestarts=0
ActiveState=active

a-clockwork-plex-camilladsp.service
MainPID=944
NRestarts=0
ActiveState=active
```

The unchanged `MainPID` values and `NRestarts=0` prove the normal AirPlay takeover/disconnect path did not restart Plexamp, Shairport Sync or CamillaDSP. This closes the AirPlay functional slice of the final replacement-SD clean-room run.

## NFC album-tag / debounce functional PASS

A known-good NFC album tag was exercised against the replacement-SD appliance. The first valid presentation switched the dashboard into Plexamp mode and started the expected album through the local Plexamp Headless playback endpoint. The NFC listener remained continuously healthy before and after the test:

```text
MainPID=1910
NRestarts=0
ActiveState=active
```

The listener's five-second same-UID debounce was then tested explicitly. A repeat presentation within roughly two seconds did not restart playback and produced no second `Tag UID`/playback entry, proving the repeat was discarded at the UID debounce gate. After the debounce window expired, presenting the same tag again restarted playback as expected. Representative journal evidence included a valid trigger followed by the next eligible trigger only after the debounce interval:

```text
21:43:40 Tag UID: 0x4 0x7d 0x12 0x1c 0x7f 0x61 0x80
21:43:41 Playback triggered!
21:43:47 Tag UID: 0x4 0x7d 0x12 0x1c 0x7f 0x61 0x80
21:43:48 Playback triggered!
```

An earlier boundary presentation also demonstrated the listener's malformed/truncated NDEF guard: an incomplete read was safely rejected rather than sent to Plexamp. The optional `xdotool` browser-navigation path is not installed on this clean appliance, but the dashboard mode API path visibly switched the UI correctly, so no NFC navigation failure is inferred from that informational message.

This closes the NFC functional/debounce slice of the final replacement-SD clean-room run.

## Scheduled alarm / fade / safety functional PASS

A real enabled scheduled alarm named **Clean-room test** was exercised while Plexamp was already playing. The configured alarm used a 10% fade start, approximately 51% per-alarm target, 20-second fade and one-minute Snooze. The persistent **Maximum Alarm Volume** output ceiling was set to 25% before the occurrence.

Physical behaviour passed the release-candidate checks:

- the real scheduled occurrence paused Plexamp and activated the full-screen alarm surface;
- the alarm began quietly and audibly increased over the configured 20-second fade;
- Snooze stopped the alarm and did not automatically resume Plexamp;
- exactly one minute later the occurrence re-rang, starting quietly again and performing a fresh fade rather than resuming at the prior high level;
- Dismiss stopped the re-ring and again did not automatically restart Plexamp;
- Plexamp could then be manually resumed successfully.

The dashboard, Plexamp and canonical CamillaDSP services remained active with zero restart counters after the alarm sequence:

```text
Id=a-clockwork-plex.service
MainPID=982356
NRestarts=0
ActiveState=active

Id=plexamp.service
MainPID=1909
NRestarts=0
ActiveState=active

Id=a-clockwork-plex-camilladsp.service
MainPID=944
NRestarts=0
ActiveState=active
```

Scheduler/API evidence matched the physical sequence: the alarm activated at 21:53:00 local time, Snooze returned HTTP 200 at 21:53:24, the alarm surface returned at 21:54:24, and Dismiss returned HTTP 200 at 21:54:42.

The scheduled stream's own runtime history recorded `start_percent=10`, `target_percent=51`, `fade_seconds=20`, `volume_cap_percent=100` for both ring cycles. That `volume_cap_percent` is the separate internal scheduled-stream cap, not the Settings **Maximum Alarm Volume** control. The latter is the downstream shared ALSA `alarm` mixer stage. Journal evidence showed it being set to 25% before the alarm, and a final mixer status check confirmed:

```text
master: 66%  -3.6 dB
alarm: 25%  -12.2 dB
```

Music Master independence was then physically proved with another scheduled occurrence: setting the shared `master` channel to 0% silenced Plexamp, but the scheduled alarm remained audible. The original Music Master value of 66% was restored afterwards. This proves the final alarm route remains independent of Music Master while retaining the dedicated downstream Maximum Alarm Volume ceiling.

This closes the real scheduled-alarm functional/safety slice of the replacement-SD clean-room run.

## Representative reboot + formal verifier PASS

After all major functional slices passed, the fully commissioned replacement-SD appliance was deliberately rebooted. The tested checkout remained exactly:

```text
dcb4433e8c72350f4c11de2f643f83a4ffa6a1a9
```

After boot, every release-critical managed service checked was both active and enabled:

```text
a-clockwork-plex.service                 active / enabled
plexamp.service                          active / enabled
nfc-listener.service                     active / enabled
shairport-sync.service                   active / enabled
a-clockwork-plex-camilladsp.service      active / enabled
```

Real Plexamp playback was then started successfully, providing a physical post-reboot audio sanity check in addition to service state.

The formal fresh-bootstrap verifier then passed the pinned player/runtime, NFC runtime, live PN532 I2C address `0x24`, DAC `CARD=Pro`, active/enabled Plexamp and NFC services, Plexamp API and NFC import checks with:

```text
Failures: 0
Warnings: 0
FRESH_BOOTSTRAP_VERIFY=PASS
```

The formal appliance verifier was run with the selected production profiles:

```bash
bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations weather-underground \
  --project-user "$USER" \
  --project-dir "$PWD"
```

It passed dashboard/system integration, AirPlay helpers/metadata service, alarm/weather/mixer restricted helpers and sudoers, persistent mixer defaults, kiosk launcher, standalone EQ verification, WU/Open-Meteo configuration, presence-only managed WU credential verification, active/enabled Plexamp/Shairport/dashboard/metadata services, mixer/dashboard/weather/EQ APIs and the four-channel mixer contract with:

```text
Failures: 0
Warnings: 0
APPLIANCE_VERIFY=PASS
```

Finally, the dedicated audio verifier returned:

```text
[A Clockwork Plex] EQ-capable audio verification passed.
```

The three non-secret outputs were preserved in the clean-room evidence directory as:

```text
20-post-reboot-bootstrap-verifier.txt
21-post-reboot-appliance-verifier.txt
22-post-reboot-audio-verifier.txt
```

This closes the representative commissioned reboot and first formal-verifier gate.

## Repeat public setup / commissioned-Weather idempotence — PASS

The first physical repeat-install attempt exposed a genuine idempotence regression: plain public `setup.sh` still carried the fresh-install Ecowitt default into the lower installer and could therefore replace an already-commissioned Weather Underground observation profile. That failed attempt was not accepted as a release gate.

Checkpoint #63 corrected the contract at source. When `config.json` already exists and the operator supplies no explicit Weather provider option, the public/lower installer chain now resolves the commissioned provider from the live configuration and uses an internal **preserve-commissioned-profile** path. For a preserved WU profile the guarded preflight checks only boolean managed-credential presence through the restricted root-owned helper; the application transaction skips Weather mutation but still runs the normal whole-appliance verifier. Explicit Weather selections continue to converge deliberately as before. Dedicated regression coverage is in `tests/test_weather_repeat_preservation.py`.

The replacement appliance was then cleanly fast-forwarded from its previously exercised `dcb4433...` source to exact checkpoint source head:

```text
git status --short
# no output

git pull --ff-only
Updating dcb4433..215bced
Fast-forward
...

git rev-parse HEAD
215bcedb43369844b5968ae24a7169e49636ef99
```

After the source update the dashboard service was deliberately restarted and returned `active` before the repeat installer was invoked.

The exact public repeat command was then run as the normal appliance user with no Weather override:

```bash
bash setup.sh
```

The repeat plan correctly reported:

```text
Audio profile:        eq
Weather observations: weather-underground
Weather mutation:     preserve-commissioned-profile
Forecast provider:    open-meteo (retained)
```

The staged preflight checks repeatedly confirmed the managed WU credential was present and that the commissioned profile would be preserved. Hardware remained accepted (`PN532_I2C=PASS`, `DAC_PRO=PASS`), the pinned Plexamp/Node runtime remained valid, and no fresh claim checkpoint was requested.

Inside the guarded whole-appliance transaction, the decisive preservation evidence was:

```text
Weather observations: weather-underground
Weather mutation:     preserve-commissioned-profile
...
[A Clockwork Plex] Preserving commissioned Weather configuration and managed credential.
```

The already-installed EQ path converged through its guarded repair/verification lifecycle, restricted helpers and AirPlay integration were revalidated/reinstalled through their normal owners, and the final appliance verifier reported:

```text
Failures: 0
Warnings: 0
APPLIANCE_VERIFY=PASS
```

The enclosing transaction and root installer then committed successfully:

```text
APPLICATION_TRANSACTION=COMMITTED
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=fresh-bootstrap
APPLICATION_VERIFY=PASS

[A Clockwork Plex] Setup completed successfully.
```

There was no `PLEXAMP_RUNTIME=CLAIM-REQUIRED`, no exit-76 claim stop and no exit-75 `REBOOT-REQUIRED` checkpoint. The success footer still prints the generic first-install advisory `Reboot once to enter the installed appliance and confirm dashboard kiosk startup.`; this was not a guarded reboot-required stop, and the repeat verifier set was run immediately afterwards without reboot.

The post-repeat formal evidence was preserved as:

```text
33-repeat-bootstrap-verifier.txt
34-repeat-appliance-verifier.txt
35-repeat-audio-verifier.txt
```

The fresh-bootstrap verifier again passed the pinned Plexamp/Node identities, persistent claim state, pinned NFC source/venv/unit, live I2C/PN532, DAC Pro, Plexamp/NFC services and APIs with:

```text
Failures: 0
Warnings: 0
FRESH_BOOTSTRAP_VERIFY=PASS
```

The repeat appliance verifier explicitly targeted the commissioned production profile and confirmed `weather-provider weather-underground`, Open-Meteo forecasts, no secret in `config.json`, station `ILIPHO12`, presence-only managed WU credential status, active/enabled runtime services, EQ, mixer and dashboard/weather APIs with:

```text
Failures: 0
Warnings: 0
APPLIANCE_VERIFY=PASS
```

The dedicated repeat audio verifier finished with:

```text
[A Clockwork Plex] EQ-capable audio verification passed.
```

Physical sanity after the repeat matched the formal evidence: Plexamp audio remained audible, the managed EQ remained active, and Weather Underground was still the selected observation source. This closes checkpoint #63 and proves the public repeat-install path preserves commissioned WU state rather than reverting to the fresh-install Ecowitt default.

## Remaining clean-room gates

All major functional clean-room slices, the representative reboot/first verifier set, and the public repeat-install/second verifier set are now physically complete. The remaining release-candidate proof is:

- confirm normal operation leaves `git status --porcelain` clean and preserve that output as final clean-checkout evidence;
- update/finalize the active roadmap and clean-room evidence around that result;
- complete deliberate release/repository hygiene and the final validation pass;
- obtain explicit owner approval before PR #2 may leave Draft or merge.

No final Phase 7 acceptance is claimed by this progress record until the remaining clean-checkout/release-hygiene gates and explicit owner approval are complete.
