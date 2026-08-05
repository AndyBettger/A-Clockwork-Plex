# Stage C host discovery — 5 August 2026

Status: **PASS**. Read-only discovery completed on `plexamp-bedroom`. No file, service, module, mixer level or audio route was changed.

## Host

- hostname: `plexamp-bedroom`
- architecture: `aarch64`
- kernel: `6.18.39+rpt-rpi-2712`
- project user: `andy`

## snd_aloop contract

The loopback module is already loaded and physically proven with these exact runtime parameters:

- module: `/lib/modules/6.18.39+rpt-rpi-2712/kernel/sound/drivers/snd-aloop.ko.xz`
- card index: `7`
- requested ID: `ACP_Loopback`
- ALSA card identity: `ACPLoopback`
- enabled instances: first instance only
- PCM substreams: `2`
- PCM notify: `1`
- timer source: default jiffies timer

The module is not currently persisted by a matching file under `/etc/modules-load.d` or `/etc/modprobe.d`. `/etc/modules` contains only `i2c-dev` and explicitly notes that modules-load.d is the supported mechanism.

The persistent Stage C package must therefore generate deterministic candidates equivalent to:

```text
/etc/modules-load.d/a-clockwork-plex-aloop.conf
    snd_aloop

/etc/modprobe.d/a-clockwork-plex-aloop.conf
    options snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1
```

Those files remain candidates only until the guarded installation transaction is reviewed and approved.

## ALSA and DAC identities

Detected cards:

- card 0: `vc4hdmi0`
- card 1: `vc4hdmi1`
- card 2: `Pro` — Raspberry Pi DAC Pro
- card 7: `ACPLoopback` — Loopback

The physical output is:

```text
hw:CARD=Pro,DEV=0
/dev/snd/pcmC2D0p
```

Observed live hardware parameters:

- access: `MMAP_INTERLEAVED`
- format: `S16_LE`
- channels: `2`
- sample rate: `44100`
- period size: `1024`
- buffer size: `8192`

At discovery time the DAC was correctly owned by Plexamp Headless's `node` process. Discovery opened no PCM.

## Current production route

- active file: `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`
- SHA-256: `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`
- mode: `0644`
- owner: `root:root`

The current pre-Stage-C alarm softvol remains beneath Music Master:

```text
pcm.acp_alarm_volume {
    type softvol
    slave.pcm "acp_master"
    control {
        name "A Clockwork Alarm"
        card "Pro"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
```

That exact file is the uninstall rollback target, not the managed runtime failback target. Stage C0 physically proved the separate direct alarm-bypass failback graph.

## Service contract

The existing appliance services are all active and enabled:

- `plexamp.service`
- `shairport-sync.service`
- `a-clockwork-plex.service`

The proposed Stage C units do not currently exist:

- `a-clockwork-plex-audio-route.service`
- `a-clockwork-plex-camilladsp.service`
- `a-clockwork-plex-audio-failback.service`

No existing Stage C unit or CamillaDSP process needs migration.

## Verified CamillaDSP binary

- version: `CamillaDSP 4.1.3 (05e9cfc)`
- discovery path: `/tmp/a-clockwork-plex-camilladsp-4.1.3/bin/camilladsp`
- SHA-256: `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`

A future activated transaction may copy only a binary matching both this version and digest. It must not download an executable during activation.

## Promotion decision

The host is suitable for Stage C package generation with these pinned assumptions:

1. aarch64 host;
2. physical DAC `Pro`, device 0, card index 2;
3. deterministic loopback card index 7 and ID `ACP_Loopback`;
4. two loopback substreams with `pcm_notify=1`;
5. 44.1 kHz, S16_LE, period 1024 and buffer 8192;
6. verified CamillaDSP 4.1.3 binary digest;
7. exact current direct-route checksum;
8. three existing application services enabled and active;
9. no existing Stage C services or persistent module configuration.

The next step is a prepare-only Stage C route package. Persistent activation remains blocked.