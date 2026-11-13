(() => {
  if (window.ACPNavPointerFeedback) return;
  const drawer = document.getElementById('nav-drawer');
  if (!drawer || !window.PointerEvent) return;

  let open = document.body.classList.contains('nav-open');
  let pointer = null;
  let anchor = null;
  let armed = false;
  let hovered = null;

  function clearHover() {
    hovered?.classList.remove('is-pointer-hover');
    hovered = null;
  }

  function reset() {
    clearHover();
    armed = false;
    anchor = pointer;
  }

  function syncOpen() {
    const next = document.body.classList.contains('nav-open');
    if (next === open) return;
    open = next;
    reset();
  }

  function hoverPointer(event) {
    return !event.sourceCapabilities?.firesTouchEvents
      && (event.pointerType === 'mouse'
        || (event.pointerType === 'pen' && event.buttons === 0));
  }

  document.addEventListener('pointermove', (event) => {
    syncOpen();
    if (!hoverPointer(event)) {
      pointer = null;
      reset();
      return;
    }
    const point = { x: event.clientX, y: event.clientY };
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return;
    pointer = point;
    if (!open) {
      reset();
      return;
    }
    // An entering button is not pointer intent. Require fresh coordinate
    // movement after every opening; repeated stationary events cannot arm it.
    if (!anchor) anchor = point;
    if (!armed && Math.hypot(point.x - anchor.x, point.y - anchor.y) > 2) armed = true;
    if (!armed) return;
    const button = document.elementFromPoint(point.x, point.y)?.closest('.nav-button');
    const next = button && drawer.contains(button) ? button : null;
    if (next === hovered) return;
    clearHover();
    hovered = next;
    hovered?.classList.add('is-pointer-hover');
  }, { capture: true, passive: true });

  document.addEventListener('pointerdown', (event) => {
    if (hoverPointer(event)) {
      pointer = { x: event.clientX, y: event.clientY };
    } else {
      pointer = null;
      reset();
    }
  }, { capture: true, passive: true });
  document.addEventListener('pointercancel', reset, { passive: true });
  document.addEventListener('pointerout', (event) => {
    if (!event.relatedTarget) reset();
  }, { passive: true });
  window.addEventListener('blur', reset);
  new MutationObserver(syncOpen).observe(document.body, {
    attributes: true, attributeFilter: ['class'],
  });
  document.documentElement.classList.add('acp-nav-pointer-intent');
  window.ACPNavPointerFeedback = Object.freeze({
    status: () => ({ open, armed, hovered: hovered?.getAttribute('href') || hovered?.id || null }),
  });
})();
