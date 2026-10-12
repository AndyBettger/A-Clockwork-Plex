# Native Plexamp desktop / visualiser migration

**Status:** ACTIVE — Phase B native Linux Plexamp migration; Phase A physically accepted; Headless remains the accepted rollback runtime  
**Roadmap item:** #94  
**Last updated:** 12 October 2026

## Goal

Investigate replacing the legacy Plexamp Headless + embedded browser UI with the
current ARM64 Linux desktop Plexamp so the bedside appliance gains native
visualisers and a supported desktop-player lifecycle without losing the parts of
A Clockwork Plex that are already physically accepted:

- NFC media launch;
- the managed `acp_plexamp` audio entry point and downstream trim / Music Master /
  CamillaDSP EQ / limiter / alarm-safe graph;
- alarm and AirPlay playback ownership;
- touchscreen-first navigation;
- backup/reset ownership;
- deterministic recovery and rollback.

This is a rehearsal-first migration. The accepted Headless runtime remains the
rollback until a native-player candidate passes all physical gates.

## Phase B entry point — 10 October 2026

Plexamp's 4.50 desktop rebuild changes the practical starting point for this work:
official Linux ARM64 desktop builds now exist as both AppImage and Flatpak. The
latest stable release verified at this checkpoint is **4.50.19**; the 4.50.20
series is still beta and is not a production acceptance candidate; it was nevertheless installed for strictly bounded discovery after the Flathub beta remote changed upstream.

The first commissioned-Pi step is therefore discovery rather than replacement:

1. record OS/architecture/session/runtime state and the accepted Headless service;
2. record the host ALSA view, especially `acp_plexamp`;
3. launch one native ARM64 package side-by-side without changing autostart (the initial Flatpak discovery install is 4.50.20-beta.22; require a suitable stable candidate before production acceptance);
4. prove visual presentation and whether the package can address `acp_plexamp`;
5. only then choose the packaging/runtime integration path.

The Linux Flatpak gained direct ALSA-device access in Plexamp 4.50.12, but a
generic physical DAC appearing in its picker is not sufficient acceptance. ACP's
named managed PCM and downstream trim/Music Master/EQ/limiter ownership must stay
authoritative. AppImage remains a valid comparison if sandboxing hides or alters
that boundary.

### 11 October 2026 Phase-B installation evidence

- Commissioned board: **Raspberry Pi 5 Model B Rev 1.1**, Debian 13 ARM64, labwc/Wayland, Chromium kiosk.
- Accepted baseline: Headless `plexamp.service`, ACP dashboard, CamillaDSP and NFC listener confirmed active after install. Host `aplay -L` exposes `acp_plexamp`; DAC Pro and ACP loopback remain enumerated.
- PipeWire presents only `Dummy Output`; do not accept PipeWire output as proof of managed ACP audio.
- Initial `flathub-beta` install failed to resolve `org.gnome.Platform/aarch64/50` until the main `flathub` remote was added. Final installation completed with GNOME Platform 50, system Flatpak ID `com.plexamp.Plexamp`, ARM64 beta branch.
- Installed Plexamp **4.50.20-beta.22** (Flatpak commit `b2b1645ac82777cba8169910b3107c997ecda71cc9f5e3451cef1009a5023d65`). As Plex confirmed 7 October, its Flathub beta remote now delivers Plexamp betas, not stable builds (https://forums.plex.tv/t/plexamp-flatpak-linux-beta-not-updating/944063/2). The old assumption that the remote guarantees stable builds is superseded.
- **Manual launch and remote capture PASSED:** a one-shot Flatpak launch under `XDG_RUNTIME_DIR=/run/user/1000`, `WAYLAND_DISPLAY=wayland-0`, and the existing session D-Bus opened Plexamp's Welcome screen in labwc above ACP's Chromium kiosk; WayVNC displayed both. `flatpak kill com.plexamp.Plexamp` removed only the native window and ACP remained visible. The launch printed `MESA-EGL` driver/device warnings; accelerated rendering and visualisers remain **unverified**.

**Audio confinement gap discovered:** default Plexamp permissions grant `devices=all` plus Wayland and PulseAudio sockets. The Flatpak can enumerate `/dev/snd` including card 2 (DAC Pro) and card 7 (ACP loopback), but cannot read either `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf` or `/run/host/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`. Hardware device visibility does **not** imply the managed named `acp_plexamp` PCM is configured inside the sandbox. A read-only, one-shot `--filesystem=host-etc:ro` diagnostic can make the host's `/etc` visible at `/run/host/etc`, but does **not by itself** integrate it with the Flatpak runtime's ALSA configuration. Inspect the real ACP PCM file and inclusions first; design a minimal/maintainable bridge before audio playback, without broad persistent permissions or bypassing the accepted audio graph.

**ALSA routing topology and readonly exposure (11 October):** The host's root-owned `99-a-clockwork-plex-shared.conf` defines a single music entry `acp_plexamp` as a `plug` over Plexamp-specific `softvol`, then `acp_master`/`softvol`, then two-channel music route bound to channels 0/1 of a four-channel `dmix` operating at 192 kHz on `hw:7,0,0`; the alarm route binds channels 2/3. Softvol controls reference card `Pro`. A one-shot Flatpak `--filesystem=host-etc:ro` invocation confirmed the same config can be read at `/run/host/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`, but `ALSA_CONFIG_PATH=/usr/share/alsa/alsa-flatpak.conf` remains authoritative and an included/registered custom PCM has **not** been established. The Flatpak `alsa-flatpak.conf` has since been inspected and directly includes optional user-specific `$XDG_CONFIG_HOME/asound.conf` and `$XDG_CONFIG_HOME/alsa/asoundrc` via its native pre-load hook. This is a supported app-local configuration seam, so replacing `ALSA_CONFIG_PATH`, modifying the host `/etc/alsa`, or granting persistent `host-etc` access is unnecessary for the first controlled PCM test. GNOME runtime lacks the `aplay`/`alsactl`/`speaker-test` tools, but sound card nodes and `/proc/asound/cards` are visible. Per Flatpak's documented XDG defaults, Plexamp's private user config is normally `~/.var/app/com.plexamp.Plexamp/config` (https://docs.flatpak.org/en/latest/conventions.html). Next: preserve any existing app-specific ALSA file; otherwise stage a byte-for-byte **test copy** at `config/alsa/asoundrc`, confirm sandbox visibility, and inspect native Plexamp's output options before any playback. A copied config can become stale: longer-term ACP installer integration must update/remove it safely and ensure it corresponds to the active host audio profile.

No production release, touchscreen Search, login/player identity, playback, visualiser, NFC, alarm/AirPlay or native-shell integration gate has passed. Headless remains authoritative. Beta can be used for discovery but not yet for production acceptance.

### 11 October 2026 native Flatpak ALSA device discovery accepted

The application-specific config test did not find a pre-existing `~/.var/app/com.plexamp.Plexamp/config/alsa/asoundrc` or `config/asound.conf`. A byte-for-byte copy of `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf` was installed at the first path, with matching SHA-256 `9de505b8e9ef326558fd317f22afaba2006d056efb0c34c79457c43ec9881fec`. The sandbox uses `XDG_CONFIG_HOME=/home/andy/.var/app/com.plexamp.Plexamp/config`, retains `ALSA_CONFIG_PATH=/usr/share/alsa/alsa-flatpak.conf`, and can read `pcm.acp_plexamp` through its existing optional user-config hook.

The native Plexamp 4.50.20-beta.22 GUI **physically shows** `A Clockwork Plex - Plexamp` in its Audio Device selector, along with ACP Music master, AirPlay and Alarm ceiling outputs. Separate scroll-position screenshots also show PipeWire, OSS, DAC Pro and raw Loopback devices. This closes **named ALSA PCM discovery**, not audio playback or processing acceptance. The next bounded gate is to select exclusively the Plexamp-specific PCM, pause but not stop Headless, ensure no active alarm or AirPlay override, then test low-volume native music while checking ACP's trim/master/EQ and CamillaDSP path. A display name alone does not prove that ALSA device opening, softvol controls, shared dmix IPC, hardware access, or downstream processing work correctly.

The private config file is an **experimental copy** of the host policy. Before final migration, own its installation/update/removal in ACP's setup path (and handle any pre-existing user configuration), avoid divergence, and address the brittle `hw:7,0,0` card-number dependency as part of runtime recovery/robustness. Headless continues as the accepted player and rollback.

### 11 October 2026 native playback / visualiser commissioning result

First real native Plexamp Flatpak playback into `acp_plexamp` produces audible music. **ACP Plexamp Trim, Music Master and EQ respond audibly**. This supports that native audio opens the PCM and traverses the intended ACP softvol/mixer/DSP graph, not a direct physical DAC selection. Native visualisers are rendered and functional, but GPU acceleration/load have not been measured.

**B2 audio stability is not accepted:** intermittent audible glitches were heard; no simultaneous CamillaDSP journal, process-load, throttling or ALSA hardware-parameter capture was yet provided. The native Plexamp volume slider visibly moves but does not alter audible level; its relationship to output backend, software-gain/bit-perfect policy, system volume and the accepted ACP softvol control is unknown. A previous Headless/Chromium UI-load glitch was monitor-only with no reproduction/XRUN evidence; do not assume it is the same mechanism as the current native-player problem.

**Immediate bounded investigation:** (1) compare constant-format music for 30–60 seconds with the native visualiser inactive/active at fixed ACP settings, noting audible glitch timing and VNC status; (2) capture CamillaDSP XRUN/error journal, kernel audio/MMC events, Pi throttling/temperature and process loads; (3) compare `amixer -c Pro sget "A Clockwork Plexamp"` before/after moving native player's slider, without changing mixer ownership. No rate/buffer/GPU/Flatpak override changes until evidence supports one. Fullscreen is a separate compositor-presentation gate: labwc's standard Alt+Space `client-menu` exposes `ToggleFullscreen`; production should later use a Plexamp-specific window rule or shell workspace integration, not a global kiosk alteration.

### 11 October 2026 B2 follow-up — fullscreen and audio stability

The native player continues to render visualisers and play through ACP Trim/Music Master/EQ; no more audible glitches were reported. Read-only diagnostic evidence did capture **one** CamillaDSP playback-buffer underrun recovery at 02:15:34. No kernel ALSA/MMC/throttle events matched, Pi throttling was `0x0`, temperature 64.8°C, and loopback parameters stayed `S32_LE, 192 kHz, 4ch, 4096/32768`. This is new evidence relative to the earlier B6 Headless/Chromium nonreproducible glitch and does not establish its cause; only one warning and later clean playback were observed. Do not change buffers without a repeatable timed correlation.

The native Plexamp volume slider has no audible effect and did not move `amixer -c Pro sget 'A Clockwork Plexamp'` (255/255, 100%, 0 dB before/after). This confirms it does not manipulate the ACP softvol, not that any specific alternative gain backend is active. Retain working ACP controls pending policy decision.

A WayVNC screenshot after attempted fullscreen shows Plexamp full-width but below an ACP-colored strip at the top, suggesting `Maximize` constrained to the panel's usable area instead of compositor `ToggleFullscreen` (hypothesis, not yet proven). Labwc supports both actions. Next: nonpersistent `wlrctl toplevel find app_id:com.plexamp.Plexamp` then `wlrctl toplevel fullscreen` only if matched; avoid modifying the system panel, kiosk or global compositor margins. If compositor fullscreen still leaves a strip, inspect native-client geometry and full-screen state before adding a Plexamp-only rule.

### 11 October 2026 follow-up — audible glitch with CamillaDSP capture/processing stall

A second audible native Plexamp glitch was accompanied by **fresh XRUN evidence**: CamillaDSP at 02:25:50.894 logged ALSA `snd_pcm_readi` capture overrun (`Broken pipe (32)`); at 02:25:51.064 logged capture/processing stalled; at 02:25:51.401 playback-buffer underrun; and at 02:26:00.699 a second playback underrun recovery. This is not the earlier B6 Headless monitor-only unexplained click. It also differs from the initial single 02:15:34 recovery warning. It demonstrates managed-graph discontinuity but does not uniquely implicate native decoding, graphical load, buffers, dmix capture, scheduling or the sandbox. Audible-event correlation is approximate rather than instrumented.

The kernel journal audio/MMC/throttle filter was empty, `vcgencmd get_throttled=0x0`, Pi temperature 66.4°C. Live loopback maintained `S32_LE/192 kHz/4 channels`, period 4096 and buffer 32768. Snapshot `ps %CPU` values indicate concurrent Chromium/WebKit/WayVNC activity but are not instantaneous XRUN measurements. Historical #85 A/B tests established that the accepted production CamillaDSP configuration should have `chunksize=4096`, `target_level=12288`, `queuelimit=4` with live capture/DAC 2048/16384. Confirm those **current** values using the existing read-only `scripts/audio/snapshot-airplay-hi-res.py --no-journal` before proposing changes.

Use two non-mutating, settled 60–90 second native Plexamp windows on the same track: visualiser inactive versus active (while keeping output, VNC and ACP mixer settings constant). Bound the CamillaDSP journal separately to each start/end timestamp. If only the active visualiser generates timed XRUNs, pursue display GPU/WebKit/WayVNC load and thread scheduling; if the issue persists in both, compare native and Headless source behaviour on the accepted PCM. Keep `acp_plexamp` and stable service ownership; do not alter the production audio geometry or introduce aggressive scheduling without measured justification.

### 11 October 2026 B2 clean short A/B and exact accepted timing confirmation

The user clarified that the original upper-bar fullscreen symptom was due to **Maximise** rather than true fullscreen, so no global Raspberry Pi panel reservation changes are warranted. Treat a dedicated compositor-fullscreen application rule as a later scoped integration detail, not a current defect fix.

The legacy read-only timing snapshot `scripts/audio/snapshot-airplay-hi-res.py --no-journal` shows the currently accepted production audio geometry *unchanged*: `S32_LE` / 192 kHz, 4-channel dmix `4096/32768`, capture `2048/16384` (4ch), DAC `2048/16384` (2ch), CamillaDSP `chunksize=4096`, `target_level=12288` (64ms), `queuelimit=4`, `adjust_period=1`, `enable_rate_adjust=true`. The active CamillaDSP PID remained 925 in the snapshot. No new buffer-size tuning is supported by this measurement.

Two short native-player sessions with the same material were fully clean to the ear and CamillaDSP's bounded XRUN log: visualiser **inactive** 02:35:44–02:38:44, then **active** 02:39:15–02:42:15, both 180 seconds. However the user has separately heard audio discontinuities with visualisers **off**; prior confirmed capture-overrun/stall/playback-underrun cluster at 02:25:50–02:26:00 remains a real failure. This rules out the simplistic assertion that visualisers alone trigger every interruption, but does not prove WebKit, VNC, scheduling or source rate are irrelevant.

**Next decision gate:** longer bounded no-interaction native-versus-Headless playback (same track, only one playing, matched ACP route and processing), with per-run timestamps and CamillaDSP journal rather than changing buffers based on a clean six-minute test. If a native-only difference emerges, separate its PCM output behavior from WebKit/WayVNC compute competition; if XRUNs occur on both player sources, investigate the shared ALSA loopback/CamillaDSP path. Preserve rollback and all existing production ownership until evidence is actionable.

### 12 October 2026 native/Headless comparison and ALSA PCM-versus-CTL boundary

Two bounded listening windows were physically completed with no CamillaDSP XRUN/stall/error matches: **native Plexamp 00:37:27–00:47:27** and **Headless Plexamp 00:51:47–01:01:47** on 12 October (Pi local time). The user noted only one possible tiny native click, not confidently an audio discontinuity (potential heater click), and no corresponding log anomaly. Combined with the clean 3-minute no-visualiser and 3-minute with-visualiser runs, these are **26 minutes** of positive bounded evidence, not enough to erase earlier confirmed capture overrun / processing stall / playback underrun faults or declare final stability acceptance. Preserve the accepted S32_LE/192 kHz geometry and continue observing ordinary playback and native startup/shutdown separately.

During the native Flatpak's SSH-launched session, **nine** `ALSA lib ... snd_ctl_open_noupdate Invalid CTL acp_plexamp` lines were visible. The current ACP configuration creates `pcm.acp_plexamp` (a plug over Plexamp-specific softvol and the ACP managed split-bus) but **does not** create a `ctl.acp_plexamp` control object. Libasound has separate `pcm.NAME` and `ctl.NAME` namespaces (ALSA's official `doc/asoundrc.txt` defines them independently). ALSA client control-name probing is the leading explanation; the successful PCM test demonstrates that the warning is not fatal to sample playback. **This is not exclusively new with the native app:** the 10 October B6b diagnostic snapshot of the earlier Headless run also logged `Invalid CTL acp_plexamp`. The native slider's lack of effect, and the unchanged `amixer -c Pro` ACP softvol reading, may be related but **causation is unproven**. A naive `ctl.acp_plexamp` alias to `hw:Pro` could expose controls affecting the entire physical DAC, including the independent alarm lane; do not install that alias without defining and testing the desired volume ownership. A future solution may require native-source software gain control or explicit ACP Trim integration, not simply a CTL alias.

**Next:** a brief read-only comparison of ALSA PCM vs CTL lookup only if useful, then continue native Plexamp's touchscreen keyboard, NFC Companion, workspace/window and alarm/AirPlay gates on the isolated side-by-side candidate. The experiment does not authorise retiring Headless, changing audio defaults or changing service autostart.

### 12 October 2026 — physically confirmed PCM versus CTL

The commissioned Pi confirms `amixer -D acp_plexamp scontrols` fails with `Invalid CTL acp_plexamp` because the host defines a PCM playback path but no identically named ALSA CTL object. `amixer -D hw:Pro scontrols` works and lists the separate ACP Plexamp, Master, AirPlay/Live and Alarm virtual softvol controls **plus** broader card controls including Analogue/Digital and DSP Program. This explains the non-fatal named-CTL diagnostic; it does not establish why Plexamp's native volume slider fails to change audible gain. Do not alias `ctl.acp_plexamp` blindly to the entire DAC control surface. Preserve accepted control separation.

Native touchscreen Search/OSK is the next isolated acceptance boundary: the ACP Chrome DOM keyboard is not directly usable by a native Wayland app. Test physical touch and WayVNC first; collect OSK/Wayland facts if missing before altering compositor, autostart, audio or Headless.

### 12 October 2026 — bounded manual native-player launch path

`scripts/launch-native-plexamp.sh` is a Phase-B-only operator convenience for the currently installed ARM64 Flatpak (`com.plexamp.Plexamp`, `beta`). Invoked as `bash scripts/launch-native-plexamp.sh` by the normal desktop user, including over SSH, it validates installation and avoids duplicate native instances, resolves the existing user Wayland socket and session D-Bus, uses `nohup flatpak run --branch=beta` to detach from SSH and saves output privately to `~/.cache/a-clockwork-plex/native-plexamp.log`. It cannot start its own Wayland session, change compositor/window focus/fullscreen, install the Flatpak or alter ACP Headless, audio, kiosk startup, alarms or NFC. Use `flatpak kill com.plexamp.Plexamp` only when deliberately closing the **native** player, not the Headless service. The branch pin is intentionally temporary for discovery; the accepted production release/runtime owner is still undecided. Script syntax and mock launcher tests passed locally; physical use on the commissioned Pi remains unverified.

### 12 October 2026 — manual Flatpak launcher CLI compatibility fix

The first real `scripts/launch-native-plexamp.sh` invocation failed before launch and falsely said the previously installed beta application was unavailable. The `flatpak info` subcommand does **not** accept `--branch=beta`; its interface is `flatpak info [OPTION...] NAME [BRANCH]`. Only `flatpak run` accepts `--branch=BRANCH` as used by the helper. The launcher preflight now calls `flatpak info "$APP_ID" "$APP_BRANCH"`; mock subprocess assertions no longer return unconditional success for any `info` invocation, and a branch-argument regression assertion runs even in root CI contexts. This is a manual helper-only correction; no Headless, mixer, compositor or installation state was changed. Pi physical launch still needs user verification.

### 12 October 2026 — native SSH launch acceptance and fullscreen OSK layering

The corrected one-command manual launcher successfully opened native Plexamp in the user's labwc/Wayland session. Two physical screenshots show **working automatic Pi OS on-screen keyboard over a windowed native Plexamp Search** and corresponding `test` search results; the OS keyboard was visible through WayVNC. After moving the native app to *genuine fullscreen*, the keyboard disappeared while Search itself continued to render. This repeats our July 2026 experiments with `wvkbd-mobintl` and Squeekboard: their normal labwc layer is obscured by full-screen/kiosk windows. The relevant wlroots layer-shell stacking places ordinary `top` below exclusive full-screen surfaces and `overlay` above them (see https://github.com/labwc/labwc/issues/2926 and https://github.com/droidian/squeekboard/issues/6). **Touch-only native Search is functionally accepted in windowed mode, but fullscreen touch text-entry is blocked.**

To simplify manually reproducing the compositor state, the Phase-B helper now accepts **opt-in** `--fullscreen`, requires pre-existing `wlrctl`, identifies exactly `app_id:com.plexamp.Plexamp` with a 20-second wait, then issues `wlrctl toplevel fullscreen`. It intentionally does not force fullscreen for normal launch because that would hide the OSK. Failure to find that Wayland app_id must be reported rather than guessing/targeting Chromium; physical `--fullscreen` test is pending. No production `rc.xml`, panel reservation, kiosk, service, DAC or Flatpak settings are changed.

Next investigate an **overlay-layer** on-screen keyboard (possible newer `wvkbd` implementations support a `--wayland-layer overlay` option, but the installed Pi build and integration must be checked), versus an ACP-owned borderless, non-fullscreen workspace preserving keyboard layering. Avoid blindly installing an unofficial system-wide patched Squeekboard: overlay layers can cover system security surfaces and the appliance needs scoped lifecycle ownership. Existing ACP DOM keyboard cannot input directly to native WebKit.

### 12 October 2026 — actual Wayland identity versus Flatpak ID

The commissioned Pi installed Debian `wlrctl 0.2.2-2`. The first manual `--fullscreen` attempt found that the Flatpak instance existed but **no** foreign toplevel matched `app_id:com.plexamp.Plexamp` during 20 seconds. This is **not** evidence that the native player failed to launch; the prior launcher and manual GUI proofs remain accepted. The root cause of the unsuccessful match is not yet proven; a different actual Wayland app ID is the leading explanation.

Inspection of the Debian wlrctl 0.2.2 source shows it implements an otherwise-undocumented `toplevel list` action that prints `app_id: title` for every known foreign toplevel. The revised manual helper first tries the configured Flatpak identifier, then queries the real compositor and finds only a single **exact-title `Plexamp`** window whose app ID is nonblank and is not Chromium/Chrome/Firefox. It makes a separate `wlrctl toplevel find app_id:<discovered> title:Plexamp` check before issuing the corresponding `fullscreen` action. If no unique match appears, it fails closed and emits the window inventory. This is still an opt-in test, not a new labwc window rule, kiosk alteration or stable release commitment. Source-derived behavior: https://sources.debian.org/src/wlrctl/0.2.2-2/toplevel.c.

**12 October commissioned-Pi acceptance:** after pulling the revised launcher, the user confirms that its `--fullscreen` path now successfully puts native Plexamp into genuine Wayland fullscreen. Window discovery and targeted fullscreen behaviour are physically accepted. This does **not** resolve the Squeekboard visibility issue or justify enabling fullscreen by default; touchscreen Search currently remains functional with native Plexamp windowed. No changes were made to the compositor, kiosk, Headless or audio routing.

The OSK inventory identifies `/usr/bin/squeekboard` running as PID 1484, while `wvkbd-mobintl` is absent. Squeekboard is visible and functional above windowed native Plexamp but **not** above compositor-fullscreen Plexamp; this matches the already investigated Chromium kiosk/labwc stacking behavior. Investigate the actual Squeekboard/labwc layer capabilities (or a borderless non-fullscreen workspace) rather than reinstalling another OSK without an explicit bounded hypothesis. Retain the working Headless and default windowed launch.

### 12 October 2026 — upstream evidence for Squeekboard's fullscreen layer

The browser-owned ACP keyboard and system Squeekboard are distinct. In native Plexamp, **windowed Search triggers and accepts the Pi OS Squeekboard through physical touch and WayVNC**, but genuine compositor fullscreen obscures the keyboard. labwc developers confirmed their layer stack is (bottom to top): ordinary windows, `top` layer, fullscreen windows, `overlay`, lock screen (https://github.com/labwc/labwc/issues/2926). The Raspberry Pi Squeekboard source's `panel_manager_request_widget` creates a `PHOSH_TYPE_LAYER_SURFACE` with `"layer", ZWLR_LAYER_SHELL_V1_LAYER_TOP` (https://github.com/raspberrypi-ui/squeekboard/blob/master/src/panel.c). Raspberry Pi UI issue #13 reproduces this exact symptom and reports success when changing the layer to 3/OVERLAY (https://github.com/raspberrypi-ui/squeekboard/issues/13).

**Design consequences:** globally moving the stock keyboard to `overlay` is a plausible technical fix, but its presentation may cover sensitive full-screen/system interfaces; no global package replacement or unreviewed community `.deb` builder should be run on the accepted appliance. No supported runtime knob has yet been verified on the exact installed Pi Squeekboard binary. The `SQUEEKBOARD_LAYER=overlay` mechanism discussed on Raspberry Pi forums is a proposed *source modification*, not a confirmed existing distro feature. Another option is a Plexamp-specific borderless `Maximize` presentation so the OSK in `top` remains visible; labwc supports `windowRule serverDecoration=no` and maximisation but the Pi panel currently reserves a top screen strip, so it needs a separate reversible visual-geometry experiment.

**Next physical gate:** gather *read-only* installed Squeekboard version/vendor and its launch ownership (desktop autostart vs user service), along with labwc version. Only then select a reversible proof: ideally a session-scoped separately built overlay-capable keyboard (not replacing `/usr/bin/squeekboard` or modifying global services), with explicit restoration and a checksheet for full-screen Search/Shift/Backspace/Done, VNC, ACP return, and system lock surfaces. If a separate instance conflicts with input-method ownership, fail closed and prefer a bounded, explicitly approved package-level rehearsal with backup/rollback. None of this changes native Plexamp audio or Headless runtime.

### 12 October 2026 — commissioned Pi keyboard package/startup ownership

Read-only Pi output fixes the runtime at **labwc `0.9.8-1+rpt1` arm64** and **Squeekboard `1.43.1-1+rpt1` arm64**, the Raspberry Pi OS-patched Trixie package (repository `archive.raspberrypi.com/debian`, priority 500), not Debian's baseline `1.43.1-1`. Running keyboard is `/usr/bin/squeekboard`, PID 1484, parent PID 1439. There is **no** `squeekboard.service` under `systemctl --user`; scanned XDG references show `/etc/xdg/autostart/squeekboard.desktop`. This strongly suggests the desktop autostart owner, but the file and parent must be read before we assume its activation semantics. The Raspberry Pi repository exposes exact source/distro files and the corresponding binary package for future recovery (https://archive.raspberrypi.org/debian/pool/main/s/squeekboard/).

A community report/build targets this exact version and Raspberry Pi 5/labwc, changing the Squeekboard layer from `TOP` to `OVERLAY` (https://github.com/CaputoDavide93/Squeekboard-Overlay-Patch). Its system-wide installation mechanism and permanently privileged overlay stacking are not an acceptable unreviewed rollout on ACP. First inspect desktop `Exec`, process lineage and binary hash plus available build dependencies, then consider a source-matched **isolated executable** with a scoped manual handover and guaranteed stock restart. Squeekboard may own a singleton D-Bus/input-method interface, so running two instances concurrently must not be assumed safe. No system package, service, compositor or ACP kiosk/audio mutation has occurred.

### 12 October 2026 — `sbtest` wrapper and exact vendor executable baseline

`/etc/xdg/autostart/squeekboard.desktop` was read directly and its `Exec` points to **`/usr/bin/sbtest`** rather than the keyboard binary. `ps` confirms shell PID 1439 as `/bin/sh /usr/bin/sbtest` (PPID 1), parent of running keyboard PID 1484. No user autostart override exists. The vendor `/usr/bin/squeekboard` is a regular root-owned executable, SHA-256 **`2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338`**. This is a rollback identification record, not a claim of a saved backup. Squeekboard is not installed as an active `squeekboard.service` user unit in this session.

Local build tools present: Meson, Ninja, GCC. The required Rust compiler and Cargo are **not installed**. Squeekboard uses Rust/Cargo in its build chain (upstream README: https://github.com/raspberrypi-ui/squeekboard). The next *strictly read-only* inspection is `/usr/bin/sbtest` plus its package owner, because a vendor launch wrapper may supervise/restart the keyboard automatically. A side-by-side overlay executable must avoid conflict with the keyboard's D-Bus/input-method ownership; no safe live substitution is established until the wrapper is understood. Do not change the system-wide executable or XDG startup and do not install build tools for a test whose lifecycle is not yet designed.

### 12 October 2026 — `sbtest` source establishes one-shot lifecycle

The Pi's exact `/usr/bin/sbtest` is:

```sh
#!/bin/sh
if [ -e /usr/share/squeekboard/output ] ; then
. /usr/share/squeekboard/output
fi
if libinput list-devices | grep Capabilities | grep -qw touch ; then
 /usr/bin/squeekboard
fi
```

This 186-byte vendor script is package-owned by `squeekboard`. It launches the keyboard **once** and waits for the child, explaining why its parent PID 1439 remains in `S` state while `squeekboard` PID 1484 is `Sl`. There is no restart loop inside `sbtest`; do not infer that the desktop environment cannot separately restart a crashed process. The optional `/usr/share/squeekboard/output` is sourced and still needs read-only inspection before replicating the launch context. There is no user-level Squeekboard service, and the XDG autostart entry remains package-owned.

The Raspberry Pi Debian repository publicly offers the **version-matched** 1.43.1 base source, `1.43.1-1+rpt1` packaging patch and source descriptor together with the vendor arm64 package (https://archive.raspberrypi.org/debian/pool/main/s/squeekboard/). That makes it possible to target the installed vendor source rather than GitHub HEAD, although this does not yet prove that a recompiled binary is identical to the installed package. The planned experiment is a **sidecar build with one panel-layer change only**, retaining `/usr/bin/squeekboard`, system packages, `/etc/xdg/autostart` and accepted Chromium. Before a manual, never-simultaneous runtime switch, create a bounded watchdog/rollback path able to restore `/usr/bin/sbtest` in the established Wayland/D-Bus session after failure, and do not install any build dependencies without a deliberate user-approved step. The primary input gate is the contents (or absence) of the optional `output` file.

### 12 October 2026 — source-only overlay preparation boundary

The Pi confirmed `/usr/share/squeekboard/output` is **absent**. The vendor XDG entry invokes `/usr/bin/sbtest`, which tests for touch hardware and launches `/usr/bin/squeekboard` once. The vendor package `1.43.1-1+rpt1`, the exact executable SHA-256 and absence of a supervisor are now documented; this does **not** prove an isolated keyboard can be run alongside it.

To keep the experiment isolated, `scripts/prepare-squeekboard-overlay.py` stages a version-matched Raspberry Pi source tree only when explicitly run with `--prepare`. It preflights the installed version and original executable SHA-256; retrieves the exact `.dsc` and both archive files over HTTPS; validates their descriptor SHA-256/byte lengths and delegates vendor patch/extraction to `dpkg-source -x`. It checks that the vendor source has **exactly one** `"layer", ZWLR_LAYER_SHELL_V1_LAYER_TOP,` before replacing that one token with `OVERLAY`, then records original/changed source hashes and provenance. The user-cache destination is private and non-overwritable; temporary partial files are cleaned up after a failure. The original executable and `sbtest` are not edited. Source directory after successful staging: `~/.cache/a-clockwork-plex/squeekboard-overlay-1.43.1-1+rpt1/squeekboard-source/`.

This **does not build, install, launch or restart** either keyboard. Missing Rust/Cargo and other vendor build dependencies remain a separate approval gate. The longer-term choice between an overlay-layer OSK and a borderless maximised Plexamp application still hinges on whether an overlay keyboard remains usable/secure with labwc, lock/session controls, full-screen native Plexamp and VNC. Live switch requires deterministic re-entry into the original keyboard using the existing session Wayland/D-Bus and a timed failback, not an ad hoc `kill`/unreviewed package installer. Source descriptor hash checks are not independent source-signature verification; don't conflate them with a signed APT binary install. The Phase B keyboard gate remains **pending physical acceptance**.

### 12 October 2026 — source staging physical result, build gate and CI correction

The exact Pi source-staging helper has now been run successfully by the user. Both exact Raspberry Pi Trixie `1.43.1-1+rpt1` tarballs passed descriptor SHA-256 and size verification; `dpkg-source` extracted `1.43.1` and applied six vendor Debian patches including `sbtest`, `output`, `layouts`, `unset` and `unset2`. The helper's single recognized `TOP → OVERLAY` change and provenance file are staged in `~/.cache/a-clockwork-plex/squeekboard-overlay-1.43.1-1+rpt1/`. The archive's `dpkg-source: warning: extracting unsigned source package` is expected for a descriptor not independently GPG verified; archive hashes are checked against the HTTPS-fetched descriptor, not an independently authenticated release. Production security acceptance may require additional provenance review. There was **no** build, system package change, runtime switch, service restart, compositor reconfiguration or mutation to `/usr/bin/squeekboard`.

Before constructing any binary, the staged `debian/control` is the exact source of build dependency truth: inspect it, run `dpkg-checkbuilddeps` read-only from its directory, and validate the patched `src/panel.c` line/provenance against the intended `OVERLAY` enum. Since Rust/Cargo are absent, dependencies are expected to be missing; do not invoke `apt-get build-dep` without reviewing its transaction. Build later in the **isolated source tree**, never `ninja install` or `dpkg -i` on a live ACP test. Preserve separate input-method ownership and a timed original-keyboard restore for future live physical testing.

GitHub Tests #5528 failure was traced to two **repository hygiene assertions**, not staging logic: unlisted new test modules in `docs/development/testing/test-catalogue.md` and a stale Phase-A roadmap heading asserted by `tests/test_docs_catalog.py`. Both have been updated to the current branch; no green CI result is claimed until a new run completes.

### 12 October 2026 — exact overlay source SHA and APT simulation boundary

The commissioned Pi's staged `src/panel.c` is consistent with the narrowly patched build: source SHA-256 before modification `2983685254b5d5b81ce36d9277172a041502737450dee416a6f805b82d51c203`; after modification `61d977ba7d7805f58dc57126b2fa410c6115af172889724f3e55cd444d9df916`; overlay enum is present at line 82. `meson 1.7.0` and `ninja 1.12.1` are installed, but `dpkg-checkbuilddeps` reports a large missing closure: Rust/Cargo, Debian packaging helpers, GTK/GLib/Wayland development headers and packaged Rust crate sources. Debian's offline Rust-crate packaging model is desirable for repeatability; the exact vendor `debian/rules` and Cargo configuration must be read before choosing Meson build invocation (see https://wiki.debian.org/Gnome/Rust_Packaging).

To avoid `apt-get build-dep squeekboard` accidentally selecting a different distro/version's source requirements, `scripts/plan-squeekboard-build-deps.py` reads the **staged Raspberry Pi** `debian/control` Source stanza and asks `apt-get --simulate -o APT::Install-Recommends=false satisfy "<Build-Depends>"` directly, as supported by Debian APT's dependency-solver interface (https://manpages.debian.org/trixie/apt/apt-get.8.en.html). It rejects invalid provenance, any change to the accepted panel SHA-256 or missing overlay marker. It does **not** modify system packages, APT indices, keyboard processes, labwc configuration, audio or Headless. Review solver output for proposed upgrades/removals before any install authorization; the dry run does not grant permission for a real transaction or a full build. Local unit tests check the guard and APT simulation invocation, but the Pi-specific APT dry run remains untested.

The branch's GitHub Tests #5532 completed **successfully** after repairing the stale Phase-A title and the test catalogue. This new helper's own CI is separate and still awaiting results. No built keyboard exists; the eventual timed stock-keyboard restoration plan remains a prerequisite for a live OSK swap.

### 12 October 2026 — constrained ARM64 builder decision after Pi APT dry run

The existing Pi source staging and APT simulation both passed without any package mutation. Crucially, **the full vendor build dependency closure is excessive for production**: 355 proposed new packages and 31 upgrades, zero removals, 192 unchanged. Among the proposed upgrades are the Pi's graphics/compositor and input foundations (Mesa GL/DRI/EGL/GBM, GTK3, GLib, Wayland-adjacent xkbcommon) used by both accepted Chromium ACP and the native Plexamp proof. Do not install this dependency set on the live Pi for a one-line keyboard-layer patch. The simulation output does not state download/disk totals.

The exact `debian/rules` uses Debian's Meson-based `dh` pipeline, stores Rust crates in `debian/cargo` by setting `CARGO_HOME`, sets Debian hardening and deterministic `RUSTFLAGS`, and drops `Cargo.lock` when building architecture packages. This supports a repeatable distro-crate-based build. The preferred next implementation is an **off-device, disposable native ARM64** Docker container (`debian:trixie`) on a GitHub-hosted `ubuntu-24.04-arm` runner (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax). Compile the pinned Raspberry Pi package sources and the already physically verified `TOP→OVERLAY` patch in that isolated container, export the test-only `.deb`, binary ELF build ID, package dependency list, file hash and provenance. Reproducibility is not automatic: Debian container libraries may differ from Raspberry Pi patched libraries, so validate link dependencies on the *target Pi* before any one-instance keyboard runtime swap; a compiled artifact is not evidence of touchscreen support.

**Hard boundaries:** no `apt-get satisfy` or broad dependency upgrades on the Pi, no third-party unaudited patch installer, no replacing `/usr/bin/squeekboard`, no `dpkg -i` of compiled `.deb`, no autostart/compositor change, no concurrent Squeekboard input-method clients, and no retirement of working Headless. A future test must first have a proven timed original-keyboard recovery command scoped to the existing labwc Wayland/DBus session and physical Search/OSK/WayVNC acceptance. CI Tests #5538 are green for the prior source staging/preflight code, but the container builder does **not** exist or pass yet.

### 12 October 2026 — reproducible ARM64 test binary boundary

A dedicated repository CI candidate now prepares the exact Raspberry Pi vendor `squeekboard 1.43.1-1+rpt1` tarballs from the pinned HTTPS archive and verifies all source descriptor checksum/size entries. It uses the existing `scripts/prepare-squeekboard-overlay.py`'s pure download/patch parsing to avoid mismatched staging logic, while **requiring** the known commissioned-Pi `src/panel.c` SHA-256 both before and after the sole `ZWLR_LAYER_SHELL_V1_LAYER_TOP→OVERLAY` edit. The standard GitHub-hosted `ubuntu-24.04-arm` job runs a Debian Trixie container where the large Rust/GTK/Wayland APT dependency closure is disposable. Debian/Meson/Cargo architecture packaging runs as non-root, with `CARGO_NET_OFFLINE=true` and bounded parallelism. The build exports unsigned test-only `arm64` package, extracted ELF, original/patched source provenance, dependency and ABI manifest plus logs via Actions artifact; no script or action can deploy to the Pi. We do **not** claim that an arbitrary Debian Trixie-built ELF is ABI-compatible with Raspberry Pi OS; target-library comparison is a later physical read-only gate.

The builder refuses execution outside a Github Actions Docker container on ARM64; it has no `setup.sh` integration, physical Pi package mutation, service/autostart write, or concurrent OSK activation. The build artifact is test-only and not automatically used by ACP's installer. Success must be confirmed from actual GitHub Actions logs/artifact (not just unit tests). The unsigned vendor source descriptor is hash-verified but not independently GPG authenticated.

### 12 October 2026 — ARM64 CI run provenance and non-recurrence

The user approved an off-device ARM64 build. GitHub **Squeekboard Overlay ARM64 (test-only)** [run #3](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38196515161) was started on the Phase-B branch and verified to have reached the ephemeral Debian Trixie ARM64 container's build step. The earlier newly authored workflow push did not appear as a separate run, so an explicitly same-repository-only PR event was temporarily allowed; after the build started, both push and PR auto-triggers were deleted to prevent accidental repeats. The repository [Tests #5549](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38196515178) passed. As of this entry the binary build outcome, package artifact and ABI compatibility are unconfirmed. No external device install path exists in the builder. The workflow is manual-dispatch-only, and `workflow_dispatch` on a non-default feature branch may not be discoverable until the workflow also exists on the default branch; future retry mechanism is deliberately not presumed available.

### 12 October 2026 — first off-device ARM64 test-build failure and fixture-only repair

The first dedicated [ARM64 build #3](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38196515161) completed with **failure**. APT dependency resolution and vendor `rs` library compilation worked, but Debian's `dh_auto_test` executed `cargo.sh test --no-run` and found **Rust E0063**: the vendor `src/state.rs` scaling-test initializer for `OutputState` lacks the now-required `name` field. This is a test source mismatch *independent* of our runtime `src/panel.c` layer constant. The debug artifact #11723219236 contains logs, not a deliverable ELF or .deb. The physical Pi remains untouched and its original `/usr/bin/squeekboard` still owns the input method.

The maintained Raspberry Pi `src/outputs.rs` declares `pub name: Option<String>`, and the matching newer test fixture uses `name: None`. Accordingly the CI-only preparation now applies a **second, test-fixture-only compatibility correction** limited to the known old `Application::get_preferred_height_and_arrangement(&OutputState { ... scale, }),` initialisers, with a strict match count and provenance. This is explicitly not part of the runtime layer patch, which remains the independently SHA-verified *single change* to `src/panel.c`. It allows keeping the vendor tests enabled; no `nocheck`/test suppression is proposed. Another isolated CI run must prove whether that correction suffices. Any built ELF still requires target ABI review and guarded input-method handover before use.

### 12 October 2026 — test-only fixture scanner and ARM64 run #5

The second ARM64 [run #4](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38197421672) failed closed while trying to identify the old Rust `OutputState` test fixture in the source tree; it did **not** install the large dependency closure or produce a candidate binary. The CI staging helper now parses only the vendor `#[cfg(test)]` module, uses balanced braces to find actual `OutputState` constructions and inserts a missing optional `name: None` on the test-only scale field with a strict 1–3 repair gate. Its unit tests passed on the branch as GitHub Tests #5567, retaining the complete Debian `dh_auto_test` build chain. The source runtime modification remains exactly the SHA-verified `TOP→OVERLAY` in `src/panel.c`.

A third off-device [ARM64 run #5](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38197809476) reached the Debian Trixie arm64 builder; verdict and artifacts await inspection. Temporary PR triggering was removed after launch, so subsequent Phase-B commits do not consume builder time unexpectedly. No build binaries have been installed on the target Pi.

### 12 October 2026 — verified off-device ARM64 overlay candidate, target ABI pending

A third dedicated [ARM64 GitHub Actions run #5](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38197809476) successfully compiled and packaged Raspberry Pi OS's exact `squeekboard 1.43.1-1+rpt1` in a disposable Debian Trixie ARM64 container. The source descriptor archives and pre/post `src/panel.c` SHA-256 match the commissioned Pi; the **sole runtime logic change** is Wayland panel layer `TOP→OVERLAY`. A separate **single test-only** `OutputState` initializer received `name: None` for Rust E0063 compatibility. No `nocheck`: the complete Meson test stage executed **124 tests, all passed**, after which `dpkg-buildpackage` successfully emitted the package and test-only ELF. Evidence is in [artifact #11724201740](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38197809476/artifacts/11724201740).

Artifact contents: `squeekboard-overlay-arm64` AArch64 ELF PIE 17,109,456 bytes, SHA-256 `11e1c8ef40674503cb9a0b82a96086d8bbca319c99943b9061bc5629118166a6`; test-only `squeekboard_1.43.1-1+rpt1_arm64.deb` 2,468,116 bytes SHA-256 `f13e11f67b868d6f23beeeb607596fa99e05b5657c575526dcca43ca1ef1511e`; original/modified source hashes, build log, Build-Depends and a large `readelf -d/-V`/Debian package inspection report. Its `Depends` declares `libc6 >= 2.39`, `libglib2.0-0t64 >= 2.83.0`, `libwayland-client0 >=1.20.0`, `libxkbcommon0 >=1.0.0`, GTK3, `raspi-config >=20241028`, etc. `readelf` reports `GLIBC_2.39` highest; the target Pi's actual installed library versions and symbol availability remain unverified. Source `.dsc` lacked independent GPG signature verification; therefore artifact remains experimental regardless of test pass.

**Do not deploy now.** Never run `dpkg -i` on the production appliance or replace packaged `/usr/bin/squeekboard`. A future proof requires a read-only target package/ABI inventory, then a **pre-armed timeout/rollback guard** to restore the single stock Squeekboard instance in the correct Wayland/DBus session after stopping candidate/timeout/SSH loss. Test only the standalone executable, not its Debian package; all old ACP/Headless audio and compositor settings must remain unchanged. Even though the off-device tests passed, touchscreen full-screen OSK/WayVNC acceptance is entirely open. Normal ACP Tests #5574 green and off-device build workflow manual-only.

### 12 October 2026 — commissioned Pi matches overlay candidate package version floors

The Pi's read-only runtime inventory establishes `glibc 2.41` versus the candidate's highest required `GLIBC_2.39`, `libglib2.0-0t64 2.84.4` versus `>=2.83.0`, `libgtk-3-0t64 3.24.49` versus `>=3.23.1`, GNOME Desktop 44.3, libfeedback 0.8.2, Wayland 1.24, xkbcommon 1.7 and raspi-config 20260730, all above the **built artifact's** declared lower bounds. These versions come from the user's actual `dpkg-query`, not from a projected APT transaction. The source build produced an unsigned test-only executable, so this is a **package ABI version preflight**, not runtime Wayland or input-method acceptance.

Added a stricter read-only `scripts/inspect-squeekboard-overlay-artifact.py` for the target Pi. Given an independently transferred ZIP from [successful build #5](https://github.com/AndyBettger/A-Clockwork-Plex/actions/runs/38197809476), it checks both actual ZIP contents against pinned SHA-256 and byte sizes, confirms AArch64 ELF and package `1.43.1-1+rpt1`, checks every `.deb` `Depends` expression through installed `dpkg` versions (including the gsettings-backend alternative), and verifies 18 direct ELF library names against `ldconfig -p` (including loader path). It extracts only to a disposable mode-nonexecutable temporary directory, never runs either ELF or package and never touches active Squeekboard/ACP. This does **not** verify all ELF symbol relocations or Wayland protocol ownership; any subsequent runtime attempt requires the separately pre-armed watchdog and explicit timed restore of stock `sbtest` in the correct desktop environment.

### 12 October 2026 — complete target SONAME gate passed; isolated timed OSK swap preparation

The user physically executed the pinned target-Pi checker against experimental ARM64 GitHub run #5's downloaded ZIP. It accepted both expected ELF and `.deb` digests, arm64 package metadata, all 17 declared Debian runtime dependencies and all 18 direct dynamically needed library names. No executable was launched. Dynamic linker symbol resolution, compositor protocol access and touch Search are not yet tested.

The next opt-in tool, `scripts/try-squeekboard-overlay.py`, is **not an installer**. Its dry-run `--plan ZIP` verifies exact vendor hash, downloaded artifact SHA-256/dependencies, single running stock keyboard, labwc `wayland-0` and user D-Bus sockets, and user systemd access. The deliberate `--start ZIP` stages the checked standalone ELF under private cache, then uses `systemd-run --user --on-active=240s` to create a separately armed rollback timer **before** running a trial transient service; the worker refuses to terminate original Squeekboard unless the timer remains active and stock PID matches. Candidate is run no longer than 180s, with normal rollback in the worker's finally path. Backup service is independent of SSH, stops the trial service and starts vendor `/usr/bin/sbtest` in a distinct systemd user unit. A file lock guards against concurrent restores; the rollback routine never needs the experimental executable to remain present. Early recovery is `systemctl --user start acp-squeekboard-overlay-restore.service`. No original binary, OS package, `/etc/xdg/autostart/squeekboard.desktop`, labwc configuration, ACP, Headless or audio graph is modified. This arrangement is expected to survive a dropped SSH session while the desktop user manager remains alive; it **cannot** protect against a full reboot/systemd-user manager failure and still needs real Pi testing.

First physical gate is just `--plan`, then a separately user-initiated `--start` when native Plexamp already fullscreen and touchscreen/WayVNC are available. Only a successful visibility, typing and exact restoration trial can advance from runtime ABI to actual OSK acceptance.

### 12 October 2026 — timed OSK restore order / no-concurrent-input-method hardening

The commissioned Pi returned an actual **PLAN PASS** for the isolated OSK trial, confirming unchanged original keyboard/Wayland session and pinned successful ARM64 artifact. Before letting the user execute `--start`, a recovery concurrency audit identified a potential lock inversion: the timer's early `systemctl stop trial.service` could block on the worker's own restoration lock, deadlocking against the worker's `finally`. Recovery now stops the worker **before** acquiring `restore.lock`, and the transient unit explicitly uses systemd `KillMode=control-group` with `TimeoutStopSec=5s` so its candidate child is included in cleanup. A path-exact, owner-checked `/proc` scan ensures zero test ELF processes remain before vendor `sbtest` is restarted; otherwise recovery refuses to overlap input methods rather than hide the failure. This reduces, but does not eliminate, live-test risks (user systemd/labwc crash, broken compositor, unexpected process behaviour). All production components remain unchanged; the first physical full-screen touchscreen test is still to come.

### 12 October 2026 — real full-screen Wayland OSK layering solved in prototype

The user has now **physically verified** the separately compiled Squeekboard `ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY` build displaying above a truly fullscreen Plexamp Flatpak window, using the opt-in three-minute transient systemd-user experiment. The untouched stock `ZWLR_LAYER_SHELL_V1_LAYER_TOP` Squeekboard was previously invisible underneath fullscreen in the same labwc session. Both screenshots are WayVNC captures: first has native Search with visible text `pink f` and Pink Floyd results while virtual keyboard is in the foreground; second has the Artists add-header title modal visible behind the keyboard. These are real compositor/user-UI outputs, not a simulator. The user reports the experiment worked well. They do **not** independently prove touch-only key-level Shift/Backspace/dismissal, focus transfer for every dialog, or that all modal action buttons remain accessible; keyboard overlaps lower modal content at 1280×720, which needs a targeted usability review before appliance defaults.

The user ran the checked `--plan`, targeted actual fullscreen with the native Flatpak launcher, then `--start`; the tool reported independent 240s rollback timer armed and 180s normal window. After the experiment `ps` shows original package-owned `/usr/bin/squeekboard` PID 723443 under `/bin/sh /usr/bin/sbtest` PID 723426; no experimental candidate remains. This is **post-trial original keyboard restored**, not proof which timed recovery path executed. The requested `journalctl --user` returned `No journal files were found`; don't claim journal timelines or suggest journald itself is broken without evidence. Better evidence is systemd user unit/timer properties, private `candidate.log`, state directory, and targeted timed comparison in a subsequent bounded run if needed. Provenance includes successfully verified artifact SHA-256, 17 runtime dependency expressions, 18 direct loaded SONAME names and 124 off-device tests. No `.deb` was installed; no vendor binary, autostart, Headless, CamillaDSP, ALSA, ACP or NFC changes.

**Boundary forward:** This unblocks full-screen text entry **at the compositor-layer proof level**. Production migration should implement explicit ownership of exactly one OSK across reboot/login/logout, user XDG autostart and systemd user units with reproducible source/build provenance and opt-in rollback, rather than overwriting `/usr/bin/squeekboard`. Treat always-OVERLAY security/system prompts and keyboard-over-dialog geometry as potential design trade-offs. Full native Linux Plexamp migration remains blocked on other Phase B gates (ACP shell navigation, media NFC handover, system audio/visualiser robustness, native slider, alarm ownership); keep Headless production path unchanged.

### 12 October 2026 — virtual keyboard interoperability and palette architecture proposal

New physical user feedback confirms the experimental OVERLAY keyboard fully appeared over full-screen native Plexamp and accepted alphabetic Shift, numbers and punctuation: Search displays `Does This Help?$%&`, with the number/symbol key page on-screen. The native Artists Add modal remains operable: the user can choose Add, or tap outside its text field to hide Squeekboard and access Cancel. Thus the earlier concern about lower-modal buttons being permanently blocked is **not observed**. The user provided `candidate.log` only, not worker journal evidence: it contains a non-fatal `org.gnome.SessionManager` unavailable warning in labwc, and the missing British `gb_wide.yaml`/`gb.yaml` layout lookup before it loads the **US** `us_wide.yaml` fallback. This warrants a bundled/managed UK keyboard layout for production. `systemctl --user list-timers --all 'acp-squeekboard-overlay-*'` returns zero after the short trial, consistent with transient unit collection but not proof of exact restore trigger. The original vendor OSK is again the only running instance.

**Unification proposal, not yet deployed:** A single ACP-managed Squeekboard OVERLAY instance is a clean target for both Wayland-native Plexamp and Chromium-hosted ACP surfaces, provided the Chromium kiosk actually participates in Wayland text-input/input-method protocol and current ACP UI's accepted #91 keyboard functionality is reproduced. The current `app/static/js/settings-keyboard.js` DOM keyboard lives inside Chromium, consumes theme variables in `app/static/css/touch-keyboard.css`, intercepts custom input layouts (number/decimal/time/URL), has reusable quick-fill/Done behaviour and communicates with embedded Headless Plexamp's security-scoped content bridge. It cannot send events into the separate native Plexamp application; conversely, the Squeekboard OSK can send virtual input to Wayland-native fields but **has not yet proven Chromium Settings or embedded Headless text entry**, particularly if kiosk renders through XWayland. Do not disable #91, remove its bridge or create overlapping virtual keyboards until a bounded browser compatibility test proves parity. A build/environment switch to native Wayland Chromium, if necessary, must be trialled separately from OSK ownership.

**Theme adaptation:** Squeekboard's actual upstream GTK source (`raspberrypi-ui/squeekboard/src/style.rs`) uses `GTK_THEME`/GTK settings to select compiled GTK CSS GResources; `data/style.css`, `data/style-Adwaita:dark.css` and `data/common.css` control `sq_view`, `sq_button`, active/latched and Return styling. These are independent from ACP's browser CSS; changing `--acp-theme-control`, `--accent` or `--text` in the page does not affect the OS keyboard automatically, and Chromium's scheduled black dim overlay does not dim an ABOVE-fullscreen GTK surface. A candidate architecture would keep the vendor system GTK unaffected and load a **verified ACP-only style provider** generated from an allow-listed palette exported by ACP's settings/theme authority, including Classic Dark, six themed daytime styles, scheduled night dim/low-glare and future astronomy red. Reload on safe focus/dismissal boundaries, with fallback if the settings/dashboard process is unavailable and no mid-keystroke process restart. Fonts, key size, contrast, focus and Return/Shift states need physical review. Maintain the original one-line TOP→OVERLAY source provenance as the accepted prototype; any GB layout/theme loader changes are new isolated changes requiring separate build/test provenance and an opt-in, reversible managed user XDG/service lifecycle.

## Preferred player architecture

The preferred experiment is **native Plexamp as the real local decoder/player**,
not a second Plexamp instance acting only as a remote UI for Headless.

Target:

```text
NFC / ACP playback policy
          |
          v
native Plexamp
          |
          v
     acp_plexamp
          |
          v
Plexamp Trim -> Music Master -> reserve -> EQ -> limiter
          |
          +---- alarm-safe join
          |
          v
         DAC
```

A two-player arrangement may still be useful temporarily for discovery, but is
not the intended visualiser architecture because a remote controller does not
own the locally decoded audio data required by the visualiser.

## Phase A implementation checkpoint — A0

The first implementation checkpoint introduces a fail-safe same-document surface host without migrating any product surface yet.

Current ownership:

- `app/static/js/acp-surface-host.js` owns the future same-document lifecycle registry and View Transition commit boundary.
- A destination registers only when it has an explicit asynchronous `prepare()` function that returns a synchronous `commit()` function. This lets data/assets be prepared before the visual transition starts.
- `page-transitions.js` remains the navigation policy entry point for now, including screen-projection/manual-lease handling and Plexamp special cases.
- After those policy checks, `page-transitions.js` asks the surface host whether the destination is registered. Registered routes may commit in-document; unregistered routes continue through the existing full-document `window.location.assign()` path.
- The host updates active-surface body/navigation state and browser history only after a successful commit.
- If preparation fails, the host returns control so the caller can use the accepted full-route fallback.
- No Clock, Weather, News or Settings destination is registered at A0, so production navigation is intentionally unchanged.

This seam is the prerequisite for incremental migration. It avoids a flag-day SPA rewrite and provides a measurable rollback boundary for each surface.

### First migration candidate — implemented, physical gate pending

Use **Clock ↔ Weather** as the first real surface pair unless code inspection exposes a stronger blocker. It exercises:

- Clock hydration/live timers;
- Weather's data-heavy rendered surface and refresh lifecycle;
- per-surface CSS/script ownership;
- browser history/manual screen leases;
- the fixed 1280×720 appliance presentation.

Weather currently refreshes itself with a timed `window.location.reload()`. That must be retired as part of this first migration. The long-lived surface should instead consume an ACP-local Weather view-model/snapshot and patch changed values in place. Returning to Weather after another ACP surface should trigger an immediate snapshot refresh, while routine updates must preserve scroll/focus/open-panel state and must not invoke the top-level navigation transition engine.

The intended eventual browser boundary is one long-lived ACP document containing **all ACP-owned application surfaces** (Clock, Weather, News, AirPlay, Settings, Astronomy, future Events and alarm/takeover presentation). This does not mean one enormous permanently active DOM: surfaces may be lazily prepared, mounted, suspended and resumed behind the Surface Host contract. **Native Plexamp is the deliberate exception** and lives as a separate native application/workspace; the ACP desktop shell owns navigation and transitions across that process boundary.

Do not bring Settings transaction ownership, News modal/scroll lifecycle or Plexamp's persistent overlay into the first same-document experiment.

#### Clock ↔ Weather implementation shape

The first pair is implemented as a mount-once incremental bridge rather than a template rewrite:

- the initial Clock or Weather content is wrapped as a mounted surface after the shared navigation layer has moved its controls to `body`;
- the first visit to the other member of the pair fetches ACP's read-only rendered surface document from `/api/surfaces/<surface>`; this endpoint deliberately does not call `set_mode()`;
- missing destination styles load before commit; missing destination scripts load once after commit, when the destination is the active surface;
- both Clock and Weather DOM trees remain mounted thereafter and visibility toggles under the Surface Host, preserving their local interaction state;
- same-document activation synchronises `/api/mode/<surface>` after the visual commit while the existing manual lease/screen-projection policy remains the navigation authority;
- Weather's former periodic `window.location.reload()` has been retired. A Weather surface controller obtains a fresh ACP-rendered snapshot, replaces only the Weather data grid, preserves vertical and Rain-history scroll positions, leaves the forecast console mounted and rebinds refreshed grid controls;
- a failed surface preparation/script activation returns to the existing full-route fallback rather than trapping the appliance in a half-migrated state.

At this checkpoint only Clock and Weather register with the Surface Host, and only when the initial document itself is Clock or Weather. Entering Weather from News/Settings/AirPlay still uses the accepted full route; broader surface convergence follows only after this pair is physically accepted.

#### First physical result

The commissioned appliance confirms that the mount-once pair is visibly faster and eliminates full-page bootstrap flashes. Weather can refresh in place without resetting the reader's position, and Clock remains live after a round-trip.

The first pass also exposed two browser-lifecycle details that must be owned explicitly in the shell architecture:

- browser View Transition defaults are not ACP product motion; the shell maps ACP's configured transition style/duration to the View Transition snapshots. **Physical retest passed all configured styles and duration control**;
- component geometry measured during a surface commit can be temporarily zero/unstable. Custom controls such as Forecast scrollbars therefore need an explicit post-activation/settled-layout measurement hook rather than assuming first-frame geometry is authoritative.

These findings reinforce the Surface Host lifecycle model rather than arguing for a return to multi-document navigation.


#### A2 News migration — physically accepted

News validates that the Surface Host can own a more stateful content surface than Clock/Weather. The mounted News implementation pauses hidden refresh work, preserves story/category scroll state, defers custom-scrollbar geometry until the surface is settled, and retains article-detail/QR behaviour. Exact A2 candidate `b4e0943038779862816e65f1e291ae2b4ef2e571` passed Tests #5087 and the commissioned appliance physically accepted the News round-trip and transition behaviour.

#### A3 Settings migration — physically accepted

Settings is the first migrated surface where **transactional UI state must outlive navigation**. It therefore remains mount-once rather than being re-rendered on every visit:

- the read-only surface renderer supplies the same Settings template context as the ordinary GET route but never calls `set_mode()`;
- destination scripts load only after the Surface Host has committed Settings as the active surface, preserving existing `body[data-active-page="settings"]` initialisation guards;
- staged form values, active section/subpage and local Settings DOM state remain mounted across other ACP surfaces;
- background Settings diagnostics that previously relied on `pagehide` now also require Settings to be the active ACP surface before polling network endpoints, because hidden mounted surfaces no longer receive a document teardown;
- reactivation provides an explicit refresh opportunity for those diagnostics;
- AirPlay remains on the full-document fallback until Settings has passed its physical gate.

This is an important shell invariant: **surface-hidden is an application lifecycle state distinct from browser-hidden and document-unloaded**. Future ACP surfaces with timers, observers or background fetches must account for all three states explicitly.


The first A3 physical pass adds a second invariant: **persisted configuration and live-document configuration are separate responsibilities once document replacement is removed**. In the old route model, a successful save could rely on the next Flask-rendered document to repopulate root data attributes and page labels. A long-lived shell cannot rely on that implicit rebootstrap.

Therefore:

- a successful Settings transaction must project shell-owned values such as transition style/duration, startup/idle ownership, theme and clock format back into the live shell authority;
- the dashboard preference reader must prefer already-applied live values over immutable server boot attributes after initial bootstrap;
- surface-owned configuration changes must invalidate or refresh every affected mounted surface after persistence. Weather refreshes its detailed surface from the successful Settings event; Clock also refreshes its weather/status projection immediately and on Clock activation, so a save completing after navigation cannot leave either mounted Weather identity behind;
- server-rendered bootstrap controls that are retired by an enhancement (the old Settings Save/Discard bar) must have a first-paint-safe presentation rather than depending on late JavaScript to hide them.

This keeps autosave persistence authoritative without reintroducing full-document reloads as a hidden configuration-application mechanism.


A3 physical acceptance confirms these invariants on the commissioned Pi. The final Clock weather-title follow-up passed without document reload.

The migration also makes the former user-configurable **Dashboard observation refresh** cadence obsolete. Observation acquisition cadence belongs to the observation provider/service, while mounted ACP presentation refresh is shell lifecycle. Clock and Weather therefore use a fixed internal 60-second presentation refresh only while visible, plus immediate activation and relevant-settings refreshes. The retired `weather.auto_refresh_seconds` key is no longer exposed through Unified Settings or portable backup; old stored values are tolerated and ignored for upgrade compatibility.

#### A4 AirPlay migration — physically accepted

AirPlay is the first mounted surface whose presentation has several high-frequency clients while the underlying playback/session authorities remain useful even when the page is not visible. A4 therefore separates **AirPlay service authority** from **AirPlay presentation activity**.

`airplay-surface-lifecycle.js` is a presentation-only visibility authority. AirPlay is considered visible only when:

- `body[data-active-page="airplay"]` is authoritative;
- the browser document is visible;
- the persistent native Plexamp overlay is not visibly covering ACP.

It publishes only visibility changes, including Plexamp overlay class changes, so unrelated AirPlay body-class updates do not repeatedly reactivate clients.

The mounted AirPlay clients now follow that lifecycle:

- `airplay-live.js` suspends `/api/status` polling and progress/clock presentation ticks while hidden;
- coordinator transport and navigation clients suspend their 750 ms polling loops;
- receiver-volume polling and adaptive skip-mode polling suspend while hidden;
- the segmented mini-clock and outside-card compatibility synchroniser stop their timers while hidden;
- AirPlay layout and title-marquee measurement skip hidden geometry and explicitly remeasure on activation.

This does **not** move playback authority into the browser. Shairport/session state, playback coordinator commands, MPRIS observation, MixerController receiver volume and screen projection retain their existing owners. The shell only decides when the AirPlay DOM needs presentation work.


Commissioned-Pi acceptance confirms the complete AirPlay mounted-surface path, including manual and automatic entry, hidden-surface catch-up and return from the native Plexamp overlay.

A post-A4 Settings finding adds a small but important enhancement rule for the long-lived shell: **when upgrading a hydrated form control to a stricter HTML input type, install its constraints before changing the type and preserve the hydrated value explicitly**. Chromium's range-input sanitisation can otherwise apply default 0–100 bounds during the conversion itself. The Motion duration slider now sets its 0–2000 bounds/50 ms step first, then switches to `type=range`, restores the prior value and exposes a visible numeric output. This prevents presentation enhancement from mutating authoritative Settings data.


A second post-A4 finding generalises that rule from ranges to all Settings enhancements: **the server snapshot is authoritative; presentation widgets must be capable of representing that snapshot before they may participate in autosave**. The transition-style select previously gained several valid choices only after Javascript enhancement, so an early snapshot could assign a value the initial native select could not represent and lose it before enhancement.

The Settings boundary is therefore hardened as follows:

- accepted enum choices required for normal operation are present at first paint rather than relying on a later destructive option rebuild;
- if a backend-normalised saved value falls outside a preset dropdown's convenience choices, hydration adds a temporary current-value option instead of clearing the native select;
- programmatic hydration explicitly resynchronises custom-select and range presentation;
- dynamically inserted controls reuse the same hydration authority where practical;
- full-document Settings entry waits for the first authoritative Settings load (with a bounded fallback) before revealing the page;
- transactions clone the last authoritative snapshot and read values only from dirty UI sections/providers. Unrelated Settings controls therefore cannot overwrite authoritative values merely because they were temporarily stale or not yet enhanced.

This dirty-section rule is the defensive backstop for the entire Settings page: presentation hydration errors remain local rather than becoming cross-section configuration writes.


Commissioned-Pi retest confirms the hydration boundary: a formerly Javascript-only transition style and the transition-duration range both survive direct Settings hard reload while remaining authoritative for the live shell. The Settings hydration correction is accepted.


#### Phase A component/design-system boundary

With the ordinary ACP browser surfaces and Settings hydration contract accepted, presentation ownership now moves toward a reusable component/design-token layer. The first slice introduces semantic component tokens without changing feature geometry or service ownership. Shared panels/cards/buttons and the top-level Weather, News and AirPlay surface chrome consume the new vocabulary while the existing palette remains authoritative.

Detailed rules and migration inventory: [ACP component / design-token architecture](acp-design-system.md).

## ACP UI rendering decision

The native Plexamp investigation also exposes a separate ACP question: **should
Chromium continue to render the ACP product surfaces, or should those surfaces
eventually move into a native UI?**

The current transition implementation is not one uniform rendering model:

- ordinary ACP routes perform full document navigation and therefore have
  outgoing/incoming page boot choreography;
- Plexamp is a special persistent iframe/overlay with its own lifecycle;
- Settings behaves more like an in-document application with tabs/subpages;
- selected pages have hydration-aware reveal delays;
- screen projection, playback handoff and manual-surface leases can all influence
  when a transition is considered complete.

That mixture explains why the accepted transitions can still feel slightly less
immediate than a single continuously rendered appliance shell even after careful
optimisation.

### Decision options

Evaluate three architectures rather than framing this as a binary browser/native
choice:

1. **Current multi-document Chromium** — lowest migration cost, but retains the
   full-document navigation and mixed lifecycle boundaries that currently make
   transitions hardest to perfect.
2. **Single long-lived web surface inside an ACP shell** — keep Flask/HTML/CSS/JS
   and most current feature code, but migrate top-level ACP navigation toward one
   continuously loaded application surface. Page changes become in-process
   surface/state changes rather than browser document replacements.
3. **Native ACP surfaces** — implement some or all ACP pages in a native animated
   UI toolkit. If this path proves worthwhile, a declarative scene/state toolkit
   such as Qt/QML is a stronger fit than traditional widget-style UI because ACP
   relies heavily on touch, transforms, transitions and fixed 1280x720 appliance
   composition.

The preferred investigation order is **2 before 3**. The existing Flask APIs,
settings model, backup/reset ownership, themes, News, Weather, alarms and other
page logic are valuable working assets. Do not rewrite them merely to solve a
transition-ownership problem that may disappear once navigation stops causing
full document replacement.

A native shell may therefore own navigation and animation even if ACP content
continues to be web-rendered.

### Native rewrite threshold

A full or partial native rewrite is justified only if a prototype demonstrates
clear practical advantages over a single-document web surface in:

- transition smoothness and input latency;
- memory/GPU use on the commissioned Pi;
- touchscreen behaviour;
- visual consistency with the current ACP look;
- startup/recovery;
- implementation complexity;
- maintainability of Weather/News/Settings/Alarm-rich screens;
- testability and accessibility.

The existing look and feel is a product requirement regardless of rendering
technology.

## ACP design system and web framework boundary

The rendering investigation should preserve the long-standing separation between
content, layout and presentation rather than coupling page markup to a framework
theme.

Model ACP as four layers:

1. **content/data** — weather, news, alarms, settings values and playback state;
2. **reusable components** — setting row, status card, fader, forecast tile,
   segmented readout, navigation item and similar product primitives;
3. **design tokens/system** — colour roles, typography, spacing, radii, border
   treatment, elevation, touch targets and animation timings;
4. **application surfaces** — Clock, Weather, News, Settings, Astronomy and other
   top-level experiences.

Themes should primarily change design tokens. New feature markup should consume
reusable ACP components rather than inventing one-off card/field framing that
then needs a second styling pass.

### Material and third-party design systems

Do not adopt Material Web wholesale as the ACP visual identity. Material Design
is useful as a reference for token/component discipline, interaction states and
accessibility, but ACP has an established bespoke appearance and fixed appliance
geometry. The official Material Web Components project is currently in
maintenance mode, making it a poor new long-term foundation for the product.

If a component framework is introduced, evaluate it as an implementation aid,
not as the visual design authority. Prefer small primitives that can render ACP's
own design tokens and markup. Candidate approaches include native Web
Components/Lit-style custom elements and a compile-time component framework such
as Svelte; the prototype should justify any framework with lower complexity,
better reuse or smoother interaction rather than fashion.

### View-transition prototype

The single-document web candidate should explicitly prototype the browser View
Transition API for top-level ACP surface changes.

Preferred model:

```text
one ACP document
    |
    +-- Clock surface
    +-- Weather surface
    +-- News surface
    +-- Settings surface
    +-- Astronomy surface

state change -> document.startViewTransition(...) -> DOM surface swap
```

This removes the current full-document unload/boot/reveal boundary. The browser
captures the old view and new view for animation while ACP changes application
state inside one document.

Keep the ACP desktop shell as the transition authority only where navigation
crosses a process/workspace boundary (for example ACP <-> native Plexamp).
Within the ACP web surface, browser-native view transitions should be preferred
over a second competing top-level animation engine.

### Carousel interaction versus page transitions

Treat the spatial row/carousel as a **navigation-mode presentation**, not another
independent transition system.

When the user swipes up:

1. the shell enters navigation mode and the active surface recedes;
2. the horizontal surface row/carousel becomes the selection metaphor;
3. tapping a destination establishes the target/direction;
4. navigation mode exits;
5. exactly one destination transition commits.

For ACP-to-ACP changes, the destination commit should normally be a
same-document View Transition. For ACP-to-native-Plexamp changes, the desktop
shell performs the workspace/application transition.

Existing transition styles may survive as **destination reveal styles** (fade,
slide, cover, etc.), but they must be coordinated by one state machine rather
than running in parallel with the carousel. If the carousel provides the whole
spatial movement, the destination reveal should be deliberately restrained.

### Level-B B0 bounded spatial commit

The first carousel experiment intentionally implements **one relation only: Clock → Weather from open navigation**. Clock and Weather are already the oldest physically accepted mounted-surface pair, so they isolate spatial presentation from surface-lifecycle risk.

B0 does not build a second transition engine. Navigation policy marks that one selection with `spatialCommitDirection: "forward"` after manual-screen ownership has accepted Weather. The shell then exits navigation and waits for the configured Navigation transition duration. Once the Level-A sheet has returned to its closed state, the existing Surface Host performs its normal single `document.startViewTransition(commit)`.

For that one View Transition, the host temporarily exposes `data-acp-spatial-commit="forward"` on the document root. The first visual candidate used `±34vw`, 0.94 scale and opacity depth cues. Physical testing rejected that composition: because the snapshots no longer tiled the viewport, the incoming Weather edge exposed the white root background and the outgoing Clock read as a faded backing layer, producing an **overlay** metaphor rather than a row.

B0 v2 therefore uses an edge-lock invariant instead of depth effects:

- old Clock: `translateX(0) → translateX(-100vw)`, full scale/full opacity;
- new Weather: `translateX(100vw) → translateX(0)`, full scale/full opacity;
- duration: existing application `transition_duration_ms`;
- easing: the same ACP destination-transition cubic-bezier for both snapshots.

Because the two snapshots move equal distances with identical timing, the old snapshot's right edge and the new snapshot's left edge are coincident at every animation fraction. Physical testing confirms that geometric invariant when both root snapshots are valid.

The second B0 physical pass exposed a separate boundary: **snapshot readiness after navigation-sheet motion**. A nominal timeout equal to the navigation CSS duration is insufficient evidence that Chromium has painted the live surface's post-transform texture. On the Raspberry Pi the View Transition could occasionally capture the outgoing Clock root as blank/white even though Weather then followed the correct edge-locked trajectory. The architecture must therefore wait on a rendered-state signal rather than elapsed wall-clock time.

For B0 v3, the navigation policy attached to `main.screen` before closing the Level-A sheet and waited for the real `translate` `transitionend`/`transitioncancel` event, followed by two animation frames and a layout read. Repeated physical testing rejected that approach: 19 of 20 old-root captures were still white. The architecture therefore treats this as an unreliable **browser snapshot primitive** for the Pi spatial case rather than as a scheduling bug.

B0 v4 deliberately changes only the spatial presentation primitive. The mounted-surface model already keeps the outgoing ACP DOM alive, so the experiment can use that real DOM instead of asking Chromium to photograph the root:

- clone the current `main.screen` while Clock is still the visible mounted surface;
- make the clone non-interactive and copy the body background onto it;
- position the real live `main.screen` at `+100vw`;
- commit Weather into the real screen;
- use Web Animations to move the Clock clone to `-100vw` and Weather to `0` with identical timing;
- remove the clone and inline transform in a `finally` cleanup.

The Surface Host supports this through an optional `prepared.spatialCommit` lifecycle hook. The hook receives the normal `commit` callback, so logical surface ownership, body mode, navigation state, history, activation and settled events remain centralized in the existing host. Ordinary daytime ACP transitions may still use the View Transition API, but the host is now free to choose a surface-only live compositor when shell chrome must remain genuinely live rather than becoming a browser snapshot.

This live-DOM strip has two architectural advantages beyond avoiding the blank texture: it uses the same mounted-surface objects the future carousel would actually own, and shell chrome such as the home indicator remains a real fixed shell layer rather than becoming part of a frozen root image. Commissioned-Pi testing accepts this mechanism across repeated runs and theme changes.

### Transition-style ownership for spatial navigation

A spatial compositor must not silently replace the user's chosen application Transition style. The B0 hard override was a test harness, not an acceptable production policy.

The Motion setting is therefore the policy selector, while individual styles are free to use different rendering backends:

- Grow/fade, Crossfade, Horizontal slide, Vertical lift, Cover reveal, Zoom and Blur dissolve keep their existing visual semantics; by day they may use Chromium View Transitions, while astronomy-night mounted ACP transitions use a surface-only live-DOM/Web Animations compositor so persistent shell chrome and the night treatment remain real DOM above the moving content;
- Instant continues to suppress decorative application movement;
- **Spatial row** uses the live-DOM mounted-surface strip where that relation has been implemented.

This keeps the user-facing model simple: **one Transition style setting, one Transition duration setting**. The implementation technology is an internal concern. Selecting Cover reveal must mean Cover reveal even when the destination was chosen from shell navigation; selecting Spatial row explicitly opts into spatial navigation semantics.

The astronomy-night exception is deliberate shell ownership, not a second user-visible transition mode. Commissioned-Pi testing showed that Chromium's named persistent-navigation View Transition snapshot is painted above the live astronomy multiply overlay and repeatedly exposes captured daytime pixels. Recolouring that frozen snapshot proved unreliable and one overlay-as-snapshot experiment produced full-screen red frames. The architectural direction is therefore to avoid creating the snapshot at all: clone only the outgoing ACP `main.screen`, commit the mounted destination beneath it, animate outgoing/incoming screen layers with the selected style, and leave navigation/backdrop/handle/night overlay live. Settings inherits the same fallback when Spatial row is selected because Settings is a utility surface rather than a row member.

**Physical acceptance:** the commissioned Pi passes this model across the ordinary transition styles and the Settings fallback under Spatial row. The navigation remains in astronomy-night presentation for the full transition while only application content moves underneath it, and repeated stress testing no longer produces the earlier white, solid-red or travelling-rectangle artefacts. The zero-margin 40 px/s night-clock cluster is also accepted. This closes B7 and Phase A, allowing #94 to move into **Phase B native Linux Plexamp**; Astronomy remains queued until that migration is physically accepted.

B0 proved Clock→Weather physically. B1 introduces the first actual ordered row with two members: `['clock', 'weather']`. Navigation derives forward/reverse direction from the current and target indices, and the application-surface compositor validates the same relation independently before animating. Both directions therefore use one direction-neutral live-DOM primitive rather than separate page-specific effects. Destinations outside the currently implemented row continue to map to Horizontal slide while Spatial row is selected; that fallback remains temporary and must disappear as the ordered model expands.

Direction is part of the Surface Host presentation contract and must survive intact from navigation policy to the prepared surface hook. B1 physical testing exposed an old B0 assumption in the host that normalised only `forward` and converted every other value to empty. That silently routed a valid reverse relation into the ordinary View Transition fallback, whose Horizontal-slide keyframes include opacity fading and only a few viewport-percent of movement. The host now explicitly accepts `forward` **or** `reverse`; unknown values alone are rejected. This keeps fallback behaviour for genuinely unsupported relations without masking a supported reverse direction.

The live-DOM compositor must also preserve **per-surface layout context** across the handoff. The Surface Host changes global body mode/data-active-page as part of committing the destination; destination CSS may legitimately style `main.screen` itself. For example, Weather changes the screen grid from `minmax(0, 1fr) auto auto` to `auto minmax(0, 1fr) auto`. If the outgoing clone remains dependent on global body selectors, it can relayout into destination geometry before leaving the viewport.

For B0 the compositor therefore snapshots the outgoing screen's computed **layout properties, not its pixels**: grid templates/auto tracks, alignment, gaps and padding are copied inline onto the temporary outgoing DOM layer before the destination commit. The old surface keeps its old geometry while the incoming real screen immediately adopts the destination mode.

B1 adds the complementary **presentation-context** rule. A live outgoing DOM surface cannot depend exclusively on selectors keyed to the document's single global `body[data-active-page]` value, because the destination commit legitimately changes that value before the outgoing surface has left the viewport. The compositor marks the temporary layer with `data-acp-surface-context="<outgoing-surface>"`. Surface-specific CSS that must remain visually authoritative during handoff can target either the live body state or this local outgoing context. Weather's theme component rules and forecast-console active-page rules are the first consumers. Commissioned-Pi testing confirms this contract under Crimson Glow and Green Phosphor: Weather's forecast rails retain the selected palette throughout reverse Weather→Clock instead of reverting to the Classic cyan baseline.

This is preferable to copying computed colours onto every descendant: theme variables remain live, semantic states remain semantic, and the DOM surface still responds as a coherent surface. The architecture rule for any future multi-surface carousel is therefore two-part: **surface-local layout context plus surface-local presentation context**; global body mode remains the logical destination authority, not the sole styling authority for every simultaneously visible surface.

This policy also clarifies automatic projection: the destination mechanism should obey the selected application Transition style unless a product-critical event (for example alarm takeover) explicitly bypasses decorative animation.

The attribute is presentation-only and is removed after the transition, with a `finally` cleanup if the transition path fails. It does not alter logical surface order, history, leases, Weather lifecycle or persisted settings.

B0's asymmetric Clock→Weather test boundary is closed, and B1's commissioned-Pi acceptance confirms the same live-DOM primitive is coherent in both directions. The ordered-row model can therefore expand one adjacent member at a time.

B2 extends the order to `['clock', 'weather', 'news']`. The direction function remains index-based and the spatial compositor remains **adjacent-only**: an absolute index delta of one receives the live-DOM strip; larger jumps continue through the ordinary Spatial-row fallback. This deliberately separates two architectural questions—whether a third mounted surface can participate safely, and how non-adjacent jumps should eventually look—rather than solving both at once.

For B2 the valid spatial edges were Clock↔Weather and Weather↔News; commissioned-Pi testing accepted that three-member adjacent model.

The first B3 implementation tried a distance-independent one-viewport jump for all row members. It was mechanically simple and passed CI, but product review rejected the metaphor before physical acceptance: a mode called **Spatial row** should actually expose the intermediate neighbour on a non-adjacent jump.

B3 v2 therefore separates **visual row traversal** from **logical application activation**. Row indices determine both direction and visual distance. A Clock→News jump across two indices constructs a temporary three-layer strip at 0/+100/+200vw (mirrored for reverse) and moves the entire strip by 200vw in one animation. Weather visibly crosses the viewport, but the Surface Host still performs only one logical commit—to News. No intermediate history entry, mode sync, activation event or settled event is published for Weather.

The application Transition duration remains the duration of the complete movement regardless of row distance. This is intentionally different from chaining two ordinary transitions: chaining would double the configured duration and introduce a stop/easing restart at the intermediate page. The single strip preserves one continuous gesture and one destination lifecycle.

Intermediate layers are DOM surfaces, not screenshots. The compositor temporarily renders the already-mounted intermediate under its own presentation body state, captures its DOM plus computed root layout/background, stamps its local surface context, and restores the real source synchronously before paint. This extends the established rule that simultaneously visible surfaces carry their own layout and presentation identity even while global body state belongs to the selected destination.

Commissioned-Pi testing accepts the staged three-surface model, including 200vw Clock↔News traversal within one configured total duration and no intermediate logical activation. B4 extends the ACP row to `['clock', 'weather', 'news', 'airplay']`. The row intentionally contains ACP browser application surfaces only: Plexamp remains a separate compositor/workspace boundary and Audio remains a shell overlay. AirPlay's active-page-scoped non-Classic pulse/screen paint also consumes the outgoing `data-acp-surface-context="airplay"` contract so it can remain visually AirPlay after the live body has committed another ACP destination.

## Browser-engine evaluation

Changing browser should be treated as a measured optimisation experiment, not a
design migration.

Raspberry Pi OS supports Chromium and Firefox as first-class browser choices.
Compare the same single-document ACP prototype under Raspberry Pi OS Chromium
and Firefox for:

- animation frame pacing/jank;
- touch input latency;
- memory and GPU usage;
- startup time;
- View Transition behaviour;
- fullscreen/kiosk and Wayland integration;
- on-screen keyboard behaviour;
- remote-debug/recovery tooling.

Chromium remains the baseline because it is the Raspberry Pi OS-default path
already qualified by ACP. Firefox is the useful comparison because it is a
genuinely different rendering engine. Switching away from Chromium must justify
the cost of requalifying the existing kiosk, autoplay, iframe, touch and recovery
assumptions.

The likely optimisation order is therefore:

1. single-document ACP surface;
2. ACP component/design-system cleanup;
3. View Transition API;
4. measure Chromium;
5. compare Firefox only if performance or interaction still leaves a material gap.

## Display ownership

### Preferred first experiment: two compositor workspaces

Rather than stacking two fullscreen applications on one desktop, test:

- workspace 1: Chromium A Clockwork Plex dashboard;
- workspace 2: native Plexamp;
- deterministic ACP-owned switching between them;
- window rules that keep each application on its intended workspace;
- alarm takeover allowed to force the ACP workspace immediately.

The appliance must first verify its actual compositor/session at runtime rather
than assume labwc merely because it is the current Raspberry Pi OS default.

### Transitions

The current ACP screen changes feel deliberately polished and should not regress
to an abrupt desktop flash merely because Plexamp becomes native.

Top-level transition ownership should move into the ACP desktop shell so the same
visual grammar can cover:

- ACP web-surface to ACP web-surface navigation;
- ACP to native Plexamp workspace changes;
- native Plexamp back to ACP;
- alarm-forced presentation.

Content applications should provide readiness/state signals, not each implement
their own incompatible top-level transition choreography.

Preferred investigation:

1. ACP requests a screen/application transition.
2. A small ACP-owned Wayland overlay covers the output.
3. The overlay performs a short fade/slide.
4. The compositor switches workspace underneath.
5. The overlay reveals the destination.

This keeps animation policy under ACP while leaving the supported compositor
responsible for actual window/workspace ownership.

Compiz-style cube/exposé experiments are welcome as a development curiosity, but
must not become a reason to replace the supported compositor unless an
alternative proves equally reliable for boot, VNC, touch, alarms and recovery.

Alarm takeover is safety/product behaviour and may bypass decorative animation
if necessary.

## ACP desktop shell candidate

A small, independently restartable **ACP desktop shell** is worth prototyping as
the shared owner of UI that must appear above both Chromium and native Plexamp.

Possible responsibilities:

- bottom home-indicator affordance plus swipe-up navigation surface;
- cross-application navigation state;
- transition overlay and optional snapshot-based spatial effects;
- deterministic ACP/Plexamp workspace switching;
- optional system-level on-screen keyboard surface.

Explicit non-responsibilities:

- no audio routing;
- no playback arbitration;
- no NFC media interpretation;
- no alarm scheduling;
- no persistent settings authority beyond its own presentation preferences.

The shell should fail open: if it crashes, Chromium/Plexamp audio must continue,
and there must remain an SSH/VNC recovery path.

## Navigation shell and bottom-edge gesture

The preferred end-state is **not** a permanently visible navigation pill.

Use a small iPhone-style horizontal home indicator at the bottom edge to make the
gesture discoverable without permanently occupying useful content space.

Preferred interaction:

1. content is full screen with only the small bottom indicator visible;
2. swipe upward from the bottom edge;
3. the ACP desktop shell reveals the navigation surface;
4. the current content visually recedes enough to establish that navigation is a
   separate system layer;
5. the user chooses another ACP surface or native Plexamp;
6. the shell performs the selected transition;
7. navigation slides away and the destination returns to full-screen scale.

### Navigation presentation experiments

Test two levels of ambition.

**Level A — production-first overlay**

- current app remains live beneath the shell;
- shell dims/slightly masks the content and slides navigation in from the bottom;
- target selection triggers the transition/workspace switch;
- no compositor modification and no live-window scaling requirement.

**Level B — spatial surface strip / carousel**

Investigate the proposed model where ACP surfaces conceptually form a horizontal
row. When navigation opens, the active surface appears to shrink/recede and the
shell can slide toward the selected destination before committing the real page
or workspace switch.

Do not require the compositor to provide arbitrary live-window scaling. If a
convincing spatial transition needs a frozen screenshot/texture of the current
surface, treat that as an optional presentation technique and measure latency,
GPU cost and failure behaviour. The actual application/workspace remains the
authority underneath.

A true live Compiz-style window strip would require compositor-level transforms
that labwc intentionally does not provide as a product API; do not make a custom
compositor a prerequisite for ACP navigation.

#### Accepted topology refinement after Level-B B4

Physical acceptance of the four-surface browser strip changes the abstraction boundary. The spatial order is no longer defined as “all mounted ACP pages”; it becomes a **shell-owned workspace topology**.

Current target topology:

```text
Home  <---->  Weather  <---->  News  <---->  AirPlay  <---->  Plexamp
```

Future topology once Astronomy is implemented:

```text
Home  <---->  Weather  <---->  Astronomy  <---->  News  <---->  AirPlay  <---->  Plexamp
```

Renderer ownership is intentionally heterogeneous:

- Home, Weather, Astronomy, News and AirPlay are ACP/Chromium application surfaces;
- Plexamp is the terminal media workspace, represented by the persistent browser player during migration and by the native Wayland application later;
- Settings is a mounted ACP utility workspace but **not** part of the spatial row;
- Audio is a shell overlay and **not** a workspace position.

The user-facing first workspace is **Home**. Its established internal surface/state identifier remains `clock` and its route remains `/clock`; this is a presentation rename, not a migration of persisted configuration or API identifiers.

The shell therefore owns ordering, direction and navigation semantics above `ACPSurfaceHost`. Browser-only staged-strip mechanics may remain an implementation detail for ACP↔ACP travel, while Plexamp uses an endpoint adapter appropriate to its current renderer. Native Plexamp migration must preserve the same terminal index rather than inventing a new navigation order.

This separation is useful because native migration can replace only the Plexamp renderer/transition backend while leaving user muscle memory, left/right meaning and long-jump topology unchanged.

B6 proves that renderer independence in two stages. The adjacent AirPlay↔Plexamp boundary uses the live ACP screen plus the real persistent Plexamp layer. Long jumps then compose a literal strip from **presentation-only ACP clones plus the real endpoint renderer**. For example, Home→Plexamp stages Home/Weather/News/AirPlay at successive 100vw positions and places the persistent Plexamp layer in the terminal slot; Plexamp→Home mirrors the same topology with Plexamp live at the source, AirPlay/News/Weather as staged intermediates and live Home as the committed destination.

Intermediate ACP captures never become logical navigation destinations. Script-owned AirPlay state is refreshed while its wrapper remains hidden, then the wrapper is exposed only synchronously for body-mode/layout calibration and cloning before being restored. This preserves accurate ready/now-playing geometry without a pre-transition flash or a false mode claim. The same shell topology contract can later substitute native Wayland Plexamp for the persistent browser layer: only the terminal renderer adapter changes.

Navigation presentation follows the same semantic split. Ordinary workspace destinations remain the primary row. Audio and Settings form a separated right-edge utility cluster using scalable inline SVG controls: a speaker-with-waves icon for appliance audio and a cog for Settings. Icon controls retain full touch targets, `currentColor` theme ownership and accessible names.

### Cross-application ownership

The bottom indicator and revealed navigation must be visible over both Chromium
ACP and native Plexamp. Therefore they belong to the ACP desktop shell rather
than either content application.

During an incremental migration the browser's current HTML pill may remain as a
fallback, but the target design is one cross-application shell affordance rather
than two separate navigation implementations.


The first browser-shell ownership slice removes one historical ambiguity. `_nav.html` is now rendered once by `base.html`, outside `main.screen`, rather than being included by every page and moved into `<body>` by `nav-layer.js`. Mounted application surfaces therefore contain application content only; primary navigation is persistent shell chrome. The relocation shim is removed.

This slice deliberately retains the accepted handle/drawer interaction so structural ownership can be physically accepted independently from the later home-indicator/navigation-mode presentation.

Physical testing of that ownership slice exposed a second requirement: persistent shell DOM needs persistent **behavioural** ownership too. A shell control must not depend on a listener bound once to a particular element instance if later application-surface work can leave that instance stale. The navigation handle therefore uses delegated document-level tap/touch handling and resolves the current shell node on demand. The shell Audio button is static markup, while its dynamic mixer/EQ internals are idempotently reasserted after `acp:surface-settled`.

The shell also one-instance guards `nav-drawer.js`; this prevents duplicate long-lived listeners from turning one tap into multiple open/close toggles. Asset versioning is part of the boundary because a persistent shell cannot safely mix a newly rendered template with a stale cached behaviour owner.


Commissioned-Pi retest accepts that lifecycle contract. One cross-application input boundary remains important: pointer/touch events originating inside the persistent Plexamp iframe do not bubble into the ACP document. The shell must therefore own a real hit target above the iframe for any bottom-edge gesture it expects to work while Plexamp is visible.

The first home-indicator pass confirmed the cross-iframe approach, but physical testing showed 300×30 px was still large enough to intercept the inner edges of Plexamp Library/Search taps. The accepted design rule is therefore stricter: the ACP-owned region should be only modestly wider than the visible indicator and as shallow as reliable touch acquisition allows. The refined candidate uses roughly 180–200×22 px around a roughly 140 px visible bar. Swipe-up opens, swipe-down closes, and tap remains a fallback.

AirPlay also needs an explicit first-paint state in the long-lived shell. A newly mounted AirPlay surface is now staged as `airplay-session-unresolved` before it becomes visible. That state deliberately shares route-ready geometry and hides transport controls until the authoritative status response changes the body to idle or active. Direct AirPlay document loads receive the same unresolved class from the server template. This prevents asynchronous state resolution from visibly reflowing a false generic-player first frame.

### Gesture gate

Physically test:

- collision with Plexamp's Home/Library/Search/Settings bar near the bottom edge;
- ordinary vertical scrolling;
- touch starts within the narrow home-indicator target;
- slow/short swipes versus intentional navigation swipes;
- accidental activation during visualiser interaction;
- alarms and forced screen changes;
- screen dim/night behaviour;
- VNC as a development convenience, without making perfect VNC gesture fidelity
  a production requirement.

A tap on the home indicator may optionally reveal navigation as an accessibility
fallback.


### Production-first navigation mode

The refined home-indicator/cross-iframe gesture contract is physically accepted. Before attempting the Level-B spatial carousel, the shell now implements the Level-A treatment described above:

- the active application remains live;
- a shell backdrop sits above content but below navigation;
- opening navigation slightly recedes the active ACP surface or Plexamp layer using individual CSS `scale` and `translate` properties;
- the backdrop dims the content and owns outside-tap dismissal;
- drawer buttons and destination switching remain unchanged.

Using individual transform properties is deliberate. ACP page transitions and the persistent Plexamp handoff already use the `transform` property; navigation mode must compose with those systems rather than replace their animation value. Plexamp's transition list therefore explicitly includes `scale`, `translate` and `border-radius` so the recede animates consistently.

This Level-A treatment is the production fallback even if the later spatial-carousel experiment proves too expensive or visually fragile on the Pi.


Physical acceptance also establishes that **navigation mode is shell state, not application state**. An explicit destination change made while navigation is open should keep that shell state regardless of whether the destination is another mounted ACP surface or persistent Plexamp. Plexamp presentation APIs therefore accept a `preserveNavigation` hint for explicit shell navigation. Automatic projection changes intentionally do not use it.

The remaining Plexamp→different-ACP full-document fallback transfers only that presentation state through a short-lived pathname-scoped `sessionStorage` token. The incoming nav owner consumes it before the booting document is revealed, preserving the Level-A visual contract without making navigation persistence a server concern.

The `0.84 / -28px` follow-up physically proves the required clearance: the live application's bottom edge can sit above ordinary navigation while shell state survives the Plexamp boundary. It also shows that an app-card scale is not necessary for the production treatment. At 1280×720, shrinking the whole application to 84% costs useful legibility and makes cross-document restore more visibly expose the moment when recede geometry is applied.

The full-scale experiment confirms `scale: 1` is the better production model. Fixed translations are not robust enough, however: `-90px` over-corrects and creates a large void, while `-28px` under-corrects and lets the drawer cover live content. The production geometry therefore derives the reveal distance from the ordinary drawer itself. `nav-drawer.js` measures the main navigation row plus the drawer's vertical padding, borders and bottom inset, publishes that as `--acp-navigation-reveal-height`, and ACP/Plexamp translate upward by exactly that value. Commissioned-Pi testing accepts this measured live-surface distance. The home indicator is part of the same physical assembly and must therefore use the **same** variable, duration and easing; historical fixed `64px/56px` handle offsets are not an independent geometry authority.

Navigation motion owns an independent timing authority. Application-surface changes continue to use `transition_duration_ms` and the selected transition style. Opening/closing ordinary navigation uses `navigation_transition_duration_ms` (default 180 ms) through `--acp-navigation-transition-duration` for the drawer, indicator and backdrop, plus ACP/Plexamp lift/rounding only when **Lift content** is selected. This avoids a long page-transition preference making a small shell gesture sluggish.

The commissioned-Pi slow-motion test tightens "synchronised" into a geometry invariant rather than merely a shared duration: the **live surface bottom edge, home indicator and drawer top edge form one moving sheet**. If the measured reveal height is `H`, the live surface and indicator move `0 → -H` while the drawer moves `+H → 0`, using the same easing curve. At every intermediate animation fraction their adjoining edges therefore remain coincident. A drawer-specific `calc(100% + 18px)` path or generic `ease` violates that invariant even if the endpoints happen to look correct. The drawer also has no independent opacity choreography: it is visible throughout the sheet movement and becomes hidden only after the closed position is reached, preventing a separate fade from creating a perceptual lag despite correct geometry. The final commissioned-Pi retest passes this invariant in both directions at 1000 ms and at normal timing; this Level-A motion contract is physically accepted and remains the contract for the optional **Lift content** presentation.

#### B5 persistent-shell presentation refinement

B5 product review changes the **default** presentation without invalidating the accepted Lift geometry.

Navigation is persistent shell chrome and must not visually become part of the application transition beneath it:

- **Overlay content** is the default. Opening navigation moves the drawer/indicator/backdrop only; the current ACP/Plexamp workspace remains at its ordinary full-screen position.
- **Lift content** retains the accepted measured-sheet treatment above as an alternate Display → Motion setting.
- ordinary same-document View Transitions isolate the backdrop, drawer and home indicator into named non-animated View Transition layers above the root old/new snapshots, so Cover reveal/crossfade/etc. run behind the shell;
- the live-DOM Spatial-row compositor likewise remains below shell z-order and no longer closes/waits for navigation before beginning a selected workspace movement;
- `navigation_transition_duration_ms` still owns shell reveal/hide speed independently of application `transition_duration_ms`;
- `navigation_inactivity_seconds` owns how long an open navigation shell remains after the last shell interaction, from 0–30 seconds; `0` means never auto-hide;
- while the Audio mixer is open, inactivity auto-hide is suspended. Closing Audio resumes the configured timeout;
- shell controls share a larger touch height, workspace destinations use the standard rounded-control radius, Audio/Settings remain circular icon utilities, and the drawer uses the standard ACP card radius rather than a pill end-cap.

This separation makes the compositing model clearer: **workspace renderer below, persistent shell above**. It also removes the old latency coupling where Spatial navigation had to wait for the shell to close before the application movement could begin.

Audio is a deliberate exception because it is a **content overlay opened from navigation**, not an enlargement of navigation itself. The ordinary bottom nav therefore stays at its normal measured position. The mixer is a fixed shell overlay between the backdrop and nav, laid over the current application surface, and its reveal/hide uses `--acp-transition-duration` so it follows the user's ordinary application Transition duration. The older `audio-polish.js` animation owner is retired; one component should not have fixed 225/300/320 ms timings fighting the configured motion authority.

### Current-route navigation is a shell no-op

A main-nav tap on the already-active mounted ACP surface is not a navigation request and must never fall through to browser default link behaviour. The persistent shell owns the interaction: consume the event, leave the active surface untouched and preserve the current navigation-mode state. This is distinct from Plexamp, whose visible presentation can legitimately differ from the underlying ACP route, and from Audio, which is a shell overlay button rather than a route.

The former `target.href === window.location.href` early return was unsafe because it returned **before** `preventDefault()`; Chromium then performed a normal same-URL document load, producing a black boot flash and discarding the open drawer. Current-route detection now compares the target pathname with the Surface Host's `activeRoute()` and explicitly consumes the tap while Plexamp is not visibly open. Commissioned-Pi testing passes this contract across all mounted ACP destinations: no transition, no hard reload and navigation remains open.

### Pre-snapshot hydration for script-owned surfaces

Same-document View Transitions introduce another lifecycle boundary beyond `activated` and `settled`: Chromium captures the **incoming snapshot immediately after the update callback**. If a destination's final geometry is produced by target-specific JavaScript, activating those scripts only after `updateCallbackDone` is too late—the transition can freeze an unhydrated target and then visibly reflow when the live DOM catches up.

The Surface Host therefore supports an optional async `beforeSnapshot` hook. The update callback commits the destination DOM/body state, then awaits `beforeSnapshot` before Chromium captures the new snapshot. This hook is intentionally opt-in rather than a new global delay.

AirPlay is the first user of the boundary. On each AirPlay entry the application-surface owner resets the body to `airplay-session-unresolved`, ensures the AirPlay scripts are loaded, publishes activation, and awaits `ACPAirPlayHydration.waitForReady()`. The reusable hydration authority waits for resolved idle/active/metadata state plus two animation frames before signalling readiness. This ensures the segmented mini-clock, weather glance and status-dependent hero geometry are already stable in the **incoming snapshot**. The configured transition itself is unchanged: for example, Cover reveal still legitimately shows the old page on the unrevealed side while it runs.

## Touchscreen keyboard

The existing ACP Search keyboard is browser/DOM-owned and therefore cannot type
into a separate native Plexamp window.

Native migration is blocked until Plexamp Search and other ordinary text fields
are usable from the touchscreen.

Investigation order:

1. test the current Raspberry Pi OS Wayland on-screen keyboard over native
   fullscreen/maximised Plexamp;
2. test the same keyboard over Chromium kiosk to document the current layering
   difference;
3. if the distribution keyboard is unreliable, prototype an ACP-owned overlay
   keyboard using an appropriate Wayland input / virtual-keyboard mechanism;
4. keep password/login/claim entry outside any broad ACP key-injection bridge
   unless separately reviewed;
5. verify focus, Shift/backspace, dismissal, repeated searches and return to ACP.

If an ACP desktop shell is created, the navigation overlay and keyboard may share
that process, but the keyboard remains presentation/input plumbing rather than
playback authority.

## NFC / Companion compatibility

Current NFC tags contain Plex playMedia URLs which the listener rewrites to the
local Plexamp Companion receiver. Discovery must establish whether native Linux
Plexamp exposes compatible local receiver endpoints for:

- `/player/playback/playMedia`;
- timeline/status polling used by ACP;
- queue/activity semantics used to detect a fresh NFC launch.

Prefer adapting the endpoint/configuration around the existing tag format rather
than rewriting the physical NFC library.

## Audio acceptance

Native Plexamp must be able to feed the existing ACP-owned audio boundary.

Preferred route:

```text
native Plexamp -> ALSA acp_plexamp -> accepted fixed-192 managed graph
```

Physical gates include:

- native app sees/selects `acp_plexamp` or an equivalent controlled host ALSA
  endpoint;
- no competing Plexamp EQ/volume authority is silently introduced;
- Plexamp trim, Music Master and ACP EQ remain effective;
- fixed-192 processing/DAC diagnostics remain truthful;
- Direct failback/recovery remains valid;
- AirPlay and alarm takeover behaviour remains accepted.

## Runtime and resilience boundary

#94 begins **after #85 and before Astronomy**. Its Phase A application-shell /
single-document foundation is accepted before Astronomy starts, so Astronomy is
not knowingly built in the legacy multi-document model and then migrated.

Phase A establishes the application-shell contract first. Phase B then completes
the native Linux Plexamp migration on that accepted shell. **Astronomy begins
only after the native-player migration is physically accepted**, so #94 remains
one coherent modernisation track rather than being split around a new product
surface. Full Appliance Resilience follows the modernisation/Astronomy work so
it hardens the architecture that actually survives #94 rather than fully
hardening components that may be retired.

However, #94 itself must still prove minimum resilience before migration:

- reversible install/uninstall;
- Headless rollback retained;
- clean reboot/autostart;
- Plexamp crash and restart;
- Chromium crash and restart;
- desktop-shell crash and restart if introduced;
- alarm behaviour during/after player failure;
- VNC/SSH recovery;
- no boot loop if native Plexamp cannot start.

## Remote support

The commissioned appliance is routinely inspected over VNC/SSH. Any workspace,
overlay, native Plexamp or keyboard design must remain visible and operable both
on the physical touchscreen and through the supported remote-access path.

A design that works locally but leaves VNC blind to the foreground Plexamp or ACP
overlay is not acceptable.

## Backup / reset ownership

Do not assume the current browser bridges or Headless storage map directly onto
the rewritten native app.

Classify before migration:

- login/claim identity;
- player identity/name;
- native Plexamp preferences;
- Home customisation;
- visualiser preference;
- selected ACP audio device;
- portable vs machine-local state;
- Reset behaviour;
- Backup/Restore behaviour.

## Acceptance boundary

Headless may be retired only after the native candidate passes:

- visualiser/GPU load;
- ALSA/ACP audio path;
- NFC;
- Companion/timeline observation;
- touchscreen keyboard;
- Chromium/Plexamp workspace switching;
- navigation/edge return path;
- transition presentation;
- alarms;
- AirPlay handoff;
- Direct failback/recovery;
- backup/reset ownership;
- reboot/autostart;
- crash/recovery;
- longer ordinary-use stability.

### Settled-layout lifecycle

The first Forecast control regression exposed an important distinction between **activated** and **settled** surfaces. A mounted surface can be logically active while the compositor is still animating old/new View Transition snapshots, and a hidden mounted surface can legitimately report zero-width geometry to ResizeObserver.

The Surface Host therefore exposes two different lifecycle moments:

- `acp:surface-activated` — logical destination is committed and may begin normal application work;
- `acp:surface-settled` — emitted only after the browser View Transition's `finished` promise resolves, suitable for geometry-dependent controls.

Geometry-dependent components must not interpret zero-width measurements from a hidden mounted surface as authoritative state. Forecast custom scrollbars now preserve their previous visibility while hidden and remeasure on the settled event.

### Clock ↔ Weather A1 accepted

Physical retest closes the first same-document migration gate:

- configured transition style and duration are authoritative;
- geometry-dependent Forecast controls survive repeated hide/show cycles using the settled-layout lifecycle;
- Clock and Weather remain healthy across repeated round-trips;
- News and Settings continue to use the fail-safe full-route fallback.

This establishes the Surface Host contract as suitable for incremental migration of additional ACP-owned application surfaces.

### A2 — News joins the application-surface set

After Clock ↔ Weather A1 acceptance, the pair-specific loader is replaced by the generic `acp-application-surfaces.js` owner. The first registered set is now Clock, Weather and News.

News keeps its existing local `/api/news` ownership and rendered UI logic. The mounted-surface adaptation is lifecycle-only:

- hidden News does not continue useful 60-second refresh work;
- reactivation fetches one fresh local News snapshot;
- story/category scroll positions are preserved across routine snapshot renders;
- story and category custom scrollbars follow the same hidden-geometry / `surface-settled` rule established by Weather;
- the article-detail / QR modal remains part of the mounted News surface;
- Settings and AirPlay remain outside the registered set during A2 to preserve a known full-route escape/fallback path.

This is intentionally an incremental migration, not a News redesign.
