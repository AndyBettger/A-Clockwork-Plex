# Stage C13 typed read-only real-host adapter rehearsal — result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

Stage C13 successfully returned six fixed typed observations from the real Raspberry Pi while all remaining 27 production-adapter operations stayed blocked.

The rehearsal did not open the production lock, create a production transaction, install files, alter services or mixer controls, open a PCM or DAC, run CamillaDSP, select a route, or expose activation, failback, rollback or uninstall.

## Physical evidence

```text
Evidence root: /var/tmp/a-clockwork-plex-stage-c13-read-only-adapter.a2gZFh
Generated: 2026-08-05T13:39:31+01:00
Observation identity: stage-c13-observation-37100d7cd8e15caf5a86d2d3
Invoking user: andy
```

The observation identity was:

```text
caller_supplied=false
production_authoritative=false
persistent=false
```

A substituted observation identity was rejected before host access.

## Acceptance checks

All twelve checks passed in the required order:

| Order | Check | Result |
|---:|---|---|
| 1 | `root-scope` | PASS |
| 2 | `observation-identity` | PASS |
| 3 | `protocol-conformance` | PASS |
| 4 | `host-contract` | PASS |
| 5 | `production-lock-boundary` | PASS |
| 6 | `service-snapshot` | PASS |
| 7 | `mixer-snapshot` | PASS |
| 8 | `loopback-snapshot` | PASS |
| 9 | `dac-snapshot` | PASS |
| 10 | `blocked-operation-boundary` | PASS |
| 11 | `evidence-integrity` | PASS |
| 12 | `activation-interface` | PASS |

## Typed host observations

### Fixed host contract

The typed host contract matched the reviewed Stage C boundary:

```text
Service units: 6 fixed units
Mixer controls: Plexamp Output, AirPlay Output, Music Master, Maximum Alarm Volume
Loopback: snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1
DAC: S16_LE, 2 channels, 44100 Hz, period 1024, buffer 8192
```

The current stable ALSA route and `aarch64` host boundary also matched the pinned contract.

### Production lock

```text
Path: /run/lock/a-clockwork-plex-audio-route.lock
Exists: false
Held by caller: false
Owner UID/GID: none
Mode: none
```

The lock path was inspected with `lstat` only. It remained absent and was not opened or created.

### Services

The existing application services remained loaded, active and enabled:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
```

The future Stage C services remained absent:

```text
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

Each absent Stage C service returned:

```text
load=not-found
active=inactive
enabled=not-found
```

### Mixer snapshot

The four fixed logical mixer fields returned typed percentages:

```text
plexamp_output=94
airplay_output=100
music_master=100
maximum_alarm_volume=100
```

The rehearsal performed no mixer write.

### Loopback snapshot

```text
module=snd_aloop
card_index=7
card_id=ACP_Loopback
pcm_substreams=2
pcm_notify=1
loaded=true
```

### DAC snapshot

The live DAC boundary matched the fixed contract:

```text
sample_format=S16_LE
channels=2
rate=44100
period_size=1024
buffer_size=8192
released=false
```

One structured owner was captured:

```text
pid=466057
user=andy
command=node
access=read-write
```

## Blocked operation proof

Exactly 27 non-observation operations raised `ProductionAdapterBlocked` with their exact operation identity.

This included every operation capable of:

- acquiring or releasing the production lock;
- creating an authoritative transaction;
- capturing an activation-time filesystem snapshot;
- staging or installing managed files;
- validating candidate ALSA, sudoers, systemd or CamillaDSP assets;
- stopping, starting or restoring services;
- changing routes or mixer state;
- running music or alarm probes;
- writing a commit manifest;
- executing failback, rollback or uninstall restoration.

No blocked operation unexpectedly became executable.

## Evidence integrity

The evidence tree contained only regular files and the evidence directory itself. No symlink or special object was present.

```text
blocked-operations.tsv  mode 0644  sha256 5f7bfda1d0e85b294254f444faf6dd8135900a5c214b4b3d2260467b69ee4971
identity.tsv            mode 0644  sha256 806b69f33e66a20410e552f6b0bb53d5506c25bc33e78a46a147a70b2cf81c48
report.txt              mode 0644  sha256 623f1e51d4e6ce5c329d18c314785d3543a8b938bb5d34f0fefdb077e4c535f7
results.tsv             mode 0644  sha256 772146a111f8c123776508368bfb1b5f2bec4bcc312c6dd7b751dd6dad0ad0ba
typed-observations.json mode 0644  sha256 8f19c920e96a12dc244e958a5279f03e2dcdc39778535cb3c1c0501fc56da374
```

Root wrote only beneath:

```text
/var/tmp/a-clockwork-plex-stage-c13-read-only-adapter.a2gZFh
```

The evidence tree was returned to the invoking user after capture.

## Automated validation

The final Stage C13 implementation passed the complete project test suite before the physical rehearsal:

```text
Ran 638 tests
OK
```

An initial automated run contained one test-design false positive: a source-text assertion rejected the word `CamillaDSP` even where it appeared only in the name of an operation being deliberately proved blocked. The safety test was corrected to inspect executable AST call sites rather than symbolic operation names. The Stage C13 runtime implementation did not change for that correction.

## Proved by Stage C13

- six fixed typed observations can be obtained from the real host;
- the observation identity is adapter-generated, temporary and non-authoritative;
- substituted identities fail before host access;
- the production lock path can be observed without being opened;
- current route, services, mixer values, loopback parameters and DAC state match the reviewed host contract;
- structured DAC-owner evidence maps the live Node owner into the typed contract;
- all other 27 adapter operations remain blocked;
- the evidence writer is confined to a fresh direct child of `/var/tmp`;
- no activation interface exists.

## Not proved by Stage C13

Stage C13 does not prove:

- production-lock acquisition or contention;
- authoritative production transaction creation;
- exact activation-time filesystem backup;
- candidate package validation against a fresh authoritative transaction;
- service, mixer, module, PCM, DAC or route mutation;
- split-bus startup or health;
- runtime direct failback;
- exact rollback or explicit uninstall;
- reboot persistence.

## Safety conclusion

Stage C13 passed without changing the production appliance.

Persistent Stage C activation remains blocked. The old bare master-EQ installer remains prohibited, and this evidence must never be reused as an activation-authoritative snapshot.