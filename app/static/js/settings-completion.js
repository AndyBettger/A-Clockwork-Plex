(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsCompletionLoaded) return;
  window.__aClockworkPlexSettingsCompletionLoaded = true;

  const form = document.getElementById('settings-unified-form');
  if (!form) return;

  const path = (name) => document.querySelector(`[data-setting-path="${name}"]`);
  let lastForecastStatus = null;

  function getPath(object, dotted) {
    return String(dotted).split('.').filter(Boolean).reduce((value, key) => value?.[key], object);
  }

  function populateControls(settings) {
    document.querySelectorAll('[data-settings-completion-control][data-setting-path]').forEach((control) => {
      const value = getPath(settings, control.dataset.settingPath);
      if (control.type === 'checkbox') control.checked = value === true;
      else if (value !== undefined && value !== null) control.value = String(value);
    });
    updateDimmingOutput();
    applyDimmingPreviewConfiguration();
    const format = getPath(settings, 'display.clock_format');
    if (format) window.ACPTime?.setFormat?.(format, { announce: false });
  }

  function snapshotWhenReady(callback, attempts = 80) {
    const snapshot = window.ACPUnifiedSettings?.getSnapshot?.();
    if (snapshot?.settings) {
      callback(snapshot);
      return;
    }
    if (attempts > 0) window.setTimeout(() => snapshotWhenReady(callback, attempts - 1), 100);
  }

  function installDimmingSettings() {
    const panel = document.querySelector('[data-settings-section="display"]');
    if (!panel || panel.querySelector('[data-night-dimming-settings]')) return;

    const card = document.createElement('section');
    card.className = 'settings-card settings-night-dimming-card';
    card.dataset.nightDimmingSettings = 'true';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h3>Night dimming</h3>
          <p class="muted small">A red astronomy-style night overlay with touch-to-wake. The Alarm screen always remains fully visible.</p>
        </div>
        <span class="settings-chip" data-night-dim-status>Off</span>
      </div>
      <div class="settings-grid two-col">
        <label class="setting-toggle wide">
          <input type="checkbox" data-settings-completion-control data-setting-path="display.night_dim_enabled">
          <span><strong>Enable scheduled dimming</strong><small>The schedule may cross midnight.</small></span>
        </label>
        <label class="setting-field">
          <span>Dim from</span>
          <input type="text" inputmode="none" data-keyboard="time" placeholder="HH:MM" data-settings-completion-control data-setting-path="display.night_dim_start">
        </label>
        <label class="setting-field">
          <span>Return to daytime</span>
          <input type="text" inputmode="none" data-keyboard="time" placeholder="HH:MM" data-settings-completion-control data-setting-path="display.night_dim_end">
        </label>
        <label class="setting-field wide">
          <span>Night brightness</span>
          <input type="range" min="5" max="80" step="1" data-settings-completion-control data-setting-path="display.night_dim_level_percent">
          <output data-night-dim-level>18%</output>
          <small>The red multiply overlay suppresses green and blue light without altering the Pi display driver or audio graph.</small>
        </label>
        <label class="setting-field">
          <span>Stay awake after touch</span>
          <select data-settings-completion-control data-setting-path="display.night_dim_wake_seconds">
            <option value="15">15 seconds</option>
            <option value="30">30 seconds</option>
            <option value="60">1 minute</option>
            <option value="120">2 minutes</option>
            <option value="300">5 minutes</option>
          </select>
        </label>
        <label class="setting-toggle">
          <input type="checkbox" data-settings-completion-control data-setting-path="display.night_clock_mode">
          <span><strong>Very-dark Clock mode</strong><small>Temporarily hides Weather and the footer during the dim schedule.</small></span>
        </label>
        <label class="setting-toggle">
          <input type="checkbox" data-settings-completion-control data-setting-path="display.night_burn_in_shift">
          <span><strong>Subtle burn-in shift</strong><small>Moves the night Clock by a few pixels every five minutes.</small></span>
        </label>
      </div>
      <div class="settings-action-row">
        <button class="button settings-secondary" type="button" data-action="preview-night-dimming">Preview for 8 seconds</button>
        <span class="muted small" data-night-dim-message>First touch wakes the screen without activating the control beneath it.</span>
      </div>`;

    const motionCard = [...panel.querySelectorAll('.settings-card')]
      .find((candidate) => candidate.querySelector('h3')?.textContent.trim() === 'Motion');
    if (motionCard) panel.insertBefore(card, motionCard);
    else panel.appendChild(card);

    const clockHelp = path('display.clock_format')?.closest('.setting-field')?.querySelector('small');
    if (clockHelp) clockHelp.textContent = 'Used by every dashboard time display; alarm configuration fields remain stored as 24-hour HH:MM.';

    card.addEventListener('input', () => {
      updateDimmingOutput();
      applyDimmingPreviewConfiguration();
    });
    card.addEventListener('change', applyDimmingPreviewConfiguration);
    card.querySelector('[data-action="preview-night-dimming"]')?.addEventListener('click', () => {
      applyDimmingPreviewConfiguration();
      window.ACPDisplayDimming?.preview?.(8);
      const message = card.querySelector('[data-night-dim-message]');
      if (message) message.textContent = 'Previewing the selected red night level for eight seconds. Touch the screen to wake it.';
      window.setTimeout(() => {
        if (message) message.textContent = 'First touch wakes the screen without activating the control beneath it.';
      }, 8300);
    });
  }

  function dimmingModel() {
    return {
      night_dim_enabled: path('display.night_dim_enabled')?.checked === true,
      night_dim_start: path('display.night_dim_start')?.value || '22:00',
      night_dim_end: path('display.night_dim_end')?.value || '07:00',
      night_dim_level_percent: Number(path('display.night_dim_level_percent')?.value || 18),
      night_dim_wake_seconds: Number(path('display.night_dim_wake_seconds')?.value || 30),
      night_clock_mode: path('display.night_clock_mode')?.checked === true,
      night_burn_in_shift: path('display.night_burn_in_shift')?.checked === true,
    };
  }

  function updateDimmingOutput() {
    const value = Number(path('display.night_dim_level_percent')?.value || 18);
    const output = document.querySelector('[data-night-dim-level]');
    if (output) output.textContent = `${Math.round(value)}%`;
  }

  function applyDimmingPreviewConfiguration() {
    const model = dimmingModel();
    const status = window.ACPDisplayDimming?.configure?.(model);
    const chip = document.querySelector('[data-night-dim-status]');
    if (chip) {
      chip.textContent = !model.night_dim_enabled
        ? 'Off'
        : status?.active ? 'Red night mode' : `${model.night_dim_start}–${model.night_dim_end}`;
      chip.classList.toggle('is-warning', model.night_dim_enabled && status?.active !== true);
    }
  }

  function installGlobalClockFormat() {
    const control = path('display.clock_format');
    if (!control || control.dataset.globalClockFormatOwner === 'true') return;
    control.dataset.globalClockFormatOwner = 'true';
    const apply = () => {
      const format = control.value === '12h' ? '12h' : '24h';
      window.ACPDashboardPreferences?.write?.({ clockFormat: format });
      window.ACPTime?.setFormat?.(format);
      renderForecastFetchedTime(lastForecastStatus);
    };
    control.addEventListener('input', apply);
    control.addEventListener('change', apply);
  }

  function renderForecastFetchedTime(status) {
    if (!status || !status.fetched_at) return;
    lastForecastStatus = status;
    const message = document.querySelector('[data-forecast-message]');
    if (!message || message.dataset.actionMessage === 'true') return;
    const formatted = window.ACPTime?.formatDateTime?.(status.fetched_at, {
      seconds: false,
      weekday: '',
    });
    if (!formatted) return;

    const nextText = `Last fetched ${formatted}`;
    if (message.textContent !== nextText) message.textContent = nextText;
    if (message.dataset.acpForecastFetchedAt !== status.fetched_at) {
      message.dataset.acpForecastFetchedAt = status.fetched_at;
    }
  }

  function installForecastTimeAuthority() {
    const message = document.querySelector('[data-forecast-message]');
    if (!message || message.dataset.acpTimeAuthority === 'true') return;
    message.dataset.acpTimeAuthority = 'true';

    document.querySelector('[data-action="refresh-forecast"]')?.addEventListener('click', () => {
      window.setTimeout(() => {
        fetch('/api/settings', { cache: 'no-store' })
          .then((response) => response.ok ? response.json() : null)
          .then((payload) => renderForecastFetchedTime(payload?.status?.forecast))
          .catch(() => {});
      }, 1200);
    });

    window.addEventListener('acp:clock-format-changed', () => renderForecastFetchedTime(lastForecastStatus));
  }

  function removeRetiredAdvancedAudioControls() {
    const page = document.querySelector('[data-settings-subpage="advanced:audio"]');
    if (!page || page.dataset.readOnlyDiagnosticsReady === 'true') return;
    page.dataset.readOnlyDiagnosticsReady = 'true';

    const retiredPaths = new Set([
      'alarm_audio.shared_mixer_enabled',
      'alarm_audio.hardware_device',
      'alarm_audio.alsa_device',
    ]);
    page.querySelectorAll('[data-setting-path]').forEach((control) => {
      if (retiredPaths.has(control.dataset.settingPath)) control.closest('label')?.remove();
    });
    page.querySelectorAll('label').forEach((label) => {
      const text = label.textContent.replace(/\s+/g, ' ').trim();
      if (/^(Use shared ALSA mixer|Physical DAC|Alarm PCM)\b/i.test(text)) label.remove();
    });

    const card = page.querySelector('.settings-card');
    const grid = card?.querySelector('.settings-grid');
    const testDuration = path('alarm_audio.test_duration_seconds')?.closest('label');
    if (grid && testDuration && testDuration.parentElement === grid) {
      const heading = document.createElement('div');
      heading.className = 'setting-field settings-diagnostics-explainer';
      heading.innerHTML = '<span>Configuration boundary</span><strong>Read-only audio route</strong><small>Physical DAC, shared PCM and mixer readiness are reported below. Changing the live route requires the guarded audio-maintenance procedure.</small>';
      grid.insertBefore(heading, testDuration);
    }

    const title = card?.querySelector('h3');
    if (title) title.textContent = 'Audio diagnostics and alarm tests';
    const subpageRow = document.querySelector('[data-settings-subpage-target="advanced:audio"]');
    subpageRow?.classList.remove('is-dirty');
    subpageRow?.querySelector('.settings-subpage-dirty-dot')?.remove();
    page.querySelectorAll('.settings-option-dirty').forEach((element) => element.classList.remove('settings-option-dirty'));

    const advancedRow = document.querySelector('[data-settings-section-target="advanced"]');
    if (advancedRow?.dataset.externalDirty === 'true') {
      advancedRow.dataset.externalDirty = 'false';
      const dot = advancedRow.querySelector('.settings-dirty-dot');
      if (dot) dot.hidden = true;
    }
  }

  function clarifyForecastLength() {
    const control = path('weather.forecast.forecast_days');
    if (!control) return;
    const field = control.closest('.setting-field');
    let help = field?.querySelector('small');
    if (!help && field) {
      help = document.createElement('small');
      field.appendChild(help);
    }
    if (help) help.textContent = 'Open-Meteo supports up to 16 days; the Weather page renders every returned daily card.';
  }

  function installAboutBadge(panel) {
    const message = panel.querySelector('#about-message');
    if (!message || message.closest('.settings-about-message-row')) return;
    const row = document.createElement('div');
    row.className = 'settings-about-message-row';
    const badge = document.createElement('span');
    badge.className = 'settings-about-42-badge';
    badge.textContent = '42';
    badge.setAttribute('aria-label', 'The answer is 42');
    message.parentNode.insertBefore(row, message);
    row.append(badge, message);
  }

  function updateAbout() {
    const panel = document.querySelector('[data-settings-section="about"]');
    if (!panel || panel.dataset.currentAboutReady === 'true') return;
    panel.dataset.currentAboutReady = 'true';
    const headerCopy = panel.querySelector('.settings-detail-header p');
    if (headerCopy) headerCopy.textContent = 'Current appliance build, validated capabilities and project links.';
    const description = panel.querySelector('.settings-about-copy .muted');
    if (description) description.textContent = 'A Raspberry Pi touchscreen appliance for Plexamp, NFC albums, AirPlay, alarms, Clock, local Weather and guarded audio control.';
    installAboutBadge(panel);

    const current = document.createElement('section');
    current.className = 'settings-card';
    current.innerHTML = `
      <h3>Current appliance</h3>
      <div class="settings-about-grid" data-about-appliance-status>
        <div class="settings-about-reading"><span>Dashboard</span><strong>Unified kiosk</strong><small>Clock, Weather and source-aware screen projection</small></div>
        <div class="settings-about-reading"><span>Audio</span><strong>Shared mixer</strong><small>Plexamp, AirPlay and alarms with manual post-alarm resume</small></div>
        <div class="settings-about-reading"><span>Settings</span><strong>Autosaved</strong><small>Revisioned validation with managed AirPlay naming</small></div>
        <div class="settings-about-reading"><span>Next phase</span><strong>Production EQ</strong><small>Guarded CamillaDSP rollout; old bare installer remains blocked</small></div>
      </div>`;
    const projectLinks = [...panel.querySelectorAll('.settings-card')]
      .find((card) => card.querySelector('h3')?.textContent.trim() === 'Project links');
    panel.insertBefore(current, projectLinks || null);

    fetch('/api/settings', { cache: 'no-store' })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        if (!payload?.settings) return;
        const readings = current.querySelectorAll('.settings-about-reading');
        const receiver = payload.settings.airplay?.receiver_name;
        const forecast = payload.status?.forecast?.status;
        const eq = payload.status?.eq?.available === true ? 'Production ready' : 'Guarded rollout pending';
        if (readings[0] && receiver) readings[0].querySelector('small').textContent = `Kiosk active · AirPlay receiver ${receiver}`;
        if (readings[2] && forecast) readings[2].querySelector('small').textContent = `Autosave active · Forecast ${forecast}`;
        if (readings[3]) readings[3].querySelector('small').textContent = eq;
      })
      .catch(() => {});
  }

  function initialise() {
    installDimmingSettings();
    installGlobalClockFormat();
    installForecastTimeAuthority();
    removeRetiredAdvancedAudioControls();
    clarifyForecastLength();
    updateAbout();
    snapshotWhenReady((snapshot) => {
      populateControls(snapshot.settings);
      renderForecastFetchedTime(snapshot.status?.forecast);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialise, { once: true });
  else initialise();
})();
