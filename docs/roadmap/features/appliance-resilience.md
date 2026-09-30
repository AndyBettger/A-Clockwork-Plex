# Appliance resilience

**Status:** QUEUED after #94/Astronomy

## Goal

Harden the final runtime architecture rather than fully hardening components that #94 may retire.

## Planned scope

- [ ] System-time/NTP authority and truthful synchronisation health.
- [ ] Investigate intermittent read-only root-filesystem/SD behaviour.
- [ ] Reduce avoidable appliance writes without weakening recovery.
- [ ] Kiosk-safe Wi-Fi recovery AP and local setup flow.
- [ ] Keep credentials out of query strings, argv, logs and persistent recovery pages.
- [ ] Recovery timeout/rollback.
- [ ] Truthful health/status for storage, network and critical services.
- [ ] Harden the final ACP shell/native Plexamp/browser arrangement after #94.

## Detailed authority

- `../../development/architecture/appliance-resilience.md`
