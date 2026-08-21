# Final clean-room physical progress — 21 August 2026

**Status:** in progress — initial replacement-SD clean-room installation/identity baseline, Plexamp/EQ functional path, focused WU rainfall-history race retest and AirPlay handoff/EQ path PASS; NFC, alarm, reboot/verifiers, repeat `setup.sh`, clean-checkout proof and final acceptance remain pending.  
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

## Remaining clean-room gates

The remaining release-candidate physical proof is:

- verify one known-good NFC album tag, including immediate repeat-tag debounce;
- run a real scheduled alarm through takeover, fade, Snooze/re-ring and Dismiss;
- perform the representative post-commissioning reboot;
- run `verify-fresh-bootstrap.sh`, `verify-appliance.sh --audio eq --weather-observations weather-underground` and `scripts/audio/verify-audio.sh` and preserve non-secret outputs;
- rerun the public `bash setup.sh` to prove idempotence, then rerun all three formal verifiers;
- confirm normal operation leaves `git status --porcelain` clean;
- update the active roadmap/final evidence and complete release hygiene only after those gates pass.

No final Phase 7 acceptance is claimed by this partial progress record.
