# Astronomy

**Status:** QUEUED — follows physically accepted #94 native Linux Plexamp migration

## Goal

Build a touch-first astronomy surface using deterministic local/offline calculation authority and the existing appliance location/timezone model.

## Planned scope

- [ ] Reuse the appliance-wide **Location & Time authority** rather than creating Astronomy-only coordinates: latitude/longitude from the existing friendly Weather forecast location where configured, IANA time zone for local civil-time display, and country/region metadata where useful.
- [ ] Allow explicit latitude/longitude and time-zone overrides in Settings; astronomy calculations depend on coordinates, while the IANA zone controls local date/time/DST presentation.
- [ ] Keep the resolved location/time-zone values locally available so core astronomical calculations remain deterministic/offline after setup.
- [ ] Overview/Tonight with Julian Date, sidereal time and useful Sun/Moon events.
- [ ] Sun rise/transit/set, twilight classes, day length, position.
- [ ] Moon rise/transit/set, phase/age/illumination, principal phases, distance/angular diameter and position.
- [ ] Mercury–Neptune rise/transit/set plus useful position/magnitude/elongation where reliable.
- [ ] 1280×720 touch presentation and night treatment.
- [ ] Circumpolar/no-rise/no-set/polar/DST/local-date edge cases.
- [ ] Reference fixtures and numerical tolerances.

## Architecture dependency

Build Astronomy as an application surface on the accepted post-#94 UI foundation rather than adding another legacy full-document page that immediately needs migration.

The Phase-A shell dependency is satisfied and physically accepted:

- B5 — separated right-edge Audio/Settings SVG utility cluster — **accepted**;
- B6 — shell-owned workspace topology with Plexamp as the terminal workspace slot — **accepted**;
- B7 — night-clock anti-burn-in bouncing motion plus night-safe live-screen transition ownership — **accepted**.

The remaining prerequisite is #94 Phase B: native Linux Plexamp must be physically accepted in the terminal Plexamp workspace before Astronomy implementation begins.

Its reserved spatial position is **between Weather and News**, giving the future workspace order:

`Home ↔ Weather ↔ Astronomy ↔ News ↔ AirPlay ↔ Plexamp`

This position is part of the shell topology before Astronomy implementation begins, so adding the page must not require another navigation-order redesign.

## Related authority

- [ACP shell / native Plexamp architecture](../../development/architecture/native-plexamp-desktop.md) — application-surface/design-system dependency before Astronomy begins.
