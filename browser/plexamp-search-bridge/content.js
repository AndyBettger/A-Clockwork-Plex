(() => {
  'use strict';

  const FOCUS_TYPE = 'acp-plexamp-search-focus-v1';
  const EDIT_TYPE = 'acp-plexamp-search-edit-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const SAFE_SESSION = /^[A-Za-z0-9-]{16,96}$/;
  const SEARCH_WORD = /\bsearch\b/i;
  const ALLOWED_COMMANDS = new Set(['insert', 'backspace', 'clear', 'submit', 'done']);

  function attribute(target, name) {
    try {
      return String(target?.getAttribute?.(name) || '');
    } catch (_error) {
      return '';
    }
  }

  function isEligibleSearchTarget(target) {
    if (!target || String(target.tagName || '').toUpperCase() !== 'INPUT') return false;
    if (target.disabled === true || target.readOnly === true) return false;

    const type = String(target.type || attribute(target, 'type') || 'text').toLowerCase();
    if (!['search', 'text'].includes(type)) return false;
    if (type === 'search') return true;

    const role = attribute(target, 'role').toLowerCase();
    if (role === 'searchbox') return true;

    const clues = [
      attribute(target, 'aria-label'),
      attribute(target, 'placeholder'),
      attribute(target, 'name'),
      attribute(target, 'data-testid'),
    ];
    if (clues.some((value) => SEARCH_WORD.test(value))) return true;

    try {
      const container = target.closest?.('[role="search"], [aria-label*="search" i]');
      return Boolean(container);
    } catch (_error) {
      return false;
    }
  }

  function validInsertText(text) {
    if (typeof text !== 'string' || Array.from(text).length !== 1 || text.length > 4) return false;
    return !/[\u0000-\u001f\u007f]/.test(text);
  }

  function validateSearchEditRequest(raw) {
    if (!raw || raw.type !== EDIT_TYPE) return null;
    if (typeof raw.session_id !== 'string' || !SAFE_SESSION.test(raw.session_id)) return null;
    if (typeof raw.command !== 'string' || !ALLOWED_COMMANDS.has(raw.command)) return null;
    if (raw.command === 'insert') {
      if (!validInsertText(raw.text)) return null;
      return { session_id: raw.session_id, command: 'insert', text: raw.text };
    }
    if (raw.text !== undefined) return null;
    return { session_id: raw.session_id, command: raw.command };
  }

  function clampSelection(value, position) {
    const parsed = Number(position);
    if (!Number.isFinite(parsed)) return value.length;
    return Math.max(0, Math.min(value.length, Math.trunc(parsed)));
  }

  function planSearchEdit(value, selectionStart, selectionEnd, command, text = '') {
    const current = String(value ?? '');
    const start = clampSelection(current, selectionStart);
    const end = Math.max(start, clampSelection(current, selectionEnd));

    if (command === 'insert' && validInsertText(text)) {
      const next = `${current.slice(0, start)}${text}${current.slice(end)}`;
      const cursor = start + text.length;
      return { changed: next !== current, value: next, cursor, inputType: 'insertText', data: text };
    }
    if (command === 'clear') {
      return { changed: current.length > 0, value: '', cursor: 0, inputType: 'deleteContent', data: null };
    }
    if (command === 'backspace') {
      if (start !== end) {
        const next = `${current.slice(0, start)}${current.slice(end)}`;
        return { changed: next !== current, value: next, cursor: start, inputType: 'deleteContentBackward', data: null };
      }
      if (start <= 0) {
        return { changed: false, value: current, cursor: 0, inputType: 'deleteContentBackward', data: null };
      }
      const prefix = current.slice(0, start);
      const points = Array.from(prefix);
      points.pop();
      const before = points.join('');
      const next = `${before}${current.slice(start)}`;
      return { changed: next !== current, value: next, cursor: before.length, inputType: 'deleteContentBackward', data: null };
    }
    return null;
  }

  function setNativeInputValue(target, value) {
    const view = target?.ownerDocument?.defaultView;
    const prototype = view?.HTMLInputElement?.prototype;
    const descriptor = prototype ? Object.getOwnPropertyDescriptor(prototype, 'value') : null;
    if (descriptor?.set) descriptor.set.call(target, value);
    else target.value = value;
  }

  function dispatchInput(target, plan) {
    const view = target?.ownerDocument?.defaultView;
    let event;
    try {
      if (typeof view?.InputEvent === 'function') {
        event = new view.InputEvent('input', {
          bubbles: true,
          composed: true,
          inputType: plan.inputType,
          data: plan.data,
        });
      }
    } catch (_error) {
      event = null;
    }
    if (!event) {
      const EventCtor = view?.Event || globalThis.Event;
      event = new EventCtor('input', { bubbles: true, composed: true });
    }
    target.dispatchEvent(event);
  }

  function dispatchSubmit(target) {
    const view = target?.ownerDocument?.defaultView;
    const KeyboardEventCtor = view?.KeyboardEvent;
    if (typeof KeyboardEventCtor !== 'function') return false;

    const init = {
      key: 'Enter',
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true,
      cancelable: true,
      composed: true,
    };
    const down = new KeyboardEventCtor('keydown', init);
    const continueDefault = target.dispatchEvent(down);
    target.dispatchEvent(new KeyboardEventCtor('keypress', init));
    target.dispatchEvent(new KeyboardEventCtor('keyup', init));

    if (continueDefault && !down.defaultPrevented) {
      try {
        target.form?.requestSubmit?.();
      } catch (_error) {
        // Plexamp normally handles Search through its key/input listeners.
      }
    }
    return true;
  }

  function applySearchEdit(target, request) {
    if (!isEligibleSearchTarget(target) || target.isConnected === false) return false;
    if (request.command === 'done') {
      target.blur?.();
      return true;
    }
    if (request.command === 'submit') return dispatchSubmit(target);

    const plan = planSearchEdit(
      target.value,
      target.selectionStart,
      target.selectionEnd,
      request.command,
      request.text,
    );
    if (!plan) return false;
    if (plan.changed) {
      setNativeInputValue(target, plan.value);
      target.setSelectionRange?.(plan.cursor, plan.cursor);
      dispatchInput(target, plan);
    }
    return true;
  }

  function newSessionId(win) {
    if (typeof win?.crypto?.randomUUID === 'function') return win.crypto.randomUUID();
    if (typeof win?.crypto?.getRandomValues !== 'function') return '';
    const values = new Uint32Array(4);
    win.crypto.getRandomValues(values);
    return Array.from(values, (value) => value.toString(16).padStart(8, '0')).join('');
  }

  function installSearchBridge(win, doc) {
    if (!win?.addEventListener || !doc?.addEventListener || win.parent === win) return;

    let activeTarget = null;
    let activeSession = null;

    const notify = (state) => {
      if (!activeSession) return;
      const payload = {
        type: FOCUS_TYPE,
        kind: 'search',
        state,
        session_id: activeSession,
      };
      for (const origin of DASHBOARD_ORIGINS) {
        win.parent.postMessage(payload, origin);
      }
    };

    const deactivate = () => {
      if (!activeTarget || !activeSession) return;
      notify('blurred');
      activeTarget = null;
      activeSession = null;
    };

    const activate = (target) => {
      if (!isEligibleSearchTarget(target)) return false;
      if (target === activeTarget && activeSession) return true;
      if (activeTarget) deactivate();
      activeTarget = target;
      activeSession = newSessionId(win);
      if (!SAFE_SESSION.test(activeSession)) {
        activeTarget = null;
        activeSession = null;
        return false;
      }
      notify('focused');
      return true;
    };

    doc.addEventListener('focusin', (event) => {
      if (isEligibleSearchTarget(event.target)) activate(event.target);
    }, true);

    doc.addEventListener('focusout', (event) => {
      if (event.target !== activeTarget) return;
      win.setTimeout(() => {
        if (doc.activeElement === activeTarget) return;
        if (isEligibleSearchTarget(doc.activeElement)) activate(doc.activeElement);
        else deactivate();
      }, 0);
    }, true);

    win.addEventListener('message', (event) => {
      if (event.source !== win.parent || !DASHBOARD_ORIGINS.has(event.origin)) return;
      const request = validateSearchEditRequest(event.data);
      if (!request || !activeTarget || request.session_id !== activeSession) return;
      if (doc.activeElement !== activeTarget || activeTarget.isConnected === false) return;
      applySearchEdit(activeTarget, request);
    });
  }

  const searchApi = {
    applySearchEdit,
    isEligibleSearchTarget,
    planSearchEdit,
    validateSearchEditRequest,
  };
  if (typeof module !== 'undefined' && module.exports) {
    Object.assign(module.exports, searchApi);
  }
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    installSearchBridge(window, document);
  }
})();
