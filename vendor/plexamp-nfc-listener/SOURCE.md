# Vendored Plexamp NFC Listener provenance

This directory contains the NFC runtime needed by A Clockwork Plex without
executing the standalone project's broad `setup.sh` ownership.

Source repository: `AndyBettger/Plexamp-NFC-Listener`

Pinned source commit:

```text
8f5f04213b22cfb5affc6931cb2db91fd07de537
```

Pinned source blobs copied here:

```text
nfc_listener.py  5f87b477bfdac27a34373cb7708af8236c33c2ab
requirements.txt a35eb89930ffac8e5b25179832e450aaa4403a13
LICENSE          739abcadcd68145a60b32ac67d2ec9fcd0a395ad
```

The source is MIT licensed; the upstream licence is retained as `LICENSE`.

## Deliberate ownership split

Only the listener runtime and its Python dependency declaration are vendored.
The upstream `setup.sh` is **not** invoked or copied as an appliance installer
because it also performs OS-wide upgrade, Chromium kiosk and optional AirPlay
configuration, including historical direct Plexamp service handoff hooks.
Those responsibilities already have separate guarded owners in A Clockwork Plex.

A Clockwork Plex renders its own project-user-aware `nfc-listener.service` and
sets the dashboard display-switch integration explicitly.
