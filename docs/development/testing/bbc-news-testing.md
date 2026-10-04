# BBC News foundation testing

Checkpoint #92 deliberately tests the feed/cache authority with local RSS-shaped fixtures rather than relying on live BBC availability in CI.

Automated coverage currently protects:

- safe RSS parsing and markup-to-plain-text normalisation;
- article URL/GUID non-exposure in the public story model;
- duplicate story suppression;
- feed-supplied BBC image metadata acceptance only on approved BBC HTTPS hosts;
- selected-category fetching plus Top Stories retention for the ticker;
- last-good cache preservation after a later provider failure;
- read-only `/api/news` behaviour plus owner-triggered `POST /api/news/refresh` forced refresh that reuses the existing validated feed service;
- category/default/ticker-speed Settings validation;
- runner lifecycle ownership and unified Settings wiring.

Dedicated News regression coverage now lives primarily in `tests/test_news_article_qr.py` and `tests/test_news_custom_feed_layout.py`, with Settings integration contracts also protected by `tests/test_settings_ipad.py`. Live BBC availability is still not required in CI: forced-refresh tests use local RSS fixtures and prove the cache TTL is bypassed without widening the approved feed-source boundary.

Physical UI acceptance is not part of the #92 backend foundation. The later News presentation checkpoint must be tested on the commissioned 1280×720 Touch Display 2, including left-rail navigation, headline scrolling, detail presentation, ticker speed and stale/offline presentation.
