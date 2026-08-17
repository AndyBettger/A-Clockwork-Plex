# Weather physical follow-up — 17 August 2026

**Host:** `plexamp-test`  
**Branch:** `feature/alarm-engine`  
**Presentation fix physically accepted:** `7c163227b0faf5c8c727f72900d47f10bc5cac35`  
**Status-sync repair source/CI head:** `2d9d5bdcdaa75db9c12b461da4a2131d10497a04`  
**Physical retest/evidence head loaded on Pi:** `9dbf18ef8a09e9cb56ec845fe66f50809700f3a4`  
**Station-gap semantics source/CI head:** `a408cdd7e5359660194022cc5fd0b95427285f2d`  
**Rainy Day Fund projection/source head:** `6316a63fbc109967ccd517a631796be01b859ba2`  
**Lifetime rain + forecast-style scrollbar implementation head:** `bbdcc74dde455269def9b5bcb72c3601e295c6b2`  
**Latest green source/CI head:** `22455624917ce456087e3a11041937b3c0526623` — Tests #3523 / run `31994639762` PASS.  
**Status:** presentation, WU commissioning, live/history independence, status synchronization, Ecowitt credential preservation and Current-year station-gap semantics physically PASS; forecast-style Rainy Day Fund scrollbar and genuine WU-backed lifetime rainfall remain to be physically retested.

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

## Rainy Day Fund projection repair — source/CI PASS

Although the history API and Settings state were correct, the physical **Rainy Day Fund** initially showed no historical rainfall data.

Root cause found in source:

- `app/main.py` re-exports helpers from `dashboard_core`;
- the rainfall registration wrapped `main.weather_detail_data`;
- Flask's global template context processor is defined inside `dashboard_core` and resolves `dashboard_core.weather_detail_data` at render time;
- therefore the API service was healthy but the Weather template continued receiving the unwrapped core projection.

Source head `6316a63fbc109967ccd517a631796be01b859ba2` fixed that integration and expanded the Rainy Day Fund:

1. The rainfall registration patches the actual `dashboard_core` projection used by Flask as well as the `main` facade.
2. Rainy Day Fund history is independent of whichever single period is selected in Settings.
3. It calculates six calendar summaries: **Rain this week**, **Rain last week**, **Rain this month**, **Rain last month**, **Rain this year** and **Rain last year**.
4. The previous calendar year is backfilled once through the same maximum-31-day WU range requests and then reused from cache.
5. Confirmed station gaps remain acceptable and add concise `N days not recorded` gauge notes.
6. Supplemental prior-year gauge backfill has its own diagnostics so older comparison data cannot falsely turn a valid selected-period calculation into **History incomplete**.

Full Tests workflow **#3485 / run `31991516804`** passed compile, JavaScript/page/shell validation and all unit tests for exact source head `6316a63fbc109967ccd517a631796be01b859ba2`.

## Forecast-style Rainy Day Fund scrolling — source/CI PASS, physical pending

The first expanded Rainy Day Fund used the browser's native horizontal scrollbar. Physical screenshots showed that this did not match the two forecast strips: Chromium added native arrow buttons and used different thumb/track geometry.

The current source replaces that browser control rather than trying to cosmetically approximate it:

- the native rain scrollbar is hidden;
- `app/static/js/weather-rain-history-scroll.js` creates the same `weather-forecast-scrollbar` rail and `weather-forecast-scrollbar-thumb` used by the forecast presentation;
- rail clicks, thumb drag, strip touch scrolling and keyboard Left/Right/Home/End remain supported;
- the control tracks the real `.rain-history-scroll` scroll position and hides itself when the strip does not overflow;
- the Rainy Day Fund gauges remain full-height within the panel.

Focused source regression `test_weather_rain_history_scrollbar.py` verifies that the native scrollbar is suppressed and the forecast-style custom control is loaded. The complete branch passed Tests **#3523 / run `31994639762`** at green head `22455624917ce456087e3a11041937b3c0526623`.

## Genuine WU-backed Rain lifetime — source/CI PASS, physical pending

The earlier calculated **Rain total** was only previous calendar year + current calendar year. That is no longer considered a lifetime total.

The current source introduces `WeatherRainfallLifetimeService` and a separate station-scoped, secret-free cache `weather-rainfall-lifetime.json` so older archive work cannot race or corrupt the already accepted selected-period / Rainy Day Fund cache.

The lifetime contract is:

1. The existing rainfall-history service remains authoritative for current year and previous year.
2. The lifetime service starts immediately before that comparison window — for the 2026 acceptance run, older archive coverage ends at **31 December 2024**.
3. WU history is discovered backwards in documented maximum-31-day blocks. The automatic discovery floor is 1995.
4. Because the documented PWS metadata does not expose a station-inception date, automatic discovery stops after 24 consecutive empty 31-day probe ranges (roughly two years) before the oldest discovered record. A configured `weather.historical_rainfall.lifetime_start_date` can override that heuristic for an unusual station with a multi-year mid-life outage.
5. After the oldest record is known, missing older dates are filled in bounded batches. Dates omitted from a successful range are retried once individually before becoming confirmed station-data gaps, matching the accepted recent-history semantics.
6. Once both `discovery_complete` and `coverage_complete` are true, later refreshes return from cache with **zero WU requests**.
7. The dashboard **Rain lifetime** gauge is calculated as older archive + previous year + current year. Genuine gaps across all three portions remain explicit in the `N days not recorded` note.
8. While one-time archive work is still running, the gauge is explicitly labelled **Backfilling earlier WU history** rather than pretending the partial total is final.
9. Once ready, the note becomes **Since first WU record DD/MM/YYYY** (or the equivalent all-history copy if no start date can be displayed).

A dedicated `GET/POST /api/weather/rainfall/lifetime` endpoint exposes only sanitized archive status/calculation fields; it never exposes the WU key.

The implementation was settled at `bbdcc74dde455269def9b5bcb72c3601e295c6b2` so a completed archive becomes request-quiet. CI then caught one stale runner-contract assertion left over from the single rainfall service; `22455624917ce456087e3a11041937b3c0526623` updated that regression to require both rainfall services and their shared credential wake path. Full Tests **#3523 / run `31994639762`** passed compile, JavaScript/page/shell validation and unit tests.

## Still to prove physically

1. Fast-forward `plexamp-test` to exact green head `22455624917ce456087e3a11041937b3c0526623`, confirm a clean tree, and restart only `a-clockwork-plex.service`.
2. Confirm the Rainy Day Fund now displays the forecast-style rounded custom rail/thumb with **no Chromium arrow buttons** and that touch/drag scrolling moves the full-height gauges correctly.
3. Confirm the six calendar gauges remain present and the current-year gauge still carries the accepted `3 days not recorded` coverage note where applicable.
4. Inspect `GET /api/weather/rainfall/lifetime`. Allow the separate older archive to backfill; force additional POST refreshes only as needed until `status: ready`, `discovery_complete: true` and `coverage_complete: true`.
5. After lifetime reaches ready, force one more lifetime refresh and require `fetched_ranges: 0` and `retried_dates: 0`.
6. Physically confirm the final seventh gauge is labelled **Rain lifetime**, its note identifies the first WU record date, and it no longer says `Last year + this year`.
7. Inspect `weather-rainfall-lifetime.json` structurally: station-scoped numeric/non-negative `days`, recognized `no_station_data` gap markers only, no `null` day markers and no secret fields.
8. Confirm `weather-rainfall-history.json` still satisfies its already accepted structural contract and that live observations remain **Ecowitt Push** throughout.
9. A genuine provider/API failure remains covered by source tests; do not sabotage the real credential/provider merely to manufacture one.

PR #2 remains Draft/open/unmerged until explicit owner approval.
