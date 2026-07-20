(() => {
  if (window.__aClockworkPlexSettingsAutosaveLoaded) return;
  window.__aClockworkPlexSettingsAutosaveLoaded = true;

  const form = document.querySelector('.settings-form');
  if (!form) return;

  const indicator = document.createElement('div');
  indicator.className = 'settings-autosave-indicator';
  indicator.setAttribute('role', 'status');
  indicator.setAttribute('aria-live', 'polite');
  indicator.textContent = 'Saved';
  document.body.appendChild(indicator);
  document.body.classList.add('settings-autosave-enabled');

  let debounceTimer = null;
  let hideTimer = null;
  let saveInFlight = false;
  let saveQueued = false;

  function showState(text, isError = false, linger = 1100) {
    window.clearTimeout(hideTimer);
    indicator.textContent = text;
    indicator.classList.toggle('is-error', isError);
    indicator.classList.add('is-visible');
    if (linger > 0) {
      hideTimer = window.setTimeout(() => indicator.classList.remove('is-visible'), linger);
    }
  }

  function dedicatedWorkspace(element) {
    return Boolean(element?.closest('#settings-panel-alarms, #settings-panel-audio'));
  }

  function queueSave(delay = 550) {
    saveQueued = true;
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(saveNow, delay);
  }

  async function saveNow() {
    if (!saveQueued) return;
    if (saveInFlight) {
      queueSave(250);
      return;
    }
    saveQueued = false;
    saveInFlight = true;
    showState('Saving…', false, 0);
    try {
      const response = await fetch(window.location.pathname, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-A-Clockwork-Plex-Autosave': '1' },
      });
      if (!response.ok) throw new Error(`Settings returned ${response.status}.`);
      showState('Saved');
    } catch (error) {
      showState('Save failed', true, 2600);
    } finally {
      saveInFlight = false;
      if (saveQueued) queueSave(180);
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    queueSave(0);
  });

  form.addEventListener('input', (event) => {
    const target = event.target;
    if (!target?.name || dedicatedWorkspace(target)) return;
    queueSave(target.matches('input[type="text"], input:not([type])') ? 800 : 350);
  });

  form.addEventListener('change', (event) => {
    const target = event.target;
    if (!target?.name || dedicatedWorkspace(target)) return;
    queueSave(180);
  });

  form.addEventListener('click', (event) => {
    if (event.target.closest('.clock-card-toggle, .clock-card-order-button, .clock-card-remove-button')) {
      queueSave(300);
    }
  });

  const hiddenCards = document.getElementById('clock-card-hidden-inputs');
  if (hiddenCards) {
    new MutationObserver(() => queueSave(300)).observe(hiddenCards, { childList: true, subtree: true, attributes: true });
  }

  window.addEventListener('pagehide', () => {
    window.clearTimeout(debounceTimer);
    window.clearTimeout(hideTimer);
  });
})();
