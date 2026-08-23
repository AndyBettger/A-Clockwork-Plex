# Plexamp 4.12.4 restart investigation

The bedroom appliance previously ran Plexamp Headless 4.12.4 on Debian 13. During the stage-seven CamillaDSP rehearsal and subsequent direct-mixer reproductions, restarting `plexamp.service` could leave Plexamp logically playing with a valid timeline while no audio was heard. Manually changing or reconnecting the output revived playback.

## Observed states

- AirPlay and the direct ALSA mixer remained healthy.
- Plexamp's HTTP interface and music timeline returned.
- The timeline could report `playing` with a valid queue and advancing position while output remained silent.
- The problem was triggered by restarting Plexamp, not by changing dashboard mode.
- A temporary `ctl.acp_*` alias experiment removed the `Invalid CTL acp_plexamp` log line but did not restore playback.
- Repeating that alias experiment caused Plexamp's Audio Device page to show no selectable devices.

The live alias migration was rejected as a production fix and rolled back using the first snapshot. The alias file is absent, the normal ALSA device list is restored, and the saved Plexamp output remains `acp_plexamp`.

## Upstream match and resolution

Plexamp 4.12.4 had a Linux issue where playback might not work after application startup until the audio output was toggled. The bundled Plexamp Headless upgrade script was used after an independent backup and preparation capture.

After the upgrade:

- `plexamp.service` was restarted repeatedly;
- playback produced audio immediately without changing the output device;
- AirPlay still paused Plexamp and selected the AirPlay dashboard page;
- starting Plexamp playback while AirPlay was active still paused AirPlay;
- the correct `A Clockwork Plex - Plexamp` output remained usable.

The restart defect is therefore considered **resolved by the Plexamp upgrade**. No ALSA control alias is required.

## Current decision

The upgraded Plexamp is ready for the extended physical CamillaDSP rehearsal. Production DSP activation remains blocked until the complete post-mix route passes the long handoff/hold test and exact rollback once more.
