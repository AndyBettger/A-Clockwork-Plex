# Stage C7 root-owned disposable transaction result — 2026-08-05

## Result

**PASS on `plexamp-bedroom`.**

Stage C7 exercised real root-owned filesystem operations only inside four disposable synthetic system roots beneath:

```text
/var/tmp/a-clockwork-plex-stage-c7-root-transaction.zGuQjp
```

No production path, service, mixer, module, PCM, DAC, CamillaDSP process or production route lock was opened for mutation. Persistent Stage C activation remained blocked throughout.

## Inputs

```text
Stage C1 package: /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C6 evidence: /var/tmp/a-clockwork-plex-stage-c6-snapshot.zFiLqI
Branch head used: 4950b9cc9cd9243abf4a03128091c2b4675a3f59
```

## Top-level checks

All twelve checks passed:

1. `root-scope`
2. `input-replay`
3. `disposable-mapping`
4. `first-install-boundary`
5. `existing-directory-preservation`
6. `atomic-install`
7. `synthetic-route-selection`
8. `failure-injection`
9. `shared-rollback`
10. `exact-state-verification`
11. `production-boundary`
12. `activation-interface`

## Scenario results

| Scenario | Injected failure | Install verified | Rollback reason | Mismatches | Existing directories preserved |
|---|---|---:|---|---:|---:|
| `success-explicit-uninstall` | none | true | `explicit-uninstall` | 0 | true |
| `failure-after-files-installed` | `after-files-installed` | false | `automatic:after-files-installed` | 0 | true |
| `failure-after-route-selected` | `after-route-selected` | false | `automatic:after-route-selected` | 0 | true |
| `failure-after-state-recorded` | `after-state-recorded` | false | `automatic:after-state-recorded` | 0 | true |

The successful transaction and all three injected failures used the same rollback implementation and restored the exact baseline.

## Root-owned installed-state evidence

During the verified installed state, the important captured directories retained the expected root ownership and modes:

```text
etc/alsa             directory  755  uid=0 gid=0
etc/alsa/conf.d      directory  755  uid=0 gid=0
etc/sudoers.d        directory  750  uid=0 gid=0
```

The same modes and ownership were present after rollback in all four scenarios.

The physically validated direct ALSA route was restored with checksum:

```text
08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
```

## Defect discovered and corrected before PASS

The first physical Stage C7 attempt failed safely while seeding the first synthetic baseline because the genuine Stage C6 evidence does not list `/etc/alsa` and `/etc/alsa/conf.d` separately in `filesystem-state.tsv`.

The corrected engine now reconstructs the saved ALSA file's parent directory chain from the validated Stage C6 `rootfs`, preserving captured directory modes and ownership. `atomic_copy()` remains deliberately strict and still does not recursively invent an unknown path.

A regression test now models the genuine Pi evidence shape, preventing the earlier over-complete CI fixture from concealing this boundary again.

## What Stage C7 proved

- real root-owned atomic installation inside disposable roots;
- source checksum verification before and after each copy;
- exact candidate checksum, mode, UID and GID verification;
- existing captured directories were not chmodded or chowned during installation;
- `/etc/sudoers.d` remained `0750` throughout;
- synthetic split-bus route selection remained inside the disposable roots;
- successful explicit uninstall and three automatic failure rollbacks shared one implementation;
- exact type, mode, ownership and checksum restoration;
- Stage C1 and Stage C6 inputs remained unchanged.

## What Stage C7 did not prove

- production lock creation;
- production filesystem mutation;
- service-manager ordering or service behaviour;
- mixer, module, PCM, DAC or CamillaDSP behaviour;
- ALSA parsing or route health;
- runtime failback or reboot behaviour.

## Safety conclusion

Stage C7 passed its intended physical boundary. It does not approve or expose persistent installation or activation. The rehearsal directory is evidence only and must not be reused as a production transaction or rollback snapshot.
