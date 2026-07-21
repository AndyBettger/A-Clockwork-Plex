(() => {
  if (window.__aClockworkPlexAudioEqLoaded) return;
  window.__aClockworkPlexAudioEqLoaded = true;

  const ENDPOINT = '/api/audio/eq';
  const BANDS = ['bass', 'mid', 'treble'];
  const MIN_DB = -6;
  const MAX_DB = 6;
  const STEP_DB = 0.5;
  const POLL_MS = 2500;

  let latest = null;
  let getInFlight = false;
  let postInFlight = false;
  let pendingAction = null;
  let pollTimer = null;
  const dragging = new Set();
  const desired = new Map();
  const debounceTimers = new Map();

  const byId = (id) => document.getElementById(id);
  const clampDb = (value) => {
    const numeric = Number(value);
    const safe = Number.isFinite(numeric) ? numeric : 0;
    return Math.max(MIN_DB, Math.min(MAX_DB, Math.round(safe / STEP_DB) * STEP_DB));
  };

  function dbText(value) {
    const db = clampDb(value);
    if (db === 0) return '0 dB';
    const magnitude = Number.isInteger(Math.abs(db)) ? Math.abs(db).toFixed(0) : Math.abs(db).toFixed(1);
    return `${db > 0 ? '+' : '−'}${magnitude} dB`;
  }

  function requestJson(options = {}) {
    return fetch(ENDPOINT, { cache: 'no-store', ...options }).then(async (response) => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `EQ request returned ${response.status}.`);
      }
      return payload;
    });
  }

  function knobMarkup(band) {
    const label = band.charAt(0).toUpperCase() + band.slice(1);
    return `
      <div class="acp-eq-control" data-eq-control="${band}">
        <div
          class="acp-eq-knob"
          id="acp-eq-knob-${band}"
          role="slider"
          tabindex="0"
          aria-label="${label} equalizer gain"
          aria-valuemin="${MIN_DB}"
          aria-valuemax="${MAX_DB}"
          aria-valuenow="0"
          aria-valuetext="0 dB"
          data-eq-knob="${band}"
        ><span aria-hidden="true"></span></div>
        <strong>${label}</strong>
        <output id="acp-eq-value-${band}">0 dB</output>
      </div>
    `;
  }

  function drawerMarkup() {
    return `
      <section class="acp-eq-strip" id="acp-eq-strip" aria-label="Master equalizer">
        <header class="acp-eq-heading">
          <div>
            <strong>Master EQ</strong>
            <span>All sources · before Master</span>
          </div>
          <span class="acp-eq-health" id="acp-eq-health">Checking…</span>
        </header>
        <div class="acp-eq-console">
          <div class="acp-eq-knobs">
            ${BANDS.map(knobMarkup).join('')}
          </div>
          <div class="acp-eq-actions">
            <button type="button" id="acp-eq-bypass" class="acp-eq-button" aria-pressed="false">Bypass</button>
            <button type="button" id="acp-eq-neutral" class="acp-eq-button">Neutral</button>
          </div>
        </div>
        <p class="acp-eq-message" id="acp-eq-message" role="status"></p>
      </section>
    `;
  }

  function settingsMarkup() {
    return `
      <section class="settings-card acp-eq-settings" id="acp-eq-settings-card">
        <div class="settings-card-heading">
          <div>
            <h2>Master equalizer</h2>
            <p class="muted small">A restrained three-band curve shared by Plexamp, AirPlay and alarms before the Master output stage.</p>
          </div>
          <span class="settings-chip" id="acp-eq-settings-health">Checking…</span>
        </div>
        <div class="acp-eq-settings-grid">
          ${BANDS.map((band) => {
            const label = band.charAt(0).toUpperCase() + band.slice(1);
            return `
              <label class="acp-eq-settings-band">
                <span>${label}</span>
                <input type="range" min="${MIN_DB}" max="${MAX_DB}" step="${STEP_DB}" value="0" data-eq-range="${band}" aria-label="${label} equalizer gain">
                <output id="acp-eq-settings-value-${band}">0 dB</output>
              </label>
            `;
          }).join('')}
        </div>
        <div class="acp-eq-settings-actions">
          <button class="button settings-secondary" type="button" id="acp-eq-settings-bypass" aria-pressed="false">Bypass EQ</button>
          <button class="button settings-secondary" type="button" id="acp-eq-settings-neutral">Return to neutral</button>
          <span class="muted small" id="acp-eq-settings-message">Centre is 0 dB. Double-tap a drawer knob to centre that band.</span>
        </div>
      </section>
    `;
  }

  function installDrawer() {
    const mixer = byId('nav-live-mixer');
    if (!mixer) return false;
    if (!byId('acp-eq-strip')) {
      const grid = mixer.querySelector('.nav-live-grid');
      if (grid) grid.insertAdjacentHTML('beforebegin', drawerMarkup());
      else mixer.insertAdjacentHTML('beforeend', drawerMarkup());
      installDrawerInteractions();
    }
    return true;
  }

  function installSettings() {
    const panel = byId('settings-panel-audio');
    if (!panel) return false;
    if (!byId('acp-eq-settings-card')) {
      const defaultCard = byId('audio-airplay-default-card');
      if (defaultCard) defaultCard.insertAdjacentHTML('beforebegin', settingsMarkup());
      else panel.insertAdjacentHTML('beforeend', settingsMarkup());
      installSettingsInteractions();
    }
    return true;
  }

  function setMessage(text = '', error = false) {
    const drawer = byId('acp-eq-message');
    const settings = byId('acp-eq-settings-message');
    if (drawer) {
      drawer.textContent = text;
      drawer.classList.toggle('is-error', error);
    }
    if (settings && text) {
      settings.textContent = text;
      settings.classList.toggle('is-error', error);
    }
  }

  function setBandVisual(band, value) {
    const db = clampDb(value);
    const angle = -135 + ((db - MIN_DB) / (MAX_DB - MIN_DB)) * 270;
    const knob = byId(`acp-eq-knob-${band}`);
    const output = byId(`acp-eq-value-${band}`);
    const settingsOutput = byId(`acp-eq-settings-value-${band}`);
    const settingsRange = document.querySelector(`[data-eq-range="${band}"]`);
    if (knob) {
      knob.style.setProperty('--eq-knob-angle', `${angle}deg`);
      knob.setAttribute('aria-valuenow', String(db));
      knob.setAttribute('aria-valuetext', dbText(db));
      knob.title = `${band}: ${dbText(db)} · double-tap for 0 dB`;
    }
    if (output) output.textContent = dbText(db);
    if (settingsOutput) settingsOutput.textContent = dbText(db);
    if (settingsRange && !dragging.has(`settings-${band}`) && settingsRange.value !== String(db)) {
      settingsRange.value = String(db);
    }
  }

  function setDesired(band, value) {
    const db = clampDb(value);
    desired.set(band, db);
    setBandVisual(band, db);
    return db;
  }

  function render(eq) {
    latest = eq || {};
    const available = latest.available === true;
    const bypassed = latest.bypassed === true;
    BANDS.forEach((band) => {
      const payload = latest.bands?.[band] || {};
      const value = desired.has(band) ? desired.get(band) : Number(payload.db ?? 0);
      if (!dragging.has(band) && !dragging.has(`settings-${band}`)) setBandVisual(band, value);
      const knob = byId(`acp-eq-knob-${band}`);
      const range = document.querySelector(`[data-eq-range="${band}"]`);
      if (knob) {
        knob.setAttribute('aria-disabled', available ? 'false' : 'true');
        knob.tabIndex = available ? 0 : -1;
        knob.classList.toggle('is-bypassed', bypassed);
      }
      if (range) range.disabled = !available;
    });

    const healthText = available ? (bypassed ? 'Bypassed' : 'Active') : 'Install required';
    const health = byId('acp-eq-health');
    const settingsHealth = byId('acp-eq-settings-health');
    [health, settingsHealth].forEach((node) => {
      if (!node) return;
      node.textContent = healthText;
      node.classList.toggle('is-ready', available && !bypassed);
      node.classList.toggle('is-warning', bypassed || !available);
    });

    const bypass = byId('acp-eq-bypass');
    const settingsBypass = byId('acp-eq-settings-bypass');
    [bypass, settingsBypass].forEach((button) => {
      if (!button) return;
      button.disabled = !available;
      button.setAttribute('aria-pressed', bypassed ? 'true' : 'false');
      button.classList.toggle('is-active', bypassed);
      button.textContent = bypassed ? 'Restore EQ' : (button.id.includes('settings') ? 'Bypass EQ' : 'Bypass');
    });
    const neutral = byId('acp-eq-neutral');
    const settingsNeutral = byId('acp-eq-settings-neutral');
    if (neutral) neutral.disabled = !available;
    if (settingsNeutral) settingsNeutral.disabled = !available;

    document.querySelectorAll('.acp-eq-strip, .acp-eq-settings').forEach((node) => {
      node.classList.toggle('is-bypassed', bypassed);
      node.classList.toggle('is-unavailable', !available);
    });
    if (!available && latest.error) setMessage(latest.error, true);
  }

  async function refresh(force = false) {
    const drawerOpen = document.body.classList.contains('nav-audio-open');
    const settingsVisible = byId('settings-panel-audio')?.hidden === false;
    if (!force && !drawerOpen && !settingsVisible) return;
    if (getInFlight || postInFlight || pendingAction) return;
    getInFlight = true;
    try {
      const payload = await requestJson();
      render(payload.eq || {});
      if (payload.eq?.available) setMessage('');
    } catch (error) {
      render({ available: false, error: error.message });
    } finally {
      getInFlight = false;
    }
  }

  function queueBandChange(band, value, persist, delay = 100) {
    const db = setDesired(band, value);
    window.clearTimeout(debounceTimers.get(band));
    debounceTimers.set(band, window.setTimeout(() => {
      const previous = pendingAction;
      pendingAction = {
        action: 'set',
        band,
        db,
        persist: Boolean(persist || (previous?.band === band && previous?.persist)),
      };
      drain();
    }, delay));
  }

  async function postAction(action) {
    pendingAction = action;
    await drain();
  }

  async function drain() {
    if (postInFlight || !pendingAction) return;
    const action = pendingAction;
    pendingAction = null;
    postInFlight = true;
    try {
      const payload = await requestJson({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action),
      });
      render(payload.eq || {});
      if (action.action === 'set' && action.persist) {
        const confirmed = Number(payload.eq?.bands?.[action.band]?.db);
        window.setTimeout(() => {
          if (!dragging.has(action.band) && !dragging.has(`settings-${action.band}`) && Number(desired.get(action.band)) === confirmed) {
            desired.delete(action.band);
          }
        }, 500);
      }
      setMessage(payload.message || 'Master EQ updated.');
    } catch (error) {
      setMessage(error.message || 'Could not change the master EQ.', true);
      if (action.band && !dragging.has(action.band)) desired.delete(action.band);
    } finally {
      postInFlight = false;
      if (pendingAction) drain();
      else window.setTimeout(() => refresh(true), 180);
    }
  }

  function keyboardValue(event, current) {
    const keys = ['ArrowUp', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'PageUp', 'PageDown', 'Home'];
    if (!keys.includes(event.key)) return null;
    let next = Number(current);
    if (event.key === 'ArrowUp' || event.key === 'ArrowRight') next += STEP_DB;
    if (event.key === 'ArrowDown' || event.key === 'ArrowLeft') next -= STEP_DB;
    if (event.key === 'PageUp') next += 1;
    if (event.key === 'PageDown') next -= 1;
    if (event.key === 'Home') next = 0;
    return clampDb(next);
  }

  function installDrawerInteractions() {
    BANDS.forEach((band) => {
      const knob = byId(`acp-eq-knob-${band}`);
      if (!knob) return;
      let drag = null;
      knob.addEventListener('pointerdown', (event) => {
        if (knob.getAttribute('aria-disabled') === 'true') return;
        event.preventDefault();
        dragging.add(band);
        drag = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          startValue: Number(desired.get(band) ?? knob.getAttribute('aria-valuenow') ?? 0),
        };
        knob.classList.add('is-dragging');
        knob.setPointerCapture?.(event.pointerId);
      });
      knob.addEventListener('pointermove', (event) => {
        if (!drag || drag.pointerId !== event.pointerId) return;
        event.preventDefault();
        const pixels = (event.clientX - drag.startX) + (drag.startY - event.clientY);
        queueBandChange(band, drag.startValue + pixels / 18, false, 90);
      });
      const finish = (event) => {
        if (!drag || drag.pointerId !== event.pointerId) return;
        event.preventDefault();
        const value = Number(desired.get(band) ?? knob.getAttribute('aria-valuenow') ?? 0);
        drag = null;
        dragging.delete(band);
        knob.classList.remove('is-dragging');
        try { knob.releasePointerCapture?.(event.pointerId); } catch (error) {}
        queueBandChange(band, value, true, 0);
      };
      knob.addEventListener('pointerup', finish);
      knob.addEventListener('pointercancel', finish);
      knob.addEventListener('keydown', (event) => {
        const next = keyboardValue(event, desired.get(band) ?? knob.getAttribute('aria-valuenow'));
        if (next === null || knob.getAttribute('aria-disabled') === 'true') return;
        event.preventDefault();
        queueBandChange(band, next, true, 0);
      });
      knob.addEventListener('dblclick', (event) => {
        event.preventDefault();
        queueBandChange(band, 0, true, 0);
      });
    });
    byId('acp-eq-bypass')?.addEventListener('click', () => {
      postAction({ action: 'bypass', enabled: latest?.bypassed !== true });
    });
    byId('acp-eq-neutral')?.addEventListener('click', () => {
      desired.clear();
      postAction({ action: 'neutral' });
    });
  }

  function installSettingsInteractions() {
    document.querySelectorAll('[data-eq-range]').forEach((range) => {
      const band = range.dataset.eqRange;
      range.addEventListener('pointerdown', () => dragging.add(`settings-${band}`));
      range.addEventListener('pointerup', () => {
        dragging.delete(`settings-${band}`);
        queueBandChange(band, range.value, true, 0);
      });
      range.addEventListener('pointercancel', () => dragging.delete(`settings-${band}`));
      range.addEventListener('input', () => {
        dragging.add(`settings-${band}`);
        queueBandChange(band, range.value, false, 100);
      });
      range.addEventListener('change', () => {
        dragging.delete(`settings-${band}`);
        queueBandChange(band, range.value, true, 0);
      });
      range.addEventListener('dblclick', (event) => {
        event.preventDefault();
        dragging.delete(`settings-${band}`);
        queueBandChange(band, 0, true, 0);
      });
    });
    byId('acp-eq-settings-bypass')?.addEventListener('click', () => {
      postAction({ action: 'bypass', enabled: latest?.bypassed !== true });
    });
    byId('acp-eq-settings-neutral')?.addEventListener('click', () => {
      desired.clear();
      postAction({ action: 'neutral' });
    });
  }

  function install() {
    const drawerReady = installDrawer();
    installSettings();
    if (!drawerReady) {
      window.setTimeout(install, 100);
      return;
    }
    refresh(true);
    if (!pollTimer) pollTimer = window.setInterval(refresh, POLL_MS);
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('#nav-audio-button')) window.setTimeout(() => refresh(true), 80);
  });
  window.addEventListener('hashchange', () => window.setTimeout(() => {
    installSettings();
    refresh(true);
  }, 80));
  window.addEventListener('pagehide', () => {
    window.clearInterval(pollTimer);
    debounceTimers.forEach((timer) => window.clearTimeout(timer));
  });

  install();
})();
