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
    sectionsHelp.textContent = 'Choose which BBC News sections are enabled here. Feed order provides the compact drag-to-reorder view, while News feeds owns display names and custom RSS sources.';
  }

  const feedHelp = feedSubpage.querySelector('.settings-card .settings-card-heading .muted.small');
  if (feedHelp) {
    feedHelp.textContent = 'Curated BBC News feeds can be renamed. You can also add another complete BBC News RSS address, for example https://feeds.bbci.co.uk/news/world/europe/rss.xml. Only HTTPS BBC News feeds are accepted.';
  }

  const editorList = feedSubpage.querySelector('[data-news-feed-editor-list]');
  editorList?.classList.add('news-feed-editor-list');

  function refreshCustomFeedHelp() {
    feedSubpage.querySelectorAll('.setting-field small').forEach((help) => {
      const copy = String(help.textContent || '');
      if (!copy.includes('pass Check feed before Save Changes')) return;
      help.textContent = 'Enter or change the BBC RSS address, then press Check feed. A successful check is required before this custom feed can be used.';
    });
  }

  refreshCustomFeedHelp();
  if (editorList && 'MutationObserver' in window) {
    const observer = new MutationObserver(refreshCustomFeedHelp);
    observer.observe(editorList, { childList: true, subtree: true });
  }

  newsPanel.appendChild(feedSubpage);
})();
