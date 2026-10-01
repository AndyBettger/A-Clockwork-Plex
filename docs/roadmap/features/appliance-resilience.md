# Appliance resilience

**Status:** QUEUED after #94/Astronomy

## Goal

Harden the final runtime architecture rather than fully hardening components that #94 may retire.

## Planned scope

- [ ] Define one appliance-wide **Location & Time authority**: latitude, longitude, IANA time zone and country/region. Reuse the existing Weather forecast coordinates as the initial source rather than maintaining unrelated Weather/Astronomy locations.
- [ ] Derive the IANA time zone automatically from latitude/longitude when possible, persist the resolved zone (for example `Europe/London`) for offline use, and provide an explicit manual override. Do not infer time zone from country alone.
- [ ] Derive country/region from the friendly location lookup where available, but allow manual selection/override for formatting and regional defaults.
- [ ] Make the stored IANA zone the authoritative appliance local-time setting and reconcile it with the OS/system time zone through a guarded, reversible `timedatectl`-style owner rather than leaving app time and system time able to diverge.
- [ ] Define alarm behaviour across time-zone/DST changes: normal alarms remain local wall-clock intentions, while diagnostics expose the actual next resolved occurrence.
- [ ] System-time/NTP authority and truthful synchronisation health.
- [ ] Investigate intermittent read-only root-filesystem/SD behaviour.
- [ ] Reduce avoidable appliance writes without weakening recovery.
- [ ] Kiosk-safe Wi-Fi recovery AP and local setup flow.
- [ ] Keep credentials out of query strings, argv, logs and persistent recovery pages.
- [ ] Recovery timeout/rollback.
- [ ] Truthful health/status for storage, network and critical services.
- [ ] Harden the final ACP shell/native Plexamp/browser arrangement after #94.

## Detailed authority

- [Appliance resilience architecture](../../development/architecture/appliance-resilience.md)
