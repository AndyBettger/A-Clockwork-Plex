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
- [ ] Export one shared local Sun-event calculation service so future display dimming uses Astronomy's sunrise/sunset and timezone logic, not a second implementation.

## Architecture dependency

Build Astronomy as an application surface on the accepted post-#94 UI foundation rather than adding another legacy full-document page that immediately needs migration. The selected direction is GTK3 hosting a persistent WebKitGTK ACP document (see [#94 current checkpoint](acp-shell-native-plexamp.md)); Astronomy will use its existing Flask/surface-host/HTML/CSS/JS pattern, not a separate native GTK page. Its position in the topology is **reserved metadata only** until its route, lifecycle, content readiness and navigation are implemented and accepted.

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

## Follow-on — sun-aware night dimming

**Deferred until after full native Plexamp navigation and the shared Astronomy solar calculations.** Preserve the current **Fixed times** mode (22:00–07:00 or user-edited equivalents).

The intended UI allows independently signed **sunset offset** and **sunrise offset** sliders (hours/minutes), showing calculated local dim/start and bright/stop clock times. An offset alone does not match the user's seasonal bedtime: in a UK winter sunset may be around 16:30, well before they want dimming. Offer a configurable **earliest permissible evening dim time**, for example:
`start = max(sunset + 30 minutes, 21:00 local)`.
That yields 21:30 with a 21:00 summer sunset, but 21:00 with a 16:30 winter sunset. The morning may similarly need a minimum daytime-return time to avoid lighting the screen at an early summer sunrise; explore suitable optional upper/lower limits when implementing.

Reuse the same configured forecast location coordinates, IANA time zone, local date and DST rules. Recompute/cache locally, handle missing or stale weather Sun events, latitude extremes, no-rise/no-set and midnight-crossing offsets; fall back explicitly to saved fixed times. Astronomical sunset is distinct from preferred bedtime; civil/nautical twilight can be added as later selectable solar anchors. Seasonal day-length shifts are primarily axial tilt and latitude, not the equation of time.

**Sequence:** C3 Squeekboard → native Plexamp nav/drawer and transitions → Astronomy shared Sun calculations → sun-aware dimming. Do not make solar mode a #94 completion gate.
