# Stage C4 sandbox transaction and exact-rollback rehearsal

Status: design and implementation may proceed. This stage has no production
write path and does not authorise persistent Stage C activation.

## Purpose

Stages C1–C3 proved the generated package, unprivileged transaction review and
fresh root-owned read-only snapshot boundaries on `plexamp-bedroom`. Stage C4
now rehearses the mutation algorithm without mutating the appliance.

The rehearsal builds one or more synthetic root filesystems beneath a fresh
user-owned directory in `/var/tmp`. It uses the real Stage C1 package and the
real Stage C3 evidence as inputs, but every install, route replacement, service
state transition, injected failure and rollback happens only inside those
synthetic trees.

Stage C4 proves transaction mechanics. It does **not** prove real ALSA parsing,
CamillaDSP startup, service ordering, DAC ownership, audio output, runtime
failback or dashboard health.

## Interface

Prepare-only remains the default:

```bash
bash scripts/test-stage-c-sandbox-transaction.sh \
  --package-root /var/tmp/<validated-stage-c1-package> \
  --stage-c3-root /var/tmp/<validated-stage-c3-snapshot>
```

Prepare-only invokes no `sudo`, creates no sandbox and prints the exact guarded
rehearsal command.

The sandbox run requires this exact token:

```text
STAGE-C4-SANDBOX-TRANSACTION
```

and a fresh empty directory directly beneath `/var/tmp` named:

```text
a-clockwork-plex-stage-c4-sandbox.*
```

There is no activation, install-to-production, route, rollback-to-production or
uninstall-from-production action.

## Input replay

Before building a sandbox, Stage C4 independently replays:

1. the Stage C1 manifest, package checksums, modes and PASS evidence;
2. the complete Stage C3 twelve-check PASS result;
3. the Stage C3 evidence manifest and every listed checksum/mode/type;
4. the exact pre-Stage-C ALSA checksum;
5. all twelve managed package destinations recorded absent;
6. zero managed destination conflicts;
7. the protected sudoers destination recorded absent;
8. the six service states, four mixer controls, loopback/DAC state and rollback
   ledger required by the rehearsal.

The Stage C3 snapshot remains rehearsal evidence only. Stage C4 does not turn it
into an activation-authoritative snapshot.

## Sandbox scope

The rehearsal may write only beneath its fresh Stage C4 directory. Each scenario
contains:

- `system-root/` — a synthetic `/` tree;
- `simulated-state/` — copied service, mixer and module/DAC state plus simulated
  route and daemon-reload state;
- `baseline/` — the exact sandbox rollback source;
- `journal.tsv` — ordered sandbox-only transaction actions.

The synthetic tree is seeded from Stage C3:

- directories recorded present are recreated with their recorded modes;
- the exact snapshotted pre-Stage-C ALSA file is copied into its synthetic path;
- all twelve managed package files begin absent;
- application, proposed Stage C service, mixer and module/DAC state are copied
  into `simulated-state/`.

No absolute production destination is opened for writing. Every manifest
location is mapped beneath `system-root/` before use.

## Rehearsed transaction

The sandbox install algorithm performs the future transaction's file mechanics:

1. capture a fresh sandbox baseline and fingerprint;
2. mark only the three application services inactive in simulated state;
3. create only required missing managed directories;
4. atomically copy and verify all twelve package files;
5. atomically replace the synthetic active ALSA file with the split-bus route;
6. record one simulated daemon reload and sandbox route selection;
7. restore the three application services to their original simulated active
   states;
8. verify every installed package checksum/mode and the selected ALSA checksum;
9. write a sandbox commit marker outside the synthetic production tree.

No candidate helper, systemd unit, CamillaDSP binary or PCM is executed.

## Failure injection

The rehearsal repeats the transaction in independent synthetic trees and injects
failures after:

- all managed files have been installed;
- the synthetic active ALSA route has been replaced;
- the simulated application services have been restored.

Each injected failure must invoke the same exact rollback implementation used by
the successful scenario's explicit uninstall.

## Exact rollback

Rollback must:

1. remove every managed file that was absent in the Stage C3 first-install
   boundary;
2. restore the exact pre-Stage-C active ALSA file atomically;
3. remove only managed directories that were absent before installation and are
   empty after file removal;
4. restore all copied simulated service, mixer, module/DAC, route and reload
   state;
5. remove sandbox transaction markers;
6. compare the complete synthetic system and state fingerprints with the
   baseline;
7. report success only when the mismatch count is zero.

The successful install scenario must then run explicit uninstall through this
same rollback path and reach the same exact baseline.

## Safety boundary

Stage C4 must not:

- invoke `sudo`;
- require root;
- write `/etc`, `/usr/local`, `/var/lib`, `/run` or any production path;
- invoke `systemctl`, `amixer`, `modprobe`, `aplay`, `fuser` or CamillaDSP;
- open a PCM or device node;
- alter the Stage C1 package or Stage C3 evidence;
- create an approval marker in production;
- provide an activation or production install interface.

The rehearsal must fingerprint both input trees before and after execution and
fail if either changed.

## Evidence outputs

A successful Stage C4 run produces:

- `results.tsv`;
- `scenario-state.tsv`;
- `file-plan.tsv`;
- one journal per scenario;
- `evidence-manifest.tsv`;
- `report.txt`.

Expected scenarios are one successful install followed by explicit uninstall and
three injected-failure automatic rollbacks. Every scenario must finish with zero
baseline mismatches.

## Promotion boundary

A successful Stage C4 rehearsal permits implementation review of the real
root-owned mutation engine, still in blocked/prepare-only form. It does not
permit persistent installation.

Before physical activation can be considered, the project still requires:

- a reviewed root-owned transaction lock and fresh authoritative snapshot;
- real atomic install and exact rollback code with a single explicit token;
- route authority and bounded CamillaDSP service orchestration;
- finite real route probes;
- automatic direct alarm-bypass failback;
- EQ state/render/reload migration;
- dashboard health and degraded-mode reporting;
- deliberate physical failure injection and exact uninstall proof;
- explicit user authorisation.
