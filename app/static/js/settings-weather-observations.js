(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const form = document.getElementById('settings-unified-form');
  const provider = document.querySelector('[data-setting-path="weather.observations.provider"]');
  const panels = [...document.querySelectorAll('[data-observation-provider-panel]')];
  const wuPanel = document.querySelector('[data-observation-provider-panel="weather_underground"]');
  const statusChip = document.querySelector('[data-observation-status]');
  const statusMessage = document.querySelector('[data-observation-message]');
  if (!form || !provider) return;

  let lastRevision = null;
  let credentialConfigured = false;

  function updatePanels() {
    const selected = provider.value || 'ecowitt_push';
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.observationProviderPanel !== selected;
    });
  }

  function renderStatus(status = {}) {
    const labels = {
      push: 'Ecowitt push',
      ready: 'WU ready',
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

    // Replace the old installation-time wording in the summary card without
    // turning the secret into part of the revisioned Settings form.
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
        elements.message.textContent = payload.message || 'Weather Underground connection succeeded.';
        window.setTimeout(syncFromSnapshot, 0);
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
    updatePanels();
    if (snapshot.revision !== lastRevision) {
      lastRevision = snapshot.revision;
      renderStatus(snapshot.status?.weather_observations || {});
    }
    return true;
  }

  function waitForInitialSnapshot(attempt = 0) {
    if (syncFromSnapshot() || attempt >= 40) return;
    window.setTimeout(() => waitForInitialSnapshot(attempt + 1), 100);
  }

  provider.addEventListener('change', updatePanels);
  form.addEventListener('submit', () => {
    window.setTimeout(syncFromSnapshot, 500);
    window.setTimeout(syncFromSnapshot, 1500);
  });
  form.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="discard-settings"]')) {
      window.setTimeout(syncFromSnapshot, 0);
    }
  });

  installCredentialControls();
  updatePanels();
  waitForInitialSnapshot();
})();
