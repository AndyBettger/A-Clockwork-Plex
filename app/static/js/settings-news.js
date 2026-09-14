(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsNewsLoaded) return;
  window.__aClockworkPlexSettingsNewsLoaded = true;

  const FEED_VALIDATE_API = '/api/news/feed/validate';
  const BUILT_IN_FEEDS = Object.freeze([
    { id: 'top', label: 'Top Stories', url: 'https://feeds.bbci.co.uk/news/rss.xml' },
    { id: 'uk', label: 'UK', url: 'https://feeds.bbci.co.uk/news/uk/rss.xml' },
    { id: 'world', label: 'World', url: 'https://feeds.bbci.co.uk/news/world/rss.xml' },
    { id: 'science', label: 'Science & Environment', url: 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml' },
    { id: 'technology', label: 'Technology', url: 'https://feeds.bbci.co.uk/news/technology/rss.xml' },
    { id: 'england', label: 'England', url: 'https://feeds.bbci.co.uk/news/england/rss.xml' },
    { id: 'scotland', label: 'Scotland', url: 'https://feeds.bbci.co.uk/news/scotland/rss.xml' },
    { id: 'wales', label: 'Wales', url: 'https://feeds.bbci.co.uk/news/wales/rss.xml' },
    { id: 'northern_ireland', label: 'Northern Ireland', url: 'https://feeds.bbci.co.uk/news/northern_ireland/rss.xml' },
    { id: 'business', label: 'Business', url: 'https://feeds.bbci.co.uk/news/business/rss.xml' },
    { id: 'politics', label: 'Politics', url: 'https://feeds.bbci.co.uk/news/politics/rss.xml' },
    { id: 'health', label: 'Health', url: 'https://feeds.bbci.co.uk/news/health/rss.xml' },
    { id: 'education', label: 'Education', url: 'https://feeds.bbci.co.uk/news/education/rss.xml' },
    { id: 'entertainment', label: 'Entertainment & Arts', url: 'https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml' },
  ]);
  const DEFAULT_ENABLED = Object.freeze(['top', 'uk', 'world', 'science', 'technology']);
  const MAX_CUSTOM_FEEDS = 12;
  const CUSTOM_ID_PATTERN = /^custom-[a-z0-9][a-z0-9-]{0,47}$/;

  const sidebar = document.querySelector('.settings-sidebar-list');
  const detail = document.querySelector('.settings-detail');
  if (!sidebar || !detail) return;

  const button = document.createElement('button');
  button.className = 'settings-sidebar-row';
  button.type = 'button';
  button.dataset.settingsSectionTarget = 'news';
  button.innerHTML = '<span><strong>News</strong><small>Sections and ticker</small></span><span class="settings-dirty-dot" aria-label="Unsaved changes" hidden></span><span class="settings-chevron" aria-hidden="true">›</span>';

  const weatherButton = sidebar.querySelector('[data-settings-section-target="weather"]');
  if (weatherButton) weatherButton.insertAdjacentElement('afterend', button);
  else sidebar.appendChild(button);

  const panel = document.createElement('div');
  panel.className = 'settings-detail-panel';
  panel.dataset.settingsSection = 'news';
  panel.hidden = true;
  panel.innerHTML = `
    <header class="settings-detail-header">
      <div><h2>News</h2><p>Choose the BBC News sections shown on the appliance and how the Top Stories ticker behaves.</p></div>
    </header>
    <div class="settings-subpage-overview" data-settings-overview="news">
      <section class="settings-card">
        <div class="settings-card-heading">
          <div><h3>BBC News service</h3><p class="muted small">Headlines come from the appliance's cached BBC RSS feeds; article web pages are never opened by the kiosk.</p></div>
          <span class="settings-chip" data-news-settings-status>Loading…</span>
        </div>
        <p class="muted small" data-news-settings-message>Checking cached BBC News status.</p>
      </section>
      <button class="settings-subpage-row" type="button" data-settings-subpage-target="news:sections">
        <span><strong>Sections</strong><small>Enabled sections and the default News page</small></span><span>›</span>
      </button>
      <button class="settings-subpage-row" type="button" data-settings-subpage-target="news:presentation">
        <span><strong>Presentation</strong><small>Story summaries and Top Stories ticker</small></span><span>›</span>
      </button>
    </div>
    <section class="settings-subpage" data-settings-subpage="news:sections" hidden>
      <button class="settings-back" type="button" data-settings-back="news">‹ News</button>
      <section class="settings-card">
        <h3>Sections</h3>
        <p class="muted small">Enabled sections appear in this order in the News page's left-hand menu. At least one section must remain enabled. Rename, reorder or add BBC feeds under Advanced → News feeds.</p>
        <div class="settings-grid two-col" data-news-category-controls></div>
      </section>
      <section class="settings-card">
        <h3>Default section</h3>
        <div class="settings-grid two-col">
          <label class="setting-field">
            <span>Section opened first</span>
            <select data-news-default-category></select>
            <small>The section selected when the News page is first opened.</small>
          </label>
        </div>
      </section>
    </section>
    <section class="settings-subpage" data-settings-subpage="news:presentation" hidden>
      <button class="settings-back" type="button" data-settings-back="news">‹ News</button>
      <section class="settings-card">
        <h3>Presentation</h3>
        <div class="settings-grid two-col">
          <label class="setting-toggle"><input type="checkbox" data-news-show-summaries><span>Show story summaries</span></label>
          <label class="setting-toggle"><input type="checkbox" data-news-ticker-enabled><span>Show Top Stories ticker</span></label>
          <label class="setting-field">
            <span>Ticker speed</span>
            <select data-news-ticker-speed>
              <option value="slow">Slow</option>
              <option value="normal">Normal</option>
              <option value="fast">Fast</option>
            </select>
            <small>The ticker always uses the cached Top Stories feed, independent of the section being viewed.</small>
          </label>
        </div>
      </section>
    </section>
  `;

  const alarmsPanel = detail.querySelector('[data-settings-section="alarms"]');
  if (alarmsPanel) detail.insertBefore(panel, alarmsPanel);
  else detail.appendChild(panel);

  const advancedOverview = detail.querySelector('[data-settings-overview="advanced"]');
  const advancedPanel = detail.querySelector('[data-settings-section="advanced"]');
  let advancedFeedMount = null;
  let advancedFeedMessage = null;
  let addFeedButton = null;

  if (advancedOverview && advancedPanel) {
    const advancedRow = document.createElement('button');
    advancedRow.className = 'settings-subpage-row';
    advancedRow.type = 'button';
    advancedRow.dataset.settingsSubpageTarget = 'advanced:news-feeds';
    advancedRow.innerHTML = '<span><strong>News feeds</strong><small>Rename, reorder and add BBC News RSS feeds</small></span><span>›</span>';
    advancedOverview.appendChild(advancedRow);

    const advancedSubpage = document.createElement('section');
    advancedSubpage.className = 'settings-subpage';
    advancedSubpage.dataset.settingsSubpage = 'advanced:news-feeds';
    advancedSubpage.hidden = true;
    advancedSubpage.innerHTML = `
      <button class="settings-back" type="button" data-settings-back="advanced">‹ Advanced</button>
      <section class="settings-card">
        <div class="settings-card-heading">
          <div>
            <h3>News feeds</h3>
            <p class="muted small">Curated BBC News feeds can be renamed and reordered. You can also add another BBC News RSS feed from <code>feeds.bbci.co.uk</code>. Other hosts are deliberately rejected.</p>
          </div>
          <button class="button settings-secondary" type="button" data-news-add-feed>Add BBC feed</button>
        </div>
        <p class="muted small" data-news-feed-editor-message>Custom feeds must pass a live BBC RSS check before they can be saved. The Top Stories ticker always stays tied to Top Stories.</p>
      </section>
      <div data-news-feed-editor-list></div>
    `;
    advancedPanel.appendChild(advancedSubpage);
    advancedFeedMount = advancedSubpage.querySelector('[data-news-feed-editor-list]');
    advancedFeedMessage = advancedSubpage.querySelector('[data-news-feed-editor-message]');
    addFeedButton = advancedSubpage.querySelector('[data-news-add-feed]');
  }

  const categoriesMount = panel.querySelector('[data-news-category-controls]');
  const defaultSelect = panel.querySelector('[data-news-default-category]');
  const showSummaries = panel.querySelector('[data-news-show-summaries]');
  const tickerEnabled = panel.querySelector('[data-news-ticker-enabled]');
  const tickerSpeed = panel.querySelector('[data-news-ticker-speed]');
  const statusChip = panel.querySelector('[data-news-settings-status]');
  const statusMessage = panel.querySelector('[data-news-settings-message]');

  const builtInById = new Map(BUILT_IN_FEEDS.map((feed) => [feed.id, feed]));
  let feedState = [];
  let defaultCategory = 'top';
  let applying = false;
  let customCounter = 0;

  function clean(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
  }

  function displayLabel(feed) {
    const label = clean(feed?.label);
    if (label) return label;
    if (feed?.builtIn) return builtInById.get(feed.id)?.label || feed.id;
    return 'Custom BBC feed';
  }

  function enabledFeeds() {
    return feedState.filter((feed) => feed.enabled);
  }

  function normaliseDefault() {
    const enabled = enabledFeeds();
    if (!enabled.some((feed) => feed.id === defaultCategory)) {
      defaultCategory = enabled[0]?.id || '';
    }
  }

  function markDirty() {
    if (applying) return;
    window.ACPUnifiedSettings?.markDirty?.('news');
  }

  function setEditorMessage(message) {
    if (advancedFeedMessage) advancedFeedMessage.textContent = message;
  }

  function renderSections() {
    categoriesMount.replaceChildren();
    defaultSelect.replaceChildren();

    feedState.forEach((feed) => {
      const wrapper = document.createElement('label');
      wrapper.className = 'setting-toggle';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = feed.enabled;
      input.dataset.newsCategory = feed.id;
      const copy = document.createElement('span');
      copy.textContent = displayLabel(feed);
      wrapper.append(input, copy);
      categoriesMount.appendChild(wrapper);

      input.addEventListener('change', () => {
        if (!input.checked && enabledFeeds().length === 1 && feed.enabled) {
          input.checked = true;
          if (statusMessage) statusMessage.textContent = 'At least one BBC News section must remain enabled.';
          return;
        }
        feed.enabled = input.checked;
        normaliseDefault();
        renderAllFeedControls();
        markDirty();
      });
    });

    enabledFeeds().forEach((feed) => {
      const option = document.createElement('option');
      option.value = feed.id;
      option.textContent = displayLabel(feed);
      defaultSelect.appendChild(option);
    });
    normaliseDefault();
    defaultSelect.value = defaultCategory;
  }

  function moveFeed(feedId, delta) {
    const index = feedState.findIndex((feed) => feed.id === feedId);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= feedState.length) return;
    [feedState[index], feedState[target]] = [feedState[target], feedState[index]];
    renderAllFeedControls();
    markDirty();
  }

  function removeFeed(feedId) {
    const index = feedState.findIndex((feed) => feed.id === feedId && !feed.builtIn);
    if (index < 0) return;
    const wasEnabled = feedState[index].enabled;
    if (wasEnabled && enabledFeeds().length === 1) {
      setEditorMessage('At least one BBC News section must remain enabled before this feed can be removed.');
      return;
    }
    feedState.splice(index, 1);
    normaliseDefault();
    renderAllFeedControls();
    markDirty();
  }

  async function validateCustomFeed(feed) {
    if (!feed || feed.builtIn || feed.validating) return;
    const candidate = clean(feed.url);
    if (!candidate) {
      setEditorMessage('Enter the BBC RSS URL before checking this feed.');
      return;
    }
    const duplicate = feedState.some((other) => other !== feed && clean(other.url) === candidate);
    if (duplicate) {
      setEditorMessage('That BBC RSS URL is already present in the News feed list.');
      return;
    }

    feed.validating = true;
    renderAdvancedEditor();
    setEditorMessage(`Checking ${candidate}…`);
    try {
      const response = await fetch(FEED_VALIDATE_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({ url: candidate }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Feed check returned HTTP ${response.status}.`);
      }

      const suggestedId = clean(payload.suggested_id).toLowerCase();
      if (
        feed.isNew
        && CUSTOM_ID_PATTERN.test(suggestedId)
        && !feedState.some((other) => other !== feed && other.id === suggestedId)
      ) {
        if (defaultCategory === feed.id) defaultCategory = suggestedId;
        feed.id = suggestedId;
      }
      feed.isNew = false;
      feed.url = candidate;
      feed.validatedUrl = candidate;
      if (!clean(feed.label) || clean(feed.label) === 'Custom BBC feed') {
        feed.label = clean(payload.label) || 'Custom BBC feed';
      }
      setEditorMessage(
        `Feed checked successfully${Number.isFinite(Number(payload.story_count)) ? `; ${Number(payload.story_count)} current stories found` : ''}.`
      );
      markDirty();
    } catch (error) {
      feed.validatedUrl = '';
      setEditorMessage(`Feed check failed: ${error.message || 'BBC RSS validation failed.'}`);
    } finally {
      feed.validating = false;
      renderAllFeedControls();
    }
  }

  function renderAdvancedEditor() {
    if (!advancedFeedMount) return;
    advancedFeedMount.replaceChildren();

    feedState.forEach((feed, index) => {
      const card = document.createElement('section');
      card.className = 'settings-card';
      card.dataset.newsFeedEditorId = feed.id;

      const heading = document.createElement('div');
      heading.className = 'settings-card-heading';
      const titleWrap = document.createElement('div');
      const title = document.createElement('h3');
      title.textContent = displayLabel(feed);
      const source = document.createElement('p');
      source.className = 'muted small';
      if (feed.builtIn) source.textContent = 'Built-in BBC News feed';
      else if (feed.validatedUrl === clean(feed.url) && feed.validatedUrl) source.textContent = 'Custom BBC News feed · checked';
      else source.textContent = 'Custom BBC News feed · check required';
      titleWrap.append(title, source);

      const enabledLabel = document.createElement('label');
      enabledLabel.className = 'setting-toggle';
      const enabledInput = document.createElement('input');
      enabledInput.type = 'checkbox';
      enabledInput.checked = feed.enabled;
      const enabledCopy = document.createElement('span');
      enabledCopy.textContent = 'Enabled';
      enabledLabel.append(enabledInput, enabledCopy);
      heading.append(titleWrap, enabledLabel);

      const fields = document.createElement('div');
      fields.className = 'settings-grid two-col';

      const labelField = document.createElement('label');
      labelField.className = 'setting-field';
      const labelCaption = document.createElement('span');
      labelCaption.textContent = 'Display name';
      const labelInput = document.createElement('input');
      labelInput.value = feed.label;
      labelInput.inputMode = 'none';
      labelInput.dataset.keyboard = 'text';
      labelInput.maxLength = 80;
      labelInput.autocomplete = 'off';
      labelField.append(labelCaption, labelInput);

      const urlField = document.createElement('label');
      urlField.className = 'setting-field wide';
      const urlCaption = document.createElement('span');
      urlCaption.textContent = 'BBC RSS URL';
      const urlInput = document.createElement('input');
      urlInput.value = feed.url;
      urlInput.autocomplete = 'off';
      if (feed.builtIn) {
        urlInput.readOnly = true;
      } else {
        urlInput.inputMode = 'none';
        urlInput.dataset.keyboard = 'url';
      }
      const urlHelp = document.createElement('small');
      urlHelp.textContent = feed.builtIn
        ? 'The source URL for a built-in feed is fixed.'
        : 'Must be an HTTPS BBC News RSS URL on feeds.bbci.co.uk and pass Check feed before Save Changes.';
      urlField.append(urlCaption, urlInput, urlHelp);
      fields.append(labelField, urlField);

      const actions = document.createElement('div');
      actions.className = 'settings-action-row';

      const up = document.createElement('button');
      up.type = 'button';
      up.className = 'button settings-secondary';
      up.textContent = 'Move up';
      up.disabled = index === 0;

      const down = document.createElement('button');
      down.type = 'button';
      down.className = 'button settings-secondary';
      down.textContent = 'Move down';
      down.disabled = index === feedState.length - 1;

      actions.append(up, down);
      if (!feed.builtIn) {
        const check = document.createElement('button');
        check.type = 'button';
        check.className = 'button settings-secondary';
        check.textContent = feed.validating ? 'Checking…' : 'Check feed';
        check.disabled = feed.validating === true;
        check.addEventListener('click', () => validateCustomFeed(feed));
        actions.appendChild(check);

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'button settings-secondary';
        remove.textContent = 'Remove';
        remove.disabled = feed.validating === true;
        remove.addEventListener('click', () => removeFeed(feed.id));
        actions.appendChild(remove);
      }

      enabledInput.addEventListener('change', () => {
        if (!enabledInput.checked && feed.enabled && enabledFeeds().length === 1) {
          enabledInput.checked = true;
          setEditorMessage('At least one BBC News section must remain enabled.');
          return;
        }
        feed.enabled = enabledInput.checked;
        normaliseDefault();
        renderAllFeedControls();
        markDirty();
      });
      labelInput.addEventListener('input', () => {
        feed.label = labelInput.value;
        title.textContent = displayLabel(feed);
        renderSections();
        markDirty();
      });
      if (!feed.builtIn) {
        urlInput.addEventListener('input', () => {
          feed.url = urlInput.value.trim();
          if (feed.validatedUrl !== feed.url) feed.validatedUrl = '';
          source.textContent = 'Custom BBC News feed · check required';
          markDirty();
        });
      }
      up.addEventListener('click', () => moveFeed(feed.id, -1));
      down.addEventListener('click', () => moveFeed(feed.id, 1));

      card.append(heading, fields, actions);
      advancedFeedMount.appendChild(card);
    });

    if (addFeedButton) addFeedButton.disabled = feedState.filter((feed) => !feed.builtIn).length >= MAX_CUSTOM_FEEDS;
  }

  function renderAllFeedControls() {
    renderSections();
    renderAdvancedEditor();
  }

  function statusLabel(status) {
    return ({
      ready: 'News ready',
      degraded: 'Cached news',
      stale: 'Stale cache',
      error: 'BBC unavailable',
      empty: 'Waiting for news',
    })[String(status || '').toLowerCase()] || String(status || 'Waiting');
  }

  function renderStatus() {
    const status = window.ACPUnifiedSettings?.getSnapshot?.()?.status?.news || {};
    if (statusChip) {
      statusChip.textContent = statusLabel(status.status);
      statusChip.classList.toggle('is-warning', ['degraded', 'stale', 'error'].includes(String(status.status || '').toLowerCase()));
    }
    if (statusMessage) {
      const when = status.last_attempt_at && window.ACPTime?.formatDateTime
        ? window.ACPTime.formatDateTime(status.last_attempt_at, { seconds: false })
        : status.last_attempt_at;
      statusMessage.textContent = status.stale
        ? `The appliance is showing its last successful BBC News cache${when ? `; last checked ${when}` : ''}.`
        : when
          ? `BBC News cache last checked ${when}.`
          : 'No BBC News refresh has completed yet.';
    }
  }

  function apply(config) {
    const value = config && typeof config === 'object' ? config : {};
    const custom = Array.isArray(value.custom_feeds) ? value.custom_feeds : [];
    const labels = value.feed_labels && typeof value.feed_labels === 'object' ? value.feed_labels : {};
    const enabled = new Set(
      Array.isArray(value.enabled_categories) && value.enabled_categories.length
        ? value.enabled_categories
        : DEFAULT_ENABLED
    );

    const byId = new Map();
    BUILT_IN_FEEDS.forEach((feed) => {
      byId.set(feed.id, {
        id: feed.id,
        label: clean(labels[feed.id]) || feed.label,
        url: feed.url,
        builtIn: true,
        enabled: enabled.has(feed.id),
      });
    });
    custom.forEach((feed) => {
      const id = clean(feed?.id).toLowerCase();
      if (!id || byId.has(id)) return;
      const url = clean(feed?.url);
      byId.set(id, {
        id,
        label: clean(feed?.label),
        url,
        validatedUrl: url,
        isNew: false,
        validating: false,
        builtIn: false,
        enabled: enabled.has(id),
      });
    });

    const order = Array.isArray(value.feed_order) ? value.feed_order : [];
    const arranged = [];
    order.forEach((rawId) => {
      const id = clean(rawId).toLowerCase();
      const feed = byId.get(id);
      if (!feed || arranged.some((item) => item.id === id)) return;
      arranged.push(feed);
    });
    byId.forEach((feed) => {
      if (!arranged.some((item) => item.id === feed.id)) arranged.push(feed);
    });

    applying = true;
    feedState = arranged;
    defaultCategory = enabled.has(value.default_category) ? value.default_category : enabledFeeds()[0]?.id || 'top';
    showSummaries.checked = value.show_summaries !== false;
    tickerEnabled.checked = value.ticker?.enabled !== false;
    tickerSpeed.value = ['slow', 'normal', 'fast'].includes(value.ticker?.speed) ? value.ticker.speed : 'normal';
    tickerSpeed.disabled = !tickerEnabled.checked;
    renderAllFeedControls();
    applying = false;
    window.setTimeout(renderStatus, 0);
  }

  function get() {
    normaliseDefault();
    const feedLabels = {};
    const customFeeds = [];

    feedState.forEach((feed) => {
      if (feed.builtIn) {
        const original = builtInById.get(feed.id)?.label || feed.id;
        const label = clean(feed.label);
        if (label && label !== original) feedLabels[feed.id] = label;
      } else {
        const url = clean(feed.url);
        if (!url || feed.validatedUrl !== url) {
          throw new Error(`Check the custom BBC feed “${displayLabel(feed)}” before saving.`);
        }
        const label = clean(feed.label);
        if (!label) throw new Error('Every custom BBC feed needs a display name.');
        customFeeds.push({
          id: feed.id,
          label,
          url,
        });
      }
    });

    return {
      enabled_categories: enabledFeeds().map((feed) => feed.id),
      default_category: defaultCategory,
      feed_order: feedState.map((feed) => feed.id),
      feed_labels: feedLabels,
      custom_feeds: customFeeds,
      show_summaries: showSummaries.checked,
      ticker: {
        enabled: tickerEnabled.checked,
        speed: tickerSpeed.value,
      },
    };
  }

  defaultSelect.addEventListener('change', () => {
    defaultCategory = defaultSelect.value;
    markDirty();
  });
  showSummaries.addEventListener('change', markDirty);
  tickerEnabled.addEventListener('change', () => {
    tickerSpeed.disabled = !tickerEnabled.checked;
    markDirty();
  });
  tickerSpeed.addEventListener('change', markDirty);
  window.addEventListener('acp:clock-format-changed', renderStatus);

  addFeedButton?.addEventListener('click', () => {
    if (feedState.filter((feed) => !feed.builtIn).length >= MAX_CUSTOM_FEEDS) {
      setEditorMessage(`No more than ${MAX_CUSTOM_FEEDS} custom BBC News feeds may be configured.`);
      return;
    }
    customCounter += 1;
    const id = `custom-${Date.now().toString(36)}-${customCounter.toString(36)}`;
    feedState.push({
      id,
      label: 'Custom BBC feed',
      url: '',
      validatedUrl: '',
      isNew: true,
      validating: false,
      builtIn: false,
      enabled: false,
    });
    renderAllFeedControls();
    setEditorMessage('Enter a BBC News RSS URL, use Check feed, then optionally rename or enable it before Save Changes.');
    markDirty();
  });

  function registerProvider() {
    if (!window.ACPUnifiedSettings?.registerDomain) {
      window.setTimeout(registerProvider, 0);
      return;
    }
    window.ACPUnifiedSettings.registerDomain('news', { apply, get });
    renderStatus();
  }

  window.setTimeout(registerProvider, 0);
})();
