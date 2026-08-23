# Documentation assets

This directory contains visual assets used by the public A Clockwork Plex documentation.

## Screenshots

Current release screenshots live in [`screenshots/`](screenshots/).

The screenshot set demonstrates real appliance behaviour: Clock day/night presentation, scheduled alarms, Weather, Plexamp, AirPlay and Settings. The root README uses a product overview subset, while [`../INSTALL.md`](../INSTALL.md#8-visual-first-use-tour) uses the Settings and operating views as a compact first-use tour. Keep screenshots at the validated 1280×720 landscape presentation where practical.

Some Now Playing screenshots naturally include third-party album/book artwork and metadata because they document the player UI in normal use. That material is shown only as contextual content inside the appliance screenshot; copyright and other rights in that media remain with their respective rights holders.

Before adding or replacing screenshots:

- do not expose API keys, passwords, tokens or other secrets;
- avoid publishing precise private location data or station identifiers unless intentionally public;
- prefer representative appliance content over temporary debugging states;
- keep filenames stable when a newer screenshot simply replaces an older view;
- update `tests/test_docs_catalog.py` when the curated screenshot set intentionally changes.

A refreshed Settings → About screenshot may be added later now that the release metadata is finalised. A future physical-appliance hero photograph and finished NFC-album presentation image may also live under `docs/assets/` when available. None of those optional images is required for the 0.4.0 software release.
