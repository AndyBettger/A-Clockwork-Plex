# BBC News foundation testing

Checkpoint #92 deliberately tests the feed/cache authority with local RSS-shaped fixtures rather than relying on live BBC availability in CI.

Automated coverage currently protects:

- safe RSS parsing and markup-to-plain-text normalisation;
- article URL/GUID non-exposure in the public story model;
- duplicate story suppression;
- feed-supplied BBC image metadata acceptance only on approved BBC HTTPS hosts;
- selected-category fetching plus Top Stories retention for the ticker;
- last-good cache preservation after a later provider failure;
- read-only `/api/news` behaviour;
- category/default/ticker-speed Settings validation;
- runner lifecycle ownership and unified Settings wiring.

The existing `tests/test_weather_forecast.py` module temporarily carries the generic cached-background-feed regression cases so the maintained module catalogue remains unchanged during this first foundation slice. Split into a dedicated News module only with the matching test-catalogue update.

Physical UI acceptance is not part of the #92 backend foundation. The later News presentation checkpoint must be tested on the commissioned 1280×720 Touch Display 2, including left-rail navigation, headline scrolling, detail presentation, ticker speed and stale/offline presentation.
