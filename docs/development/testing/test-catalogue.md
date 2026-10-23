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
- `tests/test_airplay_hi_res_snapshot.py` — Checks the read-only high-resolution AirPlay timing snapshot's frame-duration calculations, CamillaDSP scalar extraction and journal-address redaction, and pins the physically accepted production fixed-192 timing geometry.
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
- `tests/test_backup_restore_layout.py` — Protects Backup/Restore Preview detail-grid shrink/wrap behaviour and the cache-busted stylesheet so long technical paths stay inside the 1280×720 Settings viewport.
- `tests/test_configuration_reset_commissioning.py` — Exercises combined ACP + Plexamp commissioning Reset planning, stale-token binding, cross-owner rollback and commissioning-only reset.
- `tests/test_configuration_backup_restore_v2_orchestrator.py` — Protects dormant schema-v2 Backup/Restore orchestration: secret-safe envelope assembly, read-only combined browser Preview, native→Home→server commit ordering, reverse browser rollback on later failure, stale-target refusal, browser-only restore and post-commit finalize handling.
- `tests/test_configuration_restore_v2.py` — Protects backward-compatible schema-v2 Restore validation, native/Home logical ownership separation, secret/identity exclusion, value-redacted Preview summaries and rejection of source-bound Home state.
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

### News

- `tests/test_news_article_qr.py` — Protects the BBC News article hand-off boundary: canonical BBC News HTTPS URL validation, link-free public snapshots, opaque story-id lookup and local SVG QR generation without arbitrary outbound navigation.
- `tests/test_news_custom_feed_layout.py` — Protects the physical configurable-News follow-up: News-owned feed-editor placement, deliberate feed-card spacing and a bounded touch-scrollable News section rail.

### Weather

- `tests/test_forecast_range_ui.py` — Checks forecast-range presentation and horizontal scrolling for longer forecast horizons.
- `tests/test_managed_weather_secret_verifier.py` — Exercises verification of the root-owned Weather Underground secret without exposing its value.
- `tests/test_weather_config_installer.py` — Exercises installer ownership of Weather configuration while preserving commissioned provider choices.
- `tests/test_weather_credentials.py` — Protects write-only Weather Underground credential storage, redaction and API boundaries.
- `tests/test_weather_forecast.py` — Exercises Open-Meteo fetching, normalisation, caching, freshness and failure fallback.
- `tests/test_weather_forecast_settings.py` — Checks forecast Settings validation, persistence and refresh behaviour.
- `tests/test_weather_forecast_ui.py` — Protects forecast cards/status attribution and browser-side rendering.
- `tests/test_weather_live_state.py` — Checks authoritative live-weather projection and freshness/staleness behaviour.
- `tests/test_weather_rain_event_summary.py` — Checks active/last WU-derived rain-event provenance projection, metric formatting, cross-midnight spans and suppression for native providers.
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

### ACP shell / navigation

- `tests/test_acp_design_tokens.py` — Protects the #94 Phase A semantic design-token boundary, load order, palette derivation and first migrated shared/application-surface consumers.
- `tests/test_acp_surface_host.py` — Protects the #94 Phase A fail-safe same-document surface-host seam: load order, prepare/commit lifecycle, View Transition ownership and the unchanged full-route fallback for unmigrated surfaces.

- `tests/test_os_keyboard_choice.py` — Protects the five-minute browser-session native OSK trial switch, original input hint restoration, Advanced UI wiring and non-regression of the accepted ACP HTML keyboard.

### Plexamp and NFC

- `tests/test_squeekboard_resource_overlay.py` — Guards private GResource stylesheet inventory, overlay mapping verification, symlink refusal and candidate-only CSS injection.
- `tests/test_squeekboard_gtk_cascade.py` — Proves the isolated GTK3 CSS cascade probe uses synthetic key contexts and never alters Squeekboard or global GTK.
- `tests/test_squeekboard_compact_number.py` — Guards private centred British numeric layout, symmetric margins, seven exact files and accepted v1 preservation.
- `tests/test_squeekboard_acp_theme_contract.py` — Checks Classic Dark fallback and all 23 existing ACP day/classic-night/astronomy-night palette selections.
- `tests/test_squeekboard_live_css_lookup.py` — Guards disposable same-process GLib resource relookup and atomic stylesheet replacement without contacting the OSK.
- `tests/test_squeekboard_gtk_hot_style.py` — Checks same-context GTK CSS-provider colour reload and the independent no-invalidate CLI option.
- `tests/test_squeekboard_hot_css_source_patch.py` — Tests the source-only candidate GTK widget CSS directory watcher, exact reversible insertions and fail-closed vendor anchors.
- `tests/test_squeekboard_hot_css_source_audit.py` — Audits reversible C source changes, hashes, read-only diff output and incompatible/symlinked source rejection.
- `tests/test_c3_night_boundary_guard.py` — Guards one-minute C3 schedule rehearsal against user-accepted 22:00–07:00 settings, checks alarm and trial inactivity, arms independent timed restoration before revisioned Settings updates, preserves unrelated configuration, verifies restored state and refuses dangerous/symlinked or conflicting trials.
- `tests/test_squeekboard_night_shadow_diagnostic.py` — Local-loopback, strict same-origin, manual one-shot C3 night shadow diagnostics; Flask route reads only saved night settings, alarm-screen status and Linux-input sequence while an explicitly URL-opted-in Settings button supplies live browser night state; tests reject malformed/proxied/LAN requests and assert no CSS writes, OSK ownership, timers, retention or global polling.
- `tests/test_squeekboard_night_shadow_compare.py` — Offline read-only snapshot comparator between ACP browser night status and Python schedule/alarm/Linux-input evidence; classifies exact parity, settings drift, alarm-presentation uncertainty, short time-boundary ambiguity and missing input. Never owns/writes C3 CSS, alarm state, dashboard timers or vendor keyboard.
- `tests/test_squeekboard_night_observation_plan.py` — Read-only browser-vs-server alarm-screen evidence (including inconsistent/missing presentation), exact Linux input sequence baseline/advance/reset/preview suppression and schedule gates, validated interaction deadlines and contract checks against current ACP JavaScript/input/alarm runtime; explicitly no CSS, services, keyboard processes or runtime integration.
- `tests/test_squeekboard_night_schedule_plan.py` — Read-only Python parity against ACP's live JavaScript local-wall-clock night scheduling: exact start/end semantics, overnight/full-day windows, Europe/London DST folds/skips, explicit preview and alarm suppression, strict invalid-state refusal and no Squeekboard/service/CSS writes. No production Python scheduler has been installed.
- `tests/test_squeekboard_c3_startup.py` — Opt-in XDG desktop-login entry, idempotent enable/disable, no foreign autostart overwrite, wait for vendor singleton before C3 handoff, stale pointer after reboot, process-overlap refusal, absent-stock fallback. No real Pi desktop state modified in tests.
- `tests/test_squeekboard_c3_dev.py` — Reversible login-scoped native C3 Squeekboard development service (no timer or boot takeover): pinned candidate checks reused from 180-second trial, stock handover, single candidate requirement, manual stop/stock recovery, and dev-only eligibility for the existing ACP browser CSS sync.
- `tests/test_squeekboard_theme_sync.py` — Verifies C3 theme-sync loopback/same-origin JSON policy, exact daytime/night payload schema, reuse of the 23-palette planner, explicit 180s trial opt-in and live PID/timer gate, idempotent private-file-only CSS updates, symlinked-lock refusal, browser event wiring and default-disabled preservation of stock/C2.
- `tests/test_squeekboard_hot_css_trial.py` — Guards independent C3 180s trial/240s rescue, dual C2/C3 overlap refusal, source/binary hash gate, Classic Dark first paint, CSS env exclusion from stock restore, and safe failure paths.
- `tests/test_squeekboard_hot_css_stage.py` — Checks C3-only 0700 private hot-CSS staging, Classic Dark default, 23 allowlisted IDs and SHA-exact source verification, candidate-only higher-contrast Midnight Blue override preserving original C2 bytes, atomic file replacement, rejection of unexpected changes/symlinks/hardlinks, and no stock/C2 OSK mutation.
- `tests/test_squeekboard_hot_css_artifact.py` — Protects the exact C3 GitHub ZIP/package/ELF SHA-256s, pinned source attestation, tamper/extra-member rejection, and read-only target-Pi ABI inspection independent of accepted C2 trial.
- `tests/test_squeekboard_hot_css_arm64_build.py` — Guards source-hash-locked disposable C3 ARM64 candidate compilation, distinct artifacts and refusal to run off-device builder on Pi.
- `tests/test_squeekboard_hot_css_ci_audit.py` — Restricts real Debian source audit to ARM64 disposable GitHub CI, separated from the accepted executable builder.
- `tests/test_squeekboard_uk_theme_validation.py` — Guards read-only post-stage candidate/manifests, expected layouts and palette contents, symlink/tamper rejection, and optional parser disclosure without installing packages or changing OSK state.
- `tests/test_squeekboard_uk_theme_stage.py` — Checks vendor-keymap GBP, apostrophe/quote, signed-decimal and time symbols; ACP-derived palette/night CSS; private staging/overwrite refusal and absence of runtime keyboard commands.
- `tests/test_squeekboard_theme_inventory.py` — Proves the UK/theme preflight only invokes read-only process/package/GSettings commands, reports known layout filenames without reading private file contents, and lists ACP's actual day palette identifiers.
- `tests/test_squeekboard_overlay_trial.py` — Guards the Pi's voluntary three-minute OSK trial, independent four-minute rollback timer, session ownership, no-overlap, exact SHA fingerprints, and restoration without the candidate file.
- `tests/test_squeekboard_overlay_abi.py` — Checks experimental ARM64 ZIP file hashes, direct shared-library inventories, Debian runtime version floors, and refusal to inspect as root/non-ARM64 without executing the keyboard.
- `tests/test_squeekboard_ci_builder.py` — Guards the disposable ARM64 Squeekboard builder's pinned source hashes, container/architecture preflight, offline Cargo boundary and artifact-only workflow.

### Plexamp and NFC

- `tests/test_squeekboard_build_dependency_plan.py` — Confirms vendor source/control parsing and source-provenance guards, and limits the proposed build dependencies operation to an APT dry run without package/keyboard mutation.

- `tests/test_native_plexamp_launcher.py` — Protects the manual native Flatpak SSH launcher, scoped fullscreen matching, missing-session handling and duplicate-launch safety.
- `tests/test_native_plexamp_window_handoff.py` — Phase B1 direct Wayland focus helper tests: exact Pi app IDs and title, duplicate/spoof rejection, no process/geometry changes, compositor failure and SSH session boundaries.
- `tests/test_native_navigation_bridge.py` — Opt-in B3 localhost-only mailbox and browser ACPNavigate hookup; strict destination set, single-use, age expiry, no LAN/proxy/HTML-form submissions; readiness ack only for the current taken command, 12s expiry and safe origin-checked status polling. Native bridge passes `animate:false` to existing ACP navigation ONLY for background preparation; avoids dependence on rendering a browser View Transition while native Plexamp covers Chromium. Standard ACP-to-ACP transitions still use configured animations. 22 Oct Pi confirmed `ready` and focus but compositor briefly presented stale Clock framebuffer; opt-in GTK curtain and new browser post-focus double-rAF `painted` acknowledgment added, Pi visual test pending. Includes 2.5s bounded cover fade/fallback and invalid flag rejection. First 22 Oct physical curtain pass revealed both GTK and ACP drawers during fade; 22 Oct Pi confirmed native drawer/handle now hide before curtain, and no Gtk.Window opacity warning; 9/9 drawer tests passed. Remaining blank Weather content interval after `painted` was caught on WayVNC. **22 Oct current Weather handoff accepted provisionally:** 10/10 bridge and 9/9 drawer tests passed, staged route, focus, forecast/panel readiness and curtain fade all logged. Deeper Weather layout work deferred to future expanded Weather and Astronomy milestones. **22 Oct theme regression rerun PASS on Pi:** bridge 12/12, drawer 11/11; the sole previous failure was a stale hard-coded asset version, now replaced with versioned script reference checks. **23 Oct theme physical partial pass:** Classic Dark, Steel Cyan, Green Phosphor visually synced, Squeekboard hide and Settings/Weather routing still functional; Astronomy night dim produced red indicator with still-green drawer because later daytime-theme-followup `!important` nav selectors beat the earlier night styles. New stylesheet `night-navigation-closure.css` loads after daytime followup, restores red colours only for active Astronomy-night outside alarm, and is guarded by `test_astronomy_red_owns_nav_after_daytime_theme_important_css`. **23 Oct Pi follow-up:** 13/13 bridge + 11/11 drawer tests passed, but live palette JSON remained green for drawer/buttons and red for handle/utility separator. The new night stylesheet is linked from changed Jinja `base.html`; service restart and live HTML verification must occur before assuming CSS cascade failure or issuing another style patch. The Rain panel screenshot maps to existing `weather.html` current/historical gauge cards with a scrollable `weather-rain-history.css` rail and nonzero event summary; record its design concern for the richer Weather milestone rather than change data logic in B3. **Actual night palette correction not yet Pi accepted.** **Pi retest pending:** strict nine-colour loopback palette publisher and reader, 20s expiry, browser polling, GTK opt-in, CSS injection rejection unchanged. No new independent Chromium timer; ordinary navigation and OSK remain unchanged.
- `tests/test_native_navigation_drawer.py` — Phase B3 native GTK preview overlay contract: bounded runtime, read-only OSK D-Bus visibility, unknown-state fail-closed, temporary drawer, ACP-shaped workspace/utility groups, raised handle, and diagnostic-only route buttons.
- `tests/test_native_navigation_indicator.py` — Phase B2 GTK3 Wayland overlay indicator test contract; bounded runtime, local-only desktop environment, layer-shell OVERLAY and no keyboard/reserved region, opt-in exact ACP focus.
- `tests/test_prepare_squeekboard_overlay.py` — Protects non-installing vendor Squeekboard source staging, strict SHA-256 descriptor requirements, one-shot TOP→OVERLAY patching and refusal of overwrite/root execution.
- `tests/test_nfc_listener_installer.py` — Exercises NFC listener installation, service wiring and expected PN532 integration ownership.
- `tests/test_nfc_python_dependency_check.py` — Checks the dedicated NFC Python environment contains the required importable dependencies.
- `tests/test_plexamp_browser_storage_probe.py` — Protects the disposable-profile browser-storage metadata inventory: Web Storage key names/families only, IndexedDB database/object-store metadata only, no stored values/records/transactions, bounded sensitive-name redaction and loopback-only transport reuse.
- `tests/test_plexamp_commissioning.py` — Protects the narrow loopback-only Plexamp player-name/audio-output commissioning owner, immutable baseline capture, dynamic managed-output resolution, stale-state refusal and rollback.
- `tests/test_plexamp_home_customization_probe.py` — Protects the disposable-profile Home customisation key-family inventory: bounded namespace, key-names-only reads, no stored values/mutation and loopback-only transport reuse.
- `tests/test_plexamp_home_hub_probe.py` — Protects the bounded disposable-profile Plexamp effective-Home hub-shape probe: fixed discovery authority, no primitive/sensitive values, no arbitrary expression input and reuse of the loopback-only transport.
- `tests/test_plexamp_home_portability_v2.py` — Protects dormant Home-v2 logical portability: clean-target context derivation, strict MMKV wrapper handling, custom UUID/query remapping, title/presentation portability, live capability gating, stale refusal and exact rollback without production activation.
- `tests/test_plexamp_home_portability_v2_transport.py` — Protects the dormant Home-v2 loopback message transport, dashboard validators, origin/nonce gates, apply/rollback/finalize round trips, dual-owner portability injection and production-manifest dormancy.
- `tests/test_plexamp_home_scrub_rehearsal.py` — Protects the disposable-only full-Home scrub rehearsal: preserved evidence ports refused, exact classified-family scope, active-edit/unknown-family refusal, bounded mode-0600 no-overwrite snapshot, stale checking, per-key scrub only, empty-target restore, exact fingerprint verification and self-rollback on mutation failure.
- `tests/test_plexamp_home_title_probe.py` — Protects the bounded disposable-profile Home-title matcher: only structurally validated `viewSettings` values are read, only the validated optional `title` field is compared, no stored title/raw value/raw key is emitted, and no arbitrary JavaScript/URL input or storage mutation is exposed.
- `tests/test_plexamp_local_storage_key_comparison.py` — Protects the two-profile Local Storage key-name comparison: key names only, no values/mutation, bounded delta output, sensitive-name redaction and loopback-only tracer/control transport.
- `tests/test_plexamp_native_portability.py` — Checks bounded live Plexamp settings portability, constructor-default restoration, stale-target refusal and rollback without touching non-portable runtime or identity state.
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
