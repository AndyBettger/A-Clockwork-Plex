# Astronomy

**Status:** QUEUED — first new content surface after the #94 UI foundation is accepted

## Goal

Build a touch-first astronomy surface using deterministic local/offline calculation authority and the existing appliance location/timezone model.

## Planned scope

- [ ] Observer/location model.
- [ ] Overview/Tonight with Julian Date, sidereal time and useful Sun/Moon events.
- [ ] Sun rise/transit/set, twilight classes, day length, position.
- [ ] Moon rise/transit/set, phase/age/illumination, principal phases, distance/angular diameter and position.
- [ ] Mercury–Neptune rise/transit/set plus useful position/magnitude/elongation where reliable.
- [ ] 1280×720 touch presentation and night treatment.
- [ ] Circumpolar/no-rise/no-set/polar/DST/local-date edge cases.
- [ ] Reference fixtures and numerical tolerances.

## Architecture dependency

Build Astronomy as an application surface on the accepted post-#94 UI foundation rather than adding another legacy full-document page that immediately needs migration.
