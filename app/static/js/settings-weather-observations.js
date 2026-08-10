(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const form = document.getElementById('settings-unified-form');
  const provider = document.querySelector('[data-setting-path="weather.observations.provider"]');
  const panels = [...document.querySelectorAll('[data-observation-provider-panel]')];
  const statusChip = document.querySelector('[data-observation-status]');
  const statusMessage = document.querySelector('[data-observation-message]');
  if (!form || !provider) return;

  let lastRevision = null;

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
      statusMessage.textContent = 'The Weather Underground API credential is not available in the configured server environment.';
    } else if (state === 'pending') {
      statusMessage.textContent = 'Weather Underground is configured and waiting for its first observation.';
    } else if (status.last_observation_at) {
      statusMessage.textContent = `Last observation ${new Date(status.last_observation_at).toLocaleString()}`;
    } else {
      statusMessage.textContent = 'Observation provider status will appear here.';
    }
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

  updatePanels();
  waitForInitialSnapshot();
})();
