# Stage C21 production baseline acceptance — 2026-08-06

## Outcome

**PASS — the fixed read-only Stage C21 inspector observed `plexamp-bedroom` in the expected untouched pre-installation state, published a complete evidence bundle and returned without changing the appliance.**

This document records the human review decision for the first target-side Stage C21 baseline. It does not grant installation, activation, transaction, approval, service, route, mixer, PCM or CamillaDSP authority.

## Reviewed source and package

The inspection exported and executed the exact reviewed branch commit from a disposable source tree:

```text
273290f5e77ae98d24cb5af368ab90c76744be60
```

The existing Pi checkout was not reset, stashed, merged or checked out. Its local modification to:

```text
scripts/launch-dashboard-kiosk.sh
```

remained byte-identical throughout the inspection.

The digest-pinned CamillaDSP 4.1.3 binary was verified as:

```text
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

The disposable current Stage C21 activation-capable package v2 then passed all package checks and produced:

```text
package fingerprint
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

package files
28

fingerprinted payload files
27
```

The package was not installed or activated.

## Evidence bundle

The fixed unprivileged wrapper published:

```text
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac
```

with the required ownership and modes:

```text
bundle directory  andy:andy 0700
report.txt        andy:andy 0600
report.json       andy:andy 0600
manifest.json     andy:andy 0600
```

Recorded evidence digests:

```text
report.txt
350ae99ee63911cb524f7220e4629e5da669f3c79f8e409d2f9fdf4652c16a85

report.json
3c6dcd3c17a3ce363ddf3f5bdd9d93c8891a2a006c0c154905a3a809b79348e0

manifest.json
4995bdf85cb06995a9b26c164fdc28991d755631e9c4dbe527eddc005253c1dc
```

The manifest recorded:

```text
complete: true
disposition: baseline-ready
candidate package: dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5
```

Its `report.txt` and `report.json` sizes and SHA-256 values exactly matched the independently printed values.

## Accepted host baseline

### Production authority objects

```text
production lock
absent

activation approval
absent

production transaction
not created
```

The inspected approval path was:

```text
/var/lib/a-clockwork-plex/split-bus/activation-approved
```

Its fixed `split-bus` ancestor was absent, which is the expected pre-installation state.

### Existing application services

```text
plexamp.service             loaded active enabled
shairport-sync.service      loaded active enabled
a-clockwork-plex.service    loaded active enabled
```

### Stage C services

```text
a-clockwork-plex-audio-route.service     not-found inactive not-found
a-clockwork-plex-camilladsp.service      not-found inactive not-found
a-clockwork-plex-audio-failback.service  not-found inactive not-found
```

This confirms that the candidate Stage C21 units are not installed.

### Mixer state

```text
Plexamp Output          94
AirPlay Output          100
Music Master            100
Maximum Alarm Volume    100
```

These are the current canonical mixer-control names. The historical Stage C5 review document still contains obsolete `A Clockwork ...` names and must not be used as the live target contract without correction.

### Loopback contract

```text
module          snd_aloop
card index      7
card ID         ACP_Loopback
substreams      2
pcm_notify      1
loaded          true
```

### DAC contract and owner

```text
format          S16_LE
channels        2
rate            44100 Hz
period          1024
buffer          8192
released        false
owners          1
```

The observed owner was the existing Plexamp Node process running as `andy` with read-write access. `released: false` is the expected stable C20 baseline and is not a failure: no preparation-only inspection was permitted to stop Plexamp or release the DAC.

## Authority result

Every authority flag remained false:

```text
production_mutation_authorised: false
activation_authorised: false
pi_execution_authorised: false
production_lock_acquired: false
transaction_created: false
```

The report field:

```text
review_bundle_persisted: false
```

is a pre-publication report-state field. The separately written final manifest is the completion proof and records `complete: true`; the field does not represent a publication failure.

## Safety result

The inspection proved that it did not:

- install or remove a package;
- acquire or release the production lock;
- create a production transaction;
- create, replace, promote or remove an approval record;
- stop, start, restart, enable, disable or reload a service;
- change an ALSA route or configuration;
- change a mixer value;
- open a PCM or DAC;
- start CamillaDSP;
- run `scripts/install-master-eq.sh`;
- merge PR #2.

The wrapper exited `0`, its child process exited `0`, and the interactive SSH shell remained open.

## Acceptance decision

The fixed target baseline is accepted for the next engineering checkpoint.

This acceptance permits repository work to prepare a current-package **pre-mutation transaction rehearsal**. It does not itself permit another Pi command.

The next rehearsal must:

1. replay this exact baseline bundle and package fingerprint;
2. use the existing canonical production-lock and authoritative-transaction owner;
3. create one fresh authoritative transaction;
4. capture all five snapshot domains;
5. stage and validate the current 28-file Stage C21 package only inside that transaction;
6. retain non-authoritative review evidence;
7. abort the transaction exactly;
8. release the production lock;
9. stop before `stop-captured-application-services`;
10. leave all four production approval operations blocked.

A separate explicit approval is required before that bounded Pi rehearsal is executed.

## Roadmap

### Done

- exact reviewed source export;
- current package v2 generation and validation;
- target-side read-only baseline inspection;
- complete evidence publication;
- human baseline acceptance.

### Current

Design and implement the current-package pre-mutation transaction rehearsal by updating the physically proved Stage C16 shape for the Stage C21 package v2 and accepted target evidence.

### Next

After automated tests and GitHub Actions pass, request explicit approval for one Pi rehearsal that acquires the canonical lock, creates and aborts one authoritative transaction, stages and validates the current package, and performs no application, audio or approval mutation.

### Risks and gates

- the accepted package exists only in disposable `/var/tmp` evidence on the Pi;
- the existing Stage C16 implementation is bound to the historical 12-file Stage C1 package and cannot be reused unchanged;
- no production approval writer exists;
- no production activation entrypoint exists;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 must remain Draft, open and unmerged.
