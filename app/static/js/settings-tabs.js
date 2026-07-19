(() => {
  const tabList = document.querySelector('[data-settings-tabs]');
  const settingsForm = document.querySelector('.settings-form');
  if (!tabList || !settingsForm) {
    return;
  }

  function ensureAudioWorkspace() {
    if (!document.querySelector('[data-settings-tab="audio"]')) {
      const tab = document.createElement('button');
      tab.className = 'settings-tab';
      tab.type = 'button';
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', 'false');
      tab.setAttribute('aria-controls', 'settings-panel-audio');
      tab.tabIndex = -1;
      tab.dataset.settingsTab = 'audio';
      tab.textContent = 'Audio';
      const plexampTab = document.querySelector('[data-settings-tab="plexamp"]');
      tabList.insertBefore(tab, plexampTab || null);
    }

    if (!document.querySelector('[data-settings-panel="audio"]')) {
      const panel = document.createElement('div');
      panel.className = 'settings-tab-panel';
      panel.id = 'settings-panel-audio';
      panel.setAttribute('role', 'tabpanel');
      panel.dataset.settingsPanel = 'audio';
      panel.hidden = true;
      panel.innerHTML = `
        <section class="settings-card is-intro">
          <div class="settings-card-heading">
            <h2>Audio</h2>
            <span class="settings-chip">Shared mixer</span>
          </div>
          <p class="muted small">Persistent output trims and starting levels. Open Audio in the bottom drawer for immediate player-aware adjustments.</p>
        </section>
      `;
      const plexampPanel = document.querySelector('[data-settings-panel="plexamp"]');
      settingsForm.insertBefore(panel, plexampPanel || settingsForm.querySelector('.settings-actions'));
    }
  }

  ensureAudioWorkspace();

  const tabs = [...document.querySelectorAll('[data-settings-tab]')];
  const panels = [...document.querySelectorAll('[data-settings-panel]')];
  if (!tabs.length || !panels.length) {
    return;
  }

  const STORAGE_KEY = 'a-clockwork-plex.settings-tab';
  const panelIds = new Set(panels.map((panel) => panel.dataset.settingsPanel));

  function normaliseTab(value) {
    const tab = String(value || '').replace(/^#/, '').trim().toLowerCase();
    return panelIds.has(tab) ? tab : 'general';
  }

  function storedTab() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function rememberTab(tabId) {
    try {
      window.localStorage.setItem(STORAGE_KEY, tabId);
    } catch (error) {
    }
  }

  function activate(tabId, options = {}) {
    const activeId = normaliseTab(tabId);

    tabs.forEach((tab) => {
      const selected = tab.dataset.settingsTab === activeId;
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      tab.tabIndex = selected ? 0 : -1;
      if (selected && options.focus) {
        tab.focus({ preventScroll: true });
      }
    });

    panels.forEach((panel) => {
      panel.hidden = panel.dataset.settingsPanel !== activeId;
    });

    rememberTab(activeId);
    if (!options.skipHash) {
      const nextUrl = `${window.location.pathname}${window.location.search}#${activeId}`;
      window.history.replaceState(null, '', nextUrl);
    }

    const activeTab = tabs.find((tab) => tab.dataset.settingsTab === activeId);
    activeTab?.scrollIntoView({ behavior: options.instant ? 'auto' : 'smooth', block: 'nearest', inline: 'center' });
    window.requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activate(tab.dataset.settingsTab));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
        return;
      }
      event.preventDefault();

      let nextIndex = index;
      if (event.key === 'ArrowLeft') {
        nextIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (event.key === 'ArrowRight') {
        nextIndex = (index + 1) % tabs.length;
      } else if (event.key === 'Home') {
        nextIndex = 0;
      } else if (event.key === 'End') {
        nextIndex = tabs.length - 1;
      }
      activate(tabs[nextIndex].dataset.settingsTab, { focus: true });
    });
  });

  window.addEventListener('hashchange', () => activate(window.location.hash, { skipHash: true }));

  const initialTab = window.location.hash || storedTab() || 'general';
  activate(initialTab, { skipHash: !window.location.hash, instant: true });

  // Alarm and Audio workspaces are split into smaller scripts so the large
  // editor remains usable on older installations during development.
  [
    '/static/js/settings-alarm-scheduler.js',
    '/static/js/settings-alarm-audio.js',
    '/static/js/settings-audio-workspace.js',
    '/static/js/settings-airplay-defaults.js',
  ].forEach((source) => {
    if (document.querySelector(`script[src="${source}"]`)) {
      return;
    }
    const script = document.createElement('script');
    script.src = source;
    script.async = false;
    document.body.appendChild(script);
  });
})();
