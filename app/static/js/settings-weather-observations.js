(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const form = document.getElementById('settings-unified-form');
  const provider = document.querySelector('[data-setting-path="weather.observations.provider"]');
  const panels = [...document.querySelectorAll('[data-observation-provider-panel]')];
  const ecowittPanel = document.querySelector('[data-observation-provider-panel="ecowitt_push"]');
  const wuPanel = document.querySelector('[data-observation-provider-panel="weather_underground"]');
  const statusChip = document.querySelector('[data-observation-status]');
  const statusMessage = document.querySelector('[data-observation-message]');
  if (!form || !provider) return;

  let lastRevision = null;
  let credentialConfigured = false;
  let rainfallPeriod = null;
  let rainfallChip = null;
  let rainfallMessage = null;

  function installWeatherSourcePage() {
    const overview = document.querySelector('[data-settings-overview="weather"]');
    const stationPage = document.querySelector('[data-settings-subpage="weather:station"]');
    const stationRow = document.querySelector('[data-settings-subpage-target="weather:station"]');
    const sourceCard = provider.closest('.settings-card');
    if (!overview || !stationPage || !stationRow || !sourceCard || document.querySelector('[data-settings-subpage="weather:source"]')) return;

    document.querySelectorAll('[data-settings-subpage="weather:forecast"] .muted.small').forEach((copy) => {
      copy.textContent = copy.textContent.replace('selected under Station', 'selected under Observation source');
    });

    stationRow.querySelector('strong').textContent = 'Station';
    const stationDescription = stationRow.querySelector('small');
    if (stationDescription) stationDescription.textContent = 'Dashboard labels and refresh';

    sourceCard.classList.add('weather-observation-source-card');

    const sourceRow = document.createElement('button');
    sourceRow.className = 'settings-subpage-row';
    sourceRow.type = 'button';
    sourceRow.dataset.settingsSubpageTarget = 'weather:source';
    sourceRow.innerHTML = '<span><strong>Observation source</strong><small>Live provider, WU history and source health</small></span><span>›</span>';
    overview.insertBefore(sourceRow, stationRow);

    const sourcePage = document.createElement('section');
    sourcePage.className = 'settings-subpage weather-settings-source';
    sourcePage.dataset.settingsSubpage = 'weather:source';
    sourcePage.hidden = true;
    sourcePage.innerHTML = '<button class="settings-back" type="button" data-weather-source-back>‹ Weather</button>';
    stationPage.parentNode.insertBefore(sourcePage, stationPage);

    sourcePage.appendChild(sourceCard);

    const rainfallCard = document.createElement('section');
    rainfallCard.className = 'settings-card weather-rainfall-card';
    rainfallCard.dataset.rainfallSettings = 'true';
    rainfallCard.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h3>Historical rainfall</h3>
          <p class="muted small">Completed days come from Weather Underground daily history; today always comes from the live station reading.</p>
        </div>
        <span class="settings-chip" data-rainfall-status>Checking…</span>
      </div>
      <div class="settings-grid two-col">
        <label class="setting-field">
          <span>Rainfall period</span>
          <select data-setting-path="weather.historical_rainfall.period" data-rainfall-period>
            <option value="today">Today</option>
            <option value="last_7_days">Last 7 days</option>
            <option value="current_month">Current month</option>
            <option value="current_year">Current year</option>
          </select>
          <small>Valid daily totals are cached locally. A date omitted from a range is retried once on its own; confirmed station gaps are counted and the displayed total remains the minimum recorded.</small>
        </label>
        <div class="setting-field">
          <span>History source</span>
          <strong>Weather Underground PWS</strong>
          <small>Independent of the live observation provider. Today does not require a history request.</small>
        </div>
      </div>
      <p class="muted small" data-rainfall-message>Historical rainfall status will appear here.</p>`;
    sourcePage.appendChild(rainfallCard);
    rainfallPeriod = rainfallCard.querySelector('[data-rainfall-period]');
    rainfallChip = rainfallCard.querySelector('[data-rainfall-status]');
    rainfallMessage = rainfallCard.querySelector('[data-rainfall-message]');

    if (ecowittPanel) sourcePage.appendChild(ecowittPanel);
    if (wuPanel) {
      const heading = wuPanel.querySelector('h3');
      if (heading) heading.textContent = 'Weather Underground PWS / rainfall history';
      const note = document.createElement('p');
      note.className = 'muted small';
      note.dataset.wuHistoryNote = 'true';
      note.textContent = 'Station ID, timeout and the write-only API key are also used for historical rainfall, even when Ecowitt supplies live observations.';
      heading?.insertAdjacentElement('afterend', note);
      sourcePage.appendChild(wuPanel);
    }

    const style = document.createElement('style');
    style.textContent = `
      [data-settings-section="weather"] .settings-subpage { gap: clamp(16px, 2.6vmin, 20px); }
      [data-settings-section="weather"] .settings-card { padding: clamp(12px, 2vmin, 18px); }
      [data-settings-section="weather"] .weather-settings-source { gap: clamp(20px, 3.2vmin, 24px); }
      [data-settings-section="weather"] .weather-settings-source .settings-card { margin-top: 0; }
      [data-settings-section="weather"] .weather-settings-source .settings-card-heading {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: start;
        gap: 10px clamp(14px, 2.4vmin, 18px);
        margin-bottom: clamp(14px, 2.4vmin, 18px);
      }
      [data-settings-section="weather"] .weather-settings-source .settings-card-heading > div { min-width: 0; }
      [data-settings-section="weather"] .weather-settings-source .settings-card-heading h3 { margin-bottom: 8px; }
      [data-settings-section="weather"] .weather-settings-source .settings-card-heading p { margin: 0; }
      [data-settings-section="weather"] .weather-settings-source .settings-chip {
        display: grid;
        place-items: center;
        align-self: start;
        justify-self: end;
        min-height: 38px;
        box-sizing: border-box;
        margin: 0;
        padding: 8px 13px;
        border: 1px solid rgba(143, 211, 255, 0.22);
        border-radius: 11px;
        color: var(--text);
        background: rgba(143, 211, 255, 0.085);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        font-family: var(--display-font);
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.025em;
        line-height: 1.1;
        white-space: nowrap;
      }
      [data-settings-section="weather"] .weather-settings-source .settings-chip.is-warning {
        border-color: rgba(255, 233, 156, 0.3);
        background: rgba(255, 233, 156, 0.09);
      }
      [data-settings-section="weather"] .weather-settings-source .settings-grid {
        column-gap: clamp(14px, 2.4vmin, 18px);
        row-gap: clamp(18px, 2.8vmin, 22px);
      }
      [data-settings-section="weather"] .weather-settings-source [data-observation-message],
      [data-settings-section="weather"] .weather-settings-source [data-rainfall-message] {
        display: block;
        margin: clamp(16px, 2.5vmin, 20px) 0 0;
        line-height: 1.4;
      }
      [data-settings-section="weather"] .weather-settings-source [data-wu-history-note] {
        margin: 0 0 clamp(16px, 2.5vmin, 20px);
        line-height: 1.4;
      }
      [data-settings-section="weather"] .weather-settings-source [data-wu-commissioning] {
        margin-top: clamp(18px, 2.8vmin, 22px);
      }
      [data-settings-section="weather"] .weather-settings-source [data-wu-commissioning] .settings-action-row {
        margin-top: clamp(16px, 2.5vmin, 20px);
      }
    `;
    document.head.appendChild(style);

    const openSource = () => {
      overview.hidden = true;
      document.querySelectorAll('[data-settings-section="weather"] [data-settings-subpage]').forEach((page) => {
        page.hidden = page !== sourcePage;
      });
      sourcePage.hidden = false;
      document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
      history.replaceState(null, '', '#weather/source');
    };
    const closeSource = () => {
      sourcePage.hidden = true;
      overview.hidden = false;
      history.replaceState(null, '', '#weather');
      document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    };
    sourceRow.addEventListener('click', openSource);
    sourcePage.querySelector('[data-weather-source-back]')?.addEventListener('click', closeSource);
    if (location.hash === '#weather/source') openSource();
  }

  function updatePanels() {
    const selected = provider.value || 'ecowitt_push';
    const historyNeedsWu = (rainfallPeriod?.value || 'last_7_days') !== 'today';
    panels.forEach((panel) => {
      if (panel === wuPanel) panel.hidden = selected !== 'weather_underground' && !historyNeedsWu;
      else panel.hidden = panel.dataset.observationProviderPanel !== selected;
    });
  }

  function renderStatus(status = {}) {
    const labels = {
      push: 'Ecowitt Push',
      ready: 'WU Ready',
      pending: 'Waiting',
      stale: 'Stale',
      degraded: 'Degraded',
      configuration_required: 'Setup required',
      credentials_required: 'Credentials required',
      error: 'Provider error',
    };
    const state = String(status.status || '');
    if (statusChip) {
      statusChip.textContent = labels[state] || 'Checking…';
      statusChip.classList.toggle(
        'is-warning',
        ['stale', 'degraded', 'configuration_required', 'credentials_required', 'error'].includes(state),
      );
    }
    if (!statusMessage) return;

    if (status.last_error) {
      statusMessage.textContent = status.last_error;
    } else if (state === 'push') {
      statusMessage.textContent = 'Waiting for observations on the configured Ecowitt custom-push endpoint.';
    } else if (state === 'credentials_required') {
      statusMessage.textContent = 'Set the Weather Underground API key below to finish commissioning.';
    } else if (state === 'pending') {
      statusMessage.textContent = 'Weather Underground is configured and waiting for its first observation.';
    } else if (status.last_observation_at) {
      statusMessage.textContent = `Last observation ${new Date(status.last_observation_at).toLocaleString()}`;
    } else {
      statusMessage.textContent = 'Observation provider status will appear here.';
    }
  }

  function renderRainfallStatus(status = {}) {
    if (!rainfallChip || !rainfallMessage) return;
    const state = String(status.status || 'pending');
    const complete = status.complete === true;
    const missingDays = Number(status.missing_days || 0);
    const pendingDays = Number(status.pending_days || 0);
    const labels = {
      ready: 'History ready',
      pending: 'Waiting',
      configuration_required: 'Station required',
      credentials_required: 'Credentials required',
      error: 'History error',
    };
    rainfallChip.textContent = labels[state] || state || 'Checking…';
    rainfallChip.classList.toggle('is-warning', state !== 'ready');
    if (status.last_error) {
      rainfallMessage.textContent = status.last_error;
    } else if (complete && status.period === 'today') {
      rainfallMessage.textContent = 'Today uses the current live station rainfall total; no historical API request is needed.';
    } else if (state === 'ready' && missingDays > 0) {
      rainfallMessage.textContent = `${status.available_days || 0} of ${status.required_days || 0} days recorded · ${missingDays} day${missingDays === 1 ? '' : 's'} had no station data. Total shown is the minimum recorded.`;
    } else if (state === 'ready' && pendingDays > 0) {
      rainfallMessage.textContent = `${pendingDays} day${pendingDays === 1 ? '' : 's'} still waiting for a usable reading; recorded days remain available.`;
    } else if (state === 'ready' && complete) {
      rainfallMessage.textContent = `${status.available_days || 0} day${status.available_days === 1 ? '' : 's'} recorded · ${status.cached_days || 0} completed day${status.cached_days === 1 ? '' : 's'} cached.`;
    } else {
      rainfallMessage.textContent = 'Historical rainfall will fill from cached daily Weather Underground totals.';
    }
  }

  function credentialElements() {
    return {
      input: wuPanel?.querySelector('[data-wu-api-key]'),
      label: wuPanel?.querySelector('[data-wu-credential-status]'),
      message: wuPanel?.querySelector('[data-wu-credential-message]'),
      save: wuPanel?.querySelector('[data-action="save-wu-api-key"]'),
      remove: wuPanel?.querySelector('[data-action="remove-wu-api-key"]'),
      test: wuPanel?.querySelector('[data-action="test-wu-connection"]'),
    };
  }

  function renderCredentialStatus(configured) {
    credentialConfigured = configured === true;
    const { label, save, remove } = credentialElements();
    if (label) label.textContent = credentialConfigured ? 'Configured' : 'Not configured';
    if (save) save.textContent = credentialConfigured ? 'Replace API key' : 'Set API key';
    if (remove) remove.disabled = !credentialConfigured;
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Request failed with HTTP ${response.status}.`);
    }
    return payload;
  }

  async function refreshRainfallStatus(force = false) {
    try {
      const payload = await requestJson(
        '/api/weather/rainfall',
        force ? { method: 'POST', body: '{}' } : {},
      );
      renderRainfallStatus(payload);
      return payload;
    } catch (error) {
      renderRainfallStatus({
        status: 'error',
        complete: false,
        last_error: error.message || 'Could not refresh historical rainfall status.',
      });
      return null;
    }
  }

  async function refreshCredentialStatus() {
    try {
      const payload = await requestJson('/api/weather/underground/credentials');
      renderCredentialStatus(payload.configured === true);
    } catch (error) {
      const { message } = credentialElements();
      if (message) message.textContent = error.message || 'Could not read credential status.';
    }
  }

  function installCredentialControls() {
    if (!wuPanel || wuPanel.querySelector('[data-wu-commissioning]')) return;

    const block = document.createElement('div');
    block.dataset.wuCommissioning = 'true';
    block.innerHTML = `
      <div class="settings-grid two-col">
        <label class="setting-field">
          <span>API key</span>
          <input type="password" autocomplete="new-password" spellcheck="false" data-wu-api-key>
          <small>The key is sent only to the local commissioning endpoint and is cleared from this field after submission.</small>
        </label>
        <div class="setting-field">
          <span>Credential status</span>
          <strong data-wu-credential-status>Checking…</strong>
          <small>The saved key is write-only and is never returned to the browser.</small>
        </div>
      </div>
      <div class="settings-action-row">
        <button class="button settings-secondary" type="button" data-action="save-wu-api-key">Set API key</button>
        <button class="button settings-secondary" type="button" data-action="remove-wu-api-key">Remove API key</button>
        <button class="button settings-secondary" type="button" data-action="test-wu-connection">Test connection</button>
        <span class="muted small" data-wu-credential-message></span>
      </div>`;
    wuPanel.appendChild(block);

    [...form.querySelectorAll('.setting-field')].forEach((field) => {
      const title = field.querySelector('span');
      if (title?.textContent?.trim() === 'Weather Underground API key' && !field.closest('[data-wu-commissioning]')) {
        const strong = field.querySelector('strong');
        const small = field.querySelector('small');
        if (strong) strong.textContent = 'Managed from this page';
        if (small) small.textContent = 'The saved key remains write-only and outside config.json.';
      }
    });

    const elements = credentialElements();
    elements.save?.addEventListener('click', async () => {
      const key = String(elements.input?.value || '');
      elements.message.textContent = '';
      try {
        const payload = await requestJson('/api/weather/underground/credentials', {
          method: 'POST',
          body: JSON.stringify({ api_key: key }),
        });
        if (elements.input) elements.input.value = '';
        renderCredentialStatus(payload.configured === true);
        elements.message.textContent = payload.message || 'API key saved.';
        await refreshRainfallStatus(true);
      } catch (error) {
        if (elements.input) elements.input.value = '';
        elements.message.textContent = error.message || 'Could not save API key.';
      }
    });

    elements.remove?.addEventListener('click', async () => {
      elements.message.textContent = '';
      try {
        const payload = await requestJson('/api/weather/underground/credentials', { method: 'DELETE' });
        if (elements.input) elements.input.value = '';
        renderCredentialStatus(false);
        elements.message.textContent = payload.message || 'API key removed.';
        await refreshRainfallStatus(true);
      } catch (error) {
        elements.message.textContent = error.message || 'Could not remove API key.';
      }
    });

    elements.test?.addEventListener('click', async () => {
      elements.message.textContent = 'Testing Weather Underground…';
      try {
        const payload = await requestJson('/api/weather/underground/test', {
          method: 'POST',
          body: '{}',
        });
        renderStatus(payload);
        elements.message.textContent = payload.message || 'Weather Underground connection succeeded.';
        await refreshRainfallStatus(true);
      } catch (error) {
        elements.message.textContent = error.message || 'Weather Underground connection test failed.';
      }
    });

    renderCredentialStatus(credentialConfigured);
    refreshCredentialStatus();
  }

  function syncFromSnapshot() {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    if (!snapshot) return false;
    const savedPeriod = snapshot.settings?.weather?.historical_rainfall?.period;
    if (rainfallPeriod && savedPeriod && !form.matches(':focus-within')) rainfallPeriod.value = savedPeriod;
    updatePanels();
    if (snapshot.revision !== lastRevision) {
      lastRevision = snapshot.revision;
      renderStatus(snapshot.status?.weather_observations || {});
    }
    return true;
  }

  function waitForInitialSnapshot(attempt = 0) {
    if (syncFromSnapshot()) {
      refreshRainfallStatus(false);
      return;
    }
    if (attempt >= 40) {
      refreshRainfallStatus(false);
      return;
    }
    window.setTimeout(() => waitForInitialSnapshot(attempt + 1), 100);
  }

  installWeatherSourcePage();
  provider.addEventListener('change', updatePanels);
  rainfallPeriod?.addEventListener('change', updatePanels);
  form.addEventListener('submit', () => {
    window.setTimeout(() => {
      syncFromSnapshot();
      refreshRainfallStatus(false);
    }, 500);
    window.setTimeout(() => {
      syncFromSnapshot();
      refreshRainfallStatus(false);
    }, 1500);
  });
  form.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="discard-settings"]')) {
      window.setTimeout(() => {
        syncFromSnapshot();
        refreshRainfallStatus(false);
      }, 0);
    }
  });

  installCredentialControls();
  updatePanels();
  waitForInitialSnapshot();
})();