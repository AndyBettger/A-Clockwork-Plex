(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsPhysicalFollowupLoaded) return;
  window.__aClockworkPlexSettingsPhysicalFollowupLoaded = true;

  const AUTOSAVE_DELAY_MS = 650;
  const TEXT_AUTOSAVE_DELAY_MS = 1100;
  let retryTimer = null;

  function initialise() {
    const form = document.getElementById('settings-unified-form');
    const authority = window.ACPUnifiedSettings;
    if (!form || !authority?.markDirty || !authority?.getSnapshot) {
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(initialise, 80);
      return;
    }

    installAutosave(form, authority);
    arrangeAudioHardware();
    installAudioDeviceSelector();
  }

  function sectionFor(element) {
    return element?.closest?.('[data-settings-section]')?.dataset.settingsSection || 'general';
  }

  function confirmationOpen() {
    const dialog = document.querySelector('[data-settings-confirmation]');
    return Boolean(dialog && !dialog.hidden);
  }

  function hasDirtySettings() {
    return Boolean(document.querySelector('.settings-dirty-dot:not([hidden])'));
  }

  function installAutosave(form, authority) {
    if (form.dataset.autosaveOwner === 'physical-followup') return;
    form.dataset.autosaveOwner = 'physical-followup';

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

      // A control may have changed while the previous transaction was active.
      // The original owner deliberately ignores dirty signals during a write,
      // so reassert those sections only after the transaction is idle.
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
      // Text entered through the touch keyboard is committed when Done closes
      // the keyboard. Desktop text fields commit on change/focusout below.
      pending = true;
      changeGeneration += 1;
      pendingSections.add(section);
      if (!control.matches('input[data-keyboard], input[type="text"], input:not([type])')) {
        queue(section, AUTOSAVE_DELAY_MS);
      }
    });

    form.addEventListener('change', (event) => {
      const control = event.target.closest?.('[data-setting-path]');
      if (!control) return;
      queue(sectionFor(control), 120);
    });

    form.addEventListener('focusout', (event) => {
      const control = event.target.closest?.('[data-setting-path]');
      if (!control) return;
      queue(sectionFor(control), 160);
    });

    form.addEventListener('acp:clock-cards-changed', () => queue('weather', 260));
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
      // Do not loop on a validation/helper failure. Only a newer user change is
      // allowed to start another automatic attempt.
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

  function moveField(path, destination) {
    const control = document.querySelector(`[data-setting-path="${path}"]`);
    const field = control?.closest('label');
    if (field && destination) destination.appendChild(field);
    return field;
  }

  function arrangeAudioHardware() {
    const audioPage = document.querySelector('[data-settings-subpage="audio:hardware"] .settings-card');
    const advancedPage = document.querySelector('[data-settings-subpage="advanced:audio"] .settings-card');
    if (!audioPage || !advancedPage || audioPage.dataset.physicalLayoutReady === 'true') return;

    audioPage.dataset.physicalLayoutReady = 'true';
    const status = document.getElementById('settings-audio-hardware-status');
    const advancedGrid = advancedPage.querySelector('.settings-grid');
    const actionRow = advancedPage.querySelector('.settings-action-row');

    const configurationGrid = document.createElement('div');
    configurationGrid.className = 'settings-grid two-col settings-audio-hardware-configuration';
    moveField('alarm_audio.shared_mixer_enabled', configurationGrid);
    moveField('alarm_audio.hardware_device', configurationGrid);
    moveField('alarm_audio.alsa_device', configurationGrid);

    const title = audioPage.querySelector('h3');
    if (title) title.textContent = 'Audio hardware';
    const description = document.createElement('p');
    description.className = 'muted small';
    description.textContent = 'Choose the physical output used beneath the shared ALSA mixer.';
    title?.insertAdjacentElement('afterend', description);
    audioPage.appendChild(configurationGrid);

    const advancedTitle = advancedPage.querySelector('h3');
    if (advancedTitle) advancedTitle.textContent = 'Audio diagnostics and alarm tests';
    if (status) {
      const statusHeading = document.createElement('h4');
      statusHeading.className = 'settings-subheading';
      statusHeading.textContent = 'Current mixer and DAC status';
      advancedPage.insertBefore(statusHeading, actionRow || null);
      advancedPage.insertBefore(status, actionRow || null);
    }

    if (advancedGrid && !advancedGrid.children.length) advancedGrid.remove();

    const audioOverview = document.querySelector('[data-settings-subpage-target="audio:hardware"]');
    const advancedOverview = document.querySelector('[data-settings-subpage-target="advanced:audio"]');
    const audioStrong = audioOverview?.querySelector('strong');
    const audioSmall = audioOverview?.querySelector('small');
    const advancedStrong = advancedOverview?.querySelector('strong');
    const advancedSmall = advancedOverview?.querySelector('small');
    if (audioStrong) audioStrong.textContent = 'Hardware';
    if (audioSmall) audioSmall.textContent = 'DAC and shared-mixer configuration';
    if (advancedStrong) advancedStrong.textContent = 'Audio diagnostics';
    if (advancedSmall) advancedSmall.textContent = 'Mixer status and controlled alarm tests';
  }

  async function installAudioDeviceSelector() {
    const input = document.querySelector('input[data-setting-path="alarm_audio.hardware_device"]');
    if (!input || input.dataset.deviceSelectorInstalled === 'true') return;

    const select = document.createElement('select');
    select.dataset.settingPath = 'alarm_audio.hardware_device';
    select.dataset.deviceSelectorInstalled = 'true';
    select.setAttribute('aria-label', 'Physical DAC');
    const current = String(input.value || '').trim();

    function addOption(value, label) {
      if (!value || [...select.options].some((option) => option.value === value)) return;
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label || value;
      select.appendChild(option);
    }

    addOption(current, current ? `${current} — Currently configured` : '');
    addOption('default', 'default — ALSA default output');
    select.value = current || 'default';
    input.replaceWith(select);

    const field = select.closest('.setting-field');
    let message = field?.querySelector('[data-audio-device-message]');
    if (!message && field) {
      message = document.createElement('small');
      message.dataset.audioDeviceMessage = 'true';
      message.textContent = 'Discovering available ALSA outputs…';
      field.appendChild(message);
    }

    try {
      const response = await fetch('/api/audio/devices', { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.error || `Audio devices returned HTTP ${response.status}.`);
      const selected = select.value;
      (Array.isArray(payload.devices) ? payload.devices : []).forEach((device) => addOption(device.id, device.label));
      if (![...select.options].some((option) => option.value === selected)) addOption(selected, selected);
      select.value = selected;
      if (message) message.textContent = payload.error || `${select.options.length} ALSA output option${select.options.length === 1 ? '' : 's'} available.`;
    } catch (error) {
      if (message) message.textContent = error.message || 'Could not enumerate ALSA outputs; the configured value remains available.';
    }
  }

  if (document.readyState === 'complete') {
    window.setTimeout(initialise, 0);
  } else {
    window.addEventListener('load', initialise, { once: true });
  }
})();
