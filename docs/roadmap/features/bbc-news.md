# BBC News

**Status:** COMPLETE #92, including article QR and configurable sections

## Accepted scope

- BBC RSS/cache authority with stale/degraded last-good behaviour.
- Touch News page, category rail, detail modal and ticker.
- Safe QR hand-off for trusted BBC article destinations.
- Configurable built-in sections plus bounded custom BBC News RSS feeds.
- Feed enable/disable/reorder, discovery and physical commissioned-appliance acceptance.
- Settings → News includes a physically accepted **Refresh feeds now** maintenance action that bypasses the normal cache TTL when connectivity has just recovered while reusing the existing validated feed/cache service.
- Post-#94 theme polish: ordinary **News ready** and **BBC feed date/time** pill borders use the active daytime `--accent` / `--panel-border` tokens rather than the legacy fixed ACP cyan accent; semantic warning styling remains separate. Candidate `1d41fbfbbea7f2e02abab2a5352c889ec3c2ee0e` passed **Tests #5278** and awaits physical colour confirmation.

## Detailed authorities

- [BBC News architecture](../../development/architecture/bbc-news.md)
- [BBC News testing](../../development/testing/bbc-news-testing.md)

The historical feature branches are fully merged into `develop`; they carry no commits absent from `develop`.
