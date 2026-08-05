# Stage C4 sandbox transaction and exact-rollback result — 5 August 2026

Status: **PASS on `plexamp-bedroom`**. This was a user-owned synthetic-filesystem rehearsal. No privileged command, production installation, audio-route change or persistent Stage C activation occurred.

## Run identity

- Host: `plexamp-bedroom`
- Invoking user: `andy`
- Repository head used for the physical Pi run: `95e806a4c0b221a2e831929404623641d14868e0`
- Stage C1 package: `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- Stage C3 review evidence: `/var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F`
- Stage C4 sandbox: `/var/tmp/a-clockwork-plex-stage-c4-sandbox.29DbuW`
- Confirmation token: `STAGE-C4-SANDBOX-TRANSACTION`
- Sandbox version: 2

The wrapper ran as the normal project user. It invoked no `sudo` command, opened no PCM or device, and constrained every mutation beneath the fresh mode-0700 Stage C4 directory.

## Result checks

All nine Stage C4 checks passed:

1. `input-replay`
2. `sandbox-scope`
3. `first-install-boundary`
4. `install-success`
5. `explicit-uninstall-rollback`
6. `failure-injection`
7. `automatic-rollback`
8. `exact-state-verification`
9. `production-boundary`

The engine reported:

```text
A Clockwork Plex Stage C4 sandbox transaction rehearsal passed.
No production path was written or changed. Persistent activation remains blocked.
```

## Input replay and first-install boundary

The run independently replayed the exact Stage C1 package and complete Stage C3 evidence. All twelve managed package files began absent in each synthetic scenario.

The candidate file plan retained the reviewed modes and checksums for:

- two route definitions;
- the CamillaDSP split-bus configuration;
- defaults and deterministic `snd_aloop` persistence;
- the restricted sudoers rule;
- three systemd units;
- the route helper;
- the pinned CamillaDSP 4.1.3 binary.

The synthetic active route began as the physically validated pre-Stage-C ALSA file with SHA-256:

```text
08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
```

## Successful transaction and explicit uninstall

The `success-explicit-uninstall` scenario:

1. installed and verified all twelve candidate files atomically beneath its synthetic root;
2. selected and verified the synthetic split-bus active route;
3. restored the simulated application-service state;
4. reached the install verification boundary;
5. invoked the same rollback implementation used by failure handling;
6. restored the complete baseline with zero mismatches.

Its recorded state was:

```text
success-explicit-uninstall  none  true  explicit-uninstall  0
```

## Failure injection and automatic rollback

Three independent scenarios injected a failure after progressively later transaction boundaries:

```text
failure-after-files-installed    automatic:after-files-installed    0
failure-after-route-selected     automatic:after-route-selected     0
failure-after-services-restored  automatic:after-services-restored  0
```

Each failure used the exact same rollback function as explicit uninstall. Every scenario finished with `rollback_mismatches=0`.

This proves the rollback path is not a separate demonstration-only implementation that could drift away from the real error path.

## Directory-mode restoration

CI had previously exposed a genuine rollback defect: installing candidate directory metadata could change the mode of a pre-existing managed parent directory, while rollback removed only newly created directories.

The corrected engine now captures and restores every pre-existing managed directory mode before final baseline comparison.

The real Stage C3 evidence recorded `/etc/sudoers.d` as mode `0750`. All four Stage C4 scenarios restored the synthetic equivalent to exactly `0750`:

```text
failure-after-files-installed     750
failure-after-route-selected      750
failure-after-services-restored   750
success-explicit-uninstall        750
```

The evidence manifest also records that restored mode.

## Exact rollback conclusion

Across all four scenarios:

- managed files that were absent at the first-install boundary were removed;
- the exact original active ALSA file was restored;
- only newly created empty managed directories were removed;
- captured modes of pre-existing managed directories were restored;
- simulated service, mixer, loopback/DAC, route and daemon-reload state returned to baseline;
- transaction markers were removed;
- complete system/state fingerprints matched their baselines;
- final rollback mismatches were zero.

The Stage C1 package and Stage C3 evidence trees remained unchanged.

## What Stage C4 proves

Stage C4 proves the reviewed file-transaction mechanics in synthetic filesystems:

- exact input replay;
- first-install absence handling;
- atomic candidate installation and verification;
- synthetic route selection;
- successful explicit uninstall;
- automatic rollback at three failure points;
- restoration of files, state and pre-existing directory modes;
- zero-mismatch final verification.

## What Stage C4 does not prove

Stage C4 deliberately does not claim to prove:

- real ALSA parsing or PCM availability;
- CamillaDSP startup, health or physical DAC ownership;
- real systemd ordering or service behaviour;
- real music/alarm lane probes;
- runtime direct alarm-bypass failback;
- EQ migration or dashboard health.

Those remain later guarded physical boundaries.

## Safety conclusion

Stage C4 clears the promotion boundary for implementation review of the real root-owned transaction engine in blocked/prepare-only form.

It does not authorise persistent installation. The Stage C3 evidence remains rehearsal evidence only and must never be reused as an activation-authoritative backup. Any future authorised activation must acquire the single route lock and capture a new root-owned snapshot immediately before mutation.

No production file was opened for writing, no service-manager or audio command executed, no approval marker was created, and persistent Stage C activation remains blocked.
