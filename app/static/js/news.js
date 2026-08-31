(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'news') return;
  if (window.__aClockworkPlexNewsLoaded) return;
  window.__aClockworkPlexNewsLoaded = true;

  const API = '/api/news';
  const MAX_VISIBLE_STORIES = 24;
  const MAX_TICKER_STORIES = 12;
  const TICKER_PIXELS_PER_SECOND = Object.freeze({ slow: 30, normal: 45, fast: 65 });
  const SAFE_LOGO_SUFFIXES = ['bbc.co.uk', 'bbci.co.uk', 'bbcimg.co.uk', 'bbc.com'];

  const page = document.querySelector('.news-page');
  const categoryMount = document.querySelector('[data-news-categories]');
  const storyMount = document.querySelector('[data-news-stories]');
  const categoryTitle = document.querySelector('[data-news-category-title]');
  const statusPill = document.querySelector('[data-news-status]');
  const sourceTime = document.querySelector('[data-news-source-time]');
  const message = document.querySelector('[data-news-message]');
  const logo = document.querySelector('[data-news-logo]');
  const logoFallback = document.querySelector('[data-news-logo-fallback]');
  const ticker = document.querySelector('[data-news-ticker]');
  const tickerTrack = document.querySelector('[data-news-ticker-track]');
  const detail = document.querySelector('[data-news-detail]');
  const detailMeta = document.querySelector('[data-news-detail-meta]');
  const detailTitle = document.querySelector('[data-news-detail-title]');
  const detailSummary = document.querySelector('[data-news-detail-summary]');
  const detailClose = document.querySelector('[data-news-detail-close]');

  let snapshot = null;
  let activeCategory = null;
  let refreshTimer = null;
  let logoSource = '';

  function text(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
  }

  function categoryLabel(category) {
    const entry = snapshot?.category_catalogue?.find?.((item) => item?.id === category);
    return text(entry?.label) || text(snapshot?.categories?.[category]?.label) || category;
  }

  function storyKey(story) {
    return text(story?.title).toLocaleLowerCase('en-GB');
  }

  function uniqueStories(items, maximum) {
    const output = [];
    const seen = new Set();
    for (const item of Array.isArray(items) ? items : []) {
      if (!item || typeof item !== 'object' || !text(item.title)) continue;
      const key = storyKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      output.push(item);
      if (output.length >= maximum) break;
    }
    return output;
  }

  function formatDate(value) {
    if (!value) return '';
    if (window.ACPTime?.formatDateTime) {
      return window.ACPTime.formatDateTime(value, { seconds: false, weekday: 'short' });
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return text(value);
    return new Intl.DateTimeFormat('en-GB', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsed);
  }

  function safeLogoUrl(value) {
    try {
      const parsed = new URL(String(value || ''), window.location.href);
      const host = parsed.hostname.toLowerCase();
      if (parsed.protocol !== 'https:') return '';
      if (!SAFE_LOGO_SUFFIXES.some((suffix) => host === suffix || host.endsWith(`.${suffix}`))) return '';
      return parsed.href;
    } catch (error) {
      return '';
    }
  }

  function renderBrand() {
    const preferred = snapshot?.categories?.[activeCategory]?.feed?.feed_image_url;
    const fallbackCategory = Object.values(snapshot?.categories || {}).find((state) => state?.feed?.feed_image_url);
    const source = safeLogoUrl(preferred || fallbackCategory?.feed?.feed_image_url);
    if (!logo || !logoFallback) return;

    if (!source) {
      logo.hidden = true;
      logoFallback.hidden = false;
      logoSource = '';
      return;
    }

    logoFallback.hidden = true;
    logo.hidden = false;
    if (source !== logoSource) {
      logoSource = source;
      logo.src = source;
    }
  }

  function statusLabel(status) {
    return ({
      ready: 'News ready',
      degraded: 'Cached news',
      stale: 'Stale cache',
      error: 'BBC unavailable',
      empty: 'Waiting for news',
    })[String(status || '').toLowerCase()] || text(status) || 'Waiting';
  }

  function renderStatus() {
    const state = snapshot?.categories?.[activeCategory] || {};
    const overall = text(snapshot?.status || state.status || 'empty').toLowerCase();
    const warning = ['degraded', 'stale', 'error'].includes(overall) || state.stale === true;

    if (statusPill) {
      statusPill.textContent = statusLabel(overall);
      statusPill.classList.toggle('is-warning', warning);
    }

    const build = state?.feed?.last_build_at;
    if (sourceTime) sourceTime.textContent = build ? `BBC feed ${formatDate(build)}` : 'BBC News';

    if (message) {
      const error = text(state.last_error);
      message.hidden = !error;
      message.textContent = error ? `Using the last available BBC News data. ${error}` : '';
    }
  }

  function renderCategories() {
    if (!categoryMount) return;
    categoryMount.replaceChildren();
    const enabled = Array.isArray(snapshot?.settings?.enabled_categories)
      ? snapshot.settings.enabled_categories
      : [];

    enabled.forEach((category) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'news-category-button';
      button.dataset.newsCategory = category;
      button.textContent = categoryLabel(category);
      if (category === activeCategory) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', () => {
        activeCategory = category;
        render();
      });
      categoryMount.appendChild(button);
    });
  }

  function storyMeta(story) {
    const parts = [categoryLabel(story?.category || activeCategory)];
    const published = formatDate(story?.published_at);
    if (published) parts.push(published);
    return parts.join(' · ');
  }

  function openDetail(story) {
    if (!detail || !detailTitle || !detailSummary || !detailMeta) return;
    detailMeta.textContent = storyMeta(story);
    detailTitle.textContent = text(story.title) || 'BBC News story';
    detailSummary.textContent = text(story.summary) || 'No additional feed summary is available for this story.';
    detail.hidden = false;
    detailClose?.focus?.({ preventScroll: true });
  }

  function closeDetail() {
    if (detail) detail.hidden = true;
  }

  function renderStories() {
    if (!storyMount) return;
    storyMount.replaceChildren();
    const state = snapshot?.categories?.[activeCategory] || {};
    const stories = uniqueStories(state?.feed?.items, MAX_VISIBLE_STORIES);
    const showSummaries = snapshot?.settings?.show_summaries !== false;

    if (categoryTitle) categoryTitle.textContent = categoryLabel(activeCategory);

    if (!stories.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = state.last_error || 'No cached BBC News stories are available for this section yet.';
      storyMount.appendChild(empty);
      return;
    }

    stories.forEach((story) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'news-story-card';
      card.setAttribute('aria-label', `Open story details: ${text(story.title)}`);

      const meta = document.createElement('span');
      meta.className = 'news-story-meta';
      meta.textContent = storyMeta(story);

      const title = document.createElement('h2');
      title.textContent = text(story.title);

      card.append(meta, title);
      if (showSummaries && text(story.summary)) {
        const summary = document.createElement('p');
        summary.textContent = text(story.summary);
        card.appendChild(summary);
      }
      card.addEventListener('click', () => openDetail(story));
      storyMount.appendChild(card);
    });
  }

  function tickerSet(stories) {
    const set = document.createElement('div');
    set.className = 'news-ticker-set';
    stories.forEach((story) => {
      const item = document.createElement('span');
      item.className = 'news-ticker-item';
      item.textContent = text(story.title);
      set.appendChild(item);
    });
    return set;
  }

  function renderTicker() {
    if (!ticker || !tickerTrack) return;
    tickerTrack.replaceChildren();
    const enabled = snapshot?.settings?.ticker?.enabled === true && snapshot?.ticker?.enabled !== false;
    const stories = uniqueStories(snapshot?.ticker?.items, MAX_TICKER_STORIES);

    if (!enabled || !stories.length) {
      ticker.hidden = true;
      page?.classList.add('is-ticker-hidden');
      return;
    }

    ticker.hidden = false;
    page?.classList.remove('is-ticker-hidden');
    const first = tickerSet(stories);
    tickerTrack.appendChild(first);

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
    if (reducedMotion) return;

    tickerTrack.appendChild(tickerSet(stories));
    window.requestAnimationFrame(() => {
      const speedName = text(snapshot?.settings?.ticker?.speed || snapshot?.ticker?.speed || 'normal').toLowerCase();
      const pixelsPerSecond = TICKER_PIXELS_PER_SECOND[speedName] || TICKER_PIXELS_PER_SECOND.normal;
      const duration = Math.max(18, first.scrollWidth / pixelsPerSecond);
      tickerTrack.style.setProperty('--news-ticker-duration', `${duration.toFixed(2)}s`);
    });
  }

  function render() {
    if (!snapshot) return;
    const enabled = Array.isArray(snapshot?.settings?.enabled_categories)
      ? snapshot.settings.enabled_categories
      : [];
    if (!enabled.includes(activeCategory)) {
      activeCategory = enabled.includes(snapshot?.settings?.default_category)
        ? snapshot.settings.default_category
        : enabled[0] || null;
    }
    renderBrand();
    renderCategories();
    renderStatus();
    renderStories();
    renderTicker();
  }

  async function loadNews() {
    if (document.hidden) return;
    try {
      const response = await fetch(API, { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `BBC News returned HTTP ${response.status}.`);
      }
      snapshot = payload;
      render();
    } catch (error) {
      if (statusPill) {
        statusPill.textContent = 'News unavailable';
        statusPill.classList.add('is-warning');
      }
      if (message) {
        message.hidden = false;
        message.textContent = error.message || 'Could not read the local BBC News cache.';
      }
    }
  }

  logo?.addEventListener('error', () => {
    logo.hidden = true;
    if (logoFallback) logoFallback.hidden = false;
  });
  detailClose?.addEventListener('click', closeDetail);
  detail?.addEventListener('click', (event) => {
    if (event.target === detail) closeDetail();
  });
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && detail && !detail.hidden) closeDetail();
  });
  window.addEventListener('acp:clock-format-changed', render);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void loadNews();
  });
  window.addEventListener('pagehide', () => window.clearInterval(refreshTimer));

  void loadNews();
  refreshTimer = window.setInterval(loadNews, 60000);
})();
