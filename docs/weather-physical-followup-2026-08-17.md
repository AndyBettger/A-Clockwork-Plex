# Weather physical follow-up — 17 August 2026

**Host:** `plexamp-test`  
**Branch:** `feature/alarm-engine`  
**Presentation fix physically accepted:** `7c163227b0faf5c8c727f72900d47f10bc5cac35`  
**Status-sync repair source/CI head:** `2d9d5bdcdaa75db9c12b461da4a2131d10497a04`  
**Physical retest/evidence head loaded on Pi:** `9dbf18ef8a09e9cb56ec845fe66f50809700f3a4`  
**Station-gap semantics source/CI head:** `a408cdd7e5359660194022cc5fd0b95427285f2d`  
**Rainy Day Fund projection/source head:** `6316a63fbc109967ccd517a631796be01b859ba2`  
**Status:** presentation, WU commissioning, live/history independence, status synchronization, Ecowitt credential preservation and Current-year station-gap semantics physically PASS; expanded Rainy Day Fund projection remains to be physically retested.

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

## Rainy Day Fund projection gap discovered

Although the history API and Settings state were correct, the physical **Rainy Day Fund** still showed no historical rainfall data.

Root cause found in source:

- `app/main.py` re-exports helpers from `dashboard_core`;
- the rainfall registration wrapped `main.weather_detail_data`;
- Flask's global template context processor is defined inside `dashboard_core` and resolves `dashboard_core.weather_detail_data` at render time;
- therefore the API service was healthy but the Weather template continued receiving the unwrapped core projection.

Source head `6316a63fbc109967ccd517a631796be01b859ba2` fixes that integration and expands the Rainy Day Fund as requested:

1. The rainfall registration patches the actual `dashboard_core` projection used by Flask as well as the `main` facade.
2. Rainy Day Fund history is independent of whichever single period is selected in Settings.
3. It calculates six calendar summaries:
   - **Rain this week** — current Monday through today;
   - **Rain last week** — previous Monday through Sunday;
   - **Rain this month**;
   - **Rain last month**;
   - **Rain this year**;
   - **Rain last year**.
4. The previous calendar year is backfilled once through the same maximum-31-day WU range requests and then reused from cache.
5. Confirmed station gaps remain acceptable and add the concise `N days not recorded` gauge note.
6. If Ecowitt provides its station-lifetime **Total rain** counter, that seventh gauge is retained; no artificial lifetime total is invented if the station does not provide one.
7. The Rainy Day Fund gauge row is a touch-friendly horizontal strip so six/seven gauges do not crush the 1280×720 or 1024×600 layouts.
8. Supplemental previous-year gauge backfill has its own `gauge_status`, `gauge_fetched_ranges` and `gauge_retried_dates` diagnostics so failure to fetch an older comparison period does not falsely turn an otherwise valid selected-period calculation into **History incomplete**.

Full Tests workflow **#3485 / run `31991516804`** passed compile, JavaScript/page/shell validation and all unit tests for exact source head `6316a63fbc109967ccd517a631796be01b859ba2`.

## Still to prove physically

- Fast-forward `plexamp-test` to the current branch head containing `6316a63f...`, restart only `a-clockwork-plex.service`, and confirm the Weather page is serving the corrected core projection.
- Force one rainfall refresh. Existing 2026 data should remain cached; the first run may show non-zero `gauge_fetched_ranges` while the previous calendar year is backfilled in 31-day-or-smaller requests.
- Force a second rainfall refresh and require `fetched_ranges: 0` and `gauge_fetched_ranges: 0` once all returned/gap-classified days are cached.
- Physically confirm the Rainy Day Fund shows This week / Last week / This month / Last month / This year / Last year, plus Total rain only if Ecowitt supplies the lifetime counter.
- Confirm the Rainy Day Fund strip scrolls horizontally by touch and remains usable on the physical display.
- Confirm Current-year still shows the 21.38 minimum-recorded total and a `3 days not recorded` note where applicable.
- Inspect `weather-rainfall-history.json` structurally: numeric/non-negative `days`, no `null` day markers, only recognized station-gap markers, and no secret fields.
- Confirm live observations remain **Ecowitt Push** after the history exercise.
- A genuine selected-period provider/API failure remains covered by source tests; do not sabotage the real credential/provider merely to manufacture one.

PR #2 remains Draft/open/unmerged until explicit owner approval.
