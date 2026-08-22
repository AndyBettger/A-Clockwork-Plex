# Documentation assets

This directory contains visual assets used by the public A Clockwork Plex documentation.

## Screenshots

Current release screenshots live in [`screenshots/`](screenshots/).

The screenshot set is intended to demonstrate real appliance behaviour: Clock day/night presentation, scheduled alarms, Weather, Plexamp, AirPlay and Settings. Keep screenshots at the validated 1280×720 landscape presentation where practical.

Before adding or replacing screenshots:

- do not expose API keys, passwords, tokens or other secrets;
- avoid publishing precise private location data or station identifiers unless intentionally public;
- prefer representative appliance content over temporary debugging states;
- keep filenames stable when a newer screenshot simply replaces an older view;
- update `tests/test_docs_catalog.py` when the curated screenshot set intentionally changes.

A future physical-appliance hero photograph and finished NFC-album presentation image may also live under `docs/assets/` when available; neither is required for the software release.
