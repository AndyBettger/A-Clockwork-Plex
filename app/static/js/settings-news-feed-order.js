(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexNewsFeedOrderLoaded) return;
  window.__aClockworkPlexNewsFeedOrderLoaded = true;

  const newsPanel = document.querySelector('[data-settings-section="news"]');
  const newsOverview = newsPanel?.querySelector('[data-settings-overview="news"]');
  const feedSubpage = newsPanel?.querySelector('[data-settings-subpage="news:feeds"]');
  const editorList = feedSubpage?.querySelector('[data-news-feed-editor-list]');
  const addFeedButton = feedSubpage?.querySelector('[data-news-add-feed]');
  if (!newsPanel || !newsOverview || !feedSubpage || !editorList) return;

  const feedRow = newsOverview.querySelector('[data-settings-subpage-target="news:feeds"]');
  if (feedRow) {
    const copy = feedRow.querySelector('small');
    if (copy) copy.textContent = 'Rename feeds and manage custom BBC RSS sources';
  }

  if (addFeedButton) addFeedButton.classList.add('news-add-feed-button');

  const feedHelp = feedSubpage.querySelector('.settings-card .settings-card-heading .muted.small');
  if (feedHelp) {
    feedHelp.textContent = 'Rename built-in feeds or add another complete BBC News RSS address, for example https://feeds.bbci.co.uk/news/world/europe/rss.xml. Use Feed order to enable sections and arrange the News menu.';
  }

  const orderRow = document.createElement('button');
  orderRow.className = 'settings-subpage-row';
  orderRow.type = 'button';
  orderRow.dataset.settingsSubpageTarget = 'news:feed-order';
  orderRow.innerHTML = '<span><strong>Feed order</strong><small>Drag sections into order and choose which are enabled</small></span><span>›</span>';

  if (feedRow) newsOverview.insertBefore(orderRow, feedRow);
  else newsOverview.appendChild(orderRow);

  const orderSubpage = document.createElement('section');
  orderSubpage.className = 'settings-subpage';
  orderSubpage.dataset.settingsSubpage = 'news:feed-order';
  orderSubpage.hidden = true;
  orderSubpage.innerHTML = `
    <button class="settings-back" type="button" data-settings-back="news">‹ News</button>
    <section class="settings-card news-feed-order-intro">
      <h3>Feed order</h3>
      <p class="muted small">Drag the grip to arrange the News menu. Use the button on the right to enable or disable a section. At least one section must remain enabled.</p>
    </section>
    <div class="news-feed-order-list" data-news-feed-order-list></div>
  `;
  newsPanel.appendChild(orderSubpage);

  const orderList = orderSubpage.querySelector('[data-news-feed-order-list]');
  let knownEditorIds = new Set();
  let syncingOrder = false;

  function editorCards() {
    return [...editorList.querySelectorAll('[data-news-feed-editor-id]')];
  }

  function editorIds() {
    return editorCards().map((card) => String(card.dataset.newsFeedEditorId || '')).filter(Boolean);
  }

  function cardFor(feedId) {
    return editorCards().find((card) => card.dataset.newsFeedEditorId === feedId) || null;
  }

  function textButton(card, text) {
    return [...(card?.querySelectorAll('button') || [])].find((button) => String(button.textContent || '').trim() === text) || null;
  }

  function enabledInput(card) {
    return card?.querySelector('.settings-card-heading .setting-toggle input[type="checkbox"]') || null;
  }

  function decorateEditor() {
    const cards = editorCards();
    cards.forEach((card) => {
      card.classList.add('news-feed-editor-card');
      const enabled = card.querySelector('.settings-card-heading .setting-toggle');
      if (enabled) {
        enabled.hidden = true;
        enabled.setAttribute('aria-hidden', 'true');
      }

      const up = textButton(card, 'Move up');
      const down = textButton(card, 'Move down');
      if (up) up.hidden = true;
      if (down) down.hidden = true;

      const actions = card.querySelector('.settings-action-row');
      if (actions) {
        const visibleButtons = [...actions.querySelectorAll('button')].filter((button) => !button.hidden);
        actions.hidden = visibleButtons.length === 0;
      }
    });
  }

  function setEnabled(feedId, nextEnabled) {
    const input = enabledInput(cardFor(feedId));
    if (!input || input.checked === nextEnabled) return;
    input.checked = nextEnabled;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function applyOrder(desiredOrder) {
    if (!Array.isArray(desiredOrder) || !desiredOrder.length) return;
    syncingOrder = true;
    let guard = Math.max(40, desiredOrder.length * desiredOrder.length + 4);

    try {
      desiredOrder.forEach((feedId, targetIndex) => {
        while (guard > 0) {
          guard -= 1;
          const current = editorIds();
          const currentIndex = current.indexOf(feedId);
          if (currentIndex < 0 || currentIndex === targetIndex) break;
          const card = cardFor(feedId);
          const button = currentIndex > targetIndex ? textButton(card, 'Move up') : textButton(card, 'Move down');
          if (!button || button.disabled) break;
          button.click();
        }
      });
    } finally {
      syncingOrder = false;
      decorateEditor();
      renderOrder();
    }
  }

  function createOrderRow(card) {
    const feedId = String(card.dataset.newsFeedEditorId || '');
    const label = String(card.querySelector('h3')?.textContent || feedId).trim();
    const source = String(card.querySelector('.settings-card-heading .muted.small')?.textContent || '').trim();
    const input = enabledInput(card);
    const isEnabled = input?.checked === true;

    const row = document.createElement('div');
    row.className = 'news-feed-order-row touch-sort-row';
    row.dataset.newsFeedOrderId = feedId;
    row.dataset.touchSortId = feedId;

    const handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'settings-drag-handle';
    handle.dataset.touchSortHandle = '';
    handle.setAttribute('aria-label', `Drag ${label} to reorder. Arrow keys also move it.`);
    handle.setAttribute('aria-grabbed', 'false');
    handle.innerHTML = '<span aria-hidden="true">⠿</span>';

    const copy = document.createElement('span');
    copy.className = 'news-feed-order-copy';
    const strong = document.createElement('strong');
    strong.textContent = label;
    const small = document.createElement('small');
    small.textContent = source || 'BBC News feed';
    copy.append(strong, small);

    const enabled = document.createElement('button');
    enabled.type = 'button';
    enabled.className = 'news-feed-enabled-button';
    enabled.setAttribute('aria-pressed', isEnabled ? 'true' : 'false');
    enabled.setAttribute('aria-label', `${isEnabled ? 'Disable' : 'Enable'} ${label}`);
    enabled.textContent = isEnabled ? 'Enabled' : 'Disabled';
    enabled.addEventListener('click', () => setEnabled(feedId, !isEnabled));

    row.append(handle, copy, enabled);
    return row;
  }

  function renderOrder() {
    if (syncingOrder) return;
    decorateEditor();
    const cards = editorCards();
    orderList.replaceChildren(...cards.map(createOrderRow));
    window.ACPTouchReorder?.bind?.(orderList, {
      itemSelector: '[data-news-feed-order-id]',
      handleSelector: '[data-touch-sort-handle]',
      onCommit: applyOrder,
    });
  }

  function scrollToNewFeed(previousIds) {
    window.requestAnimationFrame(() => {
      decorateEditor();
      const newcomer = editorCards().find((card) => !previousIds.has(card.dataset.newsFeedEditorId));
      if (!newcomer) return;
      newcomer.classList.add('is-new-feed');
      newcomer.scrollIntoView({ block: 'start', behavior: 'smooth' });
      window.setTimeout(() => newcomer.classList.remove('is-new-feed'), 1800);
    });
  }

  addFeedButton?.addEventListener('click', () => {
    const previousIds = new Set(knownEditorIds);
    window.setTimeout(() => {
      scrollToNewFeed(previousIds);
      const message = feedSubpage.querySelector('[data-news-feed-editor-message]');
      if (message && String(message.textContent || '').includes('before Save Changes')) {
        message.textContent = 'Enter a BBC News RSS URL, press Check feed, then optionally rename it. Use Feed order when you want to enable or reposition it.';
      }
    }, 0);
  });

  const observer = new MutationObserver(() => {
    decorateEditor();
    if (!syncingOrder) renderOrder();
    knownEditorIds = new Set(editorIds());
  });
  observer.observe(editorList, { childList: true, subtree: true });

  decorateEditor();
  renderOrder();
  knownEditorIds = new Set(editorIds());
})();
