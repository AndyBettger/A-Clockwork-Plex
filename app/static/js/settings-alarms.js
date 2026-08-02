(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const scheduleMount = document.getElementById('settings-alarm-schedule');
  const defaultsMount = document.getElementById('settings-alarm-defaults');
  if (!scheduleMount || !defaultsMount) return;

  const TIME_RE = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
  const SNOOZE_PRESETS = [5, 8, 10, 15, 20, 25, 30];
  const RING_PRESETS = [1, 2, 3, 5, 10];
  const EXPIRY_PRESETS = [30, 60, 120, 180, 240, 360];
  const SAFE_PREVIEW_VOLUME_PERCENT = 15;
  const SAFE_PREVIEW_GAIN = SAFE_PREVIEW_VOLUME_PERCENT / 100;

  let model = null;
  let tones = [];
  let days = [];
  let previewContext = null;
  let previewNodes = [];
  let previewTimer = null;
  let previewButton = null;
  let hasRenderedSchedule = false;

  const timePickerRefreshers = new Set();
  const expandedAlarmIds = new Set();

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const clamp = (value, fallback, minimum, maximum) => {
    const parsed = Number.parseInt(String(value), 10);
    return Math.max(minimum, Math.min(maximum, Number.isFinite(parsed) ? parsed : fallback));
  };
  const node = (tag, className = '', text = '') => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  };
  const markDirty = () => window.ACPUnifiedSettings?.markDirty?.('alarms');
  const toneById = (id) => tones.find((tone) => tone.id === id);
  const toneLabel = (id) => toneById(id)?.label || id || 'Unknown tone';
  const dayLabel = (id) => days.find((day) => day.id === id)?.label || id;
  const currentClockFormat = () => (
    String(window.ACPTime?.clockFormat || document.documentElement.dataset.clockFormat || '24h').toLowerCase() === '12h'
      ? '12h'
      : '24h'
  );

  function scheduleSummary(selected) {
    const joined = selected.join(',');
    if (selected.length === 7) return 'Every day';
    if (joined === 'mon,tue,wed,thu,fri') return 'Weekdays';
    if (joined === 'sat,sun') return 'Weekends';
    return selected.map(dayLabel).join(' ') || 'No days';
  }

  function summaryTime(value) {
    if (!TIME_RE.test(String(value || ''))) return '—';
    return window.ACPTime?.formatWallTime?.(value) || value;
  }

  function splitStoredTime(value) {
    const match = String(value || '').match(/^(\d{2}):(\d{2})$/);
    return {
      hour24: clamp(match?.[1], 11, 0, 23),
      minute: clamp(match?.[2], 0, 0, 59),
    };
  }

  function displayTimeParts(value, format = currentClockFormat()) {
    const { hour24, minute } = splitStoredTime(value);
    if (format === '24h') return { hour: hour24, minute, period: null };
    return {
      hour: hour24 % 12 || 12,
      minute,
      period: hour24 >= 12 ? 'PM' : 'AM',
    };
  }

  function storedTimeFromParts(hour, minute, period, format = currentClockFormat()) {
    let hour24 = clamp(hour, 0, format === '12h' ? 1 : 0, format === '12h' ? 12 : 23);
    const boundedMinute = clamp(minute, 0, 0, 59);
    if (format === '12h') {
      hour24 %= 12;
      if (period === 'PM') hour24 += 12;
    }
    return `${String(hour24).padStart(2, '0')}:${String(boundedMinute).padStart(2, '0')}`;
  }

  function stopPreview() {
    window.clearTimeout(previewTimer);
    previewTimer = null;
    previewNodes.forEach((item) => {
      try { item.stop?.(); item.disconnect?.(); } catch (_error) {}
    });
    previewNodes = [];
    if (previewButton) {
      previewButton.textContent = 'Preview tone';
      previewButton.classList.remove('is-playing');
      previewButton.setAttribute('aria-pressed', 'false');
      previewButton = null;
    }
  }

  async function previewTone(toneId, button) {
    if (previewButton === button) return stopPreview();
    stopPreview();
    const tone = toneById(toneId);
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!tone || !Context) return;

    previewContext ||= new Context();
    await previewContext.resume();
    previewButton = button;
    button.textContent = 'Stop preview';
    button.classList.add('is-playing');
    button.setAttribute('aria-pressed', 'true');

    const master = previewContext.createGain();
    master.gain.value = SAFE_PREVIEW_GAIN;
    master.connect(previewContext.destination);
    previewNodes.push(master);

    const end = previewContext.currentTime + Math.max(1, Math.min(8, Number(tone.preview_seconds || 4)));
    let cursor = previewContext.currentTime + .03;
    const pattern = Array.isArray(tone.pattern) ? tone.pattern : [];
    while (cursor < end && pattern.length) {
      for (const step of pattern) {
        if (cursor >= end) break;
        const duration = clamp(step.duration_ms, 200, 20, 3000) / 1000;
        const gap = clamp(step.gap_ms, 0, 0, 3000) / 1000;
        const oscillator = previewContext.createOscillator();
        const gain = previewContext.createGain();
        oscillator.type = ['sine', 'square', 'sawtooth', 'triangle'].includes(step.wave) ? step.wave : 'sine';
        oscillator.frequency.setValueAtTime(Number(step.frequency) || 440, cursor);
        if (step.end_frequency) {
          oscillator.frequency.linearRampToValueAtTime(Number(step.end_frequency), Math.min(cursor + duration, end));
        }
        gain.gain.setValueAtTime(.0001, cursor);
        gain.gain.linearRampToValueAtTime(Math.min(.22, Number(step.gain) || .12), cursor + .015);
        gain.gain.linearRampToValueAtTime(.0001, Math.min(cursor + duration, end));
        oscillator.connect(gain);
        gain.connect(master);
        oscillator.start(cursor);
        oscillator.stop(Math.min(cursor + duration + .02, end + .02));
        previewNodes.push(oscillator, gain);
        cursor += duration + gap;
      }
    }
    previewTimer = window.setTimeout(stopPreview, Math.max(0, end - previewContext.currentTime) * 1000 + 100);
  }

  function select(values, selected, label = (value) => String(value)) {
    const control = document.createElement('select');
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = String(value);
      option.textContent = label(value);
      option.selected = String(value) === String(selected);
      control.appendChild(option);
    });
    return control;
  }

  function field(label, control, help = '') {
    const wrapper = node('label', 'setting-field');
    wrapper.append(node('span', '', label), control);
    if (help) wrapper.appendChild(node('small', '', help));
    return wrapper;
  }

  function panel(title, description = '') {
    const section = node('section', 'alarm-editor-panel');
    const heading = node('div', 'alarm-editor-panel-heading');
    heading.appendChild(node('h3', '', title));
    if (description) heading.appendChild(node('p', 'muted small', description));
    section.appendChild(heading);
    return section;
  }

  function durationControl(value, presets, minimum, maximum, onChange) {
    const wrapper = node('div', 'alarm-duration-control');
    const preset = presets.includes(Number(value));
    const menu = select([...presets, 'custom'], preset ? value : 'custom', (item) => (
      item === 'custom' ? 'Custom' : `${item} minutes`
    ));
    const custom = document.createElement('input');
    custom.type = 'text';
    custom.inputMode = 'none';
    custom.dataset.keyboard = 'number';
    custom.className = 'alarm-duration-custom';
    custom.value = String(clamp(value, presets[0], minimum, maximum));
    custom.hidden = preset;
    const update = () => {
      custom.hidden = menu.value !== 'custom';
      const next = menu.value === 'custom'
        ? clamp(custom.value, presets[0], minimum, maximum)
        : clamp(menu.value, presets[0], minimum, maximum);
      onChange(next);
      markDirty();
    };
    menu.addEventListener('change', update);
    custom.addEventListener('input', update);
    wrapper.append(menu, custom);
    return wrapper;
  }

  function timePicker(alarm, card) {
    const wrapper = node('div', 'alarm-time-field');
    wrapper.appendChild(node('span', 'alarm-field-label', 'Alarm time'));
    const picker = node('div', 'alarm-time-picker');
    wrapper.appendChild(picker);
    wrapper.appendChild(node('small', '', 'Shown in the selected Clock format; stored safely as 24-hour HH:MM.'));

    const render = () => {
      const format = currentClockFormat();
      const parts = displayTimeParts(alarm.time, format);
      picker.replaceChildren();
      picker.dataset.clockFormat = format;

      const hours = format === '12h'
        ? Array.from({ length: 12 }, (_item, index) => index + 1)
        : Array.from({ length: 24 }, (_item, index) => index);
      const minutes = Array.from({ length: 60 }, (_item, index) => index);
      const hour = select(hours, parts.hour, (value) => String(value).padStart(2, '0'));
      const minute = select(minutes, parts.minute, (value) => String(value).padStart(2, '0'));
      hour.className = 'alarm-time-select';
      minute.className = 'alarm-time-select';
      hour.setAttribute('aria-label', 'Alarm hour');
      minute.setAttribute('aria-label', 'Alarm minute');

      let period = parts.period;
      const commit = () => {
        alarm.time = storedTimeFromParts(hour.value, minute.value, period, format);
        updateSummary(card, alarm);
        markDirty();
      };
      hour.addEventListener('change', commit);
      minute.addEventListener('change', commit);
      picker.append(hour, node('span', 'alarm-time-colon', ':'), minute);

      if (format === '12h') {
        const periods = node('div', 'alarm-period-control');
        ['AM', 'PM'].forEach((value) => {
          const button = node('button', 'alarm-period-button', value);
          button.type = 'button';
          const paint = () => {
            const selected = period === value;
            button.classList.toggle('is-selected', selected);
            button.setAttribute('aria-pressed', selected ? 'true' : 'false');
          };
          paint();
          button.addEventListener('click', () => {
            period = value;
            periods.querySelectorAll('.alarm-period-button').forEach((item) => {
              const selected = item.textContent === period;
              item.classList.toggle('is-selected', selected);
              item.setAttribute('aria-pressed', selected ? 'true' : 'false');
            });
            commit();
          });
          periods.appendChild(button);
        });
        picker.appendChild(periods);
      }
    };

    timePickerRefreshers.add(render);
    render();
    return wrapper;
  }

  function renderDefaults() {
    defaultsMount.replaceChildren();
    const card = node('section', 'settings-card');
    card.innerHTML = '<div class="settings-card-heading"><div><h3>Alarm defaults</h3><p class="muted small">Starting values used for newly-created alarms.</p></div><span class="settings-chip">Saved together</span></div>';
    const grid = node('div', 'alarm-model-defaults');
    const snooze = durationControl(model.defaults.snooze_minutes, SNOOZE_PRESETS, 1, 60, (value) => {
      model.defaults.snooze_minutes = value;
    });
    const ring = select(RING_PRESETS, model.defaults.ring_minutes, (value) => `${value} minute${value === 1 ? '' : 's'}`);
    ring.addEventListener('change', () => {
      model.defaults.ring_minutes = Number(ring.value);
      markDirty();
    });
    const expiry = durationControl(model.defaults.occurrence_expiry_minutes, EXPIRY_PRESETS, 15, 1440, (value) => {
      model.defaults.occurrence_expiry_minutes = value;
    });
    const tone = select(tones.map((item) => item.id), model.defaults.tone_id, toneLabel);
    tone.addEventListener('change', () => {
      model.defaults.tone_id = tone.value;
      markDirty();
    });
    grid.append(
      field('Default snooze', snooze, '1–60 minutes.'),
      field('Continuous ring cycle', ring, 'Before the automatic quiet interval.'),
      field('Occurrence expiry', expiry, 'How long a snoozed occurrence remains eligible.'),
      field('Default local tone', tone, 'Used when creating another alarm.'),
    );
    card.appendChild(grid);
    defaultsMount.appendChild(card);
  }

  function uniqueId(label = 'alarm') {
    const base = String(label)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'alarm';
    const used = new Set(model.alarms.map((alarm) => alarm.id));
    let candidate = base;
    let suffix = 2;
    while (used.has(candidate)) candidate = `${base.slice(0, 40)}-${suffix++}`;
    return candidate;
  }

  function updateSummary(card, alarm) {
    card.querySelector('[data-summary-time]').textContent = summaryTime(alarm.time);
    card.querySelector('[data-summary-label]').textContent = alarm.label || 'Unnamed alarm';
    card.querySelector('[data-summary-detail]').textContent = `${scheduleSummary(alarm.days)} · ${toneLabel(alarm.source.tone_id)} · Snooze ${alarm.snooze_minutes} min`;
    const toggle = card.querySelector('[data-alarm-enabled-toggle]');
    if (toggle) {
      toggle.textContent = alarm.enabled ? 'Enabled' : 'Off';
      toggle.classList.toggle('is-off', !alarm.enabled);
      toggle.setAttribute('aria-pressed', alarm.enabled ? 'true' : 'false');
      toggle.setAttribute('aria-label', `${alarm.enabled ? 'Disable' : 'Enable'} ${alarm.label || 'alarm'}`);
    }
    card.classList.toggle('is-disabled', !alarm.enabled);
  }

  function alarmCard(alarm, index) {
    const card = node('article', 'alarm-editor-card');
    card.dataset.alarmId = alarm.id;

    const initiallyExpanded = expandedAlarmIds.has(alarm.id) || (!hasRenderedSchedule && index === 0);
    if (initiallyExpanded) expandedAlarmIds.add(alarm.id);

    const header = node('div', 'alarm-editor-header');
    const summary = node('button', 'alarm-editor-summary');
    summary.type = 'button';
    summary.setAttribute('aria-expanded', initiallyExpanded ? 'true' : 'false');
    summary.innerHTML = '<span class="alarm-editor-time" data-summary-time></span><span class="alarm-editor-title"><strong data-summary-label></strong><span data-summary-detail></span></span><span class="alarm-editor-chevron" aria-hidden="true">⌄</span>';

    const enabled = node('button', 'alarm-enabled-toggle');
    enabled.type = 'button';
    enabled.dataset.alarmEnabledToggle = 'true';
    enabled.addEventListener('click', () => {
      alarm.enabled = !alarm.enabled;
      updateSummary(card, alarm);
      markDirty();
    });
    header.append(summary, enabled);

    const body = node('div', 'alarm-editor-body');
    body.hidden = !initiallyExpanded;
    summary.addEventListener('click', () => {
      const expanded = summary.getAttribute('aria-expanded') === 'true';
      const nextExpanded = !expanded;
      summary.setAttribute('aria-expanded', nextExpanded ? 'true' : 'false');
      body.hidden = !nextExpanded;
      if (nextExpanded) expandedAlarmIds.add(alarm.id);
      else {
        expandedAlarmIds.delete(alarm.id);
        stopPreview();
      }
    });

    const basics = panel('Alarm', 'Name it and choose the exact time without opening the keyboard.');
    const basicsGrid = node('div', 'alarm-basics-grid');
    const labelInput = document.createElement('input');
    labelInput.value = alarm.label;
    labelInput.maxLength = 80;
    labelInput.inputMode = 'none';
    labelInput.dataset.keyboard = 'text';
    labelInput.addEventListener('input', () => {
      alarm.label = labelInput.value;
      updateSummary(card, alarm);
      markDirty();
    });
    basicsGrid.append(field('Alarm name', labelInput), timePicker(alarm, card));
    basics.appendChild(basicsGrid);
    body.appendChild(basics);

    const repeat = panel('Repeat schedule', 'Tap the days when this alarm is allowed to ring.');
    const dayGrid = node('div', 'alarm-day-grid');
    days.forEach((day) => {
      const button = node('button', 'alarm-day-button', day.label);
      button.type = 'button';
      const paint = () => {
        const selected = alarm.days.includes(day.id);
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      };
      paint();
      button.addEventListener('click', () => {
        alarm.days = alarm.days.includes(day.id)
          ? alarm.days.filter((item) => item !== day.id)
          : days.map((item) => item.id).filter((item) => item === day.id || alarm.days.includes(item));
        paint();
        updateSummary(card, alarm);
        markDirty();
      });
      dayGrid.appendChild(button);
    });
    repeat.appendChild(dayGrid);
    body.appendChild(repeat);

    const behaviour = panel('Snooze behaviour', 'Control what happens after the alarm begins ringing.');
    const snooze = durationControl(alarm.snooze_minutes, SNOOZE_PRESETS, 1, 60, (value) => {
      alarm.snooze_minutes = value;
      updateSummary(card, alarm);
    });
    behaviour.appendChild(field('Snooze duration', snooze, 'Used by the Snooze button and automatic quiet interval.'));
    body.appendChild(behaviour);

    const sound = panel('Sound', 'Choose the real scheduled-alarm sound separately from the low-level browser preview.');
    const soundGrid = node('div', 'alarm-sound-grid');
    const tone = select(tones.map((item) => item.id), alarm.source.tone_id, toneLabel);
    const toneDescription = node('p', 'alarm-tone-description', toneById(alarm.source.tone_id)?.description || '');
    tone.addEventListener('change', () => {
      stopPreview();
      alarm.source.tone_id = tone.value;
      toneDescription.textContent = toneById(tone.value)?.description || '';
      updateSummary(card, alarm);
      markDirty();
    });
    soundGrid.appendChild(field('Local alarm tone', tone));
    soundGrid.appendChild(toneDescription);

    const volumeLabel = node('label', 'alarm-tone-volume');
    volumeLabel.appendChild(node('span', '', 'Scheduled alarm target volume'));
    const volume = document.createElement('input');
    volume.type = 'range';
    volume.min = '0';
    volume.max = '100';
    volume.step = '1';
    volume.value = String(alarm.volume.target_percent);
    const volumeOutput = node('strong', '', `${volume.value}%`);
    volume.addEventListener('input', () => {
      alarm.volume.target_percent = Number(volume.value);
      volumeOutput.textContent = `${volume.value}%`;
      markDirty();
    });
    volumeLabel.append(
      volume,
      volumeOutput,
      node('small', '', 'Used by the real scheduled alarm after audio takeover. It never changes preview loudness.'),
    );
    soundGrid.appendChild(volumeLabel);

    const preview = node('div', 'alarm-preview-row');
    const previewCopy = node('div');
    previewCopy.append(
      node('strong', '', 'Low-level preview'),
      node('small', '', `Fixed at ${SAFE_PREVIEW_VOLUME_PERCENT}% browser gain and capped independently from the scheduled alarm volume.`),
    );
    const previewToneButton = node('button', 'button alarm-tone-preview-button', 'Preview tone');
    previewToneButton.type = 'button';
    previewToneButton.setAttribute('aria-pressed', 'false');
    previewToneButton.addEventListener('click', () => previewTone(alarm.source.tone_id, previewToneButton));
    preview.append(previewCopy, previewToneButton);
    soundGrid.appendChild(preview);
    sound.appendChild(soundGrid);
    body.appendChild(sound);

    const actions = node('div', 'alarm-card-actions');
    const duplicate = node('button', 'button settings-secondary', 'Duplicate');
    duplicate.type = 'button';
    duplicate.addEventListener('click', () => {
      const copy = clone(alarm);
      copy.id = uniqueId(`${alarm.label}-copy`);
      copy.label = `${alarm.label || 'Alarm'} copy`.slice(0, 80);
      copy.enabled = false;
      model.alarms.splice(index + 1, 0, copy);
      expandedAlarmIds.add(copy.id);
      renderSchedule();
      markDirty();
    });

    const remove = node('button', 'button alarm-remove-button', 'Remove');
    remove.type = 'button';
    let armed = false;
    let disarmTimer = null;
    remove.addEventListener('click', () => {
      if (!armed) {
        armed = true;
        remove.classList.add('is-armed');
        remove.textContent = 'Tap again to remove';
        window.clearTimeout(disarmTimer);
        disarmTimer = window.setTimeout(() => {
          armed = false;
          remove.classList.remove('is-armed');
          remove.textContent = 'Remove';
        }, 3500);
        return;
      }
      window.clearTimeout(disarmTimer);
      expandedAlarmIds.delete(alarm.id);
      model.alarms = model.alarms.filter((item) => item.id !== alarm.id);
      renderSchedule();
      markDirty();
    });
    actions.append(duplicate, remove);
    body.appendChild(actions);

    card.append(header, body);
    updateSummary(card, alarm);
    return card;
  }

  function renderSchedule() {
    stopPreview();
    timePickerRefreshers.clear();
    scheduleMount.replaceChildren();

    const validIds = new Set(model.alarms.map((alarm) => alarm.id));
    expandedAlarmIds.forEach((id) => {
      if (!validIds.has(id)) expandedAlarmIds.delete(id);
    });

    const card = node('section', 'settings-card alarm-schedule-card');
    const heading = node('div', 'settings-card-heading alarm-schedule-heading');
    const copy = node('div');
    copy.append(
      node('h3', '', 'Alarm schedule'),
      node('p', 'muted small', 'All alarm cards are validated and saved in the same Settings transaction.'),
    );
    heading.append(copy, node('span', 'settings-chip', `${model.alarms.length} alarm${model.alarms.length === 1 ? '' : 's'}`));

    const status = node('div', 'alarm-model-status');
    status.id = 'alarm-model-status';
    status.hidden = true;

    const list = node('div', 'alarm-list');
    if (model.alarms.length) {
      model.alarms.forEach((alarm, index) => list.appendChild(alarmCard(alarm, index)));
    } else {
      const empty = node('div', 'alarm-empty-state');
      empty.append(
        node('strong', '', 'No alarms configured'),
        node('span', '', 'The scheduler has been granted a rare quiet moment.'),
      );
      list.appendChild(empty);
    }

    const add = node('button', 'alarm-add-button', '＋ Add another alarm');
    add.type = 'button';
    add.addEventListener('click', () => {
      const number = model.alarms.length + 1;
      const alarm = {
        id: uniqueId(`alarm-${number}`),
        enabled: false,
        label: `Alarm ${number}`,
        time: '11:00',
        days: days.map((day) => day.id),
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
      expandedAlarmIds.add(alarm.id);
      renderSchedule();
      markDirty();
    });

    card.append(heading, status, list, add);
    scheduleMount.appendChild(card);
    hasRenderedSchedule = true;
  }

  function validatedModel() {
    const ids = new Set();
    model.alarms.forEach((alarm) => {
      alarm.label = String(alarm.label || '').trim();
      if (!alarm.label) throw new Error('Every alarm needs a label.');
      if (!TIME_RE.test(String(alarm.time || ''))) throw new Error(`${alarm.label} has an invalid time. Use HH:MM.`);
      if (!alarm.days?.length) throw new Error(`${alarm.label} must have at least one selected day.`);
      if (ids.has(alarm.id)) throw new Error(`Duplicate alarm ID: ${alarm.id}.`);
      ids.add(alarm.id);
      if (!toneById(alarm.source.tone_id)) throw new Error(`${alarm.label} has an unknown tone.`);
    });
    return clone(model);
  }

  function applySaved(saved) {
    if (!saved || !model) return;
    model = clone(saved);
    renderDefaults();
    renderSchedule();
  }

  async function initialise() {
    try {
      const response = await fetch('/api/alarms/config', { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Alarm configuration returned HTTP ${response.status}.`);
      }
      model = clone(payload.alarm);
      tones = Array.isArray(payload.tones?.tones) ? payload.tones.tones : [];
      days = Array.isArray(payload.days) ? payload.days : [];
      renderDefaults();
      renderSchedule();
      window.ACPUnifiedSettings?.registerDomain?.('alarms', {
        get: validatedModel,
        apply: applySaved,
      });
    } catch (error) {
      scheduleMount.innerHTML = `<section class="settings-card"><p class="muted">${error.message || 'Alarm configuration unavailable.'}</p></section>`;
    }
  }

  window.addEventListener('acp:clock-format-changed', () => {
    timePickerRefreshers.forEach((refresh) => refresh());
    model?.alarms?.forEach((alarm) => {
      const card = scheduleMount.querySelector(`[data-alarm-id="${CSS.escape(alarm.id)}"]`);
      if (card) updateSummary(card, alarm);
    });
  });
  window.addEventListener('pagehide', stopPreview);
  initialise();
})();
