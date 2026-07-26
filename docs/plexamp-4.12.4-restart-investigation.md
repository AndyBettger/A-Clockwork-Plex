# Plexamp 4.12.4 restart investigation

The bedroom appliance runs Plexamp Headless 4.12.4 on Debian 13. During the stage-seven CamillaDSP rehearsal and subsequent direct-mixer reproductions, restarting `plexamp.service` could leave Plexamp logically playing with a valid timeline while no audio was heard. Manually changing or reconnecting the output could revive playback.

## Observed states

- AirPlay and the direct ALSA mixer remained healthy.
- Plexamp's HTTP interface and music timeline returned.
- The timeline could report `playing` with a valid queue and advancing position while output remained silent.
- The problem was triggered by restarting Plexamp, not by changing dashboard mode.
- A temporary `ctl.acp_*` alias experiment removed the `Invalid CTL acp_plexamp` log line but did not restore playback.
- Repeating that alias experiment caused Plexamp's Audio Device page to show no selectable devices.

The live alias migration is therefore rejected as a production fix. Its first rollback snapshot must be used to remove the temporary alias file because a later repeated apply captured the alias as already present.

## Upstream match

Plexamp 4.12.4 has a known Linux issue where playback may not work after application startup until the audio output is toggled. Plexamp 4.13.1 release notes explicitly state that the Linux output-toggle issue was fixed for desktop and headless.

The next controlled gate is:

1. remove the temporary named-control alias file and restore the pre-test service state;
2. capture the installed Plexamp service, upgrade script, audio-device setting and ALSA device list;
3. prepare a rollback-capable upgrade from 4.12.4 to the current supported headless release;
4. repeat direct-mixer restart playback before returning to CamillaDSP testing.

Production DSP activation remains blocked until Plexamp restart recovery passes without manually changing its output device.
