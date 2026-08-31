(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsNewsLoaded) return;
  window.__aClockworkPlexSettingsNewsLoaded = true;

  const CATEGORY_ORDER = Object.freeze([
    ['top', 'Top Stories'],
    ['uk', 'UK'],
    ['world', 'World'],
    ['science', 'Science'],
    ['technology', 'Technology'],
  ]);

  const sidebar = document.querySelector('.settings-sidebar-list');
  const detail = document.querySelector('.settings-detail');
  if (!sidebar || !detail) return;

  const button = document.createElement('button');
  button.className = 'settings-sidebar-row';
  button.type = 'button';
  button.dataset.settingsSectionTarget = 'news';
  button.innerHTML = '<span><strong>News</strong><small>Categories and ticker</small></span><span class="settings-dirty-dot" aria-label="Unsaved changes" hidden></span><span class="settings-chevron" aria-hidden="true">›</span>';

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
        <span><strong>Sections</strong><small>Enabled categories and the default News section</small></span><span>›</span>
      </button>
      <button class="settings-subpage-row" type="button" data-settings-subpage-target="news:presentation">
        <span><strong>Presentation</strong><small>Story summaries and Top Stories ticker</small></span><span>›</span>
      </button>
    </div>
    <section class="settings-subpage" data-settings-subpage="news:sections" hidden>
      <button class="settings-back" type="button" data-settings-back="news">‹ News</button>
      <section class="settings-card">
        <h3>Sections</h3>
        <p class="muted small">Enabled sections appear in the News page's left-hand menu. At least one section must remain enabled.</p>
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
            <small>The ticker always uses the leading cached Top Stories, independent of the section being viewed.</small>
          </label>
        </div>
      </section>
    </section>
  `;

  const alarmsPanel = detail.querySelector('[data-settings-section="alarms"]');
  if (alarmsPanel) detail.insertBefore(panel, alarmsPanel);
  else detail.appendChild(panel);

  const categoriesMount = panel.querySelector('[data-news-category-controls]');
  const defaultSelect = panel.querySelector('[data-news-default-category]');
  const showSummaries = panel.querySelector('[data-news-show-summaries]');
  const tickerEnabled = panel.querySelector('[data-news-ticker-enabled]');
  const tickerSpeed = panel.querySelector('[data-news-ticker-speed]');
  const statusChip = panel.querySelector('[data-news-settings-status]');
  const statusMessage = panel.querySelector('[data-news-settings-message]');
  let applying = false;

  CATEGORY_ORDER.forEach(([id, label]) => {
    const wrapper = document.createElement('label');
    wrapper.className = 'setting-toggle';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.dataset.newsCategory = id;
    const copy = document.createElement('span');
    copy.textContent = label;
    wrapper.append(input, copy);
    categoriesMount.appendChild(wrapper);

    const option = document.createElement('option');
    option.value = id;
    option.textContent = label;
    defaultSelect.appendChild(option);
  });

  const categoryInputs = [...panel.querySelectorAll('[data-news-category]')];

  function enabledCategories() {
    return categoryInputs.filter((input) => input.checked).map((input) => input.dataset.newsCategory);
  }

  function updateDependentControls() {
    const enabled = enabledCategories();
    [...defaultSelect.options].forEach((option) => {
      option.disabled = !enabled.includes(option.value);
    });
    if (!enabled.includes(defaultSelect.value)) defaultSelect.value = enabled[0] || 'top';
    tickerSpeed.disabled = !tickerEnabled.checked;
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
    const enabled = Array.isArray(value.enabled_categories) && value.enabled_categories.length
      ? value.enabled_categories
      : CATEGORY_ORDER.map(([id]) => id);
    applying = true;
    categoryInputs.forEach((input) => { input.checked = enabled.includes(input.dataset.newsCategory); });
    defaultSelect.value = enabled.includes(value.default_category) ? value.default_category : enabled[0];
    showSummaries.checked = value.show_summaries !== false;
    tickerEnabled.checked = value.ticker?.enabled !== false;
    tickerSpeed.value = ['slow', 'normal', 'fast'].includes(value.ticker?.speed) ? value.ticker.speed : 'normal';
    updateDependentControls();
    applying = false;
    window.setTimeout(renderStatus, 0);
  }

  function get() {
    const enabled = enabledCategories();
    return {
      enabled_categories: enabled,
      default_category: enabled.includes(defaultSelect.value) ? defaultSelect.value : enabled[0],
      show_summaries: showSummaries.checked,
      ticker: {
        enabled: tickerEnabled.checked,
        speed: tickerSpeed.value,
      },
    };
  }

  function markDirty() {
    if (applying) return;
    window.ACPUnifiedSettings?.markDirty?.('news');
  }

  categoryInputs.forEach((input) => input.addEventListener('change', () => {
    if (!input.checked && enabledCategories().length === 0) {
      applying = true;
      input.checked = true;
      applying = false;
      if (statusMessage) statusMessage.textContent = 'At least one BBC News section must remain enabled.';
      return;
    }
    updateDependentControls();
    markDirty();
  }));
  defaultSelect.addEventListener('change', markDirty);
  showSummaries.addEventListener('change', markDirty);
  tickerEnabled.addEventListener('change', () => {
    updateDependentControls();
    markDirty();
  });
  tickerSpeed.addEventListener('change', markDirty);
  window.addEventListener('acp:clock-format-changed', renderStatus);

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
