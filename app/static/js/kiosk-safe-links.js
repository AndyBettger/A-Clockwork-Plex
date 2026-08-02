(() => {
  if (window.__aClockworkPlexKioskSafeLinksLoaded) return;
  window.__aClockworkPlexKioskSafeLinksLoaded = true;

  const HOLD_MS = 1400;
  let active = null;

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

  function openExternal(anchor) {
    const url = anchor.href;
    cancelHold();
    const opened = window.open(url, '_blank', 'noopener,noreferrer');
    window.setTimeout(() => window.focus(), 0);
    if (!opened) {
      anchor.classList.add('is-kiosk-link-blocked');
      anchor.dataset.kioskLinkHint = 'Browser blocked the external page';
    }
  }

  function beginHold(event, anchor) {
    if (event.button !== undefined && event.button !== 0) return;
    cancelHold();
    event.preventDefault();
    event.stopPropagation();
    anchor.classList.remove('is-kiosk-link-blocked');
    anchor.classList.add('is-kiosk-link-holding');
    anchor.dataset.kioskLinkHint = 'Keep holding to open externally';
    active = {
      anchor,
      pointerId: event.pointerId,
      timer: window.setTimeout(() => openExternal(anchor), HOLD_MS),
    };
  }

  function finishHold(event) {
    if (!active) return;
    if (event.pointerId !== undefined && active.pointerId !== undefined && event.pointerId !== active.pointerId) return;
    const anchor = active.anchor;
    event.preventDefault();
    event.stopPropagation();
    cancelHold();
    anchor.dataset.kioskLinkHint = 'Press and hold to open externally';
  }

  function prepare(anchor) {
    if (!isExternal(anchor) || anchor.dataset.kioskSafeLink === 'true') return;
    anchor.dataset.kioskSafeLink = 'true';
    anchor.dataset.kioskLinkHint = 'Press and hold to open externally';
    anchor.removeAttribute('target');
    anchor.setAttribute('aria-description', 'Press and hold to open this external website. A normal tap stays on the dashboard.');
    anchor.addEventListener('pointerdown', (event) => beginHold(event, anchor));
    anchor.addEventListener('pointerup', finishHold);
    anchor.addEventListener('pointercancel', finishHold);
    anchor.addEventListener('pointerleave', finishHold);
    anchor.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      anchor.dataset.kioskLinkHint = 'Press and hold to open externally';
    });
    anchor.addEventListener('keydown', (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      if (event.repeat) return;
      anchor.dataset.kioskLinkHint = 'Press and hold Enter to open externally';
      active = {
        anchor,
        timer: window.setTimeout(() => openExternal(anchor), HOLD_MS),
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
    window.addEventListener('pagehide', () => {
      cancelHold();
      observer.disconnect();
    }, { once: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
