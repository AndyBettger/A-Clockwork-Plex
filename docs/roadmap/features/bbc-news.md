# BBC News

**Status:** COMPLETE #92, including article QR and configurable sections

## Accepted scope

- BBC RSS/cache authority with stale/degraded last-good behaviour.
- Touch News page, category rail, detail modal and ticker.
- Safe QR hand-off for trusted BBC article destinations.
- Configurable built-in sections plus bounded custom BBC News RSS feeds.
- Feed enable/disable/reorder, discovery and physical commissioned-appliance acceptance.
- Settings → News includes a physically accepted **Refresh feeds now** maintenance action that bypasses the normal cache TTL when connectivity has just recovered while reusing the existing validated feed/cache service.
- [x] Post-#94 theme polish: ordinary **News ready** and **BBC feed date/time** pill borders use the active daytime `--accent` / `--panel-border` tokens rather than the legacy fixed ACP cyan accent; semantic warning styling remains separate. Candidate `1d41fbfbbea7f2e02abab2a5352c889ec3c2ee0e` passed **Tests #5278** and is physically accepted on the commissioned Pi.
- [x] Post-#94 status ownership correction: the visible rail pill describes the **active News section** first. A failure in another enabled feed may legitimately make the overall service snapshot degraded, but does not turn a freshly successful active section into **Cached news**. Physically accepted on the commissioned Pi.
- [x] Semantic status colour contract: healthy **News ready** follows the selected daytime theme; genuine **Cached news / Stale cache** intentionally uses amber/yellow warning chrome across themes rather than blending into Green/Crimson/etc.

## Detailed authorities

- [BBC News architecture](../../development/architecture/bbc-news.md)
- [BBC News testing](../../development/testing/bbc-news-testing.md)

The historical feature branches are fully merged into `develop`; they carry no commits absent from `develop`.
