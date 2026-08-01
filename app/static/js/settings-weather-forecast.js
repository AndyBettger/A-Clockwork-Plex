(() => {
  const panel = document.querySelector('[data-settings-panel="weather"]');
  if (!panel || panel.querySelector('[data-weather-forecast-settings]')) {
    return;
  }

  const card = document.createElement('section');
  card.className = 'settings-card';
  card.dataset.weatherForecastSettings = '';
  card.innerHTML = `
    <div class="settings-card-heading">
      <div>
        <h2>Online forecast</h2>
        <p class="muted small">Keep Ecowitt as the local observation source and add a cached Open-Meteo forecast for this location.</p>
      </div>
      <span class="settings-chip" data-forecast-status>Loading…</span>
    </div>

    <div class="settings-grid two-col">
      <label class="setting-toggle">
        <input type="checkbox" data-forecast-field="enabled">
        <span>Enable online forecast</span>
      </label>
      <div class="setting-field forecast-provider-reading">
        <span>Provider</span>
        <strong>Open-Meteo</strong>
        <small>No API key. Forecast data are cached locally.</small>
      </div>
      <label class="setting-field">
        <span>Latitude</span>
        <input type="text" inputmode="none" autocomplete="off" data-keyboard="text" data-forecast-field="latitude" placeholder="51.5000">
        <small>Decimal degrees; north is positive.</small>
      </label>
      <label class="setting-field">
        <span>Longitude</span>
        <input type="text" inputmode="none" autocomplete="off" data-keyboard="text" data-forecast-field="longitude" placeholder="-0.1200">
        <small>Decimal degrees; west is negative.</small>
      </label>
      <label class="setting-field">
        <span>Forecast length</span>
        <select data-forecast-field="forecast_days">
          <option value="3">3 days</option>
          <option value="5">5 days</option>
          <option value="7">7 days</option>
          <option value="10">10 days</option>
          <option value="14">14 days</option>
          <option value="16">16 days</option>
        </select>
      </label>
      <label class="setting-field">
        <span>Refresh interval</span>
        <select data-forecast-field="refresh_minutes">
          <option value="15">15 minutes</option>
          <option value="30">30 minutes</option>
          <option value="60">1 hour</option>
          <option value="120">2 hours</option>
        </select>
      </label>
      <label class="setting-field">
        <span>Timezone</span>
        <input type="text" inputmode="none" autocomplete="off" data-keyboard="text" data-forecast-field="timezone" value="Europe/London">
        <small>IANA timezone used for forecast timestamps.</small>
      </label>
    </div>

    <div class="forecast-settings-actions">
      <button class="button" type="button" data-forecast-save>Save and refresh forecast</button>
      <span class="muted small" data-forecast-message aria-live="polite"></span>
    </div>

    <div class="forecast-health" data-forecast-health hidden>
      <div><span>Last forecast</span><strong data-forecast-fetched>—</strong></div>
      <div><span>Cache state</span><strong data-forecast-cache-state>—</strong></div>
      <div><span>Provider message</span><strong data-forecast-error>—</strong></div>
    </div>

    <p class="muted small forecast-attribution">Forecast data by <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo.com</a> · CC BY 4.0.</p>
  `;

  const clockCards = panel.querySelector('[data-clock-card-settings]');
  panel.insertBefore(card, clockCards || null);

  if (!document.getElementById('weather-forecast-settings-style')) {
    const style = document.createElement('style');
    style.id = 'weather-forecast-settings-style';
    style.textContent = `
      [data-weather-forecast-settings] .settings-card-heading { align-items: flex-start; }
      .forecast-provider-reading strong { font-size: 1.05rem; }
      .forecast-settings-actions { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
      .forecast-health { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin-top: 1rem; }
      .forecast-health > div { display: grid; gap: .3rem; padding: .8rem; border-radius: .8rem; background: rgba(255,255,255,.04); }
      .forecast-health span { color: var(--muted, #a8adb7); font-size: .8rem; }
      .forecast-health strong { overflow-wrap: anywhere; }
      .forecast-attribution { margin: 1rem 0 0; }
      .forecast-attribution a { color: inherit; }
      @media (max-width: 760px) { .forecast-health { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
  }

  const field = (name) => card.querySelector(`[data-forecast-field="${name}"]`);
  const statusChip = card.querySelector('[data-forecast-status]');
  const message = card.querySelector('[data-forecast-message]');
  const health = card.querySelector('[data-forecast-health]');
  const fetched = card.querySelector('[data-forecast-fetched]');
  const cacheState = card.querySelector('[data-forecast-cache-state]');
  const error = card.querySelector('[data-forecast-error]');
  const saveButton = card.querySelector('[data-forecast-save]');

  function formatTime(value) {
    if (!value) {
      return 'Not fetched yet';
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
  }

  function renderStatus(status = {}) {
    const state = String(status.status || 'disabled');
    const labels = {
      ready: 'Forecast ready',
      stale: 'Using cached forecast',
      error: 'Forecast error',
      configuration_required: 'Location required',
      disabled: 'Forecast off',
    };
    statusChip.textContent = labels[state] || state;
    statusChip.classList.toggle('is-warning', ['stale', 'error', 'configuration_required'].includes(state));
    health.hidden = state === 'disabled' && !status.fetched_at && !status.last_error;
    fetched.textContent = formatTime(status.fetched_at);
    cacheState.textContent = status.stale ? 'Stale fallback' : state === 'ready' ? 'Fresh' : state;
    error.textContent = status.last_error || 'None';
  }

  function populate(config = {}) {
    field('enabled').checked = config.enabled === true;
    field('latitude').value = config.latitude ?? '';
    field('longitude').value = config.longitude ?? '';
    field('timezone').value = config.timezone || 'Europe/London';
    field('forecast_days').value = String(config.forecast_days || 7);
    field('refresh_minutes').value = String(config.refresh_minutes || 30);
  }

  async function load() {
    try {
      const response = await fetch('/api/weather/forecast/config', { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok || payload.ok !== true) {
        throw new Error(payload.error || `Forecast settings returned HTTP ${response.status}`);
      }
      populate(payload.forecast);
      renderStatus(payload.status);
    } catch (loadError) {
      statusChip.textContent = 'Unavailable';
      message.textContent = loadError.message;
    }
  }

  function numberOrNull(value) {
    const text = String(value || '').trim();
    if (!text) {
      return null;
    }
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : text;
  }

  async function save() {
    saveButton.disabled = true;
    message.textContent = 'Saving…';
    try {
      const response = await fetch('/api/weather/forecast/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: field('enabled').checked,
          latitude: numberOrNull(field('latitude').value),
          longitude: numberOrNull(field('longitude').value),
          timezone: field('timezone').value,
          forecast_days: Number(field('forecast_days').value),
          refresh_minutes: Number(field('refresh_minutes').value),
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok !== true) {
        throw new Error(payload.error || `Forecast settings returned HTTP ${response.status}`);
      }
      populate(payload.forecast);
      renderStatus(payload.status);
      message.textContent = payload.message || 'Forecast settings saved.';
    } catch (saveError) {
      message.textContent = saveError.message;
    } finally {
      saveButton.disabled = false;
    }
  }

  saveButton.addEventListener('click', save);
  load();
})();
