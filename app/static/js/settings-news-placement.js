(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const newsPanel = document.querySelector('[data-settings-section="news"]');
  const newsOverview = newsPanel?.querySelector('[data-settings-overview="news"]');
  const advancedPanel = document.querySelector('[data-settings-section="advanced"]');
  const advancedOverview = advancedPanel?.querySelector('[data-settings-overview="advanced"]');
  const feedRow = advancedOverview?.querySelector('[data-settings-subpage-target="advanced:news-feeds"]');
  const feedSubpage = advancedPanel?.querySelector('[data-settings-subpage="advanced:news-feeds"]');

  if (!newsPanel || !newsOverview || !feedRow || !feedSubpage) return;

  feedRow.dataset.settingsSubpageTarget = 'news:feeds';
  newsOverview.appendChild(feedRow);

  feedSubpage.dataset.settingsSubpage = 'news:feeds';
  const back = feedSubpage.querySelector('[data-settings-back="advanced"]');
  if (back) {
    back.dataset.settingsBack = 'news';
    back.textContent = '‹ News';
  }

  const sectionsHelp = newsPanel.querySelector('[data-settings-subpage="news:sections"] .settings-card .muted.small');
  if (sectionsHelp) {
    sectionsHelp.textContent = 'Enabled sections appear in this order in the News page’s left-hand menu. At least one section must remain enabled. Rename, reorder or add BBC feeds under News feeds.';
  }

  const feedHelp = feedSubpage.querySelector('.settings-card .settings-card-heading .muted.small');
  if (feedHelp) {
    feedHelp.textContent = 'Curated BBC News feeds can be renamed and reordered. You can also add another complete BBC News RSS address, for example https://feeds.bbci.co.uk/news/world/europe/rss.xml. Only HTTPS BBC News feeds are accepted.';
  }

  const editorList = feedSubpage.querySelector('[data-news-feed-editor-list]');
  editorList?.classList.add('news-feed-editor-list');
  newsPanel.appendChild(feedSubpage);
})();
