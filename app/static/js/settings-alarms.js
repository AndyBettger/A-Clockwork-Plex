(() => {
  const summary = document.querySelector('[data-alarm-editor-toggle]');
  const body = document.querySelector('[data-alarm-editor-body]');
  const enabled = document.querySelector('input[name="alarm_enabled"]');
  const timeInput = document.querySelector('input[name="alarm_default_time"]');
  const summaryTime = document.querySelector('[data-alarm-summary-time]');
  const summaryState = document.querySelector('[data-alarm-summary-state]');

  const hiddenSnooze = document.getElementById('alarm-snooze-minutes');
  const presetSnooze = document.getElementById('alarm-snooze-preset');
  const customSnooze = document.getElementById('alarm-snooze-custom');
  const presetValues = new Set(['5', '8', '10', '15', '20', '25', '30']);

  const clampSnooze = (value) => {
    const parsed = Number.parseInt(String(value), 10);
    if (!Number.isFinite(parsed)) {
      return 8;
    }
    return Math.max(1, Math.min(60, parsed));
  };

  const updateSummary = () => {
    if (summaryTime && timeInput) {
      summaryTime.textContent = timeInput.value || '11:00';
    }

    if (summaryState && enabled) {
      const active = enabled.checked;
      summaryState.textContent = active ? 'Enabled' : 'Off';
      summaryState.classList.toggle('is-off', !active);
    }
  };

  if (summary && body) {
    summary.addEventListener('click', () => {
      const expanded = summary.getAttribute('aria-expanded') === 'true';
      summary.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      body.hidden = expanded;
    });
  }

  enabled?.addEventListener('change', updateSummary);
  timeInput?.addEventListener('input', updateSummary);
  updateSummary();

  if (!hiddenSnooze || !presetSnooze || !customSnooze) {
    return;
  }

  const initial = String(clampSnooze(hiddenSnooze.value || 8));
  if (presetValues.has(initial)) {
    presetSnooze.value = initial;
    customSnooze.hidden = true;
  } else {
    presetSnooze.value = 'custom';
    customSnooze.hidden = false;
    customSnooze.value = initial;
  }
  hiddenSnooze.value = initial;

  const syncSnooze = () => {
    if (presetSnooze.value === 'custom') {
      customSnooze.hidden = false;
      const value = clampSnooze(customSnooze.value || hiddenSnooze.value || 8);
      customSnooze.value = String(value);
      hiddenSnooze.value = String(value);
      return;
    }

    customSnooze.hidden = true;
    hiddenSnooze.value = String(clampSnooze(presetSnooze.value));
  };

  presetSnooze.addEventListener('change', syncSnooze);
  customSnooze.addEventListener('change', syncSnooze);
  customSnooze.addEventListener('blur', syncSnooze);
  hiddenSnooze.form?.addEventListener('submit', syncSnooze);
})();
