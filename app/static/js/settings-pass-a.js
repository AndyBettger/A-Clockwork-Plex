(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsPassALoaded) return;
  window.__aClockworkPlexSettingsPassALoaded = true;

  const MAX_CLOCK_CARD_SLOTS = 8;
  let activeKeyboardTarget = null;
  let revealTimer = null;
  let alarmCountObserver = null;

  function installStatusBadgeCleanup() {
    document.querySelector('[data-night-dim-status]')?.remove();
    document.querySelector('[data-shairport-health]')?.remove();
    document.querySelector(
      '[data-settings-subpage="audio:trims"] .settings-card-heading > .settings-chip',
    )?.remove();

    const mount = document.getElementById('settings-alarm-schedule');
    if (!mount || mount.dataset.alarmCountSummaryReady === 'true') return;
    mount.dataset.alarmCountSummaryReady = 'true';

    const updateAlarmCount = () => {
      const heading = mount.querySelector('.alarm-schedule-heading');
      const chip = heading?.querySelector('.settings-chip');
      if (!heading || !chip) return;

      const count = mount.querySelectorAll('.alarm-editor-card').length;
      const label = count === 0
        ? 'No alarms set'
        : `${count} Alarm${count === 1 ? '' : 's'} Set`;
      if (chip.textContent !== label) chip.textContent = label;
      chip.classList.add('alarm-count-summary');
    };

    alarmCountObserver = new MutationObserver(updateAlarmCount);
    alarmCountObserver.observe(mount, { childList: true, subtree: true });
    updateAlarmCount();
  }

  function installServiceStatusRefresh() {
    const refreshButton = document.querySelector('[data-action="refresh-services"]');
    const openButton = document.querySelector('[data-settings-subpage-target="advanced:services"]');
    if (!refreshButton || !openButton || refreshButton.dataset.automaticServiceRefresh === 'true') return;

    refreshButton.dataset.automaticServiceRefresh = 'true';
    refreshButton.hidden = true;
    refreshButton.tabIndex = -1;
    refreshButton.setAttribute('aria-hidden', 'true');

    openButton.addEventListener('click', () => {
      window.setTimeout(() => refreshButton.click(), 0);
    });
  }

  function installClockCardLimit() {
    const root = document.querySelector('[data-clock-card-settings]');
    const order = document.getElementById('clock-card-order');
    const palette = root?.querySelector('.clock-card-palette');
    if (!root || !order || !palette || root.dataset.clockCardLimitReady === 'true') return;
    root.dataset.clockCardLimitReady = 'true';

    const guidance = root.querySelector('h3 + p');
    const status = document.createElement('div');
    status.className = 'clock-card-selection-status';
    status.setAttribute('aria-live', 'polite');
    if (guidance) guidance.insertAdjacentElement('afterend', status);
    else root.insertBefore(status, order);

    function selectedCount() {
      return order.querySelectorAll('.clock-card-row').length;
    }

    function update() {
      const count = selectedCount();
      const atLimit = count >= MAX_CLOCK_CARD_SLOTS;
      status.textContent = `${count} of ${MAX_CLOCK_CARD_SLOTS} Clock slots selected${atLimit ? ' · remove one to choose another' : ''}`;
      status.classList.toggle('is-limit', atLimit);

      palette.querySelectorAll('.clock-card-toggle').forEach((button) => {
        const selected = button.classList.contains('is-selected')
          || button.getAttribute('aria-pressed') === 'true';
        const blocked = atLimit && !selected;
        button.disabled = blocked;
        button.classList.toggle('is-limit-blocked', blocked);
        if (blocked) {
          button.setAttribute('aria-description', 'Eight Clock weather slots are already selected. Remove a selected card first.');
          button.title = 'Remove a selected Clock card before adding another.';
        } else {
          button.removeAttribute('aria-description');
          button.removeAttribute('title');
        }
      });
    }

    const observer = new MutationObserver(update);
    observer.observe(order, { childList: true, subtree: true });
    root.addEventListener('acp:clock-cards-changed', update);
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
    update();
  }

  function keyboardHeight() {
    const keyboard = document.getElementById('touch-keyboard');
    if (!keyboard || !document.body.classList.contains('keyboard-open')) return 0;
    const height = Math.ceil(keyboard.getBoundingClientRect().height);
    document.documentElement.style.setProperty('--settings-keyboard-height', `${height}px`);
    return height;
  }

  function revealKeyboardTarget(target = activeKeyboardTarget) {
    if (!(target instanceof HTMLElement) || !document.body.classList.contains('keyboard-open')) return;
    const detail = target.closest('.settings-detail');
    if (!detail) return;

    window.clearTimeout(revealTimer);
    revealTimer = window.setTimeout(() => {
      const height = keyboardHeight();
      const detailRect = detail.getBoundingClientRect();
      const targetRect = (target.closest('.setting-field, .setting-toggle, label') || target).getBoundingClientRect();
      const visibleTop = detailRect.top + 10;
      const visibleBottom = Math.min(detailRect.bottom, window.innerHeight - height - 12);

      if (targetRect.bottom > visibleBottom) {
        detail.scrollBy({
          top: targetRect.bottom - visibleBottom + 18,
          behavior: 'smooth',
        });
      } else if (targetRect.top < visibleTop) {
        detail.scrollBy({
          top: targetRect.top - visibleTop - 10,
          behavior: 'smooth',
        });
      }
    }, 90);
  }

  function installKeyboardVisibility() {
    if (document.body.dataset.settingsKeyboardVisibilityReady === 'true') return;
    document.body.dataset.settingsKeyboardVisibilityReady = 'true';

    document.addEventListener('focusin', (event) => {
      const target = event.target.closest?.('input[data-keyboard]');
      if (!target) return;
      activeKeyboardTarget = target;
      revealKeyboardTarget(target);
    }, true);

    document.addEventListener('pointerdown', (event) => {
      const target = event.target.closest?.('input[data-keyboard]');
      if (!target) return;
      activeKeyboardTarget = target;
      window.setTimeout(() => revealKeyboardTarget(target), 120);
    }, true);

    document.addEventListener('click', (event) => {
      if (event.target.closest?.('[data-settings-subpage-target], [data-settings-section-target], [data-settings-back]')) {
        window.setTimeout(() => revealKeyboardTarget(), 140);
      }
    });

    const observer = new MutationObserver(() => {
      if (document.body.classList.contains('keyboard-open')) revealKeyboardTarget();
      else {
        document.documentElement.style.removeProperty('--settings-keyboard-height');
        activeKeyboardTarget = null;
      }
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    window.addEventListener('resize', () => revealKeyboardTarget());
    window.addEventListener('pagehide', () => {
      observer.disconnect();
      alarmCountObserver?.disconnect();
      window.clearTimeout(revealTimer);
    }, { once: true });
  }

  function installRestoreUxClarity() {
    const page = document.querySelector('[data-settings-subpage="advanced:backup"]');
    if (!page || page.dataset.restoreUxClarityReady === 'true') return;
    page.dataset.restoreUxClarityReady = 'true';

    const reviewButton = page.querySelector('[data-action="apply-configuration-restore"]');
    const confirmButton = page.querySelector('[data-action="confirm-configuration-restore"]');
    const previewButton = page.querySelector('[data-action="preview-configuration-restore"]');
    const restoreFile = page.querySelector('[data-configuration-restore-file]');
    const restoreMessage = page.querySelector('[data-configuration-restore-message]');

    if (reviewButton) {
      reviewButton.textContent = 'Review restore';
      reviewButton.title = 'Open the final confirmation. No settings change at this step.';
    }
    if (confirmButton) {
      confirmButton.textContent = 'Confirm & restore';
      confirmButton.title = 'Apply the freshly previewed server-owned settings.';
    }

    let restoreConflictDetail = '';
    const enforceConflictMessage = () => {
      if (!restoreMessage || !restoreConflictDetail) return;
      const expected = `Restore blocked — no settings were changed. ${restoreConflictDetail}`;
      if (restoreMessage.textContent !== expected) restoreMessage.textContent = expected;
      restoreMessage.classList.add('is-conflict');
    };
    const clearConflict = () => {
      restoreConflictDetail = '';
      restoreMessage?.classList.remove('is-conflict');
    };

    const conflictObserver = restoreMessage
      ? new MutationObserver(() => {
          if (restoreConflictDetail) enforceConflictMessage();
        })
      : null;
    conflictObserver?.observe(restoreMessage, { childList: true, characterData: true, subtree: true });
    window.addEventListener('pagehide', () => conflictObserver?.disconnect(), { once: true });

    previewButton?.addEventListener('click', clearConflict, true);
    restoreFile?.addEventListener('change', clearConflict, true);

    if (window.__acpRestoreConflictFetchWrapped === true) return;
    window.__acpRestoreConflictFetchWrapped = true;
    const nativeFetch = window.fetch.bind(window);

    window.fetch = async (...args) => {
      const response = await nativeFetch(...args);
      const requestTarget = args[0];
      const requestUrl = typeof requestTarget === 'string'
        ? requestTarget
        : String(requestTarget?.url || '');
      let pathname = '';
      try {
        pathname = new URL(requestUrl, window.location.href).pathname;
      } catch (_error) {
        pathname = requestUrl;
      }

      if (pathname === '/api/settings/restore/apply' && response.status === 409) {
        const payload = await response.clone().json().catch(() => ({}));
        if (payload?.fresh_preview_required === true) {
          restoreConflictDetail = String(
            payload.error || 'The restore preview is no longer current. Run Preview restore again.',
          ).trim();
          enforceConflictMessage();
        }
      }
      return response;
    };
  }

  function initialise() {
    installStatusBadgeCleanup();
    installServiceStatusRefresh();
    installClockCardLimit();
    installKeyboardVisibility();
    installRestoreUxClarity();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialise, { once: true });
  else initialise();
})();