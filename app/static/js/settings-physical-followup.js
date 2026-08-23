(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsPhysicalFollowupLoaded) return;
  window.__aClockworkPlexSettingsPhysicalFollowupLoaded = true;

  const SETTINGS_API = '/api/settings';
  const AUTOSAVE_DELAY_MS = 650;
  const TEXT_AUTOSAVE_DELAY_MS = 1100;
  const lastInteractionBySection = new Map();
  let retryTimer = null;

  function initialise() {
    const form = document.getElementById('settings-unified-form');
    const authority = window.ACPUnifiedSettings;
    if (!form || !authority?.markDirty || !authority?.getSnapshot) {
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(initialise, 80);
      return;
    }

    installDetailedDirtyIndicators(form);
    installAutosave(form, authority);
    arrangeAudioHardware(authority);
    installMixerFaderUpgrade();
    installAirplayReceiverOwner(form, authority);
  }

  function sectionFor(element) {
    return element?.closest?.('[data-settings-section]')?.dataset.settingsSection || 'general';
  }

  function visibleSubpageKey(section) {
    return document.querySelector(`[data-settings-section="${section}"] [data-settings-subpage]:not([hidden])`)?.dataset.settingsSubpage || '';
  }

  function subpageFor(element, section = sectionFor(element)) {
    return element?.closest?.('[data-settings-subpage]')?.dataset.settingsSubpage || visibleSubpageKey(section);
  }

  function confirmationOpen() {
    const dialog = document.querySelector('[data-settings-confirmation]');
    return Boolean(dialog && !dialog.hidden);
  }

  function hasDirtySettings() {
    return Boolean(document.querySelector('.settings-dirty-dot:not([hidden])'));
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

  function setSectionDirty(section, dirty, external = false) {
    const row = document.querySelector(`[data-settings-section-target="${section}"]`);
    const dot = row?.querySelector('.settings-dirty-dot');
    if (!row || !dot) return;
    if (external) row.dataset.externalDirty = dirty ? 'true' : 'false';
    if (dirty || row.dataset.externalDirty === 'true') dot.hidden = false;
    else dot.hidden = true;
  }

  function markDetailedDirty(element, explicitSection = '') {
    const section = explicitSection || sectionFor(element);
    const target = element || lastInteractionBySection.get(section) || null;
    const subpage = subpageFor(target, section);
    if (subpage) setSubpageDirty(subpage, true);
    const option = target?.closest?.('.setting-field, .setting-toggle, .alarm-editor-card, .settings-card');
    option?.classList.add('settings-option-dirty');
  }

  function clearSectionDetails(section) {
    lastInteractionBySection.delete(section);
    document.querySelectorAll(`[data-settings-subpage-target^="${section}:"]`).forEach((row) => {
      setSubpageDirty(row.dataset.settingsSubpageTarget, false);
    });
    document.querySelectorAll(`[data-settings-section="${section}"] .settings-option-dirty`).forEach((node) => {
      node.classList.remove('settings-option-dirty');
    });
  }

  function installDetailedDirtyIndicators(form) {
    if (form.dataset.detailedDirtyInstalled === 'true') return;
    form.dataset.detailedDirtyInstalled = 'true';

    form.addEventListener('pointerdown', (event) => {
      const control = event.target.closest?.('input, select, textarea, button');
      if (!control || control.closest('#settings-audio-trims')) return;
      if (control.matches('[data-settings-section-target], [data-settings-subpage-target], [data-settings-back]')) return;
      const section = sectionFor(control);
      lastInteractionBySection.set(section, control);
    }, true);

    const markControl = (event) => {
      const control = event.target.closest?.('[data-setting-path], input, select, textarea');
      if (!control || control.closest('#settings-audio-trims')) return;
      const section = sectionFor(control);
      lastInteractionBySection.set(section, control);
      markDetailedDirty(control, section);
    };
    form.addEventListener('input', markControl, true);
    form.addEventListener('change', markControl, true);

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        const dot = mutation.target;
        if (!(dot instanceof Element) || !dot.classList.contains('settings-dirty-dot')) return;
        const row = dot.closest('[data-settings-section-target]');
        const section = row?.dataset.settingsSectionTarget;
        if (!section) return;
        if (row.dataset.externalDirty === 'true') {
          dot.hidden = false;
          return;
        }
        if (dot.hidden) clearSectionDetails(section);
      });
    });
    document.querySelectorAll('.settings-dirty-dot').forEach((dot) => {
      observer.observe(dot, { attributes: true, attributeFilter: ['hidden'] });
    });
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
  }

  function installAutosave(form, authority) {
    if (form.dataset.autosaveOwner === 'physical-followup-v2') return;
    form.dataset.autosaveOwner = 'physical-followup-v2';

    let timer = null;
    let pending = false;
    let submittedGeneration = 0;
    let changeGeneration = 0;
    const pendingSections = new Set();
    const originalMarkDirty = authority.markDirty.bind(authority);

    function paintAutosaveMode() {
      document.body.classList.add('settings-autosave-enabled');
      const heroCopy = document.querySelector('.settings-ipad-hero p');
      if (heroCopy) heroCopy.textContent = 'Changes save automatically. Live controls and tests still act immediately.';
    }

    function queue(section = 'general', delay = AUTOSAVE_DELAY_MS) {
      pending = true;
      changeGeneration += 1;
      pendingSections.add(section || 'general');
      window.clearTimeout(timer);
      timer = window.setTimeout(flush, delay);
    }

    function flush() {
      window.clearTimeout(timer);
      timer = null;
      if (!pending) return;
      if (document.body.classList.contains('keyboard-open') || confirmationOpen()) {
        timer = window.setTimeout(flush, 180);
        return;
      }
      if (form.getAttribute('aria-busy') === 'true') {
        timer = window.setTimeout(flush, 220);
        return;
      }

      pendingSections.forEach((section) => originalMarkDirty(section));
      pendingSections.clear();
      if (!hasDirtySettings()) {
        pending = false;
        return;
      }

      pending = false;
      submittedGeneration = changeGeneration;
      form.requestSubmit();
    }

    authority.markDirty = (section = 'general') => {
      originalMarkDirty(section);
      markDetailedDirty(null, section);
      queue(section, TEXT_AUTOSAVE_DELAY_MS);
    };

    form.addEventListener('input', (event) => {
      const control = event.target.closest?.('[data-setting-path]');
      if (!control) return;
      const section = sectionFor(control);
      if (control.matches('input[type="range"]')) {
        queue(section, 420);
        return;
      }
      pending = true;
      changeGeneration += 1;
      pendingSections.add(section);
      if (!control.matches('input[data-keyboard], input[type="text"], input:not([type])')) {
        queue(section, AUTOSAVE_DELAY_MS);
      }
    });

    form.addEventListener('change', (event) => {
      const control = event.target.closest?.('[data-setting-path]');
      if (control) queue(sectionFor(control), 120);
    });

    form.addEventListener('focusout', (event) => {
      const control = event.target.closest?.('[data-setting-path]');
      if (control) queue(sectionFor(control), 160);
    });

    form.addEventListener('acp:clock-cards-changed', () => {
      markDetailedDirty(document.querySelector('[data-settings-subpage="weather:clock-cards"]'), 'weather');
      queue('weather', 260);
    });
    form.addEventListener('click', (event) => {
      if (event.target.closest('[data-unit-preset]')) queue('weather', 180);
      if (event.target.closest('[data-action="eq-flat"]')) queue('audio', 180);
    });

    const bodyObserver = new MutationObserver(() => {
      if (!document.body.classList.contains('keyboard-open') && pending) {
        window.clearTimeout(timer);
        timer = window.setTimeout(flush, 140);
      }
    });
    bodyObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    const transactionObserver = new MutationObserver(() => {
      if (form.getAttribute('aria-busy') === 'true') return;
      if (pending && changeGeneration > submittedGeneration) {
        window.clearTimeout(timer);
        timer = window.setTimeout(flush, 180);
      }
    });
    transactionObserver.observe(form, { attributes: true, attributeFilter: ['aria-busy'] });

    window.addEventListener('pagehide', () => {
      bodyObserver.disconnect();
      transactionObserver.disconnect();
      window.clearTimeout(timer);
    }, { once: true });

    paintAutosaveMode();
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

  function installAirplayReceiverOwner(form, authority) {
    const input = document.querySelector('[data-setting-path="airplay.receiver_name"], [data-airplay-receiver-setting]');
    if (!input || input.dataset.airplayReceiverOwner === 'physical-followup-v2') return;

    input.dataset.airplayReceiverOwner = 'physical-followup-v2';
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
    let confirmTimer = null;

    function setReceiverDirty(dirty) {
      pending = dirty;
      field?.classList.toggle('settings-option-dirty', dirty);
      setSubpageDirty('airplay:receiver', dirty);
      setSectionDirty('airplay', dirty, true);
    }

    async function initialiseValue() {
      try {
        const snapshot = authority.getSnapshot?.() || await freshSettingsSnapshot();
        currentName = String(snapshot?.settings?.airplay?.receiver_name || input.value || '').trim();
        input.value = currentName;
        setReceiverDirty(false);
      } catch (error) {
        setNotice('AirPlay setting unavailable', error.message || 'Could not read the receiver name.', 'error');
      }
    }

    function closeDialog() {
      if (dialog) dialog.hidden = true;
    }

    function requestConfirmation() {
      const nextName = String(input.value || '').trim();
      if (saving || !pending || confirmationOpen() || document.body.classList.contains('keyboard-open')) return;
      if (nextName === currentName) {
        setReceiverDirty(false);
        return;
      }
      if (!dialog || !confirmButton || !cancelButton) return;

      if (title) title.textContent = 'Restart AirPlay receiver?';
      if (copy) copy.textContent = `Change the advertised receiver name from “${currentName}” to “${nextName}”? Shairport Sync will restart briefly.`;
      dialog.hidden = false;

      const cleanup = () => {
        confirmButton.removeEventListener('click', confirm);
        cancelButton.removeEventListener('click', cancel);
      };
      const cancel = () => {
        cleanup();
        closeDialog();
        input.value = currentName;
        setReceiverDirty(false);
      };
      const confirm = async () => {
        cleanup();
        closeDialog();
        await saveReceiverName(nextName);
      };
      confirmButton.addEventListener('click', confirm);
      cancelButton.addEventListener('click', cancel);
    }

    async function saveReceiverName(nextName) {
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
        setReceiverDirty(false);
        setNotice('AirPlay receiver updated', `${currentName} is now advertised. Reloading Settings…`, 'success');
        window.setTimeout(() => window.location.reload(), 850);
      } catch (error) {
        setReceiverDirty(true);
        setNotice('AirPlay receiver update failed', error.message || 'The receiver name was not changed.', 'error');
      } finally {
        saving = false;
      }
    }

    input.addEventListener('input', () => {
      lastInteractionBySection.set('airplay', input);
      setReceiverDirty(String(input.value || '').trim() !== currentName);
    });
    input.addEventListener('change', () => {
      window.clearTimeout(confirmTimer);
      confirmTimer = window.setTimeout(requestConfirmation, 80);
    });
    input.addEventListener('focusout', () => {
      window.clearTimeout(confirmTimer);
      confirmTimer = window.setTimeout(requestConfirmation, 100);
    });

    const keyboardObserver = new MutationObserver(() => {
      if (!document.body.classList.contains('keyboard-open') && pending) {
        window.clearTimeout(confirmTimer);
        confirmTimer = window.setTimeout(requestConfirmation, 120);
      }
    });
    keyboardObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    window.addEventListener('pagehide', () => {
      keyboardObserver.disconnect();
      window.clearTimeout(confirmTimer);
    }, { once: true });

    initialiseValue();
  }

  function hideConfigurationField(path) {
    const control = document.querySelector(`[data-setting-path="${path}"]`);
    const field = control?.closest('label');
    control?.removeAttribute('data-setting-path');
    if (field) field.hidden = true;
  }

  async function arrangeAudioHardware(authority) {
    const audioPage = document.querySelector('[data-settings-subpage="audio:hardware"] .settings-card');
    const advancedPage = document.querySelector('[data-settings-subpage="advanced:audio"] .settings-card');
    if (!audioPage || !advancedPage || audioPage.dataset.physicalLayoutReady === 'v2') return;
    audioPage.dataset.physicalLayoutReady = 'v2';

    hideConfigurationField('alarm_audio.shared_mixer_enabled');
    hideConfigurationField('alarm_audio.hardware_device');
    hideConfigurationField('alarm_audio.alsa_device');

    const status = document.getElementById('settings-audio-hardware-status');
    const actionRow = advancedPage.querySelector('.settings-action-row');
    const advancedTitle = advancedPage.querySelector('h3');
    if (advancedTitle) advancedTitle.textContent = 'Audio diagnostics and alarm tests';
    if (status) {
      const statusHeading = document.createElement('h4');
      statusHeading.className = 'settings-subheading';
      statusHeading.textContent = 'Current mixer and DAC status';
      advancedPage.insertBefore(statusHeading, actionRow || null);
      advancedPage.insertBefore(status, actionRow || null);
    }

    const title = audioPage.querySelector('h3');
    if (title) title.textContent = 'Audio hardware';
    const summary = document.createElement('div');
    summary.className = 'settings-status-grid settings-hardware-summary';
    summary.innerHTML = '<p class="muted">Reading the configured audio route…</p>';
    audioPage.appendChild(summary);
    const note = document.createElement('p');
    note.className = 'muted small settings-hardware-maintenance-note';
    note.textContent = 'The physical output is intentionally read-only here. Changing it requires a guarded audio-maintenance procedure because Plexamp, AirPlay and alarms share the same ALSA graph.';
    audioPage.appendChild(note);

    const audioOverview = document.querySelector('[data-settings-subpage-target="audio:hardware"]');
    const advancedOverview = document.querySelector('[data-settings-subpage-target="advanced:audio"]');
    const audioStrong = audioOverview?.querySelector('strong');
    const audioSmall = audioOverview?.querySelector('small');
    const advancedStrong = advancedOverview?.querySelector('strong');
    const advancedSmall = advancedOverview?.querySelector('small');
    if (audioStrong) audioStrong.textContent = 'Hardware';
    if (audioSmall) audioSmall.textContent = 'Current shared output route';
    if (advancedStrong) advancedStrong.textContent = 'Audio diagnostics';
    if (advancedSmall) advancedSmall.textContent = 'Mixer status and controlled alarm tests';

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

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
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

    function scan() {
      mount.querySelectorAll('.settings-live-trim').forEach(upgrade);
    }
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