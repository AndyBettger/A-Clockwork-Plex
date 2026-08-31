# Appliance resilience roadmap

This is a future cross-cutting reliability track for A Clockwork Plex. It records appliance-hardening work exposed during commissioned-Pi testing; it is not part of BBC News checkpoint #92 acceptance.

## Storage / read-only filesystem resilience

Two development SD installations have independently experienced the Raspberry Pi root filesystem becoming read-only. In the most recent incident the dashboard, Ecowitt ingest and even an unrelated `mkdir` all failed with `EROFS`; the filesystem later returned writable after reboot. The affected cards are new SanDisk Extreme A2 media and have passed repeated H2testw capacity/read-write tests on Windows, so the investigation must not assume simple flash wear or counterfeit media.

- [ ] **Capture the root cause before mitigation claims.** On any recurrence collect kernel/system journal evidence for `mmc`, ext4, I/O, timeout, voltage/throttling and read-only remount messages; record `vcgencmd get_throttled`, power-supply/hardware context and filesystem state before reboot where possible.
- [ ] **Reduce expendable Chromium writes.** Evaluate moving Chromium disk/media cache to a bounded RAM-backed location such as `/dev/shm` or a verified tmpfs while preserving the normal persistent ACP Chromium profile, Plexamp session state and unpacked extensions. Do not use Incognito as the appliance solution.
- [ ] **Audit ACP write frequency and ownership.** Classify `state.json`, current Weather/Ecowitt observations, News cache, history, diagnostics and other runtime writes as volatile, recoverable cache, or genuinely durable user data. Avoid rewriting persistent flash when state has not materially changed.
- [ ] **Separate transient state from durable configuration.** Investigate an ACP runtime directory under `/run/a-clockwork-plex` or another tmpfs for data that need not survive reboot. Keep user configuration, alarms and genuinely valuable history durable and backup-owned.
- [ ] **Graceful `EROFS` behaviour.** A read-only filesystem should be surfaced as an appliance/storage diagnostic and should not turn otherwise renderable pages into HTTP 500 merely because a mode/current-state write failed. Define which writes may fail soft and which require an explicit warning.
- [ ] **Overlay filesystem feasibility.** Evaluate Raspberry Pi OS overlayfs only after persistent/volatile ownership is cleanly separated. Settings, software updates and durable history must not appear to save and then disappear on reboot.
- [ ] **SD-card comparison.** The project currently has a known previously-stable 64 GB SanDisk Extreme A2 card and a 128 GB SanDisk Extreme A2 test card. Use the same current software/workload when comparing them so capacity/card behaviour is not confounded with the old pre-rewrite dashboard workload.
- [ ] **Physical endurance/recurrence gate.** After hardening, run a representative multi-day appliance workload including Chromium kiosk, Ecowitt ingest, Weather/News refresh, playback and normal navigation; inspect write behaviour and kernel logs before claiming the problem mitigated.

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

This resilience track is release-quality work, not a prerequisite for closing already-proven BBC News behaviour. It should be scheduled before the next supported release is promoted to `main`; exact ordering relative to Events, high-resolution audio and Astronomy can be deliberately chosen rather than silently inferred from this file.