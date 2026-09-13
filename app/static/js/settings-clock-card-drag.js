(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexClockCardDragLoaded) return;
  window.__aClockworkPlexClockCardDragLoaded = true;

  const root = document.querySelector('[data-clock-card-settings]');
  const order = document.getElementById('clock-card-order');
  if (!root || !order || !window.ACPClockCards) return;

  const help = root.querySelector('h3 + .muted.small');
  if (help) help.textContent = 'Choose cards below, then drag the grip to set their order.';

  function decorateRows() {
    order.querySelectorAll('.clock-card-row').forEach((row) => {
      row.classList.add('touch-sort-row', 'clock-card-drag-row');
      row.dataset.touchSortId = row.dataset.cardId || '';

      row.querySelectorAll('.clock-card-order-button').forEach((button) => {
        button.hidden = true;
        button.setAttribute('aria-hidden', 'true');
        button.tabIndex = -1;
      });

      if (!row.querySelector('[data-touch-sort-handle]')) {
        const label = String(row.querySelector('.clock-card-label')?.textContent || row.dataset.cardId || 'weather card').trim();
        const handle = document.createElement('button');
        handle.type = 'button';
        handle.className = 'settings-drag-handle clock-card-drag-handle';
        handle.dataset.touchSortHandle = '';
        handle.setAttribute('aria-label', `Drag ${label} to reorder. Arrow keys also move it.`);
        handle.setAttribute('aria-grabbed', 'false');
        handle.innerHTML = '<span aria-hidden="true">⠿</span>';
        row.insertBefore(handle, row.firstChild);
      }
    });
  }

  function commit(ids) {
    if (!Array.isArray(ids) || !ids.length) return;
    window.ACPClockCards.applyStoredIds(ids);
    decorateRows();
    root.dispatchEvent(new CustomEvent('acp:clock-cards-changed', {
      bubbles: true,
      detail: { clockCards: window.ACPClockCards.storedIds() },
    }));
  }

  window.ACPTouchReorder?.bind?.(order, {
    itemSelector: '.clock-card-row[data-touch-sort-id]',
    handleSelector: '[data-touch-sort-handle]',
    onCommit: commit,
  });

  const observer = new MutationObserver(decorateRows);
  observer.observe(order, { childList: true });
  decorateRows();
})();
