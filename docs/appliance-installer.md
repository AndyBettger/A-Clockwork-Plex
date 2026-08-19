# A Clockwork Plex guarded appliance installer

`appliance-installer.sh` is the lower-level guarded installation and recovery engine used by A Clockwork Plex.

> **Normal installation:** use [`docs/INSTALL.md`](INSTALL.md) and run `bash setup.sh`. `setup.sh` is the supported human-facing entry point: it acquires the pinned CamillaDSP artifact, invokes this engine with the correct guarded arguments, and handles the interactive Plexamp claim checkpoint. Run `appliance-installer.sh` directly only when you deliberately need its advanced planning, profile or recovery controls.

The old root `install.sh` name has been removed. Historical evidence may still show commands using that former filename because those records describe what was actually run at the time.

## What this engine owns

The engine orchestrates existing specialist owners rather than duplicating their implementation. Depending on the selected route it coordinates:

- package/artifact validation;
- additive appliance package and paired main/NFC Python-environment bootstrap;
- Raspberry Pi I2C/PN532/DAC commissioning for a fresh bootstrap;
- the pinned Plexamp compatibility runtime;
- the pinned NFC listener;
- Weather observation-source configuration;
- dashboard service and kiosk integration;
- Direct or EQ audio installation;
- restricted appliance helpers and AirPlay integration;
- final whole-appliance verification inside the application transaction's commit boundary.

The forecast provider remains Open-Meteo; `--weather-observations` selects the current-observation source only.

## Safe default: read-only plan

Running the engine without `--apply` is deliberately non-mutating:

```bash
bash appliance-installer.sh
```

This is equivalent to `--plan`. It prints the selected profile, ownership boundaries, gates and commands that a guarded apply would use, then exits without changing production files, packages, services, routes, mixers, PCMs or configuration.

Examples:

```bash
# Inspect the default EQ + Ecowitt-push plan.
bash appliance-installer.sh

# Inspect Direct audio without applying it.
bash appliance-installer.sh --audio direct

# Inspect the Weather Underground profile.
bash appliance-installer.sh \
  --weather-observations weather-underground

# Inspect the staged fresh-Pi route.
bash appliance-installer.sh --fresh-bootstrap
```

## Guarded apply

Mutation requires both `--apply` and the exact confirmation token:

```bash
bash appliance-installer.sh \
  --apply \
  --confirm APPLY-A-CLOCKWORK-PLEX \
  [profile options]
```

Run an apply as the **normal project user, not root**. The engine rejects a root apply.

For ordinary fresh installation, do not construct this command yourself; `setup.sh` owns it.

## Modes

| Option | Meaning |
|---|---|
| `--plan` | Print the read-only installation plan. This is the default. |
| `--apply` | Run the selected guarded installation route. Requires the exact confirmation token. |
| `--confirm TOKEN` | Confirmation gate for `--apply`. The accepted token is `APPLY-A-CLOCKWORK-PLEX`. It is rejected without `--apply`. |
| `--fresh-bootstrap` | Use the staged fresh-Raspberry-Pi route: package/venv → hardware → player → NFC → full preflight → application transaction. |
| `-h`, `--help` | Print the engine's authoritative command-line help. |

Without `--fresh-bootstrap`, `--apply` uses the compatibility/convergence route for a host whose platform/player prerequisites already exist.

## Profile options

| Option | Accepted values / purpose |
|---|---|
| `--audio PROFILE` | `direct` or `eq`. Default: `eq`. |
| `--weather-observations PROVIDER` | `ecowitt-push` or `weather-underground`. Default: `ecowitt-push`. |
| `--project-user USER` | Normal appliance account. Defaults to the invoking/Sudo-origin user selected by the engine. |
| `--camilladsp-binary PATH` | Verified CamillaDSP 4.1.3 executable required by an EQ apply. Normal `setup.sh` acquires and supplies it automatically. |
| `--wu-station-id ID` | Weather Underground PWS station ID. Valid only with `weather-underground`. |
| `--wu-api-key-file PATH` | Path to a readable, regular, non-symlink WU API-key file. The secret itself is never accepted as a literal installer argument. |
| `--dashboard-url URL` | Local dashboard base URL. Default: `http://localhost:8088`. |
| `--non-interactive` | Require choices to come from arguments/environment rather than an interactive caller. |

The corresponding environment defaults currently understood by the engine are `ACP_AUDIO_PROFILE`, `ACP_WEATHER_OBSERVATIONS`, `ACP_PROJECT_USER`, `ACP_CAMILLA_BINARY`, `ACP_WU_STATION_ID`, `ACP_WU_API_KEY_FILE` and `ACP_DASHBOARD_URL`.

## Fresh-bootstrap sequence

`--fresh-bootstrap --apply` runs the guarded owners in this order:

1. package/artifact availability check;
2. fresh stage-zero read-only preflight;
3. additive package + paired application/NFC environment bootstrap;
4. guarded platform-hardware commissioning;
5. post-hardware/player-pending read-only preflight;
6. pinned Plexamp runtime owner;
7. pinned NFC-listener owner;
8. full host preflight;
9. one guarded whole-application transaction, including its final verifier.

The route fails closed. A hardware/player blocker does not fall through into NFC or application mutation.

### Reboot checkpoint

If I2C/DAC commissioning changes boot-time hardware configuration, the hardware owner returns `75`. The engine then prints:

```text
ROOT_INSTALL=REBOOT-REQUIRED
REBOOT_POLICY=OPERATOR-CONTROLLED
RESUME_COMMAND=...
```

The installer **never reboots automatically**. After the operator reboots, rerunning the printed `appliance-installer.sh` command is the direct-engine resume mechanism. When using the normal public workflow, simply rerun:

```bash
bash setup.sh
```

Successful additive/idempotent stages are rechecked rather than blindly repeated.

### Plexamp claim checkpoint

An unclaimed fresh Plexamp runtime can return its explicit claim-required status (currently exit `76`). The guarded engine stops before NFC/application mutation and propagates that status. The normal `setup.sh` wrapper handles this condition by launching the installed Plexamp Headless process for local claim and then resuming convergence.

Do not put Plex claim codes, Plex credentials or account passwords into installer arguments, environment variables or evidence logs.

## Weather Underground secret boundary

A WU apply requires both a station ID and an API-key **file path**:

```bash
bash appliance-installer.sh \
  --weather-observations weather-underground \
  --wu-station-id ISTATION1 \
  --wu-api-key-file /path/to/restricted/key-file \
  ...
```

The key-file path is forwarded to the preflight/application owners so they can validate and commission the credential without placing the literal API secret in `config.json`, browser state or argv. The file must be readable, regular and not a symlink.

For normal commissioning, prefer **Settings → Weather** as documented in `INSTALL.md` rather than constructing a direct WU apply.

## Direct and EQ audio profiles

### Direct

The Direct profile installs the physically accepted alarm-safe Direct route. Plexamp/AirPlay remain under Music Master while the alarm bypasses Music Master and joins the DAC-facing mix independently.

### EQ

EQ delegates to `scripts/audio/install-eq.sh` and its supported verify/repair/uninstall lifecycle. A fresh-appliance EQ install requests the `alarm-safe-direct` baseline before promoting the split-bus route. The top-level engine does not copy the specialist EQ implementation.

An EQ apply requires the exact verified CamillaDSP 4.1.3 binary path. Again, `setup.sh` acquires and supplies this for the normal installation path.

## Transaction and rollback policy

The guarded engine deliberately separates the prerequisite baseline from the application transaction:

- successfully installed additive APT prerequisites and verified application/NFC environments are retained after a later application failure;
- application-managed files, FIFO and service state are captured before application mutation;
- fresh EQ is unwound through the accepted EQ uninstaller before generic application-state restoration;
- `scripts/verify-appliance.sh` must pass before the application transaction may commit;
- a failed application transaction reports failure rather than leaving an unverified partial application as success.

A successful apply ends with markers including:

```text
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=fresh-bootstrap|compatibility
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

## Notable exit/status boundaries

These are the important orchestrator-level statuses, not an exhaustive replacement for the specialist scripts' diagnostics:

| Status | Meaning |
|---|---|
| `0` | Read-only plan completed, or guarded installation committed successfully. |
| `2` | Root-engine usage/profile/confirmation/required-input contract failure. |
| `75` | Controlled hardware reboot checkpoint; operator reboot required. |
| `76` | Pinned Plexamp runtime requires local claim; normally handled by `setup.sh`. |
| `78` | Explicit fresh hardware/player source or commissioning blocker where used by the staged owners. |
| other non-zero | A specialist gate/owner failed; the engine stops at that boundary and may propagate the specialist status. |

Always diagnose the first failed owner rather than continuing with unrelated manual changes.

## Verification and recovery

The engine prints the verifier that matches its selected profiles in plan mode. The final application transaction uses `scripts/verify-appliance.sh` as a commit gate.

The wider release/physical verification set also includes:

```bash
bash scripts/verify-fresh-bootstrap.sh
bash scripts/verify-appliance.sh
bash scripts/audio/verify-audio.sh
```

Use the profile/project arguments documented by the active acceptance runbook when running the formal release checks; do not guess them from this overview.

## Which installer should I use?

For almost everyone:

```bash
bash setup.sh
```

Use `appliance-installer.sh` directly when you specifically need to inspect a plan, reproduce an advanced profile boundary, resume/debug a guarded engine stage, or perform documented engineering/recovery work. It is intentionally powerful and explicit; it is not a second competing normal-install recipe.
