# Weather physical follow-up — 17 August 2026

**Host:** `plexamp-test`  
**Branch:** `feature/alarm-engine`  
**Presentation fix under test:** `7c163227b0faf5c8c727f72900d47f10bc5cac35`  
**Status:** presentation retest PASS; WU commissioning/history/preservation checks still in progress.

## Display acceptance envelope

The Settings UI must remain usable on both supported landscape targets:

- **1280×720 landscape** — physical bedside panel is 720×1280 native and rotated to landscape.
- **1024×600 landscape** — remains a supported lower-resolution appliance target.

Weather spacing must therefore use resolution-independent responsive/minimum spacing rather than a fix tied only to one panel size.

## Physical presentation retest

After fast-forwarding the spare-SD checkout, restarting `a-clockwork-plex.service`, and confirming `DASHBOARD_API=PASS`, the following four Weather presentation items were physically accepted:

1. Observation source status is a proper bordered status badge at the **top-right of the Observation source card**.
2. Historical rainfall has its own proper bordered status badge at the **top-right of the Historical rainfall card**.
3. Status/help copy beneath the Observation source and Historical rainfall field grids has clear breathing room from the boxes above.
4. The Weather Underground commissioning grid has clear vertical separation before the **API key / Credential status** row.

The earlier attempt that placed the live-source state beside the global Weather page heading is superseded by this accepted card-local treatment.

## Still to prove physically

- Commission the real WU API key locally without exposing it in chat, logs or `config.json`.
- When WU is selected as the live provider, obtain a sanitized successful Test connection / `WU Ready` state.
- Return live observations to Ecowitt Push while retaining WU for historical rainfall.
- Verify the root-owned `0600` managed WU secret and absence of literal secret fields in `config.json`.
- Prove Ecowitt weather reconvergence preserves the commissioned WU credential exactly.
- Exercise Today, Last 7 days, Current month and Current year historical rainfall.
- Prove completed Current-year cache reuse (`fetched_ranges: 0` on the next completed refresh), secret-free numeric cache contents and no persisted `null` gap markers.
- Confirm historical-rainfall failure/incompleteness does not take live observations down.

PR #2 remains Draft/open/unmerged until explicit owner approval.
