(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsNumericControlsLoaded) return;
  window.__aClockworkPlexSettingsNumericControlsLoaded = true;

  const form = document.getElementById('settings-unified-form');
  if (!form) return;

  const presetFields = new Map([
    ['dashboard.idle_timeout_seconds', [
      ['5', '5 seconds'],
      ['15', '15 seconds'],
      ['30', '30 seconds'],
      ['60', '1 minute'],
      ['120', '2 minutes'],
      ['180', '3 minutes'],
      ['300', '5 minutes'],
      ['600', '10 minutes'],
      ['900', '15 minutes'],
      ['1800', '30 minutes'],
      ['3600', '1 hour'],
      ['7200', '2 hours'],
      ['21600', '6 hours'],
      ['43200', '12 hours'],
      ['86400', '24 hours'],
    ]],
    ['weather.auto_refresh_seconds', [
      ['0', 'Off'],
      ['15', '15 seconds'],
      ['30', '30 seconds'],
      ['60', '1 minute'],
      ['120', '2 minutes'],
      ['300', '5 minutes'],
      ['600', '10 minutes'],
      ['900', '15 minutes'],
      ['1800', '30 minutes'],
      ['3600', '1 hour'],
    ]],
    ['airplay.pause_hold_seconds', [
      ['30', '30 seconds'],
      ['60', '1 minute'],
      ['120', '2 minutes'],
      ['300', '5 minutes'],
      ['420', '7 minutes'],
      ['600', '10 minutes'],
      ['900', '15 minutes'],
      ['1800', '30 minutes'],
      ['3600', '1 hour'],
    ]],
  ]);

  /* Provider timing values are deliberately flexible rather than a short
   consumer-facing choice list. Keep exact entry available, but make them true
   bounded number controls so a physical keyboard cannot put arbitrary text in
   the field. The server independently validates these values. */
  const boundedNumberFields = new Map([
    ['weather.observations.ecowitt_push.fresh_seconds', { min: 30, max: 3600, step: 30 }],
    ['weather.observations.weather_underground.refresh_seconds', { min: 30, max: 3600, step: 30 }],
    ['weather.observations.weather_underground.stale_seconds', { min: 60, max: 21600, step: 60 }],
    ['weather.observations.weather_underground.request_timeout_seconds', { min: 2, max: 60, step: 1 }],
    ['weather.forecast.latitude', { min: -90, max: 90, step: 0.000001, decimal: true }],
    ['weather.forecast.longitude', { min: -180, max: 180, step: 0.000001, decimal: true }],
  ]);

  const presetControls = new Map();

  function pathParts(path) {
    return String(path || '').split('.').filter(Boolean);
  }

  function getPath(object, path) {
    return pathParts(path).reduce((value, part) => value?.[part], object);
  }

  function copyUsefulAttributes(source, target) {
    for (const attribute of source.attributes) {
      if (['type', 'inputmode', 'data-keyboard', 'value'].includes(attribute.name)) continue;
      target.setAttribute(attribute.name, attribute.value);
    }
  }

  function addCustomOption(select, value) {
    const text = String(value ?? '').trim();
    if (!text || [...select.options].some((option) => option.value === text)) return;
    select.querySelector('option[data-custom-setting-value]')?.remove();
    const option = document.createElement('option');
    option.value = text;
    option.textContent = `Current custom value · ${text} seconds`;
    option.dataset.customSettingValue = 'true';
    select.appendChild(option);
  }

  function replaceWithPresetSelect(input, path, options) {
    const select = document.createElement('select');
    copyUsefulAttributes(input, select);
    select.dataset.settingPath = path;
    select.dataset.numericPreset = 'true';
    options.forEach(([value, label]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });

    const current = String(input.value || '').trim();
    if (current) {
      addCustomOption(select, current);
      select.value = current;
    }
    select.addEventListener('input', () => { select.dataset.userEdited = 'true'; });
    select.addEventListener('change', () => { select.dataset.userEdited = 'true'; });
    input.replaceWith(select);
    presetControls.set(path, select);
  }

  function hardenNumberInput(input, limits) {
    input.type = 'number';
    input.min = String(limits.min);
    input.max = String(limits.max);
    input.step = String(limits.step);
    input.setAttribute('inputmode', 'none');
    input.dataset.keyboard = limits.decimal ? 'decimal' : 'number';
  }

  function syncPresetValuesFromSnapshot() {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    if (!snapshot?.settings) return false;
    presetControls.forEach((select, path) => {
      if (select.dataset.userEdited === 'true') return;
      const saved = getPath(snapshot.settings, path);
      if (saved === undefined || saved === null) return;
      const value = String(saved);
      addCustomOption(select, value);
      select.value = value;
    });
    window.dispatchEvent(new Event('acp:settings-selects-refresh'));
    return true;
  }

  function install() {
    presetFields.forEach((options, path) => {
      const input = form.querySelector(`input[data-setting-path="${path}"]`);
      if (input) replaceWithPresetSelect(input, path, options);
    });

    boundedNumberFields.forEach((limits, path) => {
      const input = form.querySelector(`input[data-setting-path="${path}"]`);
      if (input) hardenNumberInput(input, limits);
    });

    /* Motion owns transition_duration_ms and promotes it to a 0–2000 ms range
       control in settings-display-sections.js. Do not create a second owner. */
    [0, 100, 250, 600, 1500].forEach((delay) => {
      window.setTimeout(syncPresetValuesFromSnapshot, delay);
    });
  }

  install();
})();
