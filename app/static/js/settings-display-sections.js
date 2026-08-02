(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexDisplaySectionsLoaded) return;
  window.__aClockworkPlexDisplaySectionsLoaded = true;

  const RETRY_MS = 80;
  const MAX_ATTEMPTS = 100;

  function make(tag, className = '', text = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function findCard(panel, title) {
    return [...panel.querySelectorAll(':scope > .settings-card')]
      .find((card) => card.querySelector('h3')?.textContent.trim() === title);
  }

  function openSubpage(panel, overview, key) {
    overview.hidden = true;
    panel.querySelectorAll('[data-settings-subpage^="display:"]').forEach((page) => {
      page.hidden = page.dataset.settingsSubpage !== key;
    });
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    history.replaceState(null, '', `#display/${key.split(':')[1]}`);
  }

  function closeSubpage(panel, overview) {
    overview.hidden = false;
    panel.querySelectorAll('[data-settings-subpage^="display:"]').forEach((page) => {
      page.hidden = true;
    });
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    history.replaceState(null, '', '#display');
  }

  function row(key, title, copy) {
    const button = make('button', 'settings-subpage-row');
    button.type = 'button';
    button.dataset.settingsSubpageTarget = key;
    const text = make('span');
    text.append(make('strong', '', title), make('small', '', copy));
    button.append(text, make('span', '', '›'));
    return button;
  }

  function subpage(key, card) {
    const section = make('section', 'settings-subpage');
    section.dataset.settingsSubpage = key;
    section.hidden = true;
    const back = make('button', 'settings-back', '‹ Display');
    back.type = 'button';
    back.dataset.settingsBack = 'display';
    section.append(back, card);
    return section;
  }

  function themeCard() {
    const card = make('section', 'settings-card');
    card.innerHTML = `
      <h3>Theme</h3>
      <div class="settings-grid two-col">
        <label class="setting-field">
          <span>Night appearance</span>
          <select data-setting-path="display.night_dim_style" data-night-dim-style-setting>
            <option value="classic">Classic dim</option>
            <option value="astronomy">Astronomy red</option>
          </select>
          <small>Classic preserves the normal colours under a dark overlay. Astronomy converts the dashboard to grayscale and applies a pure-red multiply layer.</small>
        </label>
        <div class="setting-field">
          <span>Daytime theme</span>
          <strong>Classic dark</strong>
          <small>Additional daytime and accent themes are deliberately deferred until after the guarded production-EQ phase.</small>
        </div>
      </div>`;
    return card;
  }

  function applyNightStyle(select) {
    const status = window.ACPDisplayDimming?.status?.() || {};
    window.ACPDisplayDimming?.configure?.({ ...status, style: select.value });
  }

  function populateNightStyle(select, attempts = 80) {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    const value = snapshot?.settings?.display?.night_dim_style;
    if (value) {
      select.value = value === 'astronomy' ? 'astronomy' : 'classic';
      applyNightStyle(select);
      return;
    }
    if (attempts > 0) window.setTimeout(() => populateNightStyle(select, attempts - 1), 100);
  }

  function install(attempt = 0) {
    const panel = document.querySelector('[data-settings-section="display"]');
    const nightCard = panel?.querySelector('[data-night-dimming-settings]');
    const clockCard = panel ? findCard(panel, 'Clock') : null;
    const motionCard = panel ? findCard(panel, 'Motion') : null;
    if (!panel || !nightCard || !clockCard || !motionCard) {
      if (attempt < MAX_ATTEMPTS) window.setTimeout(() => install(attempt + 1), RETRY_MS);
      return;
    }
    if (panel.dataset.displaySectionsReady === 'true') return;
    panel.dataset.displaySectionsReady = 'true';

    const header = panel.querySelector('.settings-detail-header');
    const headerCopy = header?.querySelector('p');
    if (headerCopy) headerCopy.textContent = 'Clock presentation, night behaviour, theme and movement between appliance surfaces.';
    const sidebarCopy = document.querySelector('[data-settings-section-target="display"] small');
    if (sidebarCopy) sidebarCopy.textContent = 'Clock, night and theme';

    const overview = make('div', 'settings-subpage-overview');
    overview.dataset.settingsOverview = 'display';
    const rows = [
      row('display:clock', 'Clock', '12/24-hour presentation'),
      row('display:night', 'Night dimming', 'Schedule, brightness and wake behaviour'),
      row('display:theme', 'Theme', 'Classic or astronomy night appearance'),
      row('display:motion', 'Motion', 'Transition style and duration'),
    ];
    overview.append(...rows);

    const pages = [
      subpage('display:clock', clockCard),
      subpage('display:night', nightCard),
      subpage('display:theme', themeCard()),
      subpage('display:motion', motionCard),
    ];

    header?.insertAdjacentElement('afterend', overview);
    pages.forEach((page) => panel.appendChild(page));

    rows.forEach((button) => {
      button.addEventListener('click', () => openSubpage(panel, overview, button.dataset.settingsSubpageTarget));
    });
    pages.forEach((page) => {
      page.querySelector('[data-settings-back="display"]')?.addEventListener('click', () => closeSubpage(panel, overview));
    });

    const styleSelect = panel.querySelector('[data-night-dim-style-setting]');
    styleSelect?.addEventListener('input', () => applyNightStyle(styleSelect));
    styleSelect?.addEventListener('change', () => applyNightStyle(styleSelect));
    if (styleSelect) populateNightStyle(styleSelect);

    const route = location.hash.replace(/^#/, '');
    if (route.startsWith('display/')) {
      const key = `display:${route.split('/')[1]}`;
      if (panel.querySelector(`[data-settings-subpage="${key}"]`)) openSubpage(panel, overview, key);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => install(), { once: true });
  else install();
})();
