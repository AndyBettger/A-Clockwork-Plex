(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexNightInteractionSettingsLoaded) return;
  window.__aClockworkPlexNightInteractionSettingsLoaded = true;

  const RETRY_MS = 80;
  const MAX_ATTEMPTS = 100;

  function setting(path) {
    return document.querySelector(`[data-setting-path="${path}"]`);
  }

  function styleLabel(value) {
    if (value === 'astronomy') return 'Astronomy red';
    return 'Classic dim';
  }

  function renderStatus() {
    const status = window.ACPDisplayDimming?.status?.();
    const chip = document.querySelector('[data-night-dim-status]');
    if (!chip || !status) return;
    if (!status.enabled) {
      chip.textContent = 'Off';
      chip.classList.remove('is-warning');
      return;
    }
    if (status.active) {
      const phase = status.interacting ? 'Active' : 'Idle';
      chip.textContent = `${phase} · ${Math.round(status.effectiveLevelPercent)}% · ${styleLabel(status.effectiveStyle)}`;
      chip.classList.remove('is-warning');
      return;
    }
    chip.textContent = `${status.start}–${status.end}`;
    chip.classList.add('is-warning');
  }

  function applyActiveLevel(control) {
    const value = Number(control.value || 35);
    const status = window.ACPDisplayDimming?.status?.() || {};
    window.ACPDisplayDimming?.configure?.({ ...status, activeLevelPercent: value });
    const output = document.querySelector('[data-night-dim-active-level]');
    if (output) output.textContent = `${Math.round(value)}%`;
    renderStatus();
  }

  function populate(control, attempts = 80) {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    const value = snapshot?.settings?.display?.night_dim_active_level_percent;
    if (value !== undefined && value !== null) {
      control.value = String(value);
      applyActiveLevel(control);
      return;
    }
    if (attempts > 0) window.setTimeout(() => populate(control, attempts - 1), 100);
  }

  function install(attempt = 0) {
    const card = document.querySelector('[data-night-dimming-settings]');
    const idleControl = setting('display.night_dim_level_percent');
    const durationControl = setting('display.night_dim_wake_seconds');
    if (!card || !idleControl || !durationControl) {
      if (attempt < MAX_ATTEMPTS) window.setTimeout(() => install(attempt + 1), RETRY_MS);
      return;
    }
    if (card.dataset.nightInteractionReady === 'true') return;
    card.dataset.nightInteractionReady = 'true';

    const headingCopy = card.querySelector('.settings-card-heading p');
    if (headingCopy) {
      headingCopy.textContent = 'Keeps a selected night-safe brightness and appearance while resting and while the touchscreen is in use. The Alarm screen always remains fully visible.';
    }

    const idleField = idleControl.closest('.setting-field');
    const idleTitle = idleField?.querySelector(':scope > span');
    const idleHelp = idleField?.querySelector('small');
    if (idleTitle) idleTitle.textContent = 'Idle night brightness';
    if (idleHelp) idleHelp.textContent = 'The resting level used during the scheduled night period.';

    const activeField = document.createElement('label');
    activeField.className = 'setting-field wide';
    activeField.innerHTML = `
      <span>Night interaction brightness</span>
      <input type="range" min="5" max="80" step="1" value="35"
        data-settings-completion-control
        data-setting-path="display.night_dim_active_level_percent">
      <output data-night-dim-active-level>35%</output>
      <small>The brighter night-safe level used while touching Settings, Weather, Plexamp or another dashboard surface.</small>`;
    idleField?.insertAdjacentElement('afterend', activeField);

    const durationField = durationControl.closest('.setting-field');
    const durationTitle = durationField?.querySelector(':scope > span');
    let durationHelp = durationField?.querySelector('small');
    if (durationTitle) durationTitle.textContent = 'Night interaction duration';
    if (!durationHelp && durationField) {
      durationHelp = document.createElement('small');
      durationField.appendChild(durationHelp);
    }
    if (durationHelp) durationHelp.textContent = 'Time after the most recent touch before returning to the idle night level.';

    const message = card.querySelector('[data-night-dim-message]');
    if (message) message.textContent = 'A touch brightens to the active night level and performs the selected action in the same tap.';

    const activeControl = activeField.querySelector('[data-setting-path="display.night_dim_active_level_percent"]');
    activeControl.addEventListener('input', () => applyActiveLevel(activeControl));
    activeControl.addEventListener('change', () => applyActiveLevel(activeControl));

    card.querySelector('[data-action="preview-night-dimming"]')?.addEventListener('click', () => {
      if (message) message.textContent = 'Previewing the idle night state. Touching switches to the configured active night state without cancelling the tap.';
      window.setTimeout(() => {
        if (message) message.textContent = 'A touch brightens to the active night level and performs the selected action in the same tap.';
      }, 8400);
    });

    window.addEventListener('acp:display-night-interaction', renderStatus);
    populate(activeControl);
    renderStatus();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => install(), { once: true });
  } else {
    install();
  }
})();
