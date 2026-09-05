# A Clockwork Plex test-suite catalogue

This is the maintainer map for the automated regression suite under `tests/`.

The catalogue is maintained at **module level**: every live `tests/test_*.py` file appears exactly once below with the behaviour it is intended to protect. Individual `test_*` methods are deliberately discovered by `unittest` rather than copied into a second 900+ row list that would drift as soon as a test is renamed or split.

`tests/test_test_catalog.py` enforces the module inventory. Adding, renaming or deleting a `test_*.py` module therefore requires this catalogue to change in the same commit.

## Running the tests

From the repository root, use the maintained full validation gate:

```bash
bash scripts/run-tests.sh
```

That is the normal pre-commit/release command. It compiles maintained Python sources, runs shell syntax checks, runs JavaScript syntax checks and then runs the complete Python unit/regression suite.

To run only the Python suite:

```bash
venv/bin/python -m unittest discover -s tests -v
```

To run one module:

```bash
venv/bin/python -m unittest discover -s tests -p 'test_alarm_audio.py' -v
```

The `-v` output is also the mechanically maintained list of the individual test cases contained in that module. To re-run one specific case, use the fully qualified test ID printed by verbose `unittest`, for example:

```text
venv/bin/python -m unittest <module>.<TestCaseClass>.<test_method> -v
```

If the checkout uses `.venv/` rather than `venv/`, substitute that interpreter; `scripts/run-tests.sh` performs that selection automatically.

## Expected result and failure meaning

Unless a module entry says otherwise, the expected automated result is:

- process exit status `0`;
- every executed test case reports `ok` (or an intentional environment-dependent `skipped` where the test itself explicitly allows it);
- `unittest` finishes with `OK`;
- the full `scripts/run-tests.sh` gate additionally reports successful Python compile, shell syntax and JavaScript syntax stages.

The suite's **test count is not a release invariant**. Adding legitimate coverage is expected to increase it. A failure means the protected contract changed or regressed, or that the test/catalogue must be deliberately updated alongside an intentional design change; it should not be silenced just to recover a previous count.

These automated modules use fakes, temporary roots, mocked runners and source-contract inspection for potentially destructive installer/audio operations. They do **not** replace the physical Raspberry Pi acceptance procedure in [`fresh-appliance-acceptance-runbook.md`](fresh-appliance-acceptance-runbook.md).

## Module catalogue

### AirPlay, Shairport and playback handoff

- `tests/test_airplay_control_coordination.py` — Coordinates AirPlay lifecycle intent with central playback ownership so source hand-off does not fight the shared authority.
- `tests/test_airplay_hold_policy.py` — Checks paused-AirPlay hold/lease policy and the release of stale sessions.
- `tests/test_airplay_integration_installer.py` — Exercises guarded Shairport/AirPlay integration installation, rendered callbacks and managed service wiring.
- `tests/test_airplay_longform_ui.py` — Protects long-form spoken-audio classification, labels and seek-style AirPlay presentation.
- `tests/test_airplay_metadata_pending_ui.py` — Checks the active-AirPlay UI while metadata is still pending.
- `tests/test_airplay_navigation_ui.py` — Protects AirPlay navigation, drawer access and kiosk-safe presentation.
- `tests/test_airplay_playback_state_ui.py` — Checks Ready, Playing and Paused AirPlay state projection in the UI.
- `tests/test_airplay_receiver_name_ui.py` — Checks receiver-name presentation and its Settings wiring.
- `tests/test_airplay_state_resolution.py` — Resolves Shairport metadata/session signals into the authoritative AirPlay state.
- `tests/test_airplay_volume_authority.py` — Protects ownership, conversion and projection of AirPlay volume.
- `tests/test_airplay_wrapper_renderer.py` — Checks generation of the managed AirPlay wrapper commands used by Shairport Sync.
- `tests/test_bidirectional_handoff.py` — Exercises Plexamp ↔ AirPlay hand-off in both directions without unnecessary service restarts.
- `tests/test_metadata_airplay_resume.py` — Checks metadata-driven AirPlay resume/release behaviour after pause or interruption.
- `tests/test_mode_watch_handoff_safety.py` — Ensures the browser mode watcher cannot override stronger playback/screen ownership.
- `tests/test_playback_authority.py` — Protects the central playback-owner priority and arbitration model.
- `tests/test_playback_handoff.py` — Exercises transitions between Plexamp, AirPlay and idle ownership.
- `tests/test_playback_navigation.py` — Checks navigation decisions that follow playback ownership and local user intent.
- `tests/test_playback_transport.py` — Checks transport-command routing and source-specific play/pause/previous/next behaviour.
- `tests/test_rapid_airplay_resume.py` — Exercises rapid AirPlay pause/resume races and stale callback protection.
- `tests/test_shairport_integration_renderer.py` — Checks generation of managed Shairport Sync integration configuration.
- `tests/test_shairport_name.py` — Protects AirPlay receiver-name validation, restricted-helper application and rollback.
- `tests/test_shairport_session.py` — Checks server-side Shairport session lifecycle and state transitions.
- `tests/test_theme_component_and_airplay_marquee_followup.py` — Regression coverage for theme-aware shared components and the final AirPlay metadata marquee behaviour.

### Alarms and scheduling

- `tests/test_alarm_api.py` — Checks alarm-definition API validation, persistence and response contracts.
- `tests/test_alarm_audio.py` — Exercises alarm audio process control, gain/fade behaviour and failure handling.
- `tests/test_alarm_audio_api.py` — Checks alarm-audio test/stop/status API safety and validation.
- `tests/test_alarm_audio_preview.py` — Protects preview-tone playback behaviour independently of a real scheduled alarm.
- `tests/test_alarm_audio_preview_api.py` — Checks the preview-tone API lifecycle, validation and cleanup.
- `tests/test_alarm_audio_screen_ownership.py` — Ensures alarm audio owns the alarm screen for the correct lifetime.
- `tests/test_alarm_audio_streaming.py` — Exercises streamed/local alarm-source process creation, termination and error handling.
- `tests/test_alarm_config.py` — Checks alarm configuration parsing, normalisation, validation and persistence.
- `tests/test_alarm_deadline_timing.py` — Protects deadline-based alarm timing against drift, late wake-ups and repeated polling.
- `tests/test_alarm_defaults.py` — Checks safe defaults used when new alarm definitions are created.
- `tests/test_alarm_playback_takeover.py` — Exercises alarm priority takeover from music and restoration after the alarm ends.
- `tests/test_alarm_runtime.py` — Checks active alarm runtime state, Snooze, re-ring, Dismiss and lifecycle transitions.
- `tests/test_alarm_runtime_api.py` — Checks the API that exposes and controls active alarm runtime state.
- `tests/test_alarm_scheduler.py` — Protects recurrence, next-occurrence calculation and scheduler firing behaviour.
- `tests/test_alarm_scheduler_api.py` — Checks scheduler/status API projection and control boundaries.
- `tests/test_alarm_status_projection.py` — Checks compact next-alarm/status projection used by Clock and Settings surfaces.
- `tests/test_scheduled_alarm_audio.py` — Protects the scheduled-alarm gain/fade contract, Maximum Alarm Volume ceiling and bypass of music EQ/Music Master.

### Audio, EQ and CamillaDSP

- `tests/test_audio_eq.py` — Core three-band EQ state, validation, persistence and control-path regression coverage.
- `tests/test_audio_eq_daytime_theme_state.py` — Ensures EQ state is independent of daytime-theme selection and presentation state.
- `tests/test_audio_eq_failback_status_copy.py` — Protects user-facing status text when EQ safely fails back to Direct audio.
- `tests/test_audio_eq_offline.py` — Checks safe behaviour when the live EQ control path is unavailable.
- `tests/test_audio_eq_presenter_authority.py` — Protects the EQ presenter/read model as the authority for displayed runtime state.
- `tests/test_audio_eq_settings_authority.py` — Checks Settings as the persisted owner of EQ configuration without inventing runtime state.
- `tests/test_audio_eq_status_privilege.py` — Ensures read-only EQ status does not require inappropriate privileged execution.
- `tests/test_audio_eq_ui.py` — Checks Master Equalizer UI controls, labels and client wiring.
- `tests/test_audio_mixer.py` — Exercises the shared mixer model, gain validation and generated mixer commands.
- `tests/test_audio_mixer_scale.py` — Checks conversion between UI fader positions and the calibrated gain scale.
- `tests/test_audio_route_helper.py` — Exercises the restricted audio-route helper for guarded Direct/EQ transitions.
- `tests/test_audio_route_quiescence.py` — Ensures route-changing operations wait for the audio path to become quiescent.
- `tests/test_camilladsp_artifact_fetcher.py` — Checks pinned CamillaDSP artifact selection, download verification and failure handling.
- `tests/test_camilladsp_eq_bypass_contract.py` — Protects the CamillaDSP bypass/restore contract used by the production EQ.
- `tests/test_camilladsp_service_lifecycle.py` — Checks managed CamillaDSP service lifecycle expectations and ownership.
- `tests/test_direct_audio_installer.py` — Exercises installation/convergence of the supported Direct-audio profile.
- `tests/test_direct_audio_profile.py` — Checks the Direct profile's ALSA/runtime assets and expected routing contract.
- `tests/test_eq_audio_backup_library.py` — Checks backup/restore helpers used before protected EQ-audio mutations.
- `tests/test_eq_audio_baseline_profiles.py` — Protects accepted Direct and EQ baseline profile contents and invariants.
- `tests/test_eq_audio_entry_hardening_contract.py` — Checks fail-closed validation and privilege boundaries at EQ-audio entry points.
- `tests/test_eq_audio_entry_scripts.py` — Exercises retained public EQ-audio lifecycle scripts and their argument/dispatch contracts.
- `tests/test_eq_audio_install_idempotence_and_failure.py` — Checks EQ installation idempotence, partial-failure handling and safe retry behaviour.
- `tests/test_eq_audio_installer_libraries.py` — Exercises installer library functions, rooted fixture installs and rendered CamillaDSP service identity.
- `tests/test_eq_audio_installer_profiles.py` — Checks profile selection, validation and installer dispatch for supported audio profiles.
- `tests/test_eq_audio_preflight_safety.py` — Protects the read-only EQ preflight gate and its refusal of unsafe states.
- `tests/test_eq_audio_protected_manifest_paths.py` — Ensures protected audio manifests only own approved paths and reject path escape/conflicts.
- `tests/test_eq_audio_runtime_assets.py` — Checks required production EQ runtime assets, templates and service/config wiring.
- `tests/test_eq_audio_runtime_safety.py` — Protects runtime security/identity invariants including unprivileged CamillaDSP execution.
- `tests/test_eq_audio_runtime_snapshot_and_permissions.py` — Checks runtime snapshots, ownership and permissions for managed EQ-audio files.
- `tests/test_eq_settings_status_pill_and_runtime_cache_ignore.py` — Regression coverage for EQ Settings health-pill presentation and exclusion of volatile runtime cache from source ownership.
- `tests/test_eq_to_direct_application_transition.py` — Exercises application-level convergence from EQ back to Direct audio.
- `tests/test_eq_uninstall_desktop_audio_quiesce.py` — Checks that EQ uninstall safely quiesces competing desktop audio before route removal.
- `tests/test_mixer_controller.py` — Exercises the restricted live mixer controller, validation, authority and command execution.

### Installer, appliance bootstrap and platform

- `tests/test_appliance_application_installer.py` — Exercises application/dashboard construction within a rooted disposable install fixture.
- `tests/test_appliance_application_transaction.py` — Checks transactional application installation, rollback and commit semantics.
- `tests/test_appliance_component_adapters.py` — Checks installer adapters that invoke independently owned appliance components safely.
- `tests/test_appliance_helpers_installer.py` — Exercises installation and permissions of restricted appliance helper commands.
- `tests/test_appliance_package_installer.py` — Exercises package/environment installation stages against fixture roots and fake runners.
- `tests/test_appliance_packages.py` — Checks the declared appliance package set and package-stage planning/validation.
- `tests/test_appliance_preflight.py` — Protects full-appliance preflight checks and fail-closed prerequisite reporting.
- `tests/test_appliance_profile_matrix.py` — Checks supported installer profile combinations and rejects invalid profile matrices.
- `tests/test_appliance_transaction.py` — Checks top-level appliance transaction state, rollback markers and commit behaviour.
- `tests/test_appliance_verifier.py` — Exercises the post-install appliance verifier against good and deliberately broken fixture states.
- `tests/test_fresh_bootstrap_verifier.py` — Exercises the non-destructive fresh-bootstrap verifier against fixture roots.
- `tests/test_full_installer_plan.py` — Checks the guarded installer's plan-only stage order and intended mutation ownership.
- `tests/test_full_installer_verifier_plan.py` — Checks verifier planning/order without performing appliance mutations.
- `tests/test_installer_repository_dependencies.py` — Protects exact repository dependency-manifest closure for both supported installer paths.
- `tests/test_platform_hardware_installer.py` — Exercises guarded Raspberry Pi/I2C/DAC platform commissioning against fake hardware roots.
- `tests/test_plexamp_commissioning_wiring.py` — Checks setup/installer dependency closure, Reset UI/backend wiring and syntax contracts for the Plexamp commissioning owner.
- `tests/test_project_user_portability.py` — Prevents live installer/runtime sources from assuming a specific username or home directory.
- `tests/test_root_installer_apply_gate.py` — Exercises root apply gates, confirmations, transaction rollback and fail-closed mutation rules.
- `tests/test_user_setup_installer.py` — Checks the public `setup.sh` hand-off, project-user selection and interactive reboot/Plexamp-claim checkpoints.

### Dashboard, display and Settings UI

- `tests/test_application_state.py` — Exercises persisted/shared application state, atomic updates and runtime-state boundaries.
- `tests/test_configuration_reset_commissioning.py` — Exercises combined ACP + Plexamp commissioning Reset planning, stale-token binding, cross-owner rollback and commissioning-only reset.
- `tests/test_dashboard_browser_auth_migration.py` — Protects browser-auth/session migration behaviour used by the dashboard kiosk.
- `tests/test_dashboard_integration_installer.py` — Exercises dashboard/kiosk integration installation and managed file/service wiring.
- `tests/test_dashboard_kiosk_install_safety.py` — Checks kiosk installation is scoped to the intended desktop user/session and safe paths.
- `tests/test_dashboard_service_install_safety.py` — Checks dashboard systemd service rendering, identity and install safety.
- `tests/test_daytime_themes.py` — Protects the daytime theme registry, token sets and theme-selection wiring.
- `tests/test_display_dimming.py` — Exercises scheduled night dimming, touch-to-wake and display-dimming state rules.
- `tests/test_final_clock_ui_polish.py` — Regression coverage for final Clock typography, colon timing, alarm annunciator and theme presentation.
- `tests/test_input_activity.py` — Checks browser/input activity tracking used by idle-return and display behaviour.
- `tests/test_screen_projection.py` — Core screen-authority projection tests for requested, owned and effective dashboard modes.
- `tests/test_screen_projection_activity.py` — Checks local activity/idle timing interaction with screen projection.
- `tests/test_screen_projection_navigation_epoch.py` — Protects navigation-epoch ordering so stale navigation cannot overwrite newer intent.
- `tests/test_screen_projection_takeover.py` — Exercises stronger screen-owner takeover and restoration semantics.
- `tests/test_screen_projection_ui.py` — Checks browser-side screen-projection wiring and mode-following presentation.
- `tests/test_settings_alarm_workspace.py` — Protects the unified alarm Settings workspace, alarm cards, repeat days and sound controls.
- `tests/test_settings_audio_level_cards.py` — Checks Settings output-level cards and labels for Music Master, source trims and Maximum Alarm Volume.
- `tests/test_settings_completion.py` — Regression coverage for completed Settings sections and removal of obsolete placeholder behaviour.
- `tests/test_settings_eq_runtime_authority.py` — Checks that Settings displays authoritative live EQ runtime status rather than stale local assumptions.
- `tests/test_settings_ipad.py` — Protects split-view/touch Settings structure, navigation and responsive tablet-style layout.
- `tests/test_settings_motion_controls.py` — Checks Settings controls for display transition style and duration.
- `tests/test_settings_numeric_and_theme_closure.py` — Exercises numeric keyboard/validation details and final theme/night Settings closure.
- `tests/test_settings_pass_a.py` — Broad final Settings pass: JS syntax, clock-card limits, keyboard scrolling, status cleanup, service refresh, About links and kiosk-safe external links.
- `tests/test_settings_physical_followup.py` — Physical-follow-up regressions: autosave ownership, calibrated audio faders, alarm ceiling copy, EQ layout, read-only hardware route and AirPlay rename transaction.
- `tests/test_settings_polish_followup.py` — Protects subsequent Settings visual/interaction polish identified during physical review.
- `tests/test_settings_selects.py` — Checks themed/select control behaviour and Settings dropdown presentation.
- `tests/test_settings_weather_observation_controls.py` — Checks Weather observation-source Settings controls, status and provider-specific visibility.
- `tests/test_settings_weather_rainfall_controls.py` — Checks rainfall-history Settings controls, period selection and status presentation.
- `tests/test_time_formatting.py` — Checks shared 12/24-hour and date/time formatting used across dashboard surfaces.
- `tests/test_unified_settings.py` — Core backend tests for Settings snapshot, validation, revision handling and transactional apply.

### Weather

- `tests/test_forecast_range_ui.py` — Checks forecast-range presentation and horizontal scrolling for longer forecast horizons.
- `tests/test_managed_weather_secret_verifier.py` — Exercises verification of the root-owned Weather Underground secret without exposing its value.
- `tests/test_weather_config_installer.py` — Exercises installer ownership of Weather configuration while preserving commissioned provider choices.
- `tests/test_weather_credentials.py` — Protects write-only Weather Underground credential storage, redaction and API boundaries.
- `tests/test_weather_forecast.py` — Exercises Open-Meteo fetching, normalisation, caching, freshness and failure fallback.
- `tests/test_weather_forecast_settings.py` — Checks forecast Settings validation, persistence and refresh behaviour.
- `tests/test_weather_forecast_ui.py` — Protects forecast cards/status attribution and browser-side rendering.
- `tests/test_weather_live_state.py` — Checks authoritative live-weather projection and freshness/staleness behaviour.
- `tests/test_weather_observation_settings.py` — Checks observation-provider configuration defaults, validation and persistence.
- `tests/test_weather_observation_source_authority.py` — Ensures the selected provider owns outdoor values while only fresh Ecowitt data may supplement WU indoor readings.
- `tests/test_weather_observation_store.py` — Exercises persisted observation state, freshness timestamps and safe update/expiry behaviour.
- `tests/test_weather_observations.py` — Exercises Ecowitt/WU observation parsing, normalisation and provider-independent field mapping.
- `tests/test_weather_rain_history_scrollbar.py` — Protects the rainfall-history horizontal scrollbar/presentation behaviour.
- `tests/test_weather_rainfall_dashboard_history.py` — Checks historical rainfall data projected into the dashboard Weather view.
- `tests/test_weather_rainfall_history.py` — Exercises WU daily-history acquisition, period aggregation, cache/update and current-day handling.
- `tests/test_weather_rainfall_lifetime.py` — Checks retained station-lifetime/Rainy Day Fund rainfall accumulation and persistence.
- `tests/test_weather_rainfall_total.py` — Checks rainfall total derivation and precedence between provider-native and calculated values.
- `tests/test_weather_repeat_preservation.py` — Ensures repeat `setup.sh` preserves a commissioned Weather provider and settings unless explicitly changed.
- `tests/test_wu_application_verifier_handoff.py` — Checks Weather Underground state/secret hand-off into the application verifier.
- `tests/test_wu_payload_inspector.py` — Exercises WU payload inspection/diagnostics while redacting credentials and sensitive values.

### Plexamp and NFC

- `tests/test_nfc_listener_installer.py` — Exercises NFC listener installation, service wiring and expected PN532 integration ownership.
- `tests/test_nfc_python_dependency_check.py` — Checks the dedicated NFC Python environment contains the required importable dependencies.
- `tests/test_plexamp_browser_storage_probe.py` — Protects the disposable-profile browser-storage metadata inventory: Web Storage key names/families only, IndexedDB database/object-store metadata only, no stored values/records/transactions, bounded sensitive-name redaction and loopback-only transport reuse.
- `tests/test_plexamp_commissioning.py` — Protects the narrow loopback-only Plexamp player-name/audio-output commissioning owner, immutable baseline capture, dynamic managed-output resolution, stale-state refusal and rollback.
- `tests/test_plexamp_home_customization_probe.py` — Protects the disposable-profile Home customisation key-family inventory: bounded namespace, key-names-only reads, no stored values/mutation and loopback-only transport reuse.
- `tests/test_plexamp_home_hub_probe.py` — Protects the bounded disposable-profile Plexamp effective-Home hub-shape probe: fixed discovery authority, no primitive/sensitive values, no arbitrary expression input and reuse of the loopback-only transport.
- `tests/test_plexamp_runtime_installer.py` — Exercises pinned Plexamp Headless/Node runtime installation, claim-state handling and service wiring.
- `tests/test_plexamp_ui_handoff_retirement.py` — Guards retirement of superseded Plexamp UI hand-off artefacts in favour of current screen authority.
- `tests/test_plexamp_upgrade_preparation_safety.py` — Checks Plexamp upgrade preparation remains non-destructive and does not bypass installer ownership.

### Documentation, release hygiene and retirement guards

- `tests/test_current_project_documentation.py` — Checks maintained project documentation describes the current appliance rather than superseded architecture.
- `tests/test_docs_catalog.py` — Enforces the intentionally small user-facing `docs/` root, classified development/archive trees and single live roadmap authority.
- `tests/test_fresh_appliance_acceptance_runbook.py` — Checks the maintained physical acceptance runbook still covers required fresh-appliance checkpoints and safe commands.
- `tests/test_release_hygiene_contract.py` — Protects release-hygiene invariants such as clean retained-source boundaries and current release evidence.
- `tests/test_retired_audio_lab_guard.py` — Prevents retired pre-production audio-lab/rehearsal executables and tests from returning to live source.
- `tests/test_retired_legacy_airplay_scripts_guard.py` — Prevents superseded legacy AirPlay scripts/callbacks from returning.
- `tests/test_retired_legacy_helper_installers_guard.py` — Prevents retired standalone helper installers from returning outside transactional ownership.
- `tests/test_retired_stage_c_guard.py` — Prevents the deliberately retired Stage-C implementation/script/test families from returning.
- `tests/test_script_catalog.py` — Ensures every retained executable/script is represented in `scripts/README.md` and retired scripts stay absent.
- `tests/test_test_catalog.py` — Ensures every live `tests/test_*.py` module is represented exactly once in this catalogue and that the documented run/result contract remains present.

## Maintenance rule

When a test module is added, renamed or removed:

1. update the appropriate module entry above in the same change;
2. run `venv/bin/python -m unittest discover -s tests -p 'test_test_catalog.py' -v`;
3. run the relevant changed subsystem tests;
4. run `bash scripts/run-tests.sh` before recording the change as release-green.

The catalogue guard intentionally compares the Markdown inventory with the live `tests/test_*.py` filesystem set in both directions. That catches both undocumented new tests and stale catalogue entries for tests that no longer exist.