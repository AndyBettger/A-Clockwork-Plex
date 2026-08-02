(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const API = '/api/settings';
  const form = document.getElementById('settings-unified-form');
  if (!form) return;

  const sectionButtons = [...document.querySelectorAll('[data-settings-section-target]')];
  const sectionPanels = [...document.querySelectorAll('[data-settings-section]')];
  const saveBar = document.querySelector('[data-settings-save-bar]');
  const saveTitle = document.querySelector('[data-settings-save-title]');
  const saveMessage = document.querySelector('[data-settings-save-message]');
  const saveButton = form.querySelector('button[type="submit"]');
  const discardButton = form.querySelector('[data-action="discard-settings"]');
  const sidebarState = document.querySelector('[data-settings-sidebar-state]');
  const confirmation = document.querySelector('[data-settings-confirmation]');
  const providers = new Map();
  const dirtySections = new Set();
  const numericPaths = new Set([
    'dashboard.idle_timeout_seconds',
    'display.transition_duration_ms',
    'weather.auto_refresh_seconds',
    'weather.forecast.latitude',
    'weather.forecast.longitude',
    'weather.forecast.forecast_days',
    'weather.forecast.refresh_minutes',
    'airplay.default_volume_percent',
    'airplay.pause_hold_seconds',
    'alarm_audio.test_duration_seconds',
    'audio.eq.bands.bass',
    'audio.eq.bands.mid',
    'audio.eq.bands.treble',
  ]);
  let snapshot = null;
  let loadedSettings = null;
  let saveInFlight = false;
  let activeSection = 'general';

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const pathParts = (path) => String(path || '').split('.').filter(Boolean);

  function getPath(object, path) {
    return pathParts(path).reduce((value, part) => value?.[part], object);
  }

  function setPath(object, path, value) {
    const parts = pathParts(path);
    let target = object;
    parts.forEach((part, index) => {
      if (index === parts.length - 1) {
        target[part] = value;
      } else {
        if (!target[part] || typeof target[part] !== 'object' || Array.isArray(target[part])) target[part] = {};
        target = target[part];
      }
    });
  }

  function sectionFor(element) {
    return element?.closest?.('[data-settings-section]')?.dataset.settingsSection || activeSection;
  }

  function setSaveState(title, message, tone = 'clean') {
    if (saveTitle) saveTitle.textContent = title;
    if (saveMessage) saveMessage.textContent = message;
    saveBar?.classList.toggle('is-dirty', tone === 'dirty');
    saveBar?.classList.toggle('is-error', tone === 'error');
  }

  function updateDirtyUi() {
    sectionButtons.forEach((button) => {
      const dot = button.querySelector('.settings-dirty-dot');
      if (dot) dot.hidden = !dirtySections.has(button.dataset.settingsSectionTarget);
    });
    const dirty = dirtySections.size > 0;
    if (saveButton) saveButton.disabled = !dirty || saveInFlight || !snapshot;
    if (discardButton) discardButton.disabled = !dirty || saveInFlight || !snapshot;
    if (sidebarState) sidebarState.textContent = dirty ? `${dirtySections.size} changed` : 'All saved';
    if (dirty) setSaveState(`${dirtySections.size} section${dirtySections.size === 1 ? '' : 's'} changed`, 'Review or save the staged configuration.', 'dirty');
    else if (snapshot) setSaveState('All changes saved', 'Live controls and tests remain immediate.', 'clean');
  }

  function markDirty(section = activeSection) {
    if (!snapshot || saveInFlight) return;
    dirtySections.add(section || 'general');
    updateDirtyUi();
  }

  function activateSection(section, { updateHash = true } = {}) {
    const valid = sectionPanels.some((panel) => panel.dataset.settingsSection === section) ? section : 'general';
    activeSection = valid;
    sectionButtons.forEach((button) => {
      const active = button.dataset.settingsSectionTarget === valid;
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    sectionPanels.forEach((panel) => { panel.hidden = panel.dataset.settingsSection !== valid; });
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'instant' });
    if (updateHash) history.replaceState(null, '', `#${valid}`);
  }

  function openSubpage(key) {
    const [section] = String(key).split(':');
    activateSection(section, { updateHash: false });
    const panel = document.querySelector(`[data-settings-section="${section}"]`);
    panel?.querySelector(`[data-settings-overview="${section}"]`)?.setAttribute('hidden', '');
    panel?.querySelectorAll('[data-settings-subpage]').forEach((page) => { page.hidden = page.dataset.settingsSubpage !== key; });
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'instant' });
    history.replaceState(null, '', `#${section}/${key.split(':')[1]}`);
  }

  function closeSubpage(section) {
    const panel = document.querySelector(`[data-settings-section="${section}"]`);
    panel?.querySelector(`[data-settings-overview="${section}"]`)?.removeAttribute('hidden');
    panel?.querySelectorAll('[data-settings-subpage]').forEach((page) => { page.hidden = true; });
    history.replaceState(null, '', `#${section}`);
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'instant' });
  }

  function initialRoute() {
    const route = location.hash.replace(/^#/, '');
    if (!route) return activateSection('general', { updateHash: false });
    const [section, subpage] = route.split('/');
    if (subpage) openSubpage(`${section}:${subpage}`);
    else activateSection(section, { updateHash: false });
  }

  function controlValue(control) {
    const path = control.dataset.settingPath;
    if (control.type === 'checkbox') return control.checked;
    if (numericPaths.has(path)) {
      const text = String(control.value ?? '').trim();
      if (!text && ['weather.forecast.latitude', 'weather.forecast.longitude'].includes(path)) return null;
      const number = Number(text);
      return Number.isFinite(number) ? number : text;
    }
    return control.value;
  }

  function renderOutput(path, value) {
    document.querySelectorAll(`[data-setting-output="${path}"]`).forEach((output) => {
      const number = Number(value);
      if (path === 'airplay.default_volume_percent') output.textContent = `${Math.round(number || 0)}%`;
      else if (path.startsWith('audio.eq.bands.')) output.textContent = `${number > 0 ? '+' : ''}${Number.isFinite(number) ? number.toFixed(1) : '0.0'} dB`;
      else output.textContent = String(value ?? '');
    });
  }

  function populateControls(settings) {
    document.querySelectorAll('[data-setting-path]').forEach((control) => {
      const path = control.dataset.settingPath;
      const value = getPath(settings, path);
      if (control.type === 'checkbox') control.checked = value === true;
      else if (value !== undefined && value !== null) control.value = String(value);
      else control.value = '';
      renderOutput(path, value);
    });
    updateUnitPreset();
  }

  function collectSettings() {
    const settings = clone(loadedSettings || {});
    document.querySelectorAll('[data-setting-path]').forEach((control) => {
      if (control.dataset.settingImmediate === 'true') return;
      setPath(settings, control.dataset.settingPath, controlValue(control));
    });
    const clockCards = [...document.querySelectorAll('#clock-card-hidden-inputs input[name="clock_cards"]')].map((input) => input.value);
    if (settings.weather) settings.weather.clock_cards = clockCards;
    providers.forEach((provider, domain) => {
      if (typeof provider.get === 'function') settings[domain] = provider.get();
    });
    return settings;
  }

  function applySnapshot(next) {
    snapshot = next;
    loadedSettings = clone(next.settings);
    populateControls(loadedSettings);
    providers.forEach((provider, domain) => provider.apply?.(clone(next.settings[domain])));
    dirtySections.clear();
    renderHealth(next);
    updateDirtyUi();
  }

  function renderHealth(next) {
    const receiver = next.status?.airplay_receiver || {};
    const receiverChip = document.querySelector('[data-shairport-health]');
    if (receiverChip) {
      receiverChip.textContent = receiver.installed ? (receiver.service_active === false ? 'Service stopped' : 'Managed') : 'Helper required';
      receiverChip.classList.toggle('is-warning', !receiver.installed || receiver.service_active === false);
    }
    const eq = next.status?.eq || {};
    const eqChip = document.querySelector('[data-eq-health]');
    if (eqChip) {
      eqChip.textContent = eq.available ? 'Production ready' : 'Backend unavailable';
      eqChip.classList.toggle('is-warning', !eq.available);
    }
    const eqMessage = document.querySelector('[data-eq-message]');
    if (eqMessage) eqMessage.textContent = eq.error || (eq.available ? 'Changes are staged and applied with Save Changes.' : 'The controls remain visible; saving EQ changes requires the production backend.');
    renderForecastStatus(next.status?.forecast || {});
  }

  function renderForecastStatus(status) {
    const chip = document.querySelector('[data-forecast-status]');
    const message = document.querySelector('[data-forecast-message]');
    const labels = { ready: 'Forecast ready', stale: 'Cached forecast', disabled: 'Forecast off', error: 'Provider error', configuration_required: 'Location required' };
    if (chip) {
      chip.textContent = labels[status.status] || status.status || 'Waiting';
      chip.classList.toggle('is-warning', ['stale', 'error', 'configuration_required'].includes(status.status));
    }
    if (message && !message.dataset.actionMessage) message.textContent = status.last_error || (status.fetched_at ? `Last fetched ${new Date(status.fetched_at).toLocaleString()}` : 'No forecast fetched yet.');
  }

  function currentUnitPreset() {
    const units = {
      temperature: document.querySelector('[data-setting-path="weather.units.temperature"]')?.value,
      pressure: document.querySelector('[data-setting-path="weather.units.pressure"]')?.value,
      rain: document.querySelector('[data-setting-path="weather.units.rain"]')?.value,
      wind: document.querySelector('[data-setting-path="weather.units.wind"]')?.value,
    };
    const presets = {
      uk: { temperature: 'c', pressure: 'hpa', rain: 'mm', wind: 'mph' },
      metric: { temperature: 'c', pressure: 'hpa', rain: 'mm', wind: 'kmh' },
      imperial: { temperature: 'f', pressure: 'inhg', rain: 'in', wind: 'mph' },
    };
    return Object.entries(presets).find(([, values]) => Object.keys(values).every((key) => values[key] === units[key]))?.[0] || 'custom';
  }

  function updateUnitPreset() {
    const selected = currentUnitPreset();
    document.querySelectorAll('[data-unit-preset]').forEach((button) => button.classList.toggle('is-selected', button.dataset.unitPreset === selected));
  }

  function applyUnitPreset(name) {
    const presets = {
      uk: { temperature: 'c', pressure: 'hpa', rain: 'mm', wind: 'mph' },
      metric: { temperature: 'c', pressure: 'hpa', rain: 'mm', wind: 'kmh' },
      imperial: { temperature: 'f', pressure: 'inhg', rain: 'in', wind: 'mph' },
    };
    const values = presets[name];
    if (!values) return updateUnitPreset();
    Object.entries(values).forEach(([key, value]) => {
      const control = document.querySelector(`[data-setting-path="weather.units.${key}"]`);
      if (control) control.value = value;
    });
    updateUnitPreset();
    markDirty('weather');
  }

  function requestConfirmation() {
    return new Promise((resolve) => {
      confirmation.hidden = false;
      const finish = (value) => {
        confirmation.hidden = true;
        confirmation.querySelector('[data-confirmation="confirm"]')?.removeEventListener('click', confirm);
        confirmation.querySelector('[data-confirmation="cancel"]')?.removeEventListener('click', cancel);
        resolve(value);
      };
      const confirm = () => finish(true);
      const cancel = () => finish(false);
      confirmation.querySelector('[data-confirmation="confirm"]')?.addEventListener('click', confirm);
      confirmation.querySelector('[data-confirmation="cancel"]')?.addEventListener('click', cancel);
    });
  }

  async function save(confirmAirplayRestart = false) {
    if (saveInFlight || !snapshot || !dirtySections.size) return;
    saveInFlight = true;
    updateDirtyUi();
    if (saveButton) saveButton.textContent = 'Saving…';
    setSaveState('Saving changes…', 'Validating every changed section before one write.', 'dirty');
    try {
      const response = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: snapshot.revision, settings: collectSettings(), confirm_airplay_restart: confirmAirplayRestart }),
      });
      const payload = await response.json().catch(() => ({}));
      if (response.status === 409 && payload.confirmation_required === 'airplay_restart') {
        saveInFlight = false;
        if (saveButton) saveButton.textContent = 'Save Changes';
        if (await requestConfirmation()) return save(true);
        updateDirtyUi();
        return;
      }
      if (!response.ok || payload.ok === false) throw new Error(payload.error || `Settings returned HTTP ${response.status}.`);
      applySnapshot(payload);
      setSaveState('All changes saved', payload.changed?.airplay_receiver_restarted ? 'AirPlay receiver restarted successfully.' : 'The appliance configuration is current.', 'clean');
    } catch (error) {
      setSaveState('Save failed', error.message || 'The configuration was not changed.', 'error');
    } finally {
      saveInFlight = false;
      if (saveButton) saveButton.textContent = 'Save Changes';
      updateDirtyUi();
    }
  }

  async function load() {
    setSaveState('Loading settings…', 'Reading the appliance configuration.');
    try {
      const response = await fetch(API, { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.error || `Settings returned HTTP ${response.status}.`);
      applySnapshot(payload);
    } catch (error) {
      setSaveState('Settings unavailable', error.message || 'Could not read the appliance configuration.', 'error');
    }
  }

  async function refreshForecast() {
    const message = document.querySelector('[data-forecast-message]');
    if (message) { message.textContent = 'Refreshing forecast…'; message.dataset.actionMessage = 'true'; }
    try {
      const response = await fetch('/api/weather/forecast', { method: 'POST', cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `Forecast returned HTTP ${response.status}.`);
      renderForecastStatus(payload);
      if (message) message.textContent = payload.last_error || 'Forecast cache refreshed.';
    } catch (error) {
      if (message) message.textContent = error.message || 'Could not refresh forecast.';
    } finally {
      if (message) delete message.dataset.actionMessage;
    }
  }

  function mixerCard(channel, data = {}) {
    const article = document.createElement('article');
    article.className = 'settings-live-trim';
    article.innerHTML = `<header><strong>${data.label || channel}</strong><output>${Math.round(Number(data.percent) || 0)}%</output></header><input type="range" min="0" max="100" step="1" value="${Math.round(Number(data.percent) || 0)}" aria-label="${data.label || channel} trim"><small>${data.error || data.pcm || `acp_${channel}`}</small>`;
    const slider = article.querySelector('input');
    const output = article.querySelector('output');
    slider.disabled = data.available !== true || data.pcm_available === false;
    slider.addEventListener('input', () => { output.textContent = `${slider.value}%`; });
    slider.addEventListener('change', async () => {
      const message = document.querySelector('[data-mixer-message]');
      if (message) message.textContent = `Applying ${data.label || channel}…`;
      try {
        const response = await fetch('/api/audio/mixer', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ channel, percent: Number(slider.value) }) });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) throw new Error(payload.error || `Mixer returned HTTP ${response.status}.`);
        if (message) message.textContent = `${data.label || channel} applied immediately.`;
      } catch (error) {
        if (message) message.textContent = error.message || 'Could not change the mixer trim.';
      }
    });
    return article;
  }

  async function refreshMixer() {
    const mount = document.getElementById('settings-audio-trims');
    const hardware = document.getElementById('settings-audio-hardware-status');
    try {
      const response = await fetch('/api/audio/mixer', { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.error || `Mixer returned HTTP ${response.status}.`);
      const mixer = payload.mixer || payload;
      const channels = mixer.channels || {};
      if (mount) mount.replaceChildren(...['master', 'plexamp', 'airplay', 'alarm'].map((channel) => mixerCard(channel, channels[channel] || {})));
      if (hardware) hardware.innerHTML = `<div class="settings-status-reading"><span>Shared mixer</span><strong>${mixer.available && mixer.configured ? 'Ready' : 'Needs attention'}</strong><small>${mixer.error || mixer.hardware_pcm || 'No hardware detail'}</small></div><div class="settings-status-reading"><span>Sample format</span><strong>${mixer.sample_rate_hz || 44100} Hz</strong><small>${mixer.channels_count || 2} channels</small></div>`;
    } catch (error) {
      if (mount) mount.innerHTML = `<p class="muted">${error.message || 'Mixer unavailable.'}</p>`;
      if (hardware) hardware.innerHTML = `<p class="muted">${error.message || 'Mixer unavailable.'}</p>`;
    }
  }

  async function refreshAuthorities() {
    const output = document.querySelector('[data-authority-status]');
    if (!output) return;
    output.textContent = 'Loading…';
    try {
      const [playbackResponse, screenResponse] = await Promise.all([fetch('/api/playback/state', { cache: 'no-store' }), fetch('/api/screen/state?visible_surface=settings', { cache: 'no-store' })]);
      const playback = await playbackResponse.json();
      const screen = await screenResponse.json();
      output.textContent = JSON.stringify({ playback: playback.playback || playback, screen: screen.screen || screen }, null, 2);
    } catch (error) { output.textContent = error.message || 'Authority diagnostics unavailable.'; }
  }

  async function refreshServices() {
    const mount = document.querySelector('[data-service-status]');
    if (!mount) return;
    try {
      const [statusResponse, settingsResponse] = await Promise.all([fetch('/api/status', { cache: 'no-store' }), fetch(API, { cache: 'no-store' })]);
      const status = await statusResponse.json();
      const settings = await settingsResponse.json();
      const receiver = settings.status?.airplay_receiver || {};
      const forecast = settings.status?.forecast || {};
      const plexamp = status?.state?.plexamp || {};
      mount.innerHTML = `<div class="settings-status-reading"><span>Plexamp</span><strong>${plexamp.available === false ? 'Unavailable' : 'Configured'}</strong><small>${plexamp.error || settings.settings?.plexamp?.url || ''}</small></div><div class="settings-status-reading"><span>Shairport Sync</span><strong>${receiver.service_active ? 'Active' : receiver.installed ? 'Stopped' : 'Helper missing'}</strong><small>${receiver.receiver_name || receiver.error || ''}</small></div><div class="settings-status-reading"><span>Forecast</span><strong>${forecast.status || 'Unknown'}</strong><small>${forecast.last_error || forecast.fetched_at || ''}</small></div>`;
    } catch (error) { mount.innerHTML = `<p class="muted">${error.message || 'Service status unavailable.'}</p>`; }
  }

  async function alarmAudioAction(action) {
    const message = document.querySelector('[data-alarm-audio-message]');
    const endpoint = action === 'stop' ? '/api/alarms/audio/stop' : '/api/alarms/audio/test';
    try {
      const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(action === 'stop' ? {} : { full_screen: false }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.error || `Alarm audio returned HTTP ${response.status}.`);
      if (message) message.textContent = payload.message || (action === 'stop' ? 'Alarm audio stopped.' : 'Controlled tone test started.');
    } catch (error) { if (message) message.textContent = error.message || 'Alarm audio action failed.'; }
  }

  function registerDomain(name, provider) {
    providers.set(name, provider || {});
    if (snapshot && provider?.apply) provider.apply(clone(snapshot.settings[name]));
  }

  window.ACPUnifiedSettings = { registerDomain, markDirty, getSnapshot: () => clone(snapshot) };

  sectionButtons.forEach((button) => button.addEventListener('click', () => {
    activateSection(button.dataset.settingsSectionTarget);
    closeSubpage(button.dataset.settingsSectionTarget);
  }));
  document.querySelectorAll('[data-settings-subpage-target]').forEach((button) => button.addEventListener('click', () => openSubpage(button.dataset.settingsSubpageTarget)));
  document.querySelectorAll('[data-settings-back]').forEach((button) => button.addEventListener('click', () => closeSubpage(button.dataset.settingsBack)));
  document.querySelectorAll('[data-unit-preset]').forEach((button) => button.addEventListener('click', () => applyUnitPreset(button.dataset.unitPreset)));

  form.addEventListener('input', (event) => {
    const control = event.target.closest('[data-setting-path]');
    if (!control) return;
    renderOutput(control.dataset.settingPath, controlValue(control));
    if (control.dataset.settingPath.startsWith('weather.units.')) updateUnitPreset();
    markDirty(sectionFor(control));
  });
  form.addEventListener('change', (event) => {
    const control = event.target.closest('[data-setting-path]');
    if (control) markDirty(sectionFor(control));
  });
  form.addEventListener('click', (event) => {
    if (event.target.closest('.clock-card-toggle, .clock-card-order-button, .clock-card-remove-button')) markDirty('weather');
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'refresh-forecast') refreshForecast();
    if (action === 'refresh-mixer') refreshMixer();
    if (action === 'eq-flat') {
      ['bass', 'mid', 'treble'].forEach((band) => {
        const control = document.querySelector(`[data-setting-path="audio.eq.bands.${band}"]`);
        if (control) { control.value = '0'; renderOutput(`audio.eq.bands.${band}`, 0); }
      });
      markDirty('audio');
    }
    if (action === 'refresh-authorities') refreshAuthorities();
    if (action === 'refresh-services') refreshServices();
    if (action === 'alarm-audio-test') alarmAudioAction('test');
    if (action === 'alarm-audio-stop') alarmAudioAction('stop');
    if (action === 'discard-settings') { populateControls(loadedSettings); providers.forEach((provider, domain) => provider.apply?.(clone(loadedSettings[domain]))); dirtySections.clear(); updateDirtyUi(); }
  });
  form.addEventListener('submit', (event) => { event.preventDefault(); save(false); });

  const hiddenCards = document.getElementById('clock-card-hidden-inputs');
  if (hiddenCards) new MutationObserver(() => snapshot && markDirty('weather')).observe(hiddenCards, { childList: true, subtree: true });

  initialRoute();
  refreshMixer();
  refreshAuthorities();
  refreshServices();
  load();
})();
