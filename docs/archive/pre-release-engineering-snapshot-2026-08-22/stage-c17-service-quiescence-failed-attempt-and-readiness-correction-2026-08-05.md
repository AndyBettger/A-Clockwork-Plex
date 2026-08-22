# Stage C17 service-quiescence failed attempt and readiness correction — 2026-08-05

## Outcome

The first physical Stage C17 service-quiescence and restoration rehearsal failed safely after the three captured-active application services had already been restored.

The failure was not a package, route, service-restoration or DAC-format defect. It was a post-restoration readiness race: `systemctl is-active` reported Plexamp active before its Node audio engine had finished reopening the physical DAC and repopulating the ALSA `hw_params` fields.

No managed file was installed, systemd was not reloaded, no route was selected, CamillaDSP was not started, no mixer control was changed, no audio probe ran, and no transaction commit was written.

Persistent Stage C activation remains blocked.

## Physical attempt identity

- Evidence root: `/var/tmp/a-clockwork-plex-stage-c17-service-quiescence.Pc6VUK`
- Package root: `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- Accepted Stage C16 evidence: `/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.FFT4Rq`
- Production-lock lease: `stage-c14-lock-f037f3f388e058f16f13b71a`
- Authoritative transaction: `stage-c15-install-37bc55cdbb98967b6ea8496a`

The failed evidence directory must be retained and must not be reused for the corrected rehearsal.

## Checks completed before failure

The physical run passed the following boundaries:

1. root scope
2. input replay
3. protocol conformance
4. pre-lock host contract
5. pre-lock boundary
6. production-lock acquisition
7. authoritative transaction creation
8. transaction identity binding
9. filesystem snapshot
10. service snapshot
11. mixer snapshot
12. loopback snapshot
13. DAC snapshot
14. snapshot integrity
15. candidate staging
16. candidate manifest binding
17. candidate ALSA validation
18. candidate sudoers validation
19. candidate unit validation
20. candidate CamillaDSP validation
21. blocked-operation boundary
22. service quiescence
23. DAC release
24. pre-install boundary
25. application-service restoration

Exactly fourteen install, route, audio, commit and recovery operations remained blocked.

The failure then occurred during `verify-dashboard-health` with:

```text
physical DAC contract mismatch: {'access': ('MMAP_INTERLEAVED', '<missing>'), 'format': ('S16_LE', '<missing>'), 'subformat': ('STD', '<missing>'), 'channels': ('2', '<missing>'), 'rate': ('44100', '<missing>'), 'period_size': ('1024', '<missing>'), 'buffer_size': ('8192', '<missing>')}
```

The missing fields represented a transient closed `hw_params` observation while Plexamp was starting, not a changed physical contract.

## Independent cleanup and restoration proof

After the failed run, independent read-only checks confirmed:

- `/run/lock/a-clockwork-plex-audio-route.lock` absent
- `/var/lib/a-clockwork-plex/split-bus/transactions` absent
- `plexamp.service` active
- `shairport-sync.service` active
- `a-clockwork-plex.service` active
- dashboard redirect from `/` followed successfully to `/clock`
- final dashboard response: HTTP 200, `text/html; charset=utf-8`
- active ALSA route checksum unchanged:
  `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`
- strict DAC observer accepted the restored physical contract:
  - sample format `S16_LE`
  - channels `2`
  - rate `44100`
  - period size `1024`
  - buffer size `8192`
  - released `false`
  - owner count `1`
  - observed owner: PID `1767472`, user `andy`, command `node`, access `read-write`

The PID is observational evidence only and is not a stable contract value.

## Root cause

The original Stage C17 verifier performed the strict DAC observation immediately after exact service-state restoration. Service-state restoration proves the systemd active state but does not prove that Plexamp's internal Node audio engine has completed its asynchronous DAC-open sequence.

The strict DAC observer therefore sampled the physical device during a short interval in which the service was active but ALSA still reported closed runtime parameters.

## Correction

The corrected readiness layer is deliberately narrow:

1. wait for the fixed local dashboard URL to resolve to healthy HTTP 200 HTML;
2. poll the same strict physical DAC observer every 0.25 seconds;
3. allow at most 30 seconds for the exact known-good DAC contract and at least one owner to return;
4. retain every readiness observation in `restoration-readiness.tsv`;
5. fail closed if the strict contract or ownership does not return within the bounded interval.

The correction does not add any appliance mutation command and does not widen the Stage C17 operation boundary. Locking, snapshots, staging, candidate validation, service stop, DAC-release proof, exact service restoration, transaction closure and lock release remain owned by the original reviewed Stage C17 implementation.

## Corrected automated gate

The corrected branch passed:

```text
Ran 725 tests in 5.090s
OK
```

This includes focused regression coverage proving:

- a closed strict DAC observation followed by a ready observation is accepted without a blind fixed delay;
- dashboard readiness is awaited before strict DAC polling;
- polling is bounded and evidenced;
- the correction is a narrow subclass with no new appliance mutation command;
- the existing wrapper selects the corrected entry module explicitly;
- all prior Stage C safety tests remain intact.

Corrected head before this result record:

`0fe195660484855ea460abdd0efdb5c7fc128277`

## Safety conclusion

The first Stage C17 physical attempt demonstrated the intended fail-safe behaviour:

- service quiescence and DAC release were physically proved;
- installation and all later appliance mutations remained blocked;
- the captured application services were restored before cleanup;
- the disposable transaction and production lock were removed only after restoration;
- the stable direct ALSA route and physical DAC contract returned unchanged.

A corrected physical retry may use a fresh Stage C17 evidence directory only after the prepare-only wrapper has been pulled and reviewed again.
