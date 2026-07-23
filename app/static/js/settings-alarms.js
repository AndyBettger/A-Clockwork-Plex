(() => {
  const panel = document.getElementById('settings-panel-alarms');
  const form = document.querySelector('.settings-form');
  if (!panel || !form) {
    return;
  }

  const SNOOZE_PRESETS = [5, 8, 10, 15, 20, 25, 30];
  const RING_PRESETS = [1, 2, 3, 5, 10];
  const EXPIRY_PRESETS = [30, 60, 120, 180, 240, 360];
  const TIME_RE = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

  let model = null;
  let tonesManifest = null;
  let dayOptions = [];
  let modelLoaded = false;
  let bypassSubmit = false;

  let previewContext = null;
  let previewNodes = [];
  let previewTimer = null;
  let previewButton = null;

  const deepClone = (value) => JSON.parse(JSON.stringify(value));
  const clamp = (value, fallback, minimum, maximum) => {
    const parsed = Number.parseInt(String(value), 10);
    const safe = Number.isFinite(parsed) ? parsed : fallback;
    return Math.max(minimum, Math.min(maximum, safe));
  };

  const element = (tag, className = '', text = '') => {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text) {
      node.textContent = text;
    }
    return node;
  };

  const toneById = (toneId) => tonesManifest?.tones?.find((tone) => tone.id === toneId) || null;
  const toneLabel = (toneId) => toneById(toneId)?.label || toneId || 'Unknown tone';
  const dayLabel = (dayId) => dayOptions.find((day) => day.id === dayId)?.label || dayId;

  function scheduleSummary(days) {
    const joined = days.join(',');
    if (days.length === 7) {
      return 'Every day';
    }
    if (joined === 'mon,tue,wed,thu,fri') {
      return 'Weekdays';
    }
    if (joined === 'sat,sun') {
      return 'Weekends';
    }
    return days.map(dayLabel).join(' ') || 'No days';
  }

  function uniqueAlarmId(label = 'alarm') {
    const base = String(label)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'alarm';
    const used = new Set(model.alarms.map((alarm) => alarm.id));
    let candidate = base;
    let suffix = 2;
    while (used.has(candidate)) {
      candidate = `${base.slice(0, 40)}-${suffix}`;
      suffix += 1;
    }
    return candidate;
  }

  function showStatus(message, tone = 'info') {
    const status = document.getElementById('alarm-model-status');
    if (!status) {
      return;
    }
    status.hidden = !message;
    status.textContent = message || '';
    status.className = `alarm-model-status is-${tone}`;
  }

  function stopPreview() {
    if (previewTimer) {
      window.clearTimeout(previewTimer);
      previewTimer = null;
    }
    previewNodes.forEach((node) => {
      try {
        node.stop?.();
        node.disconnect?.();
      } catch (error) {
      }
    });
    previewNodes = [];
    if (previewButton) {
      previewButton.textContent = 'Preview tone';
      previewButton.classList.remove('is-playing');
      previewButton = null;
    }
  }

  function audioContext() {
    if (!previewContext) {
      const Context = window.AudioContext || window.webkitAudioContext;
      previewContext = Context ? new Context() : null;
    }
    return previewContext;
  }

  async function previewTone(toneId, volumePercent, button) {
    const tone = toneById(toneId);
    const context = audioContext();
    if (!tone || !context) {
      showStatus('This Chromium build does not expose Web Audio for tone previews.', 'error');
      return;
    }

    if (previewButton === button) {
      stopPreview();
      return;
    }

    stopPreview();
    await context.resume();
    previewButton = button;
    button.textContent = 'Stop preview';
    button.classList.add('is-playing');

    const previewSeconds = clamp(tonesManifest.preview_seconds, 10, 1, 30);
    const master = context.createGain();
    const volume = clamp(volumePercent, 70, 0, 100) / 100;
    master.gain.setValueAtTime(Math.max(0.0001, volume), context.currentTime);
    master.connect(context.destination);
    previewNodes.push(master);

    const pattern = Array.isArray(tone.pattern) ? tone.pattern : [];
    const patternMs = pattern.reduce(
      (total, step) => total + clamp(step.duration_ms, 200, 20, 3000) + clamp(step.gap_ms, 0, 0, 3000),
      0,
    );
    if (!pattern.length || !patternMs) {
      stopPreview();
      return;
    }

    const start = context.currentTime + 0.03;
    const end = start + previewSeconds;
    let cursor = start;
    while (cursor < end) {
      for (const step of pattern) {
        if (cursor >= end) {
          break;
        }
        const duration = clamp(step.duration_ms, 200, 20, 3000) / 1000;
        const gap = clamp(step.gap_ms, 0, 0, 3000) / 1000;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = ['sine', 'square', 'sawtooth', 'triangle'].includes(step.wave) ? step.wave : 'sine';
        oscillator.frequency.setValueAtTime(Number(step.frequency) || 440, cursor);
        if (step.end_frequency) {
          oscillator.frequency.linearRampToValueAtTime(Number(step.end_frequency), Math.min(cursor + duration, end));
        }
        const stepGain = Math.max(0.001, Math.min(0.35, Number(step.gain) || 0.15));
        gain.gain.setValueAtTime(0.0001, cursor);
        gain.gain.linearRampToValueAtTime(stepGain, cursor + 0.015);
        gain.gain.setValueAtTime(stepGain, Math.max(cursor + 0.02, cursor + duration - 0.025));
        gain.gain.linearRampToValueAtTime(0.0001, Math.min(cursor + duration, end));
        oscillator.connect(gain);
        gain.connect(master);
        oscillator.start(cursor);
        oscillator.stop(Math.min(cursor + duration + 0.02, end + 0.02));
        previewNodes.push(oscillator, gain);
        cursor += duration + gap;
      }
    }

    previewTimer = window.setTimeout(stopPreview, previewSeconds * 1000 + 120);
  }

  function buildSelect(values, selected, labeler = (value) => String(value)) {
    const select = document.createElement('select');
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = String(value);
      option.textContent = labeler(value);
      option.selected = String(value) === String(selected);
      select.appendChild(option);
    });
    return select;
  }

  function durationControl(value, presets, minimum, maximum, onChange, labelSuffix = 'minutes') {
    const wrapper = element('div', 'alarm-duration-control');
    const isPreset = presets.includes(Number(value));
    const select = buildSelect(
      [...presets, 'custom'],
      isPreset ? value : 'custom',
      (item) => item === 'custom' ? 'Custom' : `${item} ${labelSuffix}`,
    );
    const custom = document.createElement('input');
    custom.type = 'text';
    custom.inputMode = 'none';
    custom.dataset.keyboard = 'number';
    custom.className = 'alarm-duration-custom';
    custom.value = String(clamp(value, presets[0], minimum, maximum));
    custom.hidden = isPreset;

    const sync = () => {
      if (select.value === 'custom') {
        custom.hidden = false;
        const safe = clamp(custom.value, presets[0], minimum, maximum);
        custom.value = String(safe);
        onChange(safe);
      } else {
        custom.hidden = true;
        onChange(clamp(select.value, presets[0], minimum, maximum));
      }
    };
    select.addEventListener('change', sync);
    custom.addEventListener('input', () => {
      if (select.value === 'custom') {
        onChange(clamp(custom.value, presets[0], minimum, maximum));
      }
    });
    custom.addEventListener('blur', sync);
    wrapper.append(select, custom);
    return wrapper;
  }

  function field(labelText, control, helpText = '') {
    const label = element('label', 'setting-field');
    label.appendChild(element('span', '', labelText));
    label.appendChild(control);
    if (helpText) {
      label.appendChild(element('small', '', helpText));
    }
    return label;
  }

  function renderPanelChrome() {
    panel.innerHTML = `
      <section class="settings-card is-intro">
        <div class="settings-card-heading">
          <h2>Alarms</h2>
          <span class="settings-chip">Configuration only</span>
        </div>
        <p class="muted small">Create and organise alarms safely. The scheduler remains disabled during this pass.</p>
      </section>
      <div id="alarm-model-status" class="alarm-model-status" hidden></div>
      <section class="settings-card">
        <h2>Alarm defaults</h2>
        <div class="alarm-model-defaults" id="alarm-model-defaults"></div>
      </section>
      <section class="settings-card">
        <div class="settings-card-heading">
          <h2>Configured alarms</h2>
          <span class="settings-chip" id="alarm-count-chip"></span>
        </div>
        <div class="alarm-list" id="alarm-list"></div>
        <button class="alarm-add-button" id="alarm-add-button" type="button">＋ Add another alarm</button>
      </section>
      <section class="settings-card alarm-scheduler-lockout">
        <strong>Scheduler lockout active</strong>
        <span>Saving these settings will not play, schedule or trigger an alarm yet.</span>
      </section>
    `;
  }

  function renderDefaults() {
    const container = document.getElementById('alarm-model-defaults');
    if (!container) {
      return;
    }
    container.replaceChildren();

    const snooze = durationControl(
      model.defaults.snooze_minutes,
      SNOOZE_PRESETS,
      1,
      60,
      (value) => { model.defaults.snooze_minutes = value; },
    );
    const ring = buildSelect(RING_PRESETS, model.defaults.ring_minutes, (value) => `${value} minute${value === 1 ? '' : 's'}`);
    ring.addEventListener('change', () => { model.defaults.ring_minutes = Number(ring.value); });
    const expiry = durationControl(
      model.defaults.occurrence_expiry_minutes,
      EXPIRY_PRESETS,
      15,
      1440,
      (value) => { model.defaults.occurrence_expiry_minutes = value; },
    );
    const defaultTone = buildSelect(
      tonesManifest.tones.map((tone) => tone.id),
      model.defaults.tone_id,
      toneLabel,
    );
    defaultTone.addEventListener('change', () => { model.defaults.tone_id = defaultTone.value; });

    container.append(
      field('Default snooze', snooze, '5-minute presets plus the agreed 8-minute default, or Custom up to 60.'),
      field('Continuous ring cycle', ring, 'How long a ringing cycle may sound before automatic quiet.'),
      field('Occurrence expiry', expiry, 'How long snoozes remain eligible after the scheduled time.'),
      field('Default local tone', defaultTone, 'Used when creating a new alarm.'),
    );
  }

  function updateAlarmSummary(card, alarm) {
    card.querySelector('[data-summary-time]').textContent = alarm.time || '—';
    card.querySelector('[data-summary-label]').textContent = alarm.label || 'Unnamed alarm';
    card.querySelector('[data-summary-detail]').textContent = `${scheduleSummary(alarm.days)} · ${toneLabel(alarm.source.tone_id)} · Snooze ${alarm.snooze_minutes} min`;
    const state = card.querySelector('[data-summary-state]');
    state.textContent = alarm.enabled ? 'Enabled' : 'Off';
    state.classList.toggle('is-off', !alarm.enabled);
  }

  function buildAlarmCard(alarm, index) {
    const card = element('article', 'alarm-editor-card');
    card.dataset.alarmId = alarm.id;

    const summary = element('button', 'alarm-editor-summary');
    summary.type = 'button';
    summary.setAttribute('aria-expanded', index === 0 ? 'true' : 'false');
    summary.innerHTML = `
      <span class="alarm-editor-time" data-summary-time></span>
      <span class="alarm-editor-title">
        <strong data-summary-label></strong>
        <span data-summary-detail></span>
      </span>
      <span class="alarm-editor-state" data-summary-state></span>
      <span class="alarm-editor-chevron" aria-hidden="true">⌄</span>
    `;

    const body = element('div', 'alarm-editor-body');
    body.hidden = index !== 0;
    summary.addEventListener('click', () => {
      const expanded = summary.getAttribute('aria-expanded') === 'true';
      summary.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      body.hidden = expanded;
      if (expanded) {
        stopPreview();
      }
    });

    const basics = element('div', 'settings-grid three-col');
    const enabledLabel = element('label', 'setting-toggle');
    const enabled = document.createElement('input');
    enabled.type = 'checkbox';
    enabled.checked = Boolean(alarm.enabled);
    enabled.addEventListener('change', () => {
      alarm.enabled = enabled.checked;
      updateAlarmSummary(card, alarm);
    });
    enabledLabel.append(enabled, element('span', '', 'Alarm enabled'));

    const labelInput = document.createElement('input');
    labelInput.value = alarm.label;
    labelInput.autocomplete = 'off';
    labelInput.inputMode = 'none';
    labelInput.dataset.keyboard = 'text';
    labelInput.maxLength = 80;
    labelInput.addEventListener('input', () => {
      alarm.label = labelInput.value;
      updateAlarmSummary(card, alarm);
    });

    const timeInput = document.createElement('input');
    timeInput.value = alarm.time;
    timeInput.inputMode = 'none';
    timeInput.dataset.keyboard = 'time';
    timeInput.placeholder = 'HH:MM';
    timeInput.addEventListener('input', () => {
      alarm.time = timeInput.value;
      timeInput.classList.toggle('is-invalid', Boolean(timeInput.value) && !TIME_RE.test(timeInput.value));
      updateAlarmSummary(card, alarm);
    });

    basics.append(enabledLabel, field('Label', labelInput), field('Alarm time', timeInput, '24-hour HH:MM'));
    body.appendChild(basics);

    const scheduleSection = element('section', 'alarm-editor-section');
    scheduleSection.appendChild(element('h3', 'settings-subheading', 'Repeat schedule'));
    const days = element('div', 'alarm-day-grid');
    dayOptions.forEach((day) => {
      const button = element('button', 'alarm-day-button', day.label);
      button.type = 'button';
      const refresh = () => button.classList.toggle('is-selected', alarm.days.includes(day.id));
      refresh();
      button.addEventListener('click', () => {
        if (alarm.days.includes(day.id)) {
          alarm.days = alarm.days.filter((item) => item !== day.id);
        } else {
          alarm.days = dayOptions.map((item) => item.id).filter((item) => item === day.id || alarm.days.includes(item));
        }
        refresh();
        updateAlarmSummary(card, alarm);
      });
      days.appendChild(button);
    });
    scheduleSection.appendChild(days);
    body.appendChild(scheduleSection);

    const behaviour = element('div', 'settings-grid two-col');
    const snoozeControl = durationControl(
      alarm.snooze_minutes,
      SNOOZE_PRESETS,
      1,
      60,
      (value) => {
        alarm.snooze_minutes = value;
        updateAlarmSummary(card, alarm);
      },
    );
    const toneSelect = buildSelect(
      tonesManifest.tones.map((tone) => tone.id),
      alarm.source.tone_id,
      toneLabel,
    );
    toneSelect.addEventListener('change', () => {
      stopPreview();
      alarm.source.tone_id = toneSelect.value;
      toneInfo.textContent = toneById(toneSelect.value)?.description || '';
      updateAlarmSummary(card, alarm);
    });
    behaviour.append(
      field('Snooze duration', snoozeControl, 'Per-alarm override; Custom may be 1–60 minutes.'),
      field('Local alarm tone', toneSelect, 'The scheduler will use a local tone first.'),
    );
    body.appendChild(behaviour);

    const tonePanel = element('div', 'alarm-tone-panel');
    const toneInfo = element('p', 'alarm-tone-description', toneById(alarm.source.tone_id)?.description || '');
    const previewControls = element('div', 'alarm-tone-preview-controls');
    const volumeLabel = element('label', 'alarm-tone-volume');
    volumeLabel.appendChild(element('span', '', 'Preview / target volume'));
    const volume = document.createElement('input');
    volume.type = 'range';
    volume.min = '0';
    volume.max = '100';
    volume.step = '1';
    volume.value = String(clamp(alarm.volume.target_percent, 85, 0, 100));
    const volumeValue = element('strong', '', `${volume.value}%`);
    volume.addEventListener('input', () => {
      alarm.volume.target_percent = Number(volume.value);
      volumeValue.textContent = `${volume.value}%`;
    });
    volumeLabel.append(volume, volumeValue);
    const preview = element('button', 'button alarm-tone-preview-button', 'Preview tone');
    preview.type = 'button';
    preview.addEventListener('click', () => previewTone(alarm.source.tone_id, alarm.volume.target_percent, preview));
    const stop = element('button', 'button settings-secondary', 'Stop');
    stop.type = 'button';
    stop.addEventListener('click', stopPreview);
    previewControls.append(volumeLabel, preview, stop);
    tonePanel.append(toneInfo, previewControls);
    body.appendChild(tonePanel);

    const design = element('div', 'alarm-design-grid');
    [
      ['Source', 'Local tone'],
      ['Fallback', toneLabel(alarm.source.fallback_tone_id)],
      ['Ring cycle', `${alarm.ring_minutes} min`],
      ['Expiry', `${alarm.occurrence_expiry_minutes} min`],
    ].forEach(([label, value]) => {
      const chip = element('div', 'alarm-design-chip');
      chip.append(element('span', '', label), element('strong', '', value));
      design.appendChild(chip);
    });
    body.appendChild(design);

    const actions = element('div', 'alarm-card-actions');
    const duplicate = element('button', 'button settings-secondary', 'Duplicate');
    duplicate.type = 'button';
    duplicate.addEventListener('click', () => {
      stopPreview();
      const copy = deepClone(alarm);
      copy.id = uniqueAlarmId(`${alarm.label}-copy`);
      copy.label = `${alarm.label || 'Alarm'} copy`.slice(0, 80);
      copy.enabled = false;
      model.alarms.splice(index + 1, 0, copy);
      renderAlarms();
      showStatus('Alarm duplicated in the editor. It is disabled until you choose to enable it and save.', 'info');
    });

    const remove = element('button', 'button alarm-remove-button', 'Remove');
    remove.type = 'button';
    let removeArmed = false;
    let removeTimer = null;
    remove.addEventListener('click', () => {
      if (!removeArmed) {
        removeArmed = true;
        remove.textContent = 'Tap again to remove';
        remove.classList.add('is-armed');
        removeTimer = window.setTimeout(() => {
          removeArmed = false;
          remove.textContent = 'Remove';
          remove.classList.remove('is-armed');
        }, 3500);
        return;
      }
      window.clearTimeout(removeTimer);
      stopPreview();
      model.alarms = model.alarms.filter((item) => item.id !== alarm.id);
      renderAlarms();
      showStatus('Alarm removed from the editor. Save settings to make the removal permanent.', 'info');
    });
    actions.append(duplicate, remove);
    body.appendChild(actions);

    card.append(summary, body);
    updateAlarmSummary(card, alarm);
    return card;
  }

  function renderAlarms() {
    stopPreview();
    const list = document.getElementById('alarm-list');
    const count = document.getElementById('alarm-count-chip');
    if (!list || !count) {
      return;
    }
    list.replaceChildren();
    count.textContent = `${model.alarms.length} alarm${model.alarms.length === 1 ? '' : 's'}`;

    if (!model.alarms.length) {
      const empty = element('div', 'alarm-empty-state');
      empty.append(
        element('strong', '', 'No alarms configured'),
        element('span', '', 'The scheduler will have nothing to do, which is excellent news for sleep.'),
      );
      list.appendChild(empty);
      return;
    }

    model.alarms.forEach((alarm, index) => list.appendChild(buildAlarmCard(alarm, index)));
  }

  function addAlarm() {
    const number = model.alarms.length + 1;
    const alarm = {
      id: uniqueAlarmId(`alarm-${number}`),
      enabled: false,
      label: `Alarm ${number}`,
      time: '11:00',
      days: dayOptions.map((day) => day.id),
      snooze_minutes: model.defaults.snooze_minutes,
      ring_minutes: model.defaults.ring_minutes,
      occurrence_expiry_minutes: model.defaults.occurrence_expiry_minutes,
      source: {
        type: 'tone',
        tone_id: model.defaults.tone_id,
        fallback_tone_id: model.defaults.fallback_tone_id,
      },
      volume: { start_percent: 60, target_percent: 85, fade_seconds: 10 },
    };
    model.alarms.push(alarm);
    renderAlarms();
    document.querySelector(`[data-alarm-id="${alarm.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function validateModel() {
    const ids = new Set();
    for (const alarm of model.alarms) {
      alarm.label = String(alarm.label || '').trim();
      if (!alarm.label) {
        throw new Error('Every alarm needs a label.');
      }
      if (ids.has(alarm.id)) {
        throw new Error(`Duplicate alarm ID: ${alarm.id}.`);
      }
      ids.add(alarm.id);
      if (!TIME_RE.test(String(alarm.time || ''))) {
        throw new Error(`${alarm.label} has an invalid time. Use HH:MM in 24-hour time.`);
      }
      if (!Array.isArray(alarm.days) || !alarm.days.length) {
        throw new Error(`${alarm.label} must have at least one selected day.`);
      }
      if (!toneById(alarm.source.tone_id)) {
        throw new Error(`${alarm.label} has an unknown tone.`);
      }
      alarm.snooze_minutes = clamp(alarm.snooze_minutes, model.defaults.snooze_minutes, 1, 60);
      alarm.ring_minutes = clamp(alarm.ring_minutes, model.defaults.ring_minutes, 1, 10);
      alarm.occurrence_expiry_minutes = clamp(alarm.occurrence_expiry_minutes, model.defaults.occurrence_expiry_minutes, 15, 1440);
    }
    return model;
  }

  async function saveAlarmModel() {
    validateModel();
    showStatus('Saving alarm configuration…', 'info');
    const response = await fetch('/api/alarms/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(model),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Alarm configuration save failed (${response.status}).`);
    }
    model = payload.alarm;
    showStatus(payload.message || 'Alarm configuration saved.', 'success');
  }

  form.addEventListener('submit', async (event) => {
    if (bypassSubmit || !modelLoaded) {
      return;
    }
    event.preventDefault();
    stopPreview();
    try {
      await saveAlarmModel();
      bypassSubmit = true;
      HTMLFormElement.prototype.submit.call(form);
    } catch (error) {
      showStatus(error.message || 'Could not save alarm configuration.', 'error');
      document.getElementById('settings-panel-alarms')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });

  async function initialise() {
    try {
      const response = await fetch('/api/alarms/config', { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Alarm configuration could not be loaded (${response.status}).`);
      }
      model = payload.alarm;
      tonesManifest = payload.tones;
      dayOptions = payload.days;
      renderPanelChrome();
      renderDefaults();
      renderAlarms();
      document.getElementById('alarm-add-button')?.addEventListener('click', addAlarm);
      modelLoaded = true;
    } catch (error) {
      showStatus(error.message || 'Alarm configuration could not be loaded.', 'error');
    }
  }

  window.addEventListener('pagehide', stopPreview);
  initialise();
})();
