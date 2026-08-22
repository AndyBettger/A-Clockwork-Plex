# Stage C18 managed-file installation and exact-rollback rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

Stage C18 repeated the physically accepted Stage C17 lock, transaction, snapshot, candidate staging, validation, service-quiescence and DAC-release prefix. It then crossed the first production-filesystem mutation boundary by atomically installing exactly the twelve reviewed Stage C1 package files while the application services and DAC remained quiesced.

Every installed object was bound to the transaction candidate by path, type, device, inode, mode, root ownership and SHA-256 digest. Systemd reload and both active-route selections remained blocked after installation. The adapter then removed only the exact inodes it created, restored all managed directory state to the authoritative filesystem snapshot, restored the three captured-active application services, waited for dashboard and strict DAC readiness, and proved zero filesystem, service, route, mixer, loopback or DAC mismatch.

The exact-rollback transaction closed through the typed v4 lifecycle operation, the authoritative transaction was removed, and the production lock was released only after exact rollback had been proved.

No systemd reload occurred. No split-bus or direct-failback route was selected. No managed Stage C service started. No mixer control changed. No PCM or audio probe was opened. No install commit was written. Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.H3P4Po
```

Retain this directory together with the complete Stage C evidence chain until final Stage C release review.

## Replayed inputs

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C17 result  /var/tmp/a-clockwork-plex-stage-c17-service-quiescence.3ySKhd
```

Both input trees remained unchanged.

## Exact acceptance checks

All forty checks passed in the required order:

```text
root-scope                        PASS
input-replay                      PASS
protocol-conformance              PASS
pre-lock-host-contract            PASS
pre-lock-boundary                 PASS
production-lock-acquired          PASS
authoritative-transaction-created PASS
transaction-identity-binding      PASS
filesystem-snapshot               PASS
service-snapshot                  PASS
mixer-snapshot                    PASS
loopback-snapshot                 PASS
dac-snapshot                      PASS
snapshot-integrity                PASS
candidate-staging                 PASS
candidate-manifest-binding        PASS
candidate-alsa-validation         PASS
candidate-sudoers-validation      PASS
candidate-unit-validation         PASS
candidate-camilladsp-validation   PASS
blocked-operation-boundary        PASS
service-quiescence                PASS
dac-release                       PASS
managed-file-installation         PASS
installed-manifest-binding        PASS
post-install-boundary             PASS
exact-filesystem-rollback         PASS
application-service-restoration   PASS
dashboard-health                  PASS
exact-rollback-verification       PASS
exact-restoration-boundary        PASS
pre-mutation-abort-refusal        PASS
service-only-closure-refusal      PASS
candidate-evidence-copy           PASS
exact-rollback-close-v4           PASS
exact-transaction-cleanup         PASS
production-lock-released          PASS
input-integrity                   PASS
evidence-integrity                PASS
activation-interface              PASS
```

## Authoritative identities

The adapter generated and bound these identities while it held the production lock:

```text
production-lock lease  stage-c14-lock-b55671b0b4be88a868d821f4
transaction            stage-c15-install-53a1044e4c742ee7e94b56e1
action                 install
```

The caller supplied none of these identities.

## Snapshot and candidate-validation proof

All five authoritative snapshot domains completed under one transaction identity:

1. current ALSA and all managed filesystem destinations;
2. exact six-service state, with all three application services active;
3. exact four-control mixer state;
4. exact `snd_aloop` state;
5. exact DAC format and one structured owner.

All twelve reviewed package files were staged only inside the authoritative transaction. The staged paths, modes, owners and digests matched the Stage C1 manifest.

The private validators accepted:

- both staged ALSA routes without opening a PCM;
- the restricted sudoers rules through `visudo`;
- all three staged units through the isolated systemd model;
- the staged CamillaDSP configuration through the digest-pinned binary without audio.

## Blocked-operation proof

Before service quiescence, all eleven later operations refused with their exact typed identities. The blocked set covered:

- systemd reload;
- split-bus route selection;
- direct-failback route selection;
- managed Stage C service start and stop;
- split-bus health verification;
- finite music and alarm probes;
- commit-manifest writing;
- later mixer and service restoration operations.

After the twelve files were installed, the critical post-install gate again proved that systemd reload and active-route selection remained blocked.

## Managed-file installation proof

The adapter installed exactly twelve manifest files while Plexamp, Shairport Sync and the dashboard were stopped and while the physical DAC and fixed loopback endpoints had no owners.

Publication was no-overwrite and transaction-bound. Each installed file was verified for:

- fixed manifest destination;
- regular-file type and single-link state;
- exact device and inode adopted by the rollback ledger;
- exact manifest mode;
- root ownership;
- exact SHA-256 digest matching the transaction candidate.

Any destination conflict would have refused publication rather than overwriting an unrelated object.

## Exact filesystem rollback proof

Rollback occurred before systemd reload, route selection, managed service startup, audio probing or commit.

The adapter removed only exact recorded device/inode objects created by this rehearsal. It then proved:

- every managed file destination returned to its authoritative absent state;
- every transaction-created directory was removed;
- every captured-present directory retained its exact type, mode and ownership;
- the active direct ALSA route remained bit-for-bit unchanged;
- no temporary or pending publication object remained.

The filesystem rollback state recorded:

```text
managed_files_installed  true
filesystem_restored      true
systemd_reloaded         false
route_selected           false
committed                false
```

## Service restoration and appliance health

After exact filesystem rollback, the adapter restored the captured-active application services in the accepted order:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
```

It then proved:

- the exact six-service observation returned;
- the accepted direct ALSA route remained active;
- all four mixer controls were unchanged;
- the exact loopback snapshot was unchanged;
- dashboard HTTP health returned;
- the complete strict physical DAC runtime contract and one structured owner returned;
- zero filesystem, service, route, mixer, loopback or DAC mismatch remained.

## Versioned transaction closure

Because Stage C18 crossed both the service and managed-file mutation boundaries:

- the v2 pre-mutation abort correctly refused;
- the v3 service-only restored-rehearsal closure correctly refused;
- only the typed v4 exact-rollback closure was accepted.

The closing operation was:

```text
close-exact-rollback-rehearsal-transaction
```

The closure represented an exact rollback, not an install commit:

```text
mutation_started      true
managed_files_installed true
filesystem_restored   true
systemd_reloaded      false
route_selected        false
committed             false
```

The candidate, validation root and authoritative transaction were removed; transaction-parent state was restored; and only then was the exact production lock released.

## Evidence integrity

The evidence root contains the expected Stage C18 audit artefacts, including:

```text
results.tsv
identity.tsv
service-actions.tsv
managed-file-actions.tsv
restoration-readiness.tsv
typed-operations.json
blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
evidence-manifest.tsv
report.txt
```

The complete evidence tree was checksummed and contained no symlink or special object.

## Automated gate

Before the physical rehearsal, the complete branch suite passed:

```text
Ran 755 tests
OK
```

Focused Stage C18 coverage proved, among other things:

- the v1, v2 and v3 lifecycle histories remained frozen;
- v4 added only the exact-rollback closure;
- the permitted and blocked operation partition was exact;
- rollback was armed before the first production write;
- temporary, pending-publication and installed inodes were covered by rollback;
- an existing destination was never overwritten;
- install acceptance remained stricter than rollback identity;
- pathname substitution was refused;
- rollback preceded service restoration on every failure path;
- the normal order was install, block reload/route, rollback, restore and verify;
- no activation, persistence or keep-active interface existed.

## What Stage C18 proved

Stage C18 proved:

- the complete physically accepted Stage C17 prefix;
- first real production-filesystem installation of all twelve reviewed files;
- no-overwrite atomic publication;
- exact installed-manifest binding;
- mandatory partial-install rollback coverage;
- refusal of systemd reload and route selection after installation;
- exact inode-bound filesystem rollback;
- exact application-service restoration after filesystem rollback;
- bounded dashboard and DAC readiness;
- zero mismatch across filesystem, services, route, mixer, loopback and DAC;
- v2 and v3 lifecycle refusal after managed-file mutation;
- typed v4 exact-rollback closure;
- exact transaction and lock cleanup;
- no persistent activation interface.

## What Stage C18 did not prove

Stage C18 did not prove:

- systemd daemon reload with the managed units installed;
- live systemd recognition of the three managed units;
- active split-bus or direct-failback route selection;
- CamillaDSP startup through the managed service;
- split-bus health or finite music/alarm probes;
- install commit;
- automatic rollback after systemd-manager mutation;
- runtime direct failback;
- explicit uninstall;
- reboot persistence.

Those remain separately guarded roadmap stages.

## Safety conclusion

The first production-filesystem mutation boundary has now been physically exercised and exactly reversed. All twelve reviewed files were installed and verified while the appliance was quiesced, then removed through an inode-bound authoritative rollback before systemd or the active audio route could observe them.

The accepted direct appliance state returned with zero mismatch, the authoritative transaction and lock were cleaned up, and no persistent Stage C activation occurred.

The old master-EQ installer was not run. PR #2 must remain Draft, open and unmerged until explicit approval.
