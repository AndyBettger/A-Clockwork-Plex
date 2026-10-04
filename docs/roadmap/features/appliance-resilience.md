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
- [x] The **1 October 2026** `dtparam=sd_overclock=50` experiment did **not** lower the Pi 5 storage card: `mmc0/mmcblk0` remained SDR104 at 200 MHz; the observed DDR50/50 MHz `mmc1` device is onboard WLAN SDIO.
- [x] **4 October 2026:** after another default-speed read-only-root recurrence, temporary `sdhci.debug_quirks2=4` successfully forced the real storage card to **SD High Speed / 50 MHz / 3.3 V**, confirmed through `/sys/kernel/debug/mmc0/ios`. Treat this as a live stability experiment, not yet the production mechanism.
- [x] Confirmed the same global debug quirk also forced the WLAN SDIO host (`mmc1`) to SD High Speed / 50 MHz / 3.3 V. AirPlay/networking remained functional, but this reinforces that the final mitigation must target the storage controller only.
- [x] Previous-boot journal recovery is currently unavailable: the commissioned Pi uses volatile journald storage and `journalctl --list-boots` retains only the current boot.
- [ ] Add a read-only-safe **capture-before-reboot** diagnostic helper that writes to `/run`/tmpfs and gathers MMC/ext4 kernel messages, mount state, MMC timing, throttling/power and recent warnings. Avoid enabling full persistent journald on the SD card just to collect this evidence.
- [ ] Replace the global debug quirk with a repository-owned Device Tree overlay applying `no-1-8-v` only to the Pi 5 storage controller; verify it reproduces the 50 MHz storage mode without replacing normal SDHCI platform quirks.
- [ ] Evaluate an SSD-backed appliance root/runtime as the likely long-term storage option if read-only SD failures continue; also compare a higher-endurance / Raspberry Pi 5-qualified microSD option for users who prefer removable flash.
- [ ] Reduce avoidable appliance writes without weakening recovery.
- [ ] Kiosk-safe Wi-Fi recovery AP and local setup flow.
- [ ] Keep credentials out of query strings, argv, logs and persistent recovery pages.
- [ ] Recovery timeout/rollback.
- [ ] Truthful health/status for storage, network and critical services.
- [ ] Harden the final ACP shell/native Plexamp/browser arrangement after #94.

## Detailed authority

- [Appliance resilience architecture](../../development/architecture/appliance-resilience.md)
