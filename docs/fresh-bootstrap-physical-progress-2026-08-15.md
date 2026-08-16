# Fresh appliance bootstrap physical progress — 2026-08-15

Test target: spare SD card on the real Raspberry Pi appliance hardware, hostname `plexamp-test`, Raspberry Pi OS / Debian 13 (Trixie), 64-bit `aarch64`.

This file records Phase 7 physical bootstrap evidence while the accepted production SD card remains removed and untouched. The spare SD is intentionally reused across the acceptance attempts below so each repaired owner must revalidate/converge already-accepted prerequisite state rather than relying on a wipe between failures.

## Attempt 1 — Trixie inherited Python metadata

The package owner installed the additive fresh-Pi prerequisites and built both candidate Python environments. The NFC venv intentionally uses `--system-site-packages` so Raspberry Pi OS `python3-lgpio` is visible.

A raw whole-environment `pip check` then reported nine unrelated Debian system-site metadata issues (`types-flask-*`, `types-tree-sitter-languages`, `apt-listchanges`, `types-click-default-group`, and `types-seaborn`). The installer stopped before hardware, Plexamp, NFC-service, or application commissioning and restored the paired venv prestate.

The owner was corrected so NFC dependency checking remains fail-closed for the recursive listener dependency graph while unrelated inherited Debian distributions are reported as informational. The main isolated application venv retains a whole-environment `pip check`. Checkpoint #26 is recorded in `docs/eq-audio-installer-roadmap.md`.

## Attempt 2 — hardware passed; fresh Plexamp unit verification ordering exposed

After pulling checkpoint #26, the rerun established the package/venv baseline successfully:

- main application venv: PASS;
- NFC venv owned dependency graph: PASS, 23 owned distributions;
- the same nine Trixie inherited issues: informational only;
- Shairport Sync and other fresh prerequisites: present.

Real hardware commissioning also passed:

- Raspberry Pi I2C enabled/live;
- PN532 at I2C bus 1 address `0x24`;
- Raspberry Pi DAC Pro at ALSA card id `Pro`;
- no DAC boot-config mutation;
- no firmware, bootloader, or HAT EEPROM update.

The Plexamp owner SHA-verified pinned Node 20.20.2 and Plexamp Headless 4.13.2, then stopped because `systemd-analyze verify` was being run before the staged Node candidate existed at the rendered final `ExecStart` path.

Commit `1ca97d345ddb3caa2f1123db89146246101e9631` corrected that transaction ordering so verified candidates are promoted inside rollback protection before unit verification/installation.

## Attempt 3 — Plexamp claim/resume passed; standard NFC venv interpreter layout exposed

The corrected Plexamp transaction reached the intended human authentication boundary:

- pinned Node installed under `/opt/a-clockwork-plex/node-v20.20.2-linux-arm64`;
- pinned Plexamp Headless installed under `/home/andy/plexamp`;
- root installer exited `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`.

Plexamp was claimed locally on the Pi; no claim code was placed in argv, logs, evidence, or this document. On resume, package/venv, PN532 `0x24`, `CARD=Pro`, claimed Plexamp runtime and port `32500` all passed.

The NFC owner then rejected a healthy standard Python venv because it required `bin/python` not to be a symlink. The owner was corrected to validate the venv directory/`pyvenv.cfg`, executable interpreter, `sys.prefix != sys.base_prefix`, and required runtime imports instead. Tests #3368 passed on `40c179de6a80cf6b91e4e0b5d308264a6e871b1f`.

## Attempt 4 — NFC/full preflight passed; protected sudoers verification exposed

After the NFC correction (`ac623156612030cf154e86c9851ce34759402ddf`), the spare Pi passed package/artifact availability, both venvs, PN532 `0x24`, `CARD=Pro`, claimed Plexamp, guarded NFC service and the full mandatory host preflight. The application transaction then physically passed Ecowitt-push configuration, dashboard/kiosk and the alarm-safe Direct route SHA:

`654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`

Restricted-helper post-install verification failed because it tried to traverse protected real `/etc/sudoers.d` paths as the normal project user. The helper owner was changed to perform its protected read-back checks through the same root-aware boundary that owns those files. Rollback restored the application-managed prestate; prerequisites remained retained by policy. Root installer exit: `2`.

Tests #3374 / run `31898610147` passed on `302a1ee3979c34e404b280590e43450d7cd83c16`.

## Attempt 5 — helpers/AirPlay passed; final verifier repeated the protected sudoers assumption

After pulling `a3e960e41f5ff741276bbf94516e2a7faf535057`, the Direct rerun again passed the established fresh-bootstrap gates, then physically passed:

- Ecowitt-push configuration;
- dashboard/kiosk;
- alarm-safe Direct route;
- restricted helper installation on the real protected filesystem;
- guarded AirPlay/Shairport integration and metadata service enablement.

The final whole-appliance verifier passed every check except its two ordinary-user reads beneath `/etc/sudoers.d`:

```text
FAIL  alarm-sudoers            missing/unsafe: /etc/sudoers.d/a-clockwork-plex-alarm-audio
FAIL  shairport-name-sudoers   missing/unsafe: /etc/sudoers.d/a-clockwork-plex-shairport-name
```

The independent verifier was corrected so only those production-root protected-file checks use read-only `sudo -n`; alternate-root fixtures remain unprivileged. The failed final commit gate again restored the complete application-managed prestate. Root installer exit: `2`.

Tests #3380 / run `31899362927` passed on `ab6271f896464a7bbff37e74803fbfc3e18ec5a0`.

## Attempt 6 — protected verifier passed upstream; reused spare SD exposed missing EQ → Direct convergence

On 16 August 2026 the same spare SD was fast-forwarded and the Direct fresh-bootstrap acceptance command was run again with a new timestamped evidence log:

```bash
set -o pipefail
DIRECT_CMD=(
  bash install.sh
  --fresh-bootstrap
  --audio direct
  --weather-observations ecowitt-push
  --project-user "$USER"
  --non-interactive
  --apply
  --confirm APPLY-A-CLOCKWORK-PLEX
)
DIRECT_LOG="$EVIDENCE/20-direct-install-$(date +%Y%m%d-%H%M%S).txt"
"${DIRECT_CMD[@]}" 2>&1 | tee "$DIRECT_LOG"
rc=${PIPESTATUS[0]}
```

The already-proven substrate reconverged cleanly:

- package/main/NFC venv substrate: PASS;
- PN532 bus 1 address `0x24`: PASS;
- Raspberry Pi DAC Pro `CARD=Pro`: PASS;
- pinned/claimed Plexamp repair/resume: PASS;
- guarded NFC listener: PASS;
- full mandatory host preflight: PASS;
- application transaction reached the requested audio transition.

The run then stopped with the explicit application-installer guard:

```text
Direct profile switching from an already-installed EQ appliance is not enabled
```

Authoritative installer exit: `2`.

Evidence preserved at:

`/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`

This is a convergence gap, not a package, Trixie, hardware, Plexamp, NFC or preflight failure. The reused spare SD already contained the accepted EQ appliance from earlier Phase 7 work, and the requested Direct profile must therefore be able to converge from installed EQ without a manual uninstall.

### Source repair after Attempt 6

Commit `4bfd9d0ed83927473d0ae70f5947761de6fad817` (`Converge installed EQ appliances to Direct audio`) replaced the hard rejection with an enclosing-transaction-safe transition:

- the specialist EQ uninstaller is invoked with its original pre-EQ backup retained;
- the retained backup is staged by rename to a commit-pending tombstone rather than copied through the generic file transaction;
- the currently loaded `snd_aloop` state is captured before teardown;
- rollback restores the staged backup before generic application restore;
- the outer application transaction restores the captured loopback state through its pre-service restore hook, before captured EQ services are reactivated;
- the accepted Direct installer then owns the requested Direct route;
- the retained pre-EQ backup is removed only after the outer transaction has committed;
- no manual EQ uninstall is part of the acceptance procedure.

Tests #3421 / run `31975846667` passed for `4bfd9d0ed83927473d0ae70f5947761de6fad817`.

Commit `b4e64fcf279843a7f928c5da41252adb11aae00a` (`Add EQ to Direct transition regression coverage`) then added focused alternate-root regression tests for:

- installed EQ → requested Direct successful convergence and canonical Direct SHA;
- forced failure after Direct installation restoring the prior EQ marker/manifest/route/service files and retained-backup sentinel;
- specialist `--retain-preinstall-backup` behaviour;
- loopback restoration occurring before captured service reactivation;
- retained-backup staging/rollback/commit-boundary ordering.

Tests #3423 / run `31976778069` passed for `b4e64fcf279843a7f928c5da41252adb11aae00a`.

## Current physical acceptance position

The spare-SD appliance has physically proven the fresh package/venv baseline, PN532 `0x24`, Raspberry Pi DAC Pro `CARD=Pro`, pinned/claimed Plexamp runtime, guarded NFC listener service, full mandatory host preflight, Weather configuration, dashboard/kiosk, alarm-safe Direct routing, restricted helper packaging and guarded AirPlay integration. The sequence of failed commit gates has also repeatedly demonstrated that application-managed state is restored rather than being fixed forward manually.

The current source/CI blocker is cleared: installed EQ is now a supported source state when `--audio direct` is requested, and the success/rollback contract is covered by Tests #3423. The **physical retry is still pending**. It must reuse the existing evidence directory, pull the latest green branch head, rerun the same timestamped Direct command, and require the full application transaction to commit with root installer exit `0`. Any new unexplained nonzero result must be preserved and investigated without manual fix-forward.

The accepted production SD card remains removed and untouched as the recovery path. PR #2 remains Draft/open/unmerged until explicit approval.
