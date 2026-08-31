(() => {
  'use strict';

  // Protocol strings keep the original Search name for backwards-safe deployment.
  // The payload kind is now the explicit allow-list for supported Plexamp text fields.
  const FOCUS_TYPE = 'acp-plexamp-search-focus-v1';
  const EDIT_TYPE = 'acp-plexamp-search-edit-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const SAFE_SESSION = /^[A-Za-z0-9-]{16,96}$/;
  const SEARCH_WORD = /\bsearch\b/i;
  const FIELD_KINDS = new Set([
    'search',
    'home-section-title',
    'playlist-name',
    'playlist-description',
    'home-screen-title',
    'player-name',
  ]);
  const ALLOWED_COMMANDS = new Set(['insert', 'backspace', 'clear', 'submit', 'done']);

  function attribute(target, name) {
    try {
      return String(target?.getAttribute?.(name) || '');
    } catch (_error) {
      return '';
    }
  }

  function normaliseText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function targetClues(target) {
    return normaliseText([
      attribute(target, 'aria-label'),
      attribute(target, 'placeholder'),
      attribute(target, 'name'),
      attribute(target, 'data-testid'),
      attribute(target, 'id'),
    ].join(' '));
  }

  function surroundingText(target) {
    const parts = [];
    let node = target?.parentElement || null;
    for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {
      const aria = attribute(node, 'aria-label');
      if (aria) parts.push(aria);
      let text = '';
      try {
        text = normaliseText(node.innerText || node.textContent || '');
      } catch (_error) {
        text = '';
      }
      if (text && text.length <= 2400) parts.push(text);
    }
    return normaliseText(parts.join(' ')).slice(0, 6000);
  }

  function isTextLikeTarget(target) {
    const tag = String(target?.tagName || '').toUpperCase();
    if (!['INPUT', 'TEXTAREA'].includes(tag)) return false;
    if (target.disabled === true || target.readOnly === true) return false;
    if (attribute(target, 'aria-hidden').toLowerCase() === 'true') return false;
    if (tag === 'TEXTAREA') return true;
    const type = String(target.type || attribute(target, 'type') || 'text').toLowerCase();
    return ['search', 'text'].includes(type);
  }

  function classifyTextTarget(target) {
    if (!isTextLikeTarget(target)) return null;

    const tag = String(target.tagName || '').toUpperCase();
    const type = tag === 'INPUT'
      ? String(target.type || attribute(target, 'type') || 'text').toLowerCase()
      : 'textarea';
    const role = attribute(target, 'role').toLowerCase();
    const clues = targetClues(target);
    const context = surroundingText(target);

    if (type === 'search' || role === 'searchbox' || SEARCH_WORD.test(clues)) return 'search';
    try {
      if (target.closest?.('[role="search"], [aria-label*="search" i]')) return 'search';
    } catch (_error) {
      // Continue through the explicit non-Search field allow-list.
    }

    if (/\bheader title\b/i.test(clues)) return 'home-section-title';
    if (/\bplaylist name\b/i.test(clues)) return 'playlist-name';
    if (/\bplaylist description\b/i.test(clues)) return 'playlist-description';
    if (/\bplayer name\b/i.test(clues)) return 'player-name';

    if (/\bcreate smart playlist\b/i.test(context)) {
      if (/\bdescription\b/i.test(clues) || tag === 'TEXTAREA') return 'playlist-description';
      if (/\bname\b/i.test(clues)) return 'playlist-name';
    }

    if (/\bplayer name\b/i.test(context)) return 'player-name';

    const homeEditorContext = (
      /\btitle\b/i.test(context)
      && /\bdisplay as\b/i.test(context)
      && (/\bsubtype\b/i.test(context) || /\bvisible\b/i.test(context))
    );
    if (homeEditorContext) return 'home-screen-title';

    return null;
  }

  function isEligibleTextTarget(target) {
    return FIELD_KINDS.has(classifyTextTarget(target));
  }

  function isEligibleSearchTarget(target) {
    return classifyTextTarget(target) === 'search';
  }

  function validInsertText(text) {
    if (typeof text !== 'string' || Array.from(text).length !== 1 || text.length > 4) return false;
    return !/[\u0000-\u001f\u007f]/.test(text);
  }

  function validateTextEditRequest(raw) {
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

  function planTextEdit(value, selectionStart, selectionEnd, command, text = '') {
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

  function setNativeEditableValue(target, value) {
    const view = target?.ownerDocument?.defaultView;
    const tag = String(target?.tagName || '').toUpperCase();
    const prototype = tag === 'TEXTAREA'
      ? view?.HTMLTextAreaElement?.prototype
      : view?.HTMLInputElement?.prototype;
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
      try { target.form?.requestSubmit?.(); } catch (_error) { /* compatibility only */ }
    }
    return true;
  }

  function applyTextEdit(target, request) {
    if (!isEligibleTextTarget(target) || target.isConnected === false) return false;
    if (request.command === 'done') {
      target.blur?.();
      return true;
    }
    // Legacy protocol compatibility only. ACP no longer renders a Search key;
    // Plexamp Search updates live while the user types.
    if (request.command === 'submit') return dispatchSubmit(target);

    const plan = planTextEdit(
      target.value,
      target.selectionStart,
      target.selectionEnd,
      request.command,
      request.text,
    );
    if (!plan) return false;
    if (plan.changed) {
      setNativeEditableValue(target, plan.value);
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

  function installTextBridge(win, doc) {
    if (!win?.addEventListener || !doc?.addEventListener || win.parent === win) return;

    let activeTarget = null;
    let activeSession = null;
    let activeKind = null;

    const notify = (state) => {
      if (!activeSession || !activeKind) return;
      const payload = {
        type: FOCUS_TYPE,
        kind: activeKind,
        state,
        session_id: activeSession,
      };
      for (const origin of DASHBOARD_ORIGINS) {
        win.parent.postMessage(payload, origin);
      }
    };

    const deactivate = () => {
      if (!activeTarget || !activeSession || !activeKind) return;
      notify('blurred');
      activeTarget = null;
      activeSession = null;
      activeKind = null;
    };

    const activate = (target) => {
      const kind = classifyTextTarget(target);
      if (!FIELD_KINDS.has(kind)) return false;
      if (target === activeTarget && activeSession && kind === activeKind) return true;
      if (activeTarget) deactivate();
      activeTarget = target;
      activeKind = kind;
      activeSession = newSessionId(win);
      if (!SAFE_SESSION.test(activeSession)) {
        activeTarget = null;
        activeSession = null;
        activeKind = null;
        return false;
      }
      notify('focused');
      return true;
    };

    doc.addEventListener('focusin', (event) => {
      if (isEligibleTextTarget(event.target)) activate(event.target);
    }, true);

    doc.addEventListener('focusout', (event) => {
      if (event.target !== activeTarget) return;
      win.setTimeout(() => {
        if (doc.activeElement === activeTarget) return;
        if (isEligibleTextTarget(doc.activeElement)) activate(doc.activeElement);
        else deactivate();
      }, 0);
    }, true);

    win.addEventListener('message', (event) => {
      if (event.source !== win.parent || !DASHBOARD_ORIGINS.has(event.origin)) return;
      const request = validateTextEditRequest(event.data);
      if (!request || !activeTarget || request.session_id !== activeSession) return;
      if (doc.activeElement !== activeTarget || activeTarget.isConnected === false) return;
      applyTextEdit(activeTarget, request);
    });
  }

  const textApi = {
    applyTextEdit,
    classifyTextTarget,
    isEligibleTextTarget,
    isEligibleSearchTarget,
    planTextEdit,
    validateTextEditRequest,
    // Backwards-compatible names retained for the first Search-slice contract.
    applySearchEdit: applyTextEdit,
    planSearchEdit: planTextEdit,
    validateSearchEditRequest: validateTextEditRequest,
  };
  if (typeof module !== 'undefined' && module.exports) {
    Object.assign(module.exports, textApi);
  }
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    installTextBridge(window, document);
  }
})();
