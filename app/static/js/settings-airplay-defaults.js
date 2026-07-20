(() => {
  if (window.__aClockworkPlexAirPlayDefaultsLoaded) return;
  window.__aClockworkPlexAirPlayDefaultsLoaded = true;

  const ENDPOINT = '/api/audio/defaults';
  let pollTimer = null;
  let saveDebounce = null;
  const byId = (id) => document.getElementById(id);

  async function requestStatus() {
    const response = await fetch(ENDPOINT, { cache: 'no-store' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `AirPlay defaults returned ${response.status}.`);
    return payload;
  }

  function renderApplication(application = {}, defaults = {}) {
    const health = byId('audio-airplay-default-health');
    const message = byId('audio-airplay-default-message');
    const status = String(application.status || 'waiting-for-session');
    const target = application.target_percent ?? defaults.default_volume_percent ?? 60;
    const labels = {
      disabled: 'Disabled',
      'waiting-for-session': 'Saved',
      'saved-for-next-session': 'Next session',
      'waiting-for-remote': 'Waiting…',
      applying: 'Applying…',
      retrying: 'Retrying…',
      verifying: 'Verifying…',
      applied: 'Applied',
      'timed-out': 'Timed out',
    };

    if (health) {
      health.textContent = labels[status] || 'Saved';
      health.classList.toggle('is-warning', ['disabled', 'retrying', 'timed-out'].includes(status));
    }
    if (!message) return;

    if (application.last_error) {
      message.textContent = application.last_error;
    } else if (status === 'saved-for-next-session') {
      message.textContent = `${target}% is stored for the next AirPlay connection; the current session is untouched.`;
    } else if (status === 'applied') {
      message.textContent = `AirPlay confirmed the requested ${target}% starting volume.`;
    } else if (status === 'verifying') {
      message.textContent = `AirPlay reported ${application.last_confirmed_percent ?? target}%; checking that the sender keeps it.`;
    } else if (['applying', 'retrying', 'waiting-for-remote'].includes(status)) {
      message.textContent = `Applying ${target}% while the AirPlay sender finishes connecting.`;
    } else if (status === 'disabled') {
      message.textContent = 'The value is saved, but automatic application is disabled.';
    } else {
      message.textContent = `Saved at ${defaults.default_volume_percent ?? target}% for the next AirPlay session.`;
    }
  }

  async function refreshApplication() {
    if (!byId('audio-airplay-default-card')) return;
    try {
      const payload = await requestStatus();
      renderApplication(payload.application || {}, payload.defaults || {});
    } catch (error) {
      const health = byId('audio-airplay-default-health');
      if (health) {
        health.textContent = 'Unavailable';
        health.classList.add('is-warning');
      }
      const message = byId('audio-airplay-default-message');
      if (message) message.textContent = error.message || 'Could not read AirPlay starting-volume status.';
    }
  }

  function queueSave() {
    window.clearTimeout(saveDebounce);
    saveDebounce = window.setTimeout(() => {
      const button = byId('audio-airplay-default-save');
      if (button && !button.disabled) {
        button.click();
        window.setTimeout(refreshApplication, 350);
      }
    }, 180);
  }

  function install() {
    const card = byId('audio-airplay-default-card');
    const slider = byId('audio-airplay-default-volume');
    const toggle = byId('audio-airplay-apply-default');
    if (!card || !slider || !toggle) {
      window.setTimeout(install, 100);
      return;
    }
    if (card.dataset.airplayAutoSaveInstalled === 'true') return;
    card.dataset.airplayAutoSaveInstalled = 'true';
    slider.addEventListener('change', queueSave);
    slider.addEventListener('pointerup', queueSave);
    toggle.addEventListener('change', queueSave);
    refreshApplication();
    pollTimer = window.setInterval(refreshApplication, 2000);
  }

  window.addEventListener('pagehide', () => {
    window.clearInterval(pollTimer);
    window.clearTimeout(saveDebounce);
  });

  install();
})();
