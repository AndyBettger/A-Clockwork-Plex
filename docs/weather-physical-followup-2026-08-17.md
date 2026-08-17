# Weather physical follow-up — 17 August 2026

**Host:** `plexamp-test`  
**Branch:** `feature/alarm-engine`  
**Presentation fix physically accepted:** `7c163227b0faf5c8c727f72900d47f10bc5cac35`  
**Status-sync repair source/CI head:** `2d9d5bdcdaa75db9c12b461da4a2131d10497a04`  
**Physical retest/evidence head loaded on Pi:** `9dbf18ef8a09e9cb56ec845fe66f50809700f3a4`  
**Station-gap semantics source/CI head:** `a408cdd7e5359660194022cc5fd0b95427285f2d`  
**Rainy Day Fund projection/source head:** `6316a63fbc109967ccd517a631796be01b859ba2`  
**Lifetime rain + forecast-style scrollbar implementation head:** `bbdcc74dde455269def9b5bcb72c3601e295c6b2`  
**Physical lifetime/custom-scroll head loaded on Pi:** `f0ea56557ba3d2fd09b624c9162ceea6c30de6f9`  
**Status:** presentation, WU commissioning, live/history independence, status synchronization, Ecowitt credential preservation, selected-period station-gap semantics, expanded Rainy Day Fund, forecast-style custom scrolling and WU-backed Rain lifetime physically PASS. Final cache-structure/request-quiet/live-Ecowitt checks remain before closing the Weather follow-up.

## Display acceptance envelope

The Settings UI must remain usable on both supported landscape targets:

- **1280×720 landscape** — physical bedside panel is 720×1280 native and rotated to landscape.
- **1024×600 landscape** — remains a supported lower-resolution appliance target.

Weather spacing must therefore use resolution-independent responsive/minimum spacing rather than a fix tied only to one panel size.

## Physical presentation retest — PASS

After fast-forwarding the spare-SD checkout, restarting `a-clockwork-plex.service`, and confirming `DASHBOARD_API=PASS`, the following four Weather presentation items were physically accepted:

1. Observation source status is a proper bordered status badge at the **top-right of the Observation source card**.
2. Historical rainfall has its own proper bordered status badge at the **top-right of the Historical rainfall card**.
3. Status/help copy beneath the Observation source and Historical rainfall field grids has clear breathing room from the boxes above.
4. The Weather Underground commissioning grid has clear vertical separation before the **API key / Credential status** row.

The earlier attempt that placed the live-source state beside the global Weather page heading is superseded by this accepted card-local treatment.

## WU commissioning and live/history independence — PASS

The real WU API key was entered only through the local write-only Settings control. No key material was copied into chat or terminal output.

Physical results:

- Credential status control reported **Configured**.
- `GET /api/weather/underground/credentials` returned only `configured: true` / `ok: true`; no key was returned.
- `/etc/default/a-clockwork-plex-weather` remained `600 root:root`.
- Structural `config.json` inspection reported `WU_CONFIG_SECRET_FIELDS=NONE`.
- With Weather Underground PWS selected as the live source, **Test connection** succeeded and the Observation source badge reached **WU Ready**.
- Switching the live provider back to Ecowitt custom push produced **Ecowitt Push** while the WU credential control remained **Configured**.
- With Ecowitt live, Last 7 days history returned `status: ready`, `complete: true`, seven of seven days available, six completed days cached, `fetched_ranges: 0`, a numeric total and no last error.

This physically proves that WU supplemental historical rainfall can remain healthy while Ecowitt is the live observation provider.

## Status synchronization repair — physical PASS

During initial commissioning, the **Historical rainfall** badge stayed on **Credentials required** even though the direct rainfall API was already `ready` and complete. The Observation source badge also required a page refresh/Test connection before visually catching up.

Root cause:

- WU credential changes woke the live-observation service but not the rainfall-history service;
- the Weather presenter rendered rainfall state from a revision-gated unified Settings snapshot even though weather/credential status may change without a Settings revision;
- Test connection received fresh live-provider status but then reread the cached snapshot instead of rendering the fresh response.

Repair at source/CI head `2d9d5bdcdaa75db9c12b461da4a2131d10497a04`:

- successful WU credential set/remove wakes both live observations and rainfall history;
- the presenter reads `/api/weather/rainfall` directly for the Historical rainfall badge;
- credential set/remove forces an immediate rainfall refresh;
- successful Test connection renders its fresh observation result immediately and refreshes rainfall status;
- rainfall display is no longer overwritten from the revision-gated Settings snapshot.

Full Tests workflow **#3473 / run `31988059169`** passed compile, JavaScript/page/shell validation and unit tests. Evidence synchronization head `f2087750b94a5aa92ce6c533b071c6da1528a1be` also passed full Tests workflow **#3475 / run `31988158528`**.

After fast-forwarding the Pi and restarting only `a-clockwork-plex.service`, the physical Settings page showed all three states correctly and simultaneously:

- Observation source: **Ecowitt Push**
- Historical rainfall: **History ready**
- WU Credential status: **Configured**

The status-sync repair is therefore physically accepted.

## Ecowitt reconvergence / WU history credential preservation — PASS

With the WU credential already commissioned, the guarded Weather owner was activated again with `--provider ecowitt-push`. The operation completed successfully and reported:

- `WEATHER_PROVIDER=ecowitt_push`
- `WEATHER_FORECAST=OPEN-METEO-PRESERVED`
- `WEATHER_SECRET_POLICY=ENV-FILE-ONLY`
- `WEATHER_ROLLBACK_POLICY=EXACT-MANAGED-PRESTATE-ON-FAILURE`

The managed WU secret file was compared before and after without printing the key or digest. Result:

```text
WU_HISTORY_CREDENTIAL_PRESERVED=PASS
600 root:root /etc/default/a-clockwork-plex-weather
```

This physically proves that reconverging Ecowitt as the live observation provider preserves the exact commissioned WU credential needed by supplemental rainfall history.

## Historical rainfall periods — physical results

### Today — PASS

Physical API result:

- `period: today`
- `status: ready`
- `complete: true`
- `required_days: 1`
- `available_days: 1`
- `fetched_ranges: 0`
- `total_in: 0.0`
- no unavailable dates or last error.

This confirms Today remains a live-station calculation and does not require WU history for the selected-period total.

### Current month — PASS

On 17 August the physical result returned:

- `period: current_month`
- `status: ready`
- `complete: true`
- `required_days: 17`
- `available_days: 17`
- `cached_days: 16`
- `fetched_ranges: 1`
- `total_in: 0.0`
- no unavailable dates or last error.

### Current year — station gaps physically accepted

The first physical Current-year request under the earlier all-or-nothing model successfully returned **226 of 229 required days** and cached 225 completed days, but Weather Underground supplied no daily record for:

- `2026-03-03`
- `2026-03-05`
- `2026-03-07`

The response itself was successful and the other historical dates were returned/cached. The earlier implementation reported `complete: false`, `total_in: null` and **History incomplete**. That user experience was rejected: occasional station-offline days are coverage gaps, not provider failures, and the useful recorded total should remain visible as a minimum recorded rainfall.

After loading `9dbf18ef8a09e9cb56ec845fe66f50809700f3a4` and restarting the dashboard, two forced Current-year refreshes both returned:

- `status: ready`
- `complete: true`
- `coverage_complete: false`
- `required_days: 229`
- `available_days: 226`
- `cached_days: 225`
- `missing_days: 3`
- `gap_days: 3`
- `pending_days: 0`
- `fetched_ranges: 0`
- `retried_dates: 0`
- `total_in: 21.38`
- `last_error: null`
- the same three March dates under `missing_dates` / `unavailable_dates`.

Settings → Weather → Observation source physically showed:

> 226 of 229 days recorded. 3 days had no station data. Total shown is the minimum recorded.

and the Historical rainfall badge showed **History ready**.

This is a physical PASS for the revised station-gap semantics and proves confirmed gaps are not re-fetched on every refresh.

## Rainy Day Fund projection and previous-year backfill — physical PASS

The initially blank Rainy Day Fund was traced to the rainfall registration wrapping the `app.main` facade while Flask's context processor resolves `dashboard_core.weather_detail_data`. Source head `6316a63fbc109967ccd517a631796be01b859ba2` fixed that integration.

On the real spare-SD appliance the corrected projection physically returned:

- **Rain this week**
- **Rain last week**
- **Rain this month**
- **Rain last month**
- **Rain this year** — `543.1 mm`, `3 days not recorded`
- **Rain last year** — `909.8 mm`, `8 days not recorded`

The one-time previous-year preparation fetched 12 ranges and retried 8 omitted dates; two subsequent forced rainfall refreshes both reported `fetched_ranges: 0`, `retried_dates: 0`, `gauge_fetched_ranges: 0` and `gauge_retried_dates: 0`. The comparison cache therefore settles and does not repeatedly query WU for confirmed gaps.

The full-height gauges were also physically accepted as a better use of the Rainy Day Fund panel height.

## Forecast-style Rainy Day Fund scrolling — physical PASS

The first expanded Rainy Day Fund used Chromium's native horizontal scrollbar, which displayed arrow buttons and geometry inconsistent with the two forecast strips. The accepted implementation now hides that native control and uses the same custom forecast rail/thumb mechanism.

On physical head `f0ea56557ba3d2fd09b624c9162ceea6c30de6f9` the user confirmed:

- the rain scrollbar now looks correct and matches the forecast treatment;
- Chromium's native arrow buttons are no longer visible;
- the full-height Rainy Day Fund gauges remain horizontally scrollable.

This presentation gate is physically PASS.

## Genuine WU-backed Rain lifetime — physical PASS

The final gauge is now **Rain lifetime**, not merely previous year + current year and not an unverified live station lifetime counter.

`WeatherRainfallLifetimeService` owns a separate station-scoped, secret-free `weather-rainfall-lifetime.json` archive. It discovers older WU daily history backwards in ranges of at most 31 days, with a 1995 floor and a default 24-consecutive-empty-range pre-station boundary. A configured `weather.historical_rainfall.lifetime_start_date` remains available for unusual stations with a multi-year mid-life outage.

Physical behavior on `plexamp-test`:

1. Immediately after restart, the first lifetime GET could still observe the worker as `status: pending`; it reported no older cached days yet and used `2025-01-01` as the provisional first known date from the recent comparison cache.
2. The background lifetime worker then completed between calls. The settled lifetime endpoint returned:
   - `status: ready`
   - `discovery_complete: true`
   - `coverage_complete: true`
   - `archive_end_date: 2024-12-31`
   - `available_days: 368`
   - `first_record_date: 2023-12-30`
   - `empty_probe_ranges: 24`
   - `probe_cursor_end: 2021-12-11`
   - `fetched_ranges: 36` for the completing refresh
   - `retried_dates: 0`
   - `missing_days: 0` within the older archive
   - older-archive `total_in: 46.5` inches.
3. The dashboard projection combined that older archive with the already accepted previous/current-year history and physically displayed:
   - **Rain lifetime: 2634.0 mm**
   - note: **Since first WU record 30/12/2023 · 11 days not recorded**.

The 11 missing days are the accepted gaps from the recent comparison window (3 in 2026 and 8 in 2025); the newly discovered older archive itself contained no confirmed gaps.

This proves the lifetime gauge is based on discovered WU history rather than relabelling a two-year sum. The discovered first-record date is governed by the documented acceptance heuristic above; if independent station history ever establishes an older pre-30/12/2023 record separated by a multi-year outage, configure `lifetime_start_date` and rerun discovery rather than silently overstating completeness.

## Final Weather checks still open

Before closing the focused Weather follow-up:

1. Force one more `POST /api/weather/rainfall/lifetime` after the ready state and require `fetched_ranges: 0` / `retried_dates: 0`, proving the settled lifetime archive is request-quiet on the real Pi.
2. Inspect both `weather-rainfall-history.json` and `weather-rainfall-lifetime.json` structurally: version 1, finite non-negative numeric `days`, no `null` day markers, only recognized `no_station_data` gap markers, and no secret fields.
3. Confirm `GET /api/weather/observations` still reports `provider: ecowitt_push`, `status: push`, with the observation worker healthy.
4. A genuine provider/API failure remains covered by source tests; do not sabotage the real credential/provider merely to manufacture one.

PR #2 remains Draft/open/unmerged until explicit owner approval.
