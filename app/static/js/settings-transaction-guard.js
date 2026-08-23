(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsTransactionGuardLoaded) return;
  window.__aClockworkPlexSettingsTransactionGuardLoaded = true;

  const form = document.getElementById('settings-unified-form');
  const originalFetch = window.fetch.bind(window);
  let activeTransactions = 0;

  function isSettingsWrite(input, options = {}) {
    const url = typeof input === 'string' ? input : input?.url;
    const method = String(options.method || input?.method || 'GET').toUpperCase();
    if (method !== 'POST') return false;
    try {
      return new URL(url, window.location.href).pathname === '/api/settings';
    } catch (error) {
      return false;
    }
  }

  function paint() {
    const active = activeTransactions > 0;
    document.body.classList.toggle('settings-transaction-active', active);
    form?.setAttribute('aria-busy', active ? 'true' : 'false');
    if (!active) form?.removeAttribute('aria-busy');
  }

  window.fetch = async function guardedSettingsFetch(input, options = {}) {
    if (!isSettingsWrite(input, options)) {
      return originalFetch(input, options);
    }
    activeTransactions += 1;
    paint();
    try {
      return await originalFetch(input, options);
    } finally {
      activeTransactions = Math.max(0, activeTransactions - 1);
      paint();
    }
  };

  form?.addEventListener('submit', (event) => {
    if (activeTransactions < 1) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
})();