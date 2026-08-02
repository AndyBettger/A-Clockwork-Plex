(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsPhysicalPolishLoaded) return;
  window.__aClockworkPlexSettingsPhysicalPolishLoaded = true;

  const SETTINGS_API = '/api/settings';
  let retryTimer = null;

  function initialise() {
    const form = document.getElementById('settings-unified-form');
    const authority = window.ACPUnifiedSettings;
    if (!form || !authority?.getSnapshot || !authority?.markDirty) {
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(initialise, 80);
      return;
    }

    installDetailedDirtyIndicators(form, authority);
    simplifyAudioHardware(authority);
    installMixerFaderUpgrade();
    installAirplayReceiverOwner(authority);
  }

  function sectionFor(element) {
    return element?.closest?.('[data-settings-section]')?.dataset.settingsSection || 'general';
  }

  function subpageFor(element, section = sectionFor(element)) {
    return element?.closest?.('[data-settings-subpage]')?.dataset.settingsSubpage
      || document.querySelector(`[data-settings-section="${section}"] [data-settings-subpage]:not([hidden])`)?.dataset.settingsSubpage
      || '';
  }

  function setSubpageDirty(key, dirty) {
    if (!key) return;
    const row = document.querySelector(`[data-settings-subpage-target="${key}"]`);
    if (!row) return;
    let dot = row.querySelector('.settings-subpage-dirty-dot');
    if (!dot && dirty) {
      dot = document.createElement('span');
      dot.className = 'settings-subpage-dirty-dot';
      dot.setAttribute('aria-label', 'Unsaved changes');
      row.insertBefore(dot, row.lastElementChild);
    }
    if (dot) dot.hidden = !dirty;
    row.classList.toggle('is-dirty', dirty);
  }

  function setCategoryDirty(section, dirty, external = false) {
    const row = document.querySelector(`[data-settings-section-target="${section}"]`);
    const dot = row?.querySelector('.settings-dirty-dot');
    if (!row || !dot) return;
    if (external) row.dataset.externalDirty = dirty ? 'true' : 'false';
    dot.hidden = !(dirty || row.dataset.externalDirty === 'true');
  }

  function markDetailedDirty(element, explicitSection = '') {
    const section = explicitSection || sectionFor(element);
    const subpage = subpageFor(element, section);
    if (subpage) setSubpageDirty(subpage, true);
    element?.closest?.('.setting-field, .setting-toggle, .alarm-editor-card, .settings-card')
      ?.classList.add('settings-option-dirty');
  }

  function clearSectionDetails(section) {
    document.querySelectorAll(`[data-settings-subpage-target^="${section}:"]`).forEach((row) => {
      setSubpageDirty(row.dataset.settingsSubpageTarget, false);
    });
    document.querySelectorAll(`[data-settings-section="${section}"] .settings-option-dirty`).forEach((node) => {
      node.classList.remove('settings-option-dirty');
    });
  }

  function installDetailedDirtyIndicators(form, authority) {
    if (form.dataset.detailedDirtyInstalled === 'v2') return;
    form.dataset.detailedDirtyInstalled = 'v2';

    const markControl = (event) => {
      const control = event.target.closest?.('[data-setting-path]');
      if (control) markDetailedDirty(control);
    };
    form.addEventListener('input', markControl, true);
    form.addEventListener('change', markControl, true);

    const previousMarkDirty = authority.markDirty.bind(authority);
    authority.markDirty = (section = 'general') => {
      markDetailedDirty(null, section);
      previousMarkDirty(section);
    };

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        const dot = mutation.target;
        if (!(dot instanceof Element) || !dot.classList.contains('settings-dirty-dot')) return;
        const row = dot.closest('[data-settings-section-target]');
        const section = row?.dataset.settingsSectionTarget;
        if (!section) return;
        if (row.dataset.externalDirty === 'true') {
          dot.hidden = false;
        } else if (dot.hidden) {
          clearSectionDetails(section);
        }
      });
    });
    document.querySelectorAll('.settings-dirty-dot').forEach((dot) => {
      observer.observe(dot, { attributes: true, attributeFilter: ['hidden'] });
    });
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
  }

  function setNotice(title, message, tone = 'clean') {
    const bar = document.querySelector('[data-settings-save-bar]');
    const titleNode = document.querySelector('[data-settings-save-title]');
    const messageNode = document.querySelector('[data-settings-save-message]');
    if (titleNode) titleNode.textContent = title;
    if (messageNode) messageNode.textContent = message;
    bar?.classList.toggle('is-dirty', tone === 'dirty');
    bar?.classList.toggle('is-error', tone === 'error');
    bar?.classList.toggle('is-success', tone === 'success');
  }

  async function freshSettingsSnapshot() {
    const response = await fetch(SETTINGS_API, { cache: 'no-store' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Settings returned HTTP ${response.status}.`);
    }
    return payload;
  }

  function installAirplayReceiverOwner(authority) {
    const input = document.querySelector('[data-setting-path="airplay.receiver_name"], [data-airplay-receiver-setting]');
    if (!input || input.dataset.airplayReceiverOwner === 'physical-polish-v2') return;

    input.dataset.airplayReceiverOwner = 'physical-polish-v2';
    input.dataset.airplayReceiverSetting = 'true';
    input.removeAttribute('data-setting-path');

    const field = input.closest('.setting-field');
    const dialog = document.querySelector('[data-settings-confirmation]');
    const title = dialog?.querySelector('#settings-confirmation-title');
    const copy = dialog?.querySelector('p');
    const confirmButton = dialog?.querySelector('[data-confirmation="confirm"]');
    const cancelButton = dialog?.querySelector('[data-confirmation="cancel"]');
    let currentName = '';
    let pending = false;
    let saving = false;
    let timer = null;

    function setDirty(dirty) {
      pending = dirty;
      field?.classList.toggle('settings-option-dirty', dirty);
      setSubpageDirty('airplay:receiver', dirty);
      setCategoryDirty('airplay', dirty, true);
    }

    async function initialiseValue() {
      try {
        const snapshot = authority.getSnapshot?.() || await freshSettingsSnapshot();
        currentName = String(snapshot?.settings?.airplay?.receiver_name || input.value || '').trim();
        input.value = currentName;
        setDirty(false);
      } catch (error) {
        setNotice('AirPlay setting unavailable', error.message || 'Could not read the receiver name.', 'error');
      }
    }

    async function saveName(nextName) {
      if (saving) return;
      saving = true;
      setNotice('Restarting AirPlay…', 'Validating the receiver name and restarting Shairport Sync.', 'dirty');
      try {
        const latest = await freshSettingsSnapshot();
        const settings = JSON.parse(JSON.stringify(latest.settings || {}));
        settings.airplay ||= {};
        settings.airplay.receiver_name = nextName;
        const response = await fetch(SETTINGS_API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            revision: latest.revision,
            settings,
            confirm_airplay_restart: true,
          }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.error || `AirPlay receiver update returned HTTP ${response.status}.`);
        }
        currentName = String(payload.settings?.airplay?.receiver_name || nextName);
        input.value = currentName;
        setDirty(false);
        setNotice('AirPlay receiver updated', `${currentName} is now advertised. Reloading Settings…`, 'success');
        window.setTimeout(() => window.location.reload(), 850);
      } catch (error) {
        setDirty(true);
        setNotice('AirPlay receiver update failed', error.message || 'The receiver name was not changed.', 'error');
      } finally {
        saving = false;
      }
    }

    function requestConfirmation() {
      const nextName = String(input.value || '').trim();
      if (saving || !pending || document.body.classList.contains('keyboard-open')) return;
      if (nextName === currentName) {
        setDirty(false);
        return;
      }
      if (!dialog || !confirmButton || !cancelButton || !dialog.hidden) return;

      if (title) title.textContent = 'Restart AirPlay receiver?';
      if (copy) copy.textContent = `Change the advertised receiver name from “${currentName}” to “${nextName}”? Shairport Sync will restart briefly.`;
      dialog.hidden = false;

      const cleanup = () => {
        confirmButton.removeEventListener('click', confirm);
        cancelButton.removeEventListener('click', cancel);
      };
      const cancel = () => {
        cleanup();
        dialog.hidden = true;
        input.value = currentName;
        setDirty(false);
      };
      const confirm = async () => {
        cleanup();
        dialog.hidden = true;
        await saveName(nextName);
      };
      confirmButton.addEventListener('click', confirm);
      cancelButton.addEventListener('click', cancel);
    }

    input.addEventListener('input', () => setDirty(String(input.value || '').trim() !== currentName));
    input.addEventListener('change', () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(requestConfirmation, 80);
    });
    input.addEventListener('focusout', () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(requestConfirmation, 100);
    });

    const keyboardObserver = new MutationObserver(() => {
      if (!document.body.classList.contains('keyboard-open') && pending) {
        window.clearTimeout(timer);
        timer = window.setTimeout(requestConfirmation, 120);
      }
    });
    keyboardObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    window.addEventListener('pagehide', () => {
      keyboardObserver.disconnect();
      window.clearTimeout(timer);
    }, { once: true });

    initialiseValue();
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function hideHardwareControl(path) {
    const control = document.querySelector(`[data-setting-path="${path}"]`);
    const field = control?.closest('label');
    control?.removeAttribute('data-setting-path');
    if (field) field.hidden = true;
  }

  async function simplifyAudioHardware(authority) {
    const audioPage = document.querySelector('[data-settings-subpage="audio:hardware"] .settings-card');
    if (!audioPage || audioPage.dataset.readOnlyRoute === 'true') return;
    audioPage.dataset.readOnlyRoute = 'true';

    hideHardwareControl('alarm_audio.shared_mixer_enabled');
    hideHardwareControl('alarm_audio.hardware_device');
    hideHardwareControl('alarm_audio.alsa_device');
    audioPage.querySelector('.settings-audio-hardware-configuration')?.remove();

    const title = audioPage.querySelector('h3');
    if (title) title.textContent = 'Audio hardware';
    audioPage.querySelectorAll('p.muted.small').forEach((node) => {
      if (node.textContent.includes('Choose the physical output')) node.remove();
    });

    const summary = document.createElement('div');
    summary.className = 'settings-status-grid settings-hardware-summary';
    summary.innerHTML = '<p class="muted">Reading the configured audio route…</p>';
    audioPage.appendChild(summary);
    const note = document.createElement('p');
    note.className = 'muted small settings-hardware-maintenance-note';
    note.textContent = 'The physical output is intentionally read-only here. Changing it requires a guarded audio-maintenance procedure because Plexamp, AirPlay and alarms share the same ALSA graph.';
    audioPage.appendChild(note);

    const overview = document.querySelector('[data-settings-subpage-target="audio:hardware"]');
    const small = overview?.querySelector('small');
    if (small) small.textContent = 'Current shared output route';

    try {
      const snapshot = authority.getSnapshot?.() || await freshSettingsSnapshot();
      const audio = snapshot?.settings?.alarm_audio || {};
      summary.innerHTML = `
        <div class="settings-status-reading">
          <span>Physical DAC</span>
          <strong>${escapeHtml(audio.hardware_device || 'Not configured')}</strong>
          <small>Configured beneath the shared mixer</small>
        </div>
        <div class="settings-status-reading">
          <span>Shared alarm PCM</span>
          <strong>${escapeHtml(audio.alsa_device || 'Not configured')}</strong>
          <small>${audio.shared_mixer_enabled ? 'Shared mixer enabled' : 'Shared mixer disabled'}</small>
        </div>`;
    } catch (error) {
      summary.innerHTML = `<p class="muted">${escapeHtml(error.message || 'Could not read the configured audio route.')}</p>`;
    }
  }

  function installMixerFaderUpgrade() {
    const mount = document.getElementById('settings-audio-trims');
    if (!mount || mount.dataset.faderUpgradeInstalled === 'v2') return;
    mount.dataset.faderUpgradeInstalled = 'v2';

    function upgrade(article) {
      if (!(article instanceof Element) || !article.classList.contains('settings-live-trim')) return;
      if (article.dataset.properFader === 'true') return;
      const input = article.querySelector('input[type="range"]');
      const small = article.querySelector('small');
      const label = article.querySelector('header strong')?.textContent || 'Output';
      if (!input) return;

      article.dataset.properFader = 'true';
      input.dataset.mixerSlider = label.toLowerCase();
      input.setAttribute('orient', 'vertical');

      const fader = document.createElement('div');
      fader.className = 'nav-live-fader settings-output-fader';
      fader.innerHTML = `
        <span class="nav-fader-scale-label is-top" aria-hidden="true">11</span>
        <span class="nav-fader-scale-label is-bottom" aria-hidden="true">0</span>
        <div class="nav-live-step-row">
          <button type="button" data-settings-fader-step="-5" aria-label="Reduce ${escapeHtml(label)}">−</button>
          <button type="button" data-settings-fader-step="5" aria-label="Increase ${escapeHtml(label)}">＋</button>
        </div>`;
      fader.insertBefore(input, fader.querySelector('.nav-live-step-row'));
      article.insertBefore(fader, small || null);

      fader.querySelectorAll('[data-settings-fader-step]').forEach((button) => {
        button.disabled = input.disabled;
        button.addEventListener('click', () => {
          if (input.disabled) return;
          const next = Math.max(Number(input.min || 0), Math.min(Number(input.max || 100), Number(input.value || 0) + Number(button.dataset.settingsFaderStep || 0)));
          input.value = String(next);
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        });
      });
    }

    const scan = () => mount.querySelectorAll('.settings-live-trim').forEach(upgrade);
    const observer = new MutationObserver(scan);
    observer.observe(mount, { childList: true, subtree: true });
    scan();
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
  }

  if (document.readyState === 'complete') {
    window.setTimeout(initialise, 0);
  } else {
    window.addEventListener('load', initialise, { once: true });
  }
})();