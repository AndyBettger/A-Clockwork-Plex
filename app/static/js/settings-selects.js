(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsSelectsLoaded) return;
  window.__aClockworkPlexSettingsSelectsLoaded = true;

  const form = document.getElementById('settings-unified-form');
  if (!form) return;

  const enhanced = new Set();
  let sequence = 0;
  let openState = null;
  let refreshQueued = false;

  const layer = document.createElement('div');
  layer.id = 'acp-settings-select-layer';
  layer.className = 'acp-settings-select-layer';
  layer.hidden = true;
  document.body.appendChild(layer);

  function labelFor(select) {
    const explicit = String(select.getAttribute('aria-label') || '').trim();
    if (explicit) return explicit;
    const fieldLabel = select.closest('.setting-field')?.querySelector(':scope > span');
    const text = String(fieldLabel?.textContent || '').trim();
    return text || select.name || select.id || 'Choose an option';
  }

  function selectedLabel(select) {
    return select.selectedOptions?.[0]?.textContent?.trim()
      || select.options?.[select.selectedIndex]?.textContent?.trim()
      || 'Choose';
  }

  function close({ restoreFocus = false } = {}) {
    if (!openState) return;
    const { trigger } = openState;
    trigger.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
    layer.hidden = true;
    layer.replaceChildren();
    layer.style.cssText = '';
    openState = null;
    if (restoreFocus && trigger.isConnected) trigger.focus({ preventScroll: true });
  }

  function sync(state) {
    const { select, trigger, valueText } = state;
    if (!select.isConnected || !trigger.isConnected) return;
    valueText.textContent = selectedLabel(select);
    trigger.disabled = select.disabled;
    trigger.setAttribute('aria-label', `${labelFor(select)}: ${selectedLabel(select)}`);
    trigger.classList.toggle('is-disabled', select.disabled);
    if (openState?.state === state) {
      layer.querySelectorAll('.acp-settings-select-option').forEach((option) => {
        const selected = option.dataset.value === select.value;
        option.classList.toggle('is-selected', selected);
        option.setAttribute('aria-selected', selected ? 'true' : 'false');
        option.tabIndex = selected ? 0 : -1;
        option.querySelector('.acp-settings-select-mark').textContent = selected ? '✓' : '';
      });
    }
  }

  function dispatchSelection(select, value) {
    const changed = select.value !== value;
    select.value = value;
    if (!changed) return;
    select.dispatchEvent(new Event('input', { bubbles: true }));
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function menuOptions(select) {
    return [...select.options].map((option) => ({
      value: option.value,
      label: option.textContent?.trim() || option.value,
      disabled: option.disabled || option.parentElement?.disabled === true,
      selected: option.selected,
      group: option.parentElement instanceof HTMLOptGroupElement
        ? option.parentElement.label
        : '',
    }));
  }

  function positionLayer(state) {
    const bounds = state.trigger.getBoundingClientRect();
    const viewport = window.visualViewport;
    const viewportWidth = viewport?.width || window.innerWidth;
    const viewportHeight = viewport?.height || window.innerHeight;
    const margin = 10;
    const gap = 6;
    const minimumWidth = 174;
    const width = Math.min(
      Math.max(bounds.width, minimumWidth),
      Math.max(minimumWidth, viewportWidth - (margin * 2)),
    );
    const left = Math.min(
      Math.max(bounds.left, margin),
      Math.max(margin, viewportWidth - width - margin),
    );
    const roomBelow = Math.max(0, viewportHeight - bounds.bottom - margin - gap);
    const roomAbove = Math.max(0, bounds.top - margin - gap);
    const opensUp = roomBelow < 190 && roomAbove > roomBelow;
    const available = Math.max(96, opensUp ? roomAbove : roomBelow);
    const maxHeight = Math.min(320, available);

    layer.style.left = `${Math.round(left)}px`;
    layer.style.width = `${Math.round(width)}px`;
    layer.style.maxHeight = `${Math.round(maxHeight)}px`;
    layer.classList.toggle('opens-up', opensUp);
    if (opensUp) {
      layer.style.top = 'auto';
      layer.style.bottom = `${Math.round(viewportHeight - bounds.top + gap)}px`;
    } else {
      layer.style.bottom = 'auto';
      layer.style.top = `${Math.round(bounds.bottom + gap)}px`;
    }
  }

  function focusRelative(menu, direction) {
    const options = [...menu.querySelectorAll('.acp-settings-select-option:not(:disabled)')];
    if (!options.length) return;
    const current = options.indexOf(document.activeElement);
    const next = current < 0
      ? (direction > 0 ? 0 : options.length - 1)
      : (current + direction + options.length) % options.length;
    options[next].focus({ preventScroll: true });
    options[next].scrollIntoView({ block: 'nearest' });
  }

  function buildMenu(state) {
    if (openState?.state !== state) return;
    const { select, menuId } = state;
    const menu = document.createElement('div');
    menu.className = 'acp-settings-select-menu';
    menu.id = menuId;
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', labelFor(select));

    let lastGroup = null;
    let selectedButton = null;
    menuOptions(select).forEach((item) => {
      if (item.group && item.group !== lastGroup) {
        const heading = document.createElement('div');
        heading.className = 'acp-settings-select-group';
        heading.textContent = item.group;
        heading.setAttribute('role', 'presentation');
        menu.appendChild(heading);
        lastGroup = item.group;
      }

      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'acp-settings-select-option';
      option.dataset.value = item.value;
      option.disabled = item.disabled;
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', item.selected ? 'true' : 'false');
      option.tabIndex = item.selected ? 0 : -1;

      const text = document.createElement('span');
      text.textContent = item.label;
      const mark = document.createElement('span');
      mark.className = 'acp-settings-select-mark';
      mark.textContent = item.selected ? '✓' : '';
      mark.setAttribute('aria-hidden', 'true');
      option.append(text, mark);
      if (item.selected) {
        option.classList.add('is-selected');
        selectedButton = option;
      }

      option.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        dispatchSelection(select, item.value);
        sync(state);
        close({ restoreFocus: true });
      });
      menu.appendChild(option);
    });

    menu.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close({ restoreFocus: true });
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        focusRelative(menu, 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        focusRelative(menu, -1);
      } else if (event.key === 'Home') {
        event.preventDefault();
        menu.querySelector('.acp-settings-select-option:not(:disabled)')?.focus({ preventScroll: true });
      } else if (event.key === 'End') {
        event.preventDefault();
        [...menu.querySelectorAll('.acp-settings-select-option:not(:disabled)')].at(-1)?.focus({ preventScroll: true });
      }
    });

    layer.replaceChildren(menu);
    positionLayer(state);
    window.requestAnimationFrame(() => {
      selectedButton?.scrollIntoView({ block: 'center' });
      selectedButton?.focus({ preventScroll: true });
    });
  }

  function open(state) {
    if (state.select.disabled) return;
    if (openState?.state === state) return close();
    close();
    openState = { state, trigger: state.trigger };
    state.trigger.classList.add('is-open');
    state.trigger.setAttribute('aria-expanded', 'true');
    layer.hidden = false;
    buildMenu(state);
  }

  function enhance(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    if (select.multiple || Number(select.size || 0) > 1) return;
    if (select.dataset.acpNativeSelect === 'true' || select.dataset.acpSelectEnhanced === 'true') return;

    const shell = document.createElement('div');
    shell.className = 'acp-settings-select-shell';
    const trigger = document.createElement('button');
    const valueText = document.createElement('span');
    const arrow = document.createElement('span');
    const menuId = `acp-settings-select-menu-${++sequence}`;

    trigger.type = 'button';
    trigger.className = 'acp-settings-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', menuId);
    valueText.className = 'acp-settings-select-value';
    arrow.className = 'acp-settings-select-arrow';
    arrow.textContent = '⌄';
    arrow.setAttribute('aria-hidden', 'true');
    trigger.append(valueText, arrow);
    shell.appendChild(trigger);

    select.dataset.acpSelectEnhanced = 'true';
    select.classList.add('acp-settings-select-native');
    select.setAttribute('aria-hidden', 'true');
    select.tabIndex = -1;
    select.insertAdjacentElement('afterend', shell);

    const state = { select, shell, trigger, valueText, menuId, observer: null };
    const ownerLabel = select.closest('label');
    enhanced.add(state);

    trigger.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      open(state);
    });
    trigger.addEventListener('keydown', (event) => {
      if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault();
        open(state);
      }
    });
    ownerLabel?.addEventListener('click', (event) => {
      if (shell.contains(event.target)) return;
      if (event.target.closest('button, input, textarea, a, [role="button"]')) return;
      event.preventDefault();
      event.stopPropagation();
      open(state);
    });
    select.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      open(state);
    });
    select.addEventListener('input', () => sync(state));
    select.addEventListener('change', () => sync(state));

    state.observer = new MutationObserver(() => {
      sync(state);
      if (openState?.state === state) buildMenu(state);
    });
    state.observer.observe(select, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled', 'label', 'selected', 'value'],
    });
    sync(state);
  }

  function refresh() {
    form.querySelectorAll('select').forEach(enhance);
    [...enhanced].forEach((state) => {
      if (!state.select.isConnected || !state.trigger.isConnected) {
        state.observer?.disconnect();
        enhanced.delete(state);
        if (openState?.state === state) close();
        return;
      }
      sync(state);
    });
  }

  function queueRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    window.requestAnimationFrame(() => {
      refreshQueued = false;
      refresh();
    });
  }

  const observer = new MutationObserver(queueRefresh);
  observer.observe(form, { childList: true, subtree: true });

  const syncTimer = window.setInterval(refresh, 2000);
  [0, 150, 500, 1500].forEach((delay) => window.setTimeout(queueRefresh, delay));

  document.addEventListener('pointerdown', (event) => {
    if (!openState) return;
    if (layer.contains(event.target) || openState.trigger.contains(event.target)) return;
    close();
  }, true);
  document.addEventListener('click', () => window.setTimeout(queueRefresh, 0));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && openState) {
      event.preventDefault();
      close({ restoreFocus: true });
    }
  });
  document.addEventListener('scroll', (event) => {
    if (openState && !layer.contains(event.target)) close();
  }, true);
  window.addEventListener('resize', close);
  window.visualViewport?.addEventListener('resize', close);
  window.addEventListener('hashchange', close);
  window.addEventListener('pagehide', () => {
    close();
    window.clearInterval(syncTimer);
    observer.disconnect();
    enhanced.forEach((state) => state.observer?.disconnect());
  });
  window.addEventListener('acp:settings-selects-refresh', queueRefresh);

  window.ACPSettingsSelects = Object.freeze({
    refresh: queueRefresh,
    close,
  });

  refresh();
})();
