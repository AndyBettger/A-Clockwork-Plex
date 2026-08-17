# Weather physical follow-up — 17 August 2026

**Host:** `plexamp-test`  
**Branch:** `feature/alarm-engine`  
**Presentation fix physically accepted:** `7c163227b0faf5c8c727f72900d47f10bc5cac35`  
**Status-sync repair source/CI head:** `2d9d5bdcdaa75db9c12b461da4a2131d10497a04`  
**Physical retest/evidence head loaded on Pi:** `f2087750b94a5aa92ce6c533b071c6da1528a1be`  
**Station-gap semantics source/CI head:** `a408cdd7e5359660194022cc5fd0b95427285f2d`  
**Status:** presentation, WU commissioning, live/history independence, status synchronization, Ecowitt credential preservation, Today and Current-month history PASS; physical Current-year station-gap retest remains open.

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

After fast-forwarding the Pi to `f2087750b94a5aa92ce6c533b071c6da1528a1be` and restarting only `a-clockwork-plex.service`, the physical Settings page showed all three states correctly and simultaneously:

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

This confirms Today remains a live-station calculation and does not require a WU history fetch.

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

### Current year — provider coverage gap discovered; semantics revised

The first physical Current-year request under the earlier all-or-nothing model successfully returned **226 of 229 required days** and cached 225 completed days, but Weather Underground supplied no daily record for:

- `2026-03-03`
- `2026-03-05`
- `2026-03-07`

The response itself was successful (`status: ready`, no API error) and the other 225 historical dates were returned/cached. This is therefore not evidence that a missing date invalidates or empties a 31-day range; it is direct physical evidence that a successful range response may contain useful data while omitting individual station-offline dates.

The earlier implementation reported `complete: false`, `total_in: null` and **History incomplete**. Physical review rejected that user experience: occasional genuine station-offline days should be treated as coverage gaps, not provider failures, and the useful recorded total should remain visible as a **minimum recorded rainfall**.

## Revised station-gap semantics — source/CI PASS, physical retest pending

Source head `a408cdd7e5359660194022cc5fd0b95427285f2d` changes the model as follows:

1. Missing completed dates are still fetched in contiguous WU daily-history requests of at most 31 days.
2. If a successful multi-day response omits a requested date, that date is retried once with its own single-day daily-history request.
3. If that successful single-day request still contains no usable record, the date is classified as a confirmed **station-data gap**, not an API error.
4. Confirmed station gaps are stored separately from numeric daily totals and are not repeatedly refetched on every refresh.
5. A successful history with confirmed station gaps remains **History ready** and displays the sum of recorded days as the **minimum recorded** total.
6. Coverage is reported independently through `missing_days`, `missing_dates` and `coverage_complete`.
7. The Rainy Day Fund historical gauge may show a concise note such as **3 days not recorded**.
8. Actual API/configuration/credential failures still use an error state and suppress the historical aggregate.
9. The numeric `days` cache remains free of `null` gap markers and secret material.

Full Tests workflow **#3481 / run `31990132651`** passed compile, JavaScript/page/shell validation and all unit tests for exact head `a408cdd7e5359660194022cc5fd0b95427285f2d`.

## Still to prove physically

- Fast-forward the Pi to the station-gap semantics head and force Current-year refresh.
- Confirm the three March dates are either recovered by their targeted single-day requests or classified as confirmed station-data gaps without making history an error.
- Confirm Current year remains **History ready**, returns a numeric minimum-recorded total and reports the missing-day count when genuine gaps remain.
- Confirm the Rainy Day Fund historical gauge displays the numeric total and a concise missing-day note when applicable.
- Repeat Current-year refresh and require no further fetches for numeric cached days or confirmed station gaps (`fetched_ranges: 0`).
- Inspect `weather-rainfall-history.json` structurally: numeric/non-negative `days`, no `null` day markers, only recognized station-gap markers, and no secret fields.
- Confirm live observations remain Ecowitt Push after the history exercise.
- A genuine provider/API failure remains covered by source tests; do not sabotage the real credential/provider merely to manufacture one.

PR #2 remains Draft/open/unmerged until explicit owner approval.
