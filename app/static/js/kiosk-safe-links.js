(() => {
  if (window.__aClockworkPlexKioskSafeLinksLoaded) return;
  window.__aClockworkPlexKioskSafeLinksLoaded = true;

  const HOLD_MS = 1400;
  let active = null;
  let modal = null;
  let modalTitle = null;
  let modalUrl = null;
  let modalStatus = null;
  let lastAnchor = null;

  function isExternal(anchor) {
    if (!(anchor instanceof HTMLAnchorElement)) return false;
    if (!anchor.href) return false;
    try {
      const url = new URL(anchor.href, window.location.href);
      return ['http:', 'https:'].includes(url.protocol) && url.origin !== window.location.origin;
    } catch (_error) {
      return false;
    }
  }

  function cancelHold() {
    if (!active) return;
    window.clearTimeout(active.timer);
    active.anchor.classList.remove('is-kiosk-link-holding');
    active.anchor.style.removeProperty('--kiosk-link-hold-progress');
    active = null;
  }

  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement('section');
    modal.className = 'kiosk-link-modal';
    modal.dataset.kioskLinkModal = 'true';
    modal.hidden = true;
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'kiosk-link-modal-title');
    modal.innerHTML = `
      <div class="kiosk-link-modal-card">
        <div class="kiosk-link-modal-heading">
          <div>
            <span class="kiosk-link-modal-kicker">External website</span>
            <h2 id="kiosk-link-modal-title">Open on another device</h2>
          </div>
          <button type="button" class="kiosk-link-modal-close" data-kiosk-link-close aria-label="Close">×</button>
        </div>
        <p>This dashboard stays in kiosk mode. Use the address below on a phone or computer.</p>
        <code class="kiosk-link-modal-url" data-kiosk-link-url></code>
        <p class="kiosk-link-modal-status" data-kiosk-link-status aria-live="polite"></p>
        <div class="kiosk-link-modal-actions">
          <button type="button" class="button settings-secondary" data-kiosk-link-copy>Copy address</button>
          <button type="button" class="button" data-kiosk-link-close>Close</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modalTitle = modal.querySelector('#kiosk-link-modal-title');
    modalUrl = modal.querySelector('[data-kiosk-link-url]');
    modalStatus = modal.querySelector('[data-kiosk-link-status]');

    modal.querySelectorAll('[data-kiosk-link-close]').forEach((button) => {
      button.addEventListener('click', closeModal);
    });
    modal.querySelector('[data-kiosk-link-copy]')?.addEventListener('click', async () => {
      const url = modalUrl?.textContent || '';
      try {
        await navigator.clipboard.writeText(url);
        if (modalStatus) modalStatus.textContent = 'Address copied.';
      } catch (_error) {
        if (modalStatus) modalStatus.textContent = 'Copy is unavailable. The address remains visible above.';
      }
    });
    modal.addEventListener('pointerdown', (event) => {
      if (event.target === modal) closeModal();
    });
    return modal;
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('kiosk-link-modal-open');
    if (modalStatus) modalStatus.textContent = '';
    lastAnchor?.blur();
    lastAnchor = null;
  }

  function showExternalAddress(anchor) {
    cancelHold();
    const url = new URL(anchor.href, window.location.href);
    const label = anchor.querySelector('strong')?.textContent?.trim()
      || anchor.textContent.trim()
      || url.hostname;
    ensureModal();
    lastAnchor = anchor;
    if (modalTitle) modalTitle.textContent = label;
    if (modalUrl) modalUrl.textContent = url.href;
    if (modalStatus) modalStatus.textContent = '';
    modal.hidden = false;
    document.body.classList.add('kiosk-link-modal-open');
    modal.querySelector('[data-kiosk-link-close]')?.focus({ preventScroll: true });
  }

  function beginHold(event, anchor) {
    if (event.button !== undefined && event.button !== 0) return;
    cancelHold();
    event.preventDefault();
    event.stopPropagation();
    anchor.classList.add('is-kiosk-link-holding');
    anchor.dataset.kioskLinkHint = 'Keep holding to view the address';
    active = {
      anchor,
      pointerId: event.pointerId,
      timer: window.setTimeout(() => showExternalAddress(anchor), HOLD_MS),
    };
  }

  function finishHold(event) {
    if (!active) return;
    if (event.pointerId !== undefined && active.pointerId !== undefined && event.pointerId !== active.pointerId) return;
    const anchor = active.anchor;
    event.preventDefault();
    event.stopPropagation();
    cancelHold();
    anchor.dataset.kioskLinkHint = 'Press and hold to view the address';
    anchor.blur();
  }

  function prepare(anchor) {
    if (!isExternal(anchor) || anchor.dataset.kioskSafeLink === 'true') return;
    anchor.dataset.kioskSafeLink = 'true';
    anchor.dataset.kioskLinkHint = 'Press and hold to view the address';
    anchor.removeAttribute('target');
    anchor.setAttribute('aria-description', 'Press and hold to view this external website address. The kiosk never leaves the dashboard.');
    anchor.addEventListener('pointerdown', (event) => beginHold(event, anchor));
    anchor.addEventListener('pointerup', finishHold);
    anchor.addEventListener('pointercancel', finishHold);
    anchor.addEventListener('pointerleave', finishHold);
    anchor.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      anchor.dataset.kioskLinkHint = 'Press and hold to view the address';
      window.setTimeout(() => anchor.blur(), 250);
    });
    anchor.addEventListener('keydown', (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      if (event.repeat) return;
      anchor.dataset.kioskLinkHint = 'Keep holding to view the address';
      active = {
        anchor,
        timer: window.setTimeout(() => showExternalAddress(anchor), HOLD_MS),
      };
    });
    anchor.addEventListener('keyup', (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      finishHold(event);
    });
    anchor.addEventListener('blur', cancelHold);
  }

  function scan(root = document) {
    root.querySelectorAll?.('a[href]').forEach(prepare);
  }

  function install() {
    ensureModal();
    scan();
    const observer = new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach((node) => {
          if (node.nodeType !== Node.ELEMENT_NODE) return;
          if (node.matches?.('a[href]')) prepare(node);
          scan(node);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && modal && !modal.hidden) closeModal();
    });
    window.addEventListener('pagehide', () => {
      cancelHold();
      observer.disconnect();
    }, { once: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
