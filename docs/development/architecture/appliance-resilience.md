# Appliance resilience design

This is a future cross-cutting reliability track for A Clockwork Plex. It records appliance-hardening work exposed during commissioned-Pi testing; it is not part of BBC News checkpoint #92 acceptance. The single live priority/backlog authority remains `docs/roadmap/ROADMAP.md`.

## Storage / read-only filesystem resilience

Two development SD installations have independently experienced the Raspberry Pi root filesystem becoming read-only. In the most recent incident the dashboard, Ecowitt ingest and even an unrelated `mkdir` all failed with `EROFS`; the filesystem later returned writable after reboot. The affected cards are new SanDisk Extreme A2 media and have passed repeated H2testw capacity/read-write tests on Windows, so the investigation must not assume simple flash wear or counterfeit media.

- [ ] **Capture the root cause before mitigation claims.** On any recurrence collect kernel/system journal evidence for `mmc`, ext4, I/O, timeout, voltage/throttling and read-only remount messages; record `vcgencmd get_throttled`, power-supply/hardware context and filesystem state before reboot where possible.
- [ ] **Reduce expendable Chromium writes.** Evaluate moving Chromium disk/media cache to a bounded RAM-backed location such as `/dev/shm` or a verified tmpfs while preserving the normal persistent ACP Chromium profile, Plexamp session state and unpacked extensions. Do not use Incognito as the appliance solution.
- [ ] **Audit ACP write frequency and ownership.** Classify `state.json`, current Weather/Ecowitt observations, News cache, history, diagnostics and other runtime writes as volatile, recoverable cache, or genuinely durable user data. Avoid rewriting persistent flash when state has not materially changed.
- [ ] **Separate transient state from durable configuration.** Investigate an ACP runtime directory under `/run/a-clockwork-plex` or another tmpfs for data that need not survive reboot. Keep user configuration, alarms and genuinely valuable history durable and backup-owned.
- [ ] **Graceful `EROFS` behaviour.** A read-only filesystem should be surfaced as an appliance/storage diagnostic and should not turn otherwise renderable pages into HTTP 500 merely because a mode/current-state write failed. Define which writes may fail soft and which require an explicit warning.
- [ ] **Overlay filesystem feasibility.** Evaluate Raspberry Pi OS overlayfs only after persistent/volatile ownership is cleanly separated. Settings, software updates and durable history must not appear to save and then disappear on reboot.
- [ ] **SD-card comparison.** The project currently has a known previously-stable 64 GB SanDisk Extreme A2 card and a 128 GB SanDisk Extreme A2 test card. Use the same current software/workload when comparing them so capacity/card behaviour is not confounded with the old pre-rewrite dashboard workload.
- [ ] **Attempted reduced SD bus-speed mitigation — 1 October 2026; observed ineffective on the Pi 5 storage interface.** After further recurring read-only-root incidents, `dtparam=sd_overclock=50` was manually added to `/boot/firmware/config.txt`. Post-reboot evidence showed the actual storage device remained `mmc0` / `mmcblk0` at **SDR104, 200 MHz**; both root/boot partitions are on that one device. The separate `mmc1` device at **DDR50, 50 MHz** is the onboard WLAN SDIO interface, not another storage partition. Raspberry Pi documents `sd_overclock` as changing the clock when the MMC framework requests 50 MHz, so it does not cap an already-negotiated SDR104 path. Do not treat this setting as an active mitigation.
- [x] **Lower-speed proof achieved with a temporary kernel debug quirk — 4 October 2026.** After another spontaneous read-only-root recurrence on the default Pi 5 SDR104 path, `sdhci.debug_quirks2=4` was added to the single-line kernel command line in `/boot/firmware/cmdline.txt`. Post-reboot `/sys/kernel/debug/mmc0/ios` proved the actual 128 GB storage card at **50 MHz, 3.3 V, timing spec 2 (SD High Speed)** rather than SDR104/200 MHz/1.8 V. Linux defines decimal bitmask 4 as `SDHCI_QUIRK2_NO_1_8_V`; the SDHCI core responds by removing SDR104, SDR50, DDR50 and other 1.8 V UHS capabilities. This is therefore a genuine reduced-speed experiment.
- [ ] **Replace the debug quirk with a targeted Device Tree overlay before treating it as a supported mitigation.** `sdhci.debug_quirks2` is a global SDHCI debugging parameter and the core assigns `host->quirks2 = debug_quirks2`, potentially replacing platform-specific quirk bits for every affected SDHCI host. Prefer a repository-owned overlay that adds the standard `no-1-8-v` property only to the Pi 5 storage controller (`sdio1`). The upstream Raspberry Pi 5 DTS already shows this property as a commented option on that node. The targeted overlay should reproduce the observed SD High Speed/50 MHz storage mode without globally overriding SDHCI quirks.
- [ ] **Observe stability at 50 MHz before causal claims.** Run normal ACP workload for several days and capture any recurrence. If the filesystem again becomes read-only, collect `mmc`, ext4, I/O/CRC/timeout, power/throttling and mount-state evidence before reboot where practical. If the problem disappears, treat that as strong evidence of a marginal SDR104/card/host signalling interaction, but still qualify it against media and power before declaring root cause.
- [ ] **Do not hide the root cause behind the slower bus setting.** If read-only remounts recur, capture `mmc`, ext4, timeout/CRC/I/O and throttling/power evidence before reboot where practical. If they stop, keep enough evidence to distinguish a marginal card/host timing interaction from reduced write pressure or coincidence.
- [ ] **Storage-media migration candidate.** Evaluate moving the appliance root filesystem/runtime workload to an SSD (USB/UAS or an appropriate Raspberry Pi 5 PCIe/NVMe arrangement) after the current audio/UI work settles. Compare boot/recovery complexity, power, enclosure/thermal impact and failure handling before making SSD the supported appliance baseline.
- [ ] **Higher-spec / officially-qualified microSD candidate.** If retaining microSD, compare media with strong A2/endurance characteristics and Raspberry Pi 5 SDR104 qualification rather than assuming capacity or desktop H2testw success predicts long-running random-write stability.
- [ ] **Physical endurance/recurrence gate.** After hardening, run a representative multi-day appliance workload including Chromium kiosk, Weather/News refresh, playback and normal navigation; inspect write behaviour and kernel logs before claiming the problem mitigated.

## Kiosk-safe Wi-Fi recovery / provisioning

A commissioned kiosk can currently become difficult to recover if its remembered Wi-Fi network is unavailable: Chromium owns the screen and the normal desktop Wi-Fi join workflow requires escaping the kiosk with a keyboard. The appliance should have a touch/phone-friendly recovery path without exposing Wi-Fi credentials or leaving a permanent management access point.

### Preferred design spike

Investigate an appliance-owned recovery flow inspired by consumer-device onboarding:

1. Detect that no usable configured Wi-Fi connection has been established for a bounded recovery period.
2. Offer a local **Wi-Fi recovery** screen rather than silently remaining stranded in kiosk mode.
3. On explicit user action (or a carefully bounded commissioning condition), create a temporary NetworkManager-backed access point with an appliance-specific SSID.
4. Show a QR code on the Pi display containing only the temporary AP join information so an iPhone/phone can connect easily.
5. Serve a small local captive-portal-style page from the Pi listing nearby SSIDs and accepting the selected Wi-Fi passphrase over the temporary local network.
6. Pass the chosen credentials to a narrow privileged NetworkManager owner (`nmcli`/D-Bus or equivalent), never argv/logs/browser storage.
7. Tear down the temporary AP after successful association, restore normal client mode and return the kiosk to its configured startup/idle surface.
8. If association fails, keep the recovery UI useful and allow retry/another network without requiring a keyboard.

### Security / ownership requirements

- [ ] **No permanent open management network.** Temporary AP exists only during an explicit/bounded recovery session and stops after success/timeout/cancel.
- [ ] **No credential leakage.** Wi-Fi passphrases never enter ACP backup, logs, query strings, command-line arguments or persistent browser storage.
- [ ] **Least-privilege network helper.** If privileged NetworkManager mutation is required, expose only enumerate/connect/recovery-AP operations rather than broad shell/root authority.
- [ ] **Local-only provisioning page.** The provisioning service is reachable only on the temporary recovery network/loopback and is unavailable during normal appliance operation.
- [ ] **QR code is join metadata, not the target Wi-Fi secret.** Prefer QR information for the temporary AP; the household Wi-Fi passphrase is entered on the local page unless a later design proves another path safer.
- [ ] **Fallback touch path.** The Pi display must also show recovery status, retry/cancel controls and enough information to proceed if the phone does not automatically open a captive portal.
- [ ] **Do not disrupt working Ethernet.** Define behaviour when wired connectivity is present even though Wi-Fi is unavailable.
- [ ] **Physical acceptance.** Forget/disable the normal WLAN, enter recovery using only the touchscreen + phone, connect to a replacement SSID, verify the temporary AP disappears, verify ACP regains online services, and reboot to prove the recovered NetworkManager profile persists.

## Relationship to feature work

This resilience track is release-quality work, not a prerequisite for closing already-proven BBC News behaviour. It should be scheduled before the next supported release is promoted to `main`; exact ordering relative to Events, high-resolution audio and Astronomy can be deliberately chosen rather than silently inferred from this design note.