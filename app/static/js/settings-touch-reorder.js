(() => {
  if (window.ACPTouchReorder) return;

  function scrollParentFor(element) {
    let node = element?.parentElement || null;
    while (node && node !== document.body) {
      const style = window.getComputedStyle(node);
      const overflowY = String(style.overflowY || '');
      if (/(auto|scroll)/.test(overflowY) && node.scrollHeight > node.clientHeight + 2) return node;
      node = node.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  }

  function orderFor(container, itemSelector) {
    return [...container.querySelectorAll(itemSelector)]
      .map((item) => String(item.dataset.touchSortId || '').trim())
      .filter(Boolean);
  }

  function sameOrder(a, b) {
    return a.length === b.length && a.every((value, index) => value === b[index]);
  }

  function bind(container, {
    itemSelector = '[data-touch-sort-id]',
    handleSelector = '[data-touch-sort-handle]',
    onCommit = () => {},
  } = {}) {
    if (!container || container.dataset.touchSortBound === 'true') return;
    container.dataset.touchSortBound = 'true';

    let active = null;

    function commit(startOrder) {
      const nextOrder = orderFor(container, itemSelector);
      if (!sameOrder(startOrder, nextOrder)) onCommit(nextOrder);
    }

    function autoScroll(clientY) {
      if (!active?.scrollParent) return;
      const scrollParent = active.scrollParent;
      const isDocument = scrollParent === document.scrollingElement || scrollParent === document.documentElement;
      const rect = isDocument
        ? { top: 0, bottom: window.innerHeight, height: window.innerHeight }
        : scrollParent.getBoundingClientRect();
      const edge = Math.max(52, Math.min(90, rect.height * 0.16));
      let delta = 0;
      if (clientY < rect.top + edge) delta = -Math.max(16, Math.round((rect.top + edge - clientY) / 2));
      else if (clientY > rect.bottom - edge) delta = Math.max(16, Math.round((clientY - (rect.bottom - edge)) / 2));
      if (!delta) return;
      if (isDocument) window.scrollBy({ top: delta, behavior: 'auto' });
      else scrollParent.scrollBy({ top: delta, behavior: 'auto' });
    }

    function moveToPointer(clientY) {
      if (!active?.item) return;
      const siblings = [...container.querySelectorAll(itemSelector)].filter((item) => item !== active.item);
      const before = siblings.find((item) => {
        const rect = item.getBoundingClientRect();
        return clientY < rect.top + rect.height / 2;
      });
      if (before) container.insertBefore(active.item, before);
      else container.appendChild(active.item);
    }

    function finish(event) {
      if (!active || (event?.pointerId !== undefined && event.pointerId !== active.pointerId)) return;
      const state = active;
      active = null;
      state.item.classList.remove('is-dragging');
      state.handle.classList.remove('is-dragging');
      state.handle.setAttribute('aria-grabbed', 'false');
      container.classList.remove('is-reordering');
      try {
        if (state.handle.hasPointerCapture?.(state.pointerId)) state.handle.releasePointerCapture(state.pointerId);
      } catch (_) {
        // Pointer capture can disappear when a row is moved; release is best effort.
      }
      commit(state.startOrder);
      state.handle.focus({ preventScroll: true });
    }

    container.addEventListener('pointerdown', (event) => {
      const handle = event.target.closest?.(handleSelector);
      if (!handle || !container.contains(handle)) return;
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      const item = handle.closest(itemSelector);
      if (!item || item.parentElement !== container) return;

      event.preventDefault();
      active = {
        item,
        handle,
        pointerId: event.pointerId,
        startOrder: orderFor(container, itemSelector),
        scrollParent: scrollParentFor(container),
      };
      item.classList.add('is-dragging');
      handle.classList.add('is-dragging');
      handle.setAttribute('aria-grabbed', 'true');
      container.classList.add('is-reordering');
      try { handle.setPointerCapture?.(event.pointerId); } catch (_) {}
    });

    container.addEventListener('pointermove', (event) => {
      if (!active || event.pointerId !== active.pointerId) return;
      event.preventDefault();
      autoScroll(event.clientY);
      moveToPointer(event.clientY);
    });

    container.addEventListener('pointerup', finish);
    container.addEventListener('pointercancel', finish);

    container.addEventListener('keydown', (event) => {
      const handle = event.target.closest?.(handleSelector);
      if (!handle || !container.contains(handle) || !['ArrowUp', 'ArrowDown'].includes(event.key)) return;
      const item = handle.closest(itemSelector);
      if (!item || item.parentElement !== container) return;
      const items = [...container.querySelectorAll(itemSelector)];
      const index = items.indexOf(item);
      const target = event.key === 'ArrowUp' ? index - 1 : index + 1;
      if (target < 0 || target >= items.length) return;

      event.preventDefault();
      const startOrder = orderFor(container, itemSelector);
      if (event.key === 'ArrowUp') container.insertBefore(item, items[target]);
      else container.insertBefore(item, items[target].nextSibling);
      commit(startOrder);
      handle.focus({ preventScroll: true });
    });
  }

  window.ACPTouchReorder = Object.freeze({ bind });
})();
