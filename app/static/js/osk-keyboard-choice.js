(() => {
  'use strict';

  // Phase B #94: opt-in, Chromium-tab-only OSK experiment. The existing
  // ACP keyboard remains the default; no server setting or system changes.
  // A bounded trial is required because the vendor TOP-layer Squeekboard
  // is hidden by true fullscreen. User must start the guarded OVERLAY test.
  if (window.ACPKeyboardChoice) return;

  const KEY = 'acp.phase-b.native-osk-trial.until';
  const LIMIT_MS = 5 * 60 * 1000;
  const hints = Object.freeze({
    text: 'text',
    number: 'numeric',
    decimal: 'decimal',
    time: 'text', // keep ':' accessible for alarm times
    url: 'url',
  });
  const originalHints = new WeakMap();
  let expiryTimer = null;

  function savedExpiry() {
    try {
      const value = Number(window.sessionStorage.getItem(KEY));
      return Number.isFinite(value) && value > 0 ? value : 0;
    } catch (_error) {
      // Storage blocked: safely retain the original ACP keyboard.
      return 0;
    }
  }

  function nativeMode() {
    const expires = savedExpiry();
    return expires > Date.now() && expires - Date.now() <= LIMIT_MS;
  }

  function restoreInputHints() {
    if (!document.querySelectorAll) return;
    document.querySelectorAll('input[data-keyboard]').forEach((input) => {
      if (!originalHints.has(input)) return;
      const original = originalHints.get(input);
      if (original === null) input.removeAttribute('inputmode');
      else input.setAttribute('inputmode', original);
      originalHints.delete(input);
    });
  }

  function prepareInput(input) {
    if (!nativeMode() || !input?.matches?.('input[data-keyboard]')) return;
    if (!originalHints.has(input)) {
      originalHints.set(input, input.getAttribute('inputmode'));
    }
    input.setAttribute('inputmode', hints[input.dataset.keyboard] || 'text');
  }

  function prepareInputs() {
    if (!document.querySelectorAll) return;
    document.querySelectorAll('input[data-keyboard]').forEach(prepareInput);
  }

  function updateControls() {
    const enabled = nativeMode();
    document.querySelectorAll?.('[data-osk-trial-toggle]').forEach((button) => {
      button.textContent = enabled ? 'Restore ACP keyboard' : 'Try system keyboard';
      button.setAttribute('aria-pressed', String(enabled));
    });
    document.querySelectorAll?.('[data-osk-trial-status]').forEach((label) => {
      label.textContent = enabled
        ? 'Native keyboard selected for this browser tab. The separately started Squeekboard trial lasts up to 180 seconds from its SSH launch; this browser choice expires after five minutes. Restore ACP keyboard if native input stops.'
        : 'Using the existing ACP keyboard. System keyboard trial is off.';
    });
    document.querySelectorAll?.('[data-osk-native-probes]').forEach((panel) => {
      panel.hidden = !enabled;
    });
  }

  function notify() {
    document.documentElement.dataset.acpKeyboardChoice = nativeMode() ? 'native' : 'acp';
    if (nativeMode()) prepareInputs();
    else restoreInputHints();
    updateControls();
    window.dispatchEvent(new CustomEvent('acp:keyboard-choice-changed', {
      detail: { native: nativeMode() },
    }));
  }

  function clearTrial() {
    try { window.sessionStorage.removeItem(KEY); } catch (_error) { /* no-op */ }
    if (expiryTimer !== null) {
      window.clearTimeout(expiryTimer);
      expiryTimer = null;
    }
    notify();
  }

  function scheduleExpiry() {
    if (expiryTimer !== null) window.clearTimeout(expiryTimer);
    expiryTimer = null;
    const remaining = savedExpiry() - Date.now();
    if (remaining > 0 && remaining <= LIMIT_MS) {
      expiryTimer = window.setTimeout(clearTrial, remaining + 20);
    }
  }

  function setNative(enable) {
    if (!enable) {
      clearTrial();
      return true;
    }
    const expires = Date.now() + LIMIT_MS;
    try {
      window.sessionStorage.setItem(KEY, String(expires));
      if (Number(window.sessionStorage.getItem(KEY)) !== expires) throw Error('storage blocked');
    } catch (_error) {
      clearTrial();
      return false;
    }
    scheduleExpiry();
    notify();
    return true;
  }

  // Capture pointer input *before* Chromium focuses the editable field.
  // The previous ACP markup has inputmode=none to suppress native keyboards.
  document.addEventListener('pointerdown', (event) => {
    prepareInput(event.target?.closest?.('input[data-keyboard]'));
  }, true);
  document.addEventListener('focusin', (event) => prepareInput(event.target), true);

  document.addEventListener('click', (event) => {
    const toggle = event.target?.closest?.('[data-osk-trial-toggle]');
    if (!toggle) return;
    event.preventDefault();
    setNative(!nativeMode());
  });

  window.ACPKeyboardChoice = Object.freeze({
    isNative: nativeMode,
    setNative,
  });

  // Expired/invalid session values are discarded so an old tab cannot keep
  // the custom keyboard hidden after the independent OSK trial ends.
  if (!nativeMode()) {
    clearTrial();
  } else {
    scheduleExpiry();
    if (document.readyState !== 'loading') notify();
    else document.addEventListener('DOMContentLoaded', notify, { once: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateControls, { once: true });
  } else {
    updateControls();
  }
})();
