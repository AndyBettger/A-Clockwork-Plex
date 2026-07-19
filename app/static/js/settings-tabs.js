(() => {
  const tabList = document.querySelector('[data-settings-tabs]');
  const tabs = [...document.querySelectorAll('[data-settings-tab]')];
  const panels = [...document.querySelectorAll('[data-settings-panel]')];
  if (!tabList || !tabs.length || !panels.length) {
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
})();
