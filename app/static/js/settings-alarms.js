(() => {
  const summary = document.querySelector('[data-alarm-editor-toggle]');
  const body = document.querySelector('[data-alarm-editor-body]');
  const enabled = document.querySelector('input[name="alarm_enabled"]');
  const timeInput = document.querySelector('input[name="alarm_default_time"]');
  const summaryTime = document.querySelector('[data-alarm-summary-time]');
  const summaryState = document.querySelector('[data-alarm-summary-state]');
  const summaryDetail = document.querySelector('.alarm-editor-title span');

  const hiddenSnooze = document.getElementById('alarm-snooze-minutes');
  const presetSnooze = document.getElementById('alarm-snooze-preset');
  const customSnooze = document.getElementById('alarm-snooze-custom');
  const presetValues = new Set(['5', '8', '10', '15', '20', '25', '30']);
  const toneStorageKey = 'a-clockwork-plex.alarm-tone-preview';

  let selectedToneLabel = 'Classic Klaxon';
  let previewContext = null;
  let previewNodes = [];
  let previewTimer = null;
  let previewButton = null;
  let stopButton = null;

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

    if (summaryDetail && hiddenSnooze) {
      summaryDetail.textContent = `Every day · ${selectedToneLabel} · Snooze ${clampSnooze(hiddenSnooze.value)} min`;
    }
  };

  const findDesignValue = (label) => {
    const chips = Array.from(document.querySelectorAll('.alarm-design-chip'));
    const chip = chips.find((item) => item.querySelector('span')?.textContent.trim().toLowerCase() === label.toLowerCase());
    return chip?.querySelector('strong') || null;
  };

  const stopPreview = async () => {
    if (previewTimer) {
      window.clearTimeout(previewTimer);
      previewTimer = null;
    }

    previewNodes.forEach((node) => {
      try {
        node.stop();
      } catch (error) {
      }
    });
    previewNodes = [];

    if (previewContext) {
      try {
        await previewContext.close();
      } catch (error) {
      }
      previewContext = null;
    }

    previewButton?.classList.remove('is-playing');
    if (previewButton) {
      previewButton.textContent = '▶ Preview tone';
    }
    if (stopButton) {
      stopButton.disabled = true;
    }
  };

  const playTone = async (tone, previewSeconds) => {
    await stopPreview();

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error('This browser does not support Web Audio previews.');
    }

    previewContext = new AudioContextClass();
    await previewContext.resume();

    const startAt = previewContext.currentTime + 0.04;
    const finishAt = startAt + Math.max(1, Math.min(10, Number(previewSeconds) || 10));
    let cursor = startAt;
    const pattern = Array.isArray(tone.pattern) ? tone.pattern : [];

    if (!pattern.length) {
      throw new Error('This tone has no playable pattern.');
    }

    while (cursor < finishAt) {
      for (const step of pattern) {
        if (cursor >= finishAt) {
          break;
        }

        const duration = Math.max(40, Number(step.duration_ms) || 200) / 1000;
        const gap = Math.max(0, Number(step.gap_ms) || 0) / 1000;
        const noteEnd = Math.min(cursor + duration, finishAt);
        const oscillator = previewContext.createOscillator();
        const gain = previewContext.createGain();
        const level = Math.max(0.02, Math.min(0.28, Number(step.gain) || 0.16));

        oscillator.type = ['sine', 'square', 'sawtooth', 'triangle'].includes(step.wave) ? step.wave : 'sine';
        oscillator.frequency.setValueAtTime(Math.max(40, Number(step.frequency) || 440), cursor);
        if (step.end_frequency) {
          oscillator.frequency.linearRampToValueAtTime(Math.max(40, Number(step.end_frequency)), noteEnd);
        }

        gain.gain.setValueAtTime(0.0001, cursor);
        gain.gain.exponentialRampToValueAtTime(level, Math.min(cursor + 0.018, noteEnd));
        gain.gain.setValueAtTime(level, Math.max(cursor + 0.018, noteEnd - 0.025));
        gain.gain.exponentialRampToValueAtTime(0.0001, noteEnd);

        oscillator.connect(gain);
        gain.connect(previewContext.destination);
        oscillator.start(cursor);
        oscillator.stop(noteEnd + 0.015);
        previewNodes.push(oscillator);
        cursor = noteEnd + gap;
      }
    }

    previewButton?.classList.add('is-playing');
    if (previewButton) {
      previewButton.textContent = 'Playing preview…';
    }
    if (stopButton) {
      stopButton.disabled = false;
    }

    previewTimer = window.setTimeout(() => {
      stopPreview();
    }, Math.ceil((finishAt - previewContext.currentTime + 0.1) * 1000));
  };

  const buildToneWorkspace = async () => {
    if (!body || body.querySelector('[data-alarm-tone-workspace]')) {
      return;
    }

    let manifest;
    try {
      const response = await fetch('/static/alarm-tones.json', {cache: 'no-store'});
      if (!response.ok) {
        throw new Error(`Tone manifest returned HTTP ${response.status}.`);
      }
      manifest = await response.json();
    } catch (error) {
      console.warn('A Clockwork Plex: could not load alarm tone manifest.', error);
      return;
    }

    const tones = Array.isArray(manifest.tones) ? manifest.tones : [];
    if (!tones.length) {
      return;
    }

    const workspace = document.createElement('section');
    workspace.className = 'alarm-tone-workspace';
    workspace.dataset.alarmToneWorkspace = '';
    workspace.innerHTML = `
      <div class="alarm-tone-heading">
        <div>
          <h3>Local alarm tone</h3>
          <p>Choose a self-contained tone and preview it through the Pi browser.</p>
        </div>
        <span class="alarm-tone-character" data-alarm-tone-character></span>
      </div>
      <div class="alarm-tone-controls">
        <label class="setting-field alarm-tone-select-field">
          <span>Tone</span>
          <select data-alarm-tone-select aria-label="Alarm tone"></select>
        </label>
        <label class="setting-field alarm-tone-volume-field">
          <span>Preview volume</span>
          <input data-alarm-tone-volume type="range" min="15" max="100" value="65" step="5">
          <small><span data-alarm-tone-volume-value>65</span>% · preview only</small>
        </label>
      </div>
      <p class="alarm-tone-description" data-alarm-tone-description></p>
      <div class="alarm-tone-actions">
        <button class="button alarm-tone-preview" type="button" data-alarm-tone-preview>▶ Preview tone</button>
        <button class="button settings-secondary alarm-tone-stop" type="button" data-alarm-tone-stop disabled>■ Stop</button>
      </div>
      <p class="alarm-tone-note">Tone choice is retained in this browser for previewing. Server-side alarm persistence follows in the scheduler data-model pass.</p>
    `;

    const designGrid = body.querySelector('.alarm-design-grid');
    body.insertBefore(workspace, designGrid || body.firstChild);

    const select = workspace.querySelector('[data-alarm-tone-select]');
    const description = workspace.querySelector('[data-alarm-tone-description]');
    const character = workspace.querySelector('[data-alarm-tone-character]');
    const volume = workspace.querySelector('[data-alarm-tone-volume]');
    const volumeValue = workspace.querySelector('[data-alarm-tone-volume-value]');
    previewButton = workspace.querySelector('[data-alarm-tone-preview]');
    stopButton = workspace.querySelector('[data-alarm-tone-stop]');

    tones.forEach((tone) => {
      const option = document.createElement('option');
      option.value = tone.id;
      option.textContent = tone.label;
      select.appendChild(option);
    });

    let savedToneId = manifest.default_tone_id || 'classic-klaxon';
    try {
      const stored = window.localStorage.getItem(toneStorageKey);
      if (stored && tones.some((tone) => tone.id === stored)) {
        savedToneId = stored;
      }
    } catch (error) {
    }
    select.value = savedToneId;

    const applyTone = () => {
      const tone = tones.find((item) => item.id === select.value) || tones[0];
      select.value = tone.id;
      selectedToneLabel = tone.label;
      description.textContent = tone.description || '';
      character.textContent = tone.character || 'Local';
      findDesignValue('Tone')?.replaceChildren(document.createTextNode(tone.label));

      const fallback = tones.find((item) => item.id === manifest.fallback_tone_id);
      if (fallback) {
        findDesignValue('Fallback')?.replaceChildren(document.createTextNode(fallback.label));
      }

      try {
        window.localStorage.setItem(toneStorageKey, tone.id);
      } catch (error) {
      }
      stopPreview();
      updateSummary();
    };

    select.addEventListener('change', applyTone);
    volume.addEventListener('input', () => {
      volumeValue.textContent = volume.value;
    });
    previewButton.addEventListener('click', async () => {
      const tone = tones.find((item) => item.id === select.value) || tones[0];
      const scale = Math.max(0.15, Math.min(1, Number(volume.value) / 100));
      const scaledTone = {
        ...tone,
        pattern: tone.pattern.map((step) => ({
          ...step,
          gain: Math.max(0.01, Math.min(0.28, Number(step.gain || 0.16) * scale)),
        })),
      };

      try {
        await playTone(scaledTone, manifest.preview_seconds || 10);
      } catch (error) {
        console.warn('A Clockwork Plex: alarm preview failed.', error);
        previewButton.textContent = 'Preview unavailable';
        window.setTimeout(() => {
          previewButton.textContent = '▶ Preview tone';
        }, 1800);
      }
    });
    stopButton.addEventListener('click', stopPreview);
    window.addEventListener('pagehide', stopPreview);

    applyTone();
  };

  if (summary && body) {
    summary.addEventListener('click', () => {
      const expanded = summary.getAttribute('aria-expanded') === 'true';
      summary.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      body.hidden = expanded;
      if (expanded) {
        stopPreview();
      }
    });
  }

  enabled?.addEventListener('change', updateSummary);
  timeInput?.addEventListener('input', updateSummary);

  if (!hiddenSnooze || !presetSnooze || !customSnooze) {
    updateSummary();
    buildToneWorkspace();
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
      updateSummary();
      return;
    }

    customSnooze.hidden = true;
    hiddenSnooze.value = String(clampSnooze(presetSnooze.value));
    updateSummary();
  };

  presetSnooze.addEventListener('change', syncSnooze);
  customSnooze.addEventListener('change', syncSnooze);
  customSnooze.addEventListener('blur', syncSnooze);
  hiddenSnooze.form?.addEventListener('submit', syncSnooze);
  updateSummary();
  buildToneWorkspace();
})();
