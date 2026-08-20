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
    ['weather.observations.ecowitt_push.fresh_seconds', [
      ['30', '30 seconds'],
      ['60', '1 minute'],
      ['120', '2 minutes'],
      ['180', '3 minutes'],
      ['300', '5 minutes'],
      ['600', '10 minutes'],
      ['900', '15 minutes'],
      ['1800', '30 minutes'],
      ['3600', '1 hour'],
    ]],
    ['weather.observations.weather_underground.refresh_seconds', [
      ['30', '30 seconds'],
      ['60', '1 minute'],
      ['120', '2 minutes'],
      ['180', '3 minutes'],
      ['300', '5 minutes'],
      ['600', '10 minutes'],
      ['900', '15 minutes'],
      ['1800', '30 minutes'],
      ['3600', '1 hour'],
    ]],
    ['weather.observations.weather_underground.stale_seconds', [
      ['60', '1 minute'],
      ['120', '2 minutes'],
      ['180', '3 minutes'],
      ['300', '5 minutes'],
      ['600', '10 minutes'],
      ['900', '15 minutes'],
      ['1800', '30 minutes'],
      ['3600', '1 hour'],
      ['7200', '2 hours'],
      ['10800', '3 hours'],
      ['21600', '6 hours'],
    ]],
    ['weather.observations.weather_underground.request_timeout_seconds', [
      ['2', '2 seconds'],
      ['3', '3 seconds'],
      ['5', '5 seconds'],
      ['8', '8 seconds'],
      ['10', '10 seconds'],
      ['15', '15 seconds'],
      ['20', '20 seconds'],
      ['30', '30 seconds'],
      ['45', '45 seconds'],
      ['60', '60 seconds'],
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
      ['180', '3 minutes'],
      ['300', '5 minutes'],
      ['420', '7 minutes'],
    ]],
  ]);

  /* Forecast coordinates genuinely require arbitrary precise entry. Keep them
     as ordinary text fields driven by the custom decimal keyboard so Chromium
     never paints native number-spinner arrows. The server independently
     validates their exact numeric ranges before persistence. */
  const exactNumericFields = new Map([
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

  function normalisePresetValue(path, value) {
    const text = String(value ?? '').trim();
    if (path !== 'airplay.pause_hold_seconds' || !text) return text;
    const parsed = Number.parseInt(text, 10);
    if (!Number.isFinite(parsed)) return '420';
    return String(Math.max(30, Math.min(420, parsed)));
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

    const current = normalisePresetValue(path, input.value);
    if (current) {
      addCustomOption(select, current);
      select.value = current;
    }
    select.addEventListener('input', () => { select.dataset.userEdited = 'true'; });
    select.addEventListener('change', () => { select.dataset.userEdited = 'true'; });
    input.replaceWith(select);
    presetControls.set(path, select);
  }

  function hardenExactNumericInput(input, limits) {
    input.type = 'text';
    input.setAttribute('inputmode', 'none');
    input.dataset.keyboard = limits.decimal ? 'decimal' : 'number';
    input.dataset.numericMin = String(limits.min);
    input.dataset.numericMax = String(limits.max);
    input.dataset.numericStep = String(limits.step);
  }

  function syncPresetValuesFromSnapshot() {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    if (!snapshot?.settings) return false;
    presetControls.forEach((select, path) => {
      if (select.dataset.userEdited === 'true') return;
      const saved = getPath(snapshot.settings, path);
      if (saved === undefined || saved === null) return;
      const value = normalisePresetValue(path, saved);
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

    exactNumericFields.forEach((limits, path) => {
      const input = form.querySelector(`input[data-setting-path="${path}"]`);
      if (input) hardenExactNumericInput(input, limits);
    });

    /* Motion owns transition_duration_ms and promotes it to a 0–2000 ms range
       control in settings-display-sections.js. Do not create a second owner. */
    [0, 100, 250, 600, 1500].forEach((delay) => {
      window.setTimeout(syncPresetValuesFromSnapshot, delay);
    });
  }

  install();
})();
