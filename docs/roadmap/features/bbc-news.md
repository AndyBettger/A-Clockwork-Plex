# BBC News

**Status:** COMPLETE #92, including article QR and configurable sections

## Accepted scope

- BBC RSS/cache authority with stale/degraded last-good behaviour.
- Touch News page, category rail, detail modal and ticker.
- Safe QR hand-off for trusted BBC article destinations.
- Configurable built-in sections plus bounded custom BBC News RSS feeds.
- Feed enable/disable/reorder, discovery and physical commissioned-appliance acceptance.
- Settings → News includes an explicit **Refresh feeds now** maintenance action that bypasses the normal cache TTL when connectivity has just recovered.

## Detailed authorities

- [BBC News architecture](../../development/architecture/bbc-news.md)
- [BBC News testing](../../development/testing/bbc-news-testing.md)

The historical feature branches are fully merged into `develop`; they carry no commits absent from `develop`.
