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
  const originalTypes = new WeakMap();
  let expiryTimer = null;
  let revealTimer = null;
  // Updated by the EXISTING C3 theme-sync status poll. No extra timer or
  // keyboard service is introduced here; a live C3 keyboard takes priority
  // over the old five-minute, browser-only opt-in.
  let systemActive = false;

  // Squeekboard is a compositor overlay: it does not reduce Chromium's
  // visualViewport. Give the Settings detail SCROLLER room for the obscured
  // content, not the whole Settings page (which created a large blank gap).
  // Include ordinary editable fields generated at runtime, including the
  // Weather Underground password field without data-keyboard. Exclude
  // checkboxes, sliders and buttons that must not trigger focus scrolling.
  const nativeFields = 'input:not([type]), input[type="text"], input[type="password"], input[type="number"], input[type="email"], input[type="search"], input[type="url"], input[type="tel"], textarea';
  function clearFocusedField() {
    document.body?.classList?.remove('native-osk-field-focused');
    if (revealTimer !== null) window.clearTimeout(revealTimer);
    revealTimer = null;
  }

  function revealFocusedField() {
    if (!nativeMode()) return;
    const input = document.activeElement;
    if (!input?.matches?.(nativeFields) || input.disabled || input.readOnly) return;
    const pane = input.closest?.('.settings-detail');
    if (!pane?.getBoundingClientRect || !input.getBoundingClientRect) return;
    const bounds = pane.getBoundingClientRect();
    const field = input.getBoundingClientRect();
    const gap = 16;
    // The overlay keyboard does not reduce visualViewport on this labwc
    // session. Only the part of Settings above the real keyboard is visible.
    // Scrolling the existing detail pane avoids shrinking the entire shell.
    const viewportHeight = window.innerHeight || document.documentElement?.clientHeight || 720;
    const keyboardHeight = Math.min(330, Math.max(245, viewportHeight * 0.44));
    const visibleBottom = Math.min(bounds.bottom, viewportHeight - keyboardHeight);
    if (field.bottom > visibleBottom - gap) {
      pane.scrollTop += field.bottom - visibleBottom + gap;
    } else if (field.top < bounds.top + gap) {
      pane.scrollTop -= bounds.top + gap - field.top;
    }
  }

  function syncFocusedField() {
    const input = document.activeElement;
    if (!nativeMode() || !input?.matches?.(nativeFields) || input.disabled || input.readOnly || !input.closest?.('.settings-detail')) {
      clearFocusedField();
      return;
    }
    document.body?.classList?.add('native-osk-field-focused');
    // Reveal after scroll-padding is available; repeat once the compositor
    // keyboard has finished entering (it does not send a resize event).
    window.requestAnimationFrame?.(revealFocusedField);
    if (revealTimer !== null) window.clearTimeout(revealTimer);
    revealTimer = window.setTimeout(() => {
      revealTimer = null;
      revealFocusedField();
    }, 210);
  }

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
    if (systemActive) return true;
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
      if (originalTypes.has(input)) {
        const type = originalTypes.get(input);
        if (type === null) input.removeAttribute('type');
        else input.setAttribute('type', type);
        originalTypes.delete(input);
      }
    });
  }

  function prepareInput(input) {
    if (!nativeMode() || !input?.matches?.('input[data-keyboard]')) return;
    if (!originalHints.has(input)) {
      originalHints.set(input, input.getAttribute('inputmode'));
    }
    // Physical numeric probe: type=number sends Squeekboard the digits
    // purpose whereas type=text + inputmode=numeric was still QWERTY.
    // Convert only native-trial integer fields, never time/decimal/URL, and
    // restore the original text input when returning to ACP's keyboard.
    if (input.dataset.keyboard === 'number' && input.type === 'text') {
      originalTypes.set(input, input.getAttribute('type'));
      input.setAttribute('type', 'number');
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
      button.textContent = systemActive ? 'System keyboard active'
        : (enabled ? 'Restore ACP keyboard' : 'Try system keyboard');
      button.disabled = systemActive;
      button.setAttribute('aria-pressed', String(enabled));
    });
    document.querySelectorAll?.('[data-osk-trial-status]').forEach((label) => {
      label.textContent = systemActive
        ? 'Live C3 system keyboard detected and automatically selected. Stop the C3 session from SSH to restore the ACP keyboard.'
        : enabled
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
    else {
      clearFocusedField();
      restoreInputHints();
    }
    updateControls();
    if (nativeMode()) syncFocusedField();
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

  function setSystemActive(active) {
    const next = active === true;
    if (next === systemActive) return;
    if (next) {
      // The browser's old timed choice must not survive a later --stop,
      // leaving the ACP keyboard suppressed without a native keyboard.
      try { window.sessionStorage.removeItem(KEY); } catch (_error) { /* no-op */ }
      if (expiryTimer !== null) window.clearTimeout(expiryTimer);
      expiryTimer = null;
    }
    systemActive = next;
    notify(); // Also closes any already-visible ACP HTML keyboard.
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
    // A running native Squeekboard and ACP's HTML keyboard must never both
    // be selected. Stop the native process before choosing ACP instead.
    if (systemActive) return true;
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
  document.addEventListener('focusin', (event) => {
    prepareInput(event.target);
    syncFocusedField();
  }, true);
  document.addEventListener('focusout', () => {
    // New focus (including an adjacent numeric field) settles on the next
    // tick; never leave the Settings pane shrunk after the input blurs.
    window.setTimeout(syncFocusedField, 0);
  }, true);

  document.addEventListener('click', (event) => {
    const toggle = event.target?.closest?.('[data-osk-trial-toggle]');
    if (!toggle) return;
    event.preventDefault();
    if (!systemActive) setNative(!nativeMode());
  });

  window.ACPKeyboardChoice = Object.freeze({
    isNative: nativeMode,
    setNative,
    setSystemActive,
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
