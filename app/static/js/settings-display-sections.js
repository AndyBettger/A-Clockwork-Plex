(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexDisplaySectionsLoaded) return;
  window.__aClockworkPlexDisplaySectionsLoaded = true;

  const RETRY_MS = 80;
  const MAX_ATTEMPTS = 100;
  const TRANSITION_OPTIONS = [
    ['grow-fade', 'Grow and fade'],
    ['crossfade', 'Crossfade'],
    ['horizontal-slide', 'Horizontal slide'],
    ['vertical-lift', 'Vertical lift'],
    ['cover-reveal', 'Cover reveal'],
    ['zoom', 'Zoom'],
    ['blur-dissolve', 'Blur dissolve'],
    ['instant', 'Instant'],
  ];

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

  function restoreMotionControls(card) {
    const style = card.querySelector('[data-setting-path="display.transition_style"]');
    if (style) {
      const current = style.value;
      style.replaceChildren(...TRANSITION_OPTIONS.map(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        return option;
      }));
      if (TRANSITION_OPTIONS.some(([value]) => value === current)) style.value = current;
    }

    const duration = card.querySelector('[data-setting-path="display.transition_duration_ms"]');
    if (duration) {
      duration.type = 'range';
      duration.min = '0';
      duration.max = '2000';
      duration.step = '50';
      duration.removeAttribute('inputmode');
      duration.removeAttribute('data-keyboard');
      duration.setAttribute('aria-label', 'Transition duration in milliseconds');
    }
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
          <span>Night idle appearance</span>
          <select data-setting-path="display.night_dim_style" data-night-dim-style-setting>
            <option value="classic">Classic dim</option>
            <option value="astronomy">Astronomy red</option>
          </select>
          <small>The appearance used while the scheduled night display is resting.</small>
        </label>
        <label class="setting-field">
          <span>Night interaction appearance</span>
          <select data-setting-path="display.night_dim_active_style" data-night-dim-active-style-setting>
            <option value="same">Same as idle</option>
            <option value="classic">Classic dim</option>
            <option value="astronomy">Astronomy red</option>
          </select>
          <small>The night-safe appearance retained while touching Settings, Weather or Plexamp.</small>
        </label>
        <div class="setting-field wide">
          <span>Daytime theme</span>
          <strong>Classic dark</strong>
          <small>Additional daytime and accent themes are deliberately deferred until after the guarded production-EQ phase.</small>
        </div>
      </div>`;
    return card;
  }

  function applyNightStyles(idleSelect, activeSelect) {
    const status = window.ACPDisplayDimming?.status?.() || {};
    window.ACPDisplayDimming?.configure?.({
      ...status,
      style: idleSelect.value,
      activeStyle: activeSelect.value,
    });
  }

  function populateNightStyles(idleSelect, activeSelect, attempts = 80) {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    const display = snapshot?.settings?.display;
    if (display) {
      idleSelect.value = display.night_dim_style === 'astronomy' ? 'astronomy' : 'classic';
      activeSelect.value = ['classic', 'astronomy'].includes(display.night_dim_active_style)
        ? display.night_dim_active_style
        : 'same';
      applyNightStyles(idleSelect, activeSelect);
      return;
    }
    if (attempts > 0) window.setTimeout(() => populateNightStyles(idleSelect, activeSelect, attempts - 1), 100);
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

    restoreMotionControls(motionCard);

    const header = panel.querySelector('.settings-detail-header');
    const headerCopy = header?.querySelector('p');
    if (headerCopy) headerCopy.textContent = 'Clock presentation, night behaviour, theme and movement between appliance surfaces.';
    const sidebarCopy = document.querySelector('[data-settings-section-target="display"] small');
    if (sidebarCopy) sidebarCopy.textContent = 'Clock, night and theme';

    const overview = make('div', 'settings-subpage-overview');
    overview.dataset.settingsOverview = 'display';
    const rows = [
      row('display:clock', 'Clock', '12/24-hour presentation'),
      row('display:night', 'Night dimming', 'Idle and interaction brightness'),
      row('display:theme', 'Theme', 'Idle and interaction night appearance'),
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

    const idleSelect = panel.querySelector('[data-night-dim-style-setting]');
    const activeSelect = panel.querySelector('[data-night-dim-active-style-setting]');
    const apply = () => applyNightStyles(idleSelect, activeSelect);
    idleSelect?.addEventListener('input', apply);
    idleSelect?.addEventListener('change', apply);
    activeSelect?.addEventListener('input', apply);
    activeSelect?.addEventListener('change', apply);
    if (idleSelect && activeSelect) populateNightStyles(idleSelect, activeSelect);

    const route = location.hash.replace(/^#/, '');
    if (route.startsWith('display/')) {
      const key = `display:${route.split('/')[1]}`;
      if (panel.querySelector(`[data-settings-subpage="${key}"]`)) openSubpage(panel, overview, key);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => install(), { once: true });
  else install();
})();
