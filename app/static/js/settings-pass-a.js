(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsPassALoaded) return;
  window.__aClockworkPlexSettingsPassALoaded = true;

  const MAX_CLOCK_CARD_SLOTS = 8;
  let activeKeyboardTarget = null;
  let revealTimer = null;

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
      window.clearTimeout(revealTimer);
    }, { once: true });
  }

  function initialise() {
    installClockCardLimit();
    installKeyboardVisibility();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialise, { once: true });
  else initialise();
})();
