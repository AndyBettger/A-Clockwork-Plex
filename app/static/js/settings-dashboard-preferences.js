(() => {
  if (window.__aClockworkPlexSettingsDashboardPreferencesLoaded) return;
  window.__aClockworkPlexSettingsDashboardPreferencesLoaded = true;

  const form = document.querySelector('.settings-form');
  const preferencesApi = window.ACPDashboardPreferences;
  if (!form || !preferencesApi) return;

  const startupSelect = form.querySelector('select[name="default_mode"]');
  const startupField = startupSelect?.closest('.setting-field');
  const behaviourGrid = startupField?.parentElement;
  if (!startupSelect || !startupField || !behaviourGrid) return;

  const modeOptions = Array.from(startupSelect.options).map((option) => ({
    value: option.value,
    label: option.textContent,
  }));
  const transitionOptions = [
    ['none', 'None / instant'],
    ['grow-fade', 'Grow and fade'],
    ['crossfade', 'Crossfade'],
    ['horizontal-slide', 'Horizontal slide'],
    ['vertical-lift', 'Vertical lift'],
    ['cover-reveal', 'Cover and reveal'],
    ['zoom', 'Zoom'],
    ['blur-dissolve', 'Blur and dissolve'],
  ];

  function createSelect(options, value, name, label, description) {
    const field = document.createElement('label');
    field.className = 'setting-field acp-dashboard-preference-field';

    const heading = document.createElement('span');
    heading.textContent = label;

    const select = document.createElement('select');
    select.name = name;
    options.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.label;
      option.selected = item.value === value;
      select.appendChild(option);
    });

    const small = document.createElement('small');
    small.textContent = description;
    field.append(heading, select, small);
    return { field, select };
  }

  function createDurationField(value) {
    const field = document.createElement('label');
    field.className = 'setting-field acp-dashboard-preference-field acp-transition-duration-field';

    const heading = document.createElement('span');
    heading.textContent = 'Transition duration';

    const row = document.createElement('div');
    row.className = 'acp-transition-duration-row';

    const slider = document.createElement('input');
    slider.id = 'dashboard-transition-duration';
    slider.name = 'transition_duration_ms';
    slider.type = 'range';
    slider.min = '0';
    slider.max = '1500';
    slider.step = '50';
    slider.value = String(value);
    slider.setAttribute('aria-label', 'Page transition duration in milliseconds');

    const output = document.createElement('output');
    output.htmlFor = slider.id;
    output.textContent = `${value} ms`;

    const small = document.createElement('small');
    small.textContent = '0 ms is instant. Longer values are more theatrical and may encourage capes.';

    row.append(slider, output);
    field.append(heading, row, small);
    return { field, slider, output };
  }

  const current = preferencesApi.read();
  startupField.querySelector(':scope > span')?.replaceChildren(document.createTextNode('Startup page'));
  startupField.querySelector('small')?.remove();
  const startupDescription = document.createElement('small');
  startupDescription.textContent = 'Shown when the kiosk opens the dashboard root URL.';
  startupField.appendChild(startupDescription);
  startupSelect.value = current.startupMode;

  const idleTimeout = form.querySelector('input[name="idle_timeout_seconds"]');
  const idleTimeoutDescription = idleTimeout?.closest('.setting-field')?.querySelector('small');
  if (idleTimeoutDescription) {
    idleTimeoutDescription.textContent = 'Seconds before switching to the Idle return page while playback and alarms are quiet.';
  }

  const idleControl = createSelect(
    modeOptions,
    current.idleReturnMode,
    'idle_return_mode',
    'Idle return page',
    'Shown after the inactivity timeout when Plexamp, AirPlay and alarms are quiet.',
  );
  const transitionControl = createSelect(
    transitionOptions.map(([value, label]) => ({ value, label })),
    current.transitionStyle,
    'transition_style',
    'Page transition',
    'Used when moving between Clock, Weather, AirPlay and Settings.',
  );
  const durationControl = createDurationField(current.transitionDurationMs);

  startupField.insertAdjacentElement('afterend', idleControl.field);
  behaviourGrid.append(transitionControl.field, durationControl.field);

  function updatePreferences() {
    const next = preferencesApi.write({
      startupMode: startupSelect.value,
      idleReturnMode: idleControl.select.value,
      transitionStyle: transitionControl.select.value,
      transitionDurationMs: durationControl.slider.value,
    });
    durationControl.output.textContent = `${next.transitionDurationMs} ms`;
  }

  startupSelect.addEventListener('change', updatePreferences);
  idleControl.select.addEventListener('change', updatePreferences);
  transitionControl.select.addEventListener('change', updatePreferences);
  durationControl.slider.addEventListener('input', updatePreferences);
  durationControl.slider.addEventListener('change', updatePreferences);
})();
