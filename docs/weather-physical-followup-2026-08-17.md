# Weather physical follow-up — 17 August 2026

**Host:** `plexamp-test`  
**Branch:** `feature/alarm-engine`  
**Presentation fix physically accepted:** `7c163227b0faf5c8c727f72900d47f10bc5cac35`  
**Status-sync repair source/CI head:** `2d9d5bdcdaa75db9c12b461da4a2131d10497a04`  
**Physical retest/evidence head loaded on Pi:** `f2087750b94a5aa92ce6c533b071c6da1528a1be`  
**Status:** presentation, WU commissioning, live/history independence, status synchronization and Ecowitt credential preservation PASS; remaining period/cache checks still in progress.

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
- With Ecowitt live, `GET /api/weather/rainfall` for Last 7 days returned:
  - `status: ready`
  - `complete: true`
  - `required_days: 7`
  - `available_days: 7`
  - `cached_days: 6`
  - `fetched_ranges: 0`
  - `total_in: 0.0`
  - no unavailable dates or last error.

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

After fast-forwarding the Pi to `f2087750b94a5aa92ce6c533b071c6da1528a1be` and restarting only `a-clockwork-plex.service`, the physical Settings page showed all three states correctly and simultaneously without the earlier stale rainfall badge:

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

## Still to prove physically

- Exercise **Today**, **Current month** and **Current year** historical rainfall; Last 7 days is already backend PASS with `complete: true` and `fetched_ranges: 0`.
- Prove completed Current-year cache reuse (`fetched_ranges: 0` on the next completed refresh).
- Inspect `weather-rainfall-history.json` structurally and prove secret-free non-negative numeric cached days with no persisted `null` gap markers.
- Confirm historical-rainfall failure/incompleteness does not take live observations down if such a condition occurs naturally; do not sabotage the real credential/provider to manufacture it.

PR #2 remains Draft/open/unmerged until explicit owner approval.
