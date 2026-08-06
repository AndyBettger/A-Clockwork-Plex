# Stage C24 pre-mutation reboot-baseline failure and diagnostic correction — 2026-08-06

## Status

Stage C24 is **not accepted** and no Stage C24 mutation was performed.

The first guarded physical invocation after several power cuts reached the
Stage C24 Python entry point, then refused the live appliance before production
lock acquisition because the fixed read-only baseline inspector returned
`host-observation-failed`. The separately approved temporary restoration of the
missing runtime loopback prerequisite subsequently returned the appliance to
`baseline-ready` without changing persistent configuration.

A fresh, separately scoped approval remains mandatory before any further Stage
C24 physical rehearsal.

## Approved source and retained run paths

The guarded invocation fetched and verified the exact approved branch head:

- source head: `14a3e8cdc4a6071f6b79538ea00a13c6cff06d15`
- source root: `/var/tmp/a-clockwork-plex-stage-c24-source.Je6yws`
- fetch log: `/var/tmp/a-clockwork-plex-stage-c24-fetch.OLLJDE`
- console log: `/var/tmp/a-clockwork-plex-stage-c24-console.42MfIQ`
- empty evidence root: `/var/tmp/a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.oOHFKM`

The exact retained package, baseline, Stage C21, Stage C22 and Stage C23 inputs
and their accepted manifest digests replayed successfully before the guarded
entry point.

## Authority boundary and failure position

The console printed:

```text
STAGE_C24_GUARDED_INVOCATION_BEGIN
```

The one approved Stage C24 rehearsal was therefore consumed. The Python entry
point then raised:

```text
CurrentPackageContractErrorV7: live appliance is not baseline-ready: host-observation-failed
```

This occurred while validating the immutable report returned by
`ProductionPrepareOnlyInspectorV7`, before:

- production lock acquisition;
- authoritative transaction creation;
- service quiescence;
- physical DAC release;
- installation of any managed file;
- either permitted `systemctl daemon-reload` attempt;
- route selection, mixer mutation, CamillaDSP startup, probes, approval or
  commit.

Read-only post-run inspection proved:

- production lock absent;
- `/var/lib/a-clockwork-plex/split-bus` absent;
- authoritative transaction root absent;
- Plexamp, Shairport Sync and the dashboard active and enabled;
- all three managed Stage C units `not-found`, inactive and not enabled;
- intentionally stale local checkout unchanged;
- the C24 evidence root empty.

## Exact failed baseline domain

A follow-up read-only inspection printed each result from the already existing
prepare-only report. Five host domains passed:

- host contract;
- production lock;
- service state;
- mixer state;
- physical DAC state.

Only the loopback observation failed:

```text
cannot read snd_aloop index: [Errno 2] No such file or directory:
'/sys/module/snd_aloop/parameters/index'
```

The accepted direct shared ALSA route remained exact:

- path: `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`
- mode and owner: `0644 root:root`
- SHA-256: `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`

The four accepted software mixer controls remained present. The physical DAC
continued at `S16_LE`, two channels, 44.1 kHz, period 1024 and buffer 8192.

The current kernel contained the `snd_aloop` module, but the rebooted appliance
had no matching persistent entry under the inspected `modules`,
`modules-load.d` or `modprobe.d` configuration. `systemd-modules-load.service`
had completed successfully without loading it. The earlier live loopback state
was therefore a temporary rehearsal prerequisite lost on reboot, not corruption
of the accepted direct audio route.

## Separately approved temporary recovery

A separately scoped approval authorised exactly one non-persistent runtime load:

```text
snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1 enable=1
```

The command completed and the kernel parameters verified exactly:

- `index=7`
- `id=ACP_Loopback`
- `pcm_substreams=2`
- `pcm_notify=1`
- `enable=Y`

ALSA displays the card identifier as `ACPLoopback`; this display normalisation
is not the Stage C contract. The authoritative contract is the exact module
parameter set above and card index 7.

An over-strict auxiliary check for `/proc/asound/ACP_Loopback` stopped the first
verification shell after the approved load. It did not undo the successful
module load and did not perform any further mutation.

## Final read-only verification

The completion inspection returned:

```text
REPORT_STATUS=pass
REPORT_DISPOSITION=baseline-ready
STAGE_C24_BASELINE_READY=PASS
production_lock=absent
authoritative_transaction=absent
persistent_configuration_changed=false
TEMPORARY_SND_ALOOP_VERIFICATION=PASS
```

It also proved:

- all six fixed observations passed;
- the accepted route SHA-256 remained exact;
- the persistent module-configuration fingerprint remained
  `efe3e86a71a3525084a500584f1b15c03f61d9a37c564faeb83cdac2eaa4ed95`;
- Plexamp, Shairport Sync and the dashboard remained active and enabled;
- no production approval existed.

The temporary module will be lost at the next reboot. This incident does not
authorise or choose a persistent loopback boot policy.

## Repository diagnostic correction

The v10 rehearsal already collected a complete immutable pre-live report, but
its accepted validator exposed only the combined disposition in the thrown
exception. The new v12 compatibility entry point now prints, in fixed order,
the existing report status, disposition and detail, each of the six observation
statuses and details, and the approval observation before delegating to the
unchanged accepted validator.

The correction:

- performs no additional host observation;
- preserves the v11 hard maximum of exactly two daemon-reload attempts,
  including failures;
- changes no transaction, rollback or closure operation;
- adds no production write, service command, route, mixer, CamillaDSP, probe,
  approval or commit authority;
- makes any future pre-lock baseline refusal identify the exact failed domain
  before the traceback.

## Remaining boundary

Stage C24 remains prepared but not physically accepted. Before a new rehearsal:

1. the temporary `snd_aloop` runtime contract must still be present and pass the
   read-only baseline inspector;
2. the exact current branch head and retained evidence inputs must be approved;
3. a new separately scoped Stage C24 physical approval must be obtained;
4. the prior empty failed evidence root and retained diagnostic paths must not be
   treated as accepted C24 evidence.

No persistent activation, route selection, CamillaDSP startup, reboot test, PR
readiness or merge is authorised by this result.
