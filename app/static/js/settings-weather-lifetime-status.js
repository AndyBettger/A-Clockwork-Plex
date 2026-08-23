(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const card = document.querySelector('[data-rainfall-settings]');
  const grid = card?.querySelector('.settings-grid.two-col');
  if (!card || !grid || card.querySelector('[data-rainfall-lifetime-block]')) return;

  const periodField = card.querySelector('[data-rainfall-period]')?.closest('.setting-field');
  const periodLabel = periodField?.querySelector('span');
  if (periodLabel) periodLabel.textContent = 'Selected period';

  const block = document.createElement('div');
  block.className = 'setting-field wide';
  block.dataset.rainfallLifetimeBlock = 'true';
  block.innerHTML = `
    <span>Full station history</span>
    <strong data-rainfall-lifetime-status>Checking…</strong>
    <small data-rainfall-lifetime-message>Backfills automatically in the background, independently of the selected rainfall period.</small>`;
  grid.appendChild(block);

  const status = block.querySelector('[data-rainfall-lifetime-status]');
  const message = block.querySelector('[data-rainfall-lifetime-message]');
  let timer = null;

  function formatDate(value) {
    const text = String(value || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
    const parsed = new Date(`${text}T00:00:00`);
    return Number.isNaN(parsed.getTime()) ? text : parsed.toLocaleDateString();
  }

  function render(payload = {}) {
    const state = String(payload.status || 'pending');
    const firstRecord = formatDate(payload.first_record_date);
    const availableDays = Number(payload.available_days || 0);
    const missingDays = Number(payload.missing_days || 0);
    const labels = {
      ready: 'Full history ready',
      backfilling: 'Backfilling full history',
      pending: 'Waiting to backfill',
      configuration_required: 'Station required',
      credentials_required: 'Credentials required',
      error: 'Full history error',
    };
    status.textContent = labels[state] || state || 'Checking…';

    if (payload.last_error) {
      message.textContent = payload.last_error;
      return;
    }
    if (state === 'configuration_required') {
      message.textContent = 'Add a Weather Underground station ID to build the full station rainfall archive.';
      return;
    }
    if (state === 'credentials_required') {
      message.textContent = 'Add the write-only Weather Underground API key to build the full station rainfall archive.';
      return;
    }
    if (state === 'backfilling' && payload.discovery_complete !== true) {
      message.textContent = firstRecord
        ? `Searching backwards for the station's first Weather Underground record; earliest found so far is ${firstRecord}. This continues independently of the selected rainfall period.`
        : `Searching backwards for the station's first Weather Underground record. This continues independently of the selected rainfall period.`;
      return;
    }
    if (state === 'backfilling') {
      message.textContent = firstRecord
        ? `First station record found at ${firstRecord}; filling the remaining older daily totals. This continues independently of the selected rainfall period.`
        : `Filling the full station archive. This continues independently of the selected rainfall period.`;
      return;
    }
    if (state === 'ready') {
      const coverage = firstRecord ? ` from ${firstRecord}` : '';
      const gaps = missingDays > 0
        ? ` · ${missingDays} confirmed day${missingDays === 1 ? '' : 's'} had no station data`
        : '';
      message.textContent = `Full station history ready${coverage} · ${availableDays} recorded day${availableDays === 1 ? '' : 's'}${gaps}. It is independent of the selected rainfall period.`;
      return;
    }
    message.textContent = 'Full station history backfills automatically in the background, independently of the selected rainfall period.';
  }

  async function refresh() {
    if (document.visibilityState === 'hidden') return;
    try {
      const response = await fetch('/api/weather/rainfall/lifetime', {
        cache: 'no-store',
        credentials: 'same-origin',
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `Request failed with HTTP ${response.status}.`);
      render(payload);
    } catch (error) {
      render({ status: 'error', last_error: error.message || 'Could not read full station rainfall history status.' });
    }
  }

  refresh();
  timer = window.setInterval(refresh, 15000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') refresh();
  });
  window.addEventListener('pagehide', () => {
    if (timer !== null) window.clearInterval(timer);
    timer = null;
  }, { once: true });
})();
