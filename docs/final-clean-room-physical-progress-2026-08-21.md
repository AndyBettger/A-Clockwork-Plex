# Final clean-room physical progress — 21 August 2026

**Status:** in progress — initial replacement-SD clean-room installation and identity baseline PASS; functional commissioning, reboot/verifiers, repeat `setup.sh`, clean-checkout proof and final acceptance remain pending.  
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

So the clean-room appliance is running the exact selected green source head and the repository checkout was clean immediately after installation.

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

### Plexamp commissioning progress

Plexamp has been opened, the Plex account sign-in completed, the intended music library selected, and **`A Clockwork Plex - Plexamp`** selected as the Plexamp audio output rather than `Follows system output`.

The dashboard Audio page reports the Master EQ as active. Actual playback/EQ behaviour has not yet been exercised on this replacement-SD run, so this is not yet recorded as the functional audio PASS.

## Remaining clean-room gates

The remaining release-candidate physical proof is deliberately unchanged:

- play Plexamp through the managed output and verify Music Master, Bass/Mid/Treble and EQ bypass behaviour;
- commission Weather Underground in Settings and verify live/current/history behaviour without exposing the secret;
- verify AirPlay handoff/audio through the EQ route;
- verify one known-good NFC album tag;
- run a real scheduled alarm through takeover, fade, Snooze/re-ring and Dismiss;
- perform the representative post-commissioning reboot;
- run `verify-fresh-bootstrap.sh`, `verify-appliance.sh --audio eq --weather-observations weather-underground` and `scripts/audio/verify-audio.sh` and preserve non-secret outputs;
- rerun the public `bash setup.sh` to prove idempotence, then rerun all three formal verifiers;
- confirm normal operation leaves `git status --porcelain` clean;
- update the active roadmap/final evidence and complete release hygiene only after those gates pass.

No final Phase 7 acceptance is claimed by this partial progress record.