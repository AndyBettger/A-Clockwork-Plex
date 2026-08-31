(() => {
  'use strict';

  if (window.__aClockworkPlexTouchKeyboardLoaded) return;
  window.__aClockworkPlexTouchKeyboardLoaded = true;

  // Protocol strings retain the original Search name so old/new extension and
  // dashboard assets degrade safely during a rolling kiosk update.
  const PLEXAMP_TEXT_FOCUS_TYPE = 'acp-plexamp-search-focus-v1';
  const PLEXAMP_TEXT_EDIT_TYPE = 'acp-plexamp-search-edit-v1';
  const PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_REMOTE_SESSION = /^[A-Za-z0-9-]{16,96}$/;
  const PLEXAMP_TEXT_KINDS = new Set([
    'search',
    'home-section-title',
    'playlist-name',
    'playlist-description',
    'home-screen-title',
    'player-name',
  ]);
  const REMOTE_COMMANDS = new Set(['insert', 'backspace', 'clear', 'submit', 'done']);

  function ensureKeyboardMarkup() {
    let keyboard = document.getElementById('touch-keyboard');
    if (!keyboard) {
      keyboard = document.createElement('div');
      keyboard.className = 'touch-keyboard';
      keyboard.id = 'touch-keyboard';
      keyboard.setAttribute('aria-hidden', 'true');
      keyboard.innerHTML = '<div class="touch-keyboard-header"><span id="touch-keyboard-label">Keyboard</span><button type="button" class="touch-keyboard-command" data-action="done">Done</button></div><div class="touch-keyboard-quick" id="touch-keyboard-quick"></div><div class="touch-keyboard-keys" id="touch-keyboard-keys"></div>';
      document.body.append(keyboard);
    }
    return keyboard;
  }

  const keyboard = ensureKeyboardMarkup();
  const keyGrid = document.getElementById('touch-keyboard-keys');
  const quickRow = document.getElementById('touch-keyboard-quick');
  const label = document.getElementById('touch-keyboard-label');

  if (!keyboard || !keyGrid || !quickRow || !label) return;

  const layouts = {
    text: {
      label: 'Text keyboard',
      quick: [],
      rows: [
        ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
        ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
        ['shift', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'backspace'],
        ['numbers', 'space', 'clear'],
      ],
    },
    url: {
      label: 'URL keyboard',
      quick: ['http://', 'localhost', ':32500', '/player', '.service'],
      rows: [
        ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
        ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
        ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
        ['z', 'x', 'c', 'v', 'b', 'n', 'm', '.', '-'],
        [':', '/', '_', 'space', 'backspace', 'clear'],
      ],
    },
    number: {
      label: 'Number keyboard',
      quick: [],
      rows: [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['0', 'backspace', 'clear'],
      ],
    },
    decimal: {
      label: 'Decimal keyboard',
      quick: [],
      rows: [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['-', '0', '.'],
        ['backspace', 'clear'],
      ],
    },
    time: {
      label: 'Time keyboard',
      quick: ['07:00', '11:00', '20:00', '02:00'],
      rows: [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['0', ':', 'backspace', 'clear'],
      ],
    },
  };

  const numberRows = [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['!', '@', '#', '&', '(', ')', '-', '_', '/', ':'],
    ['.', ',', "'", '"', '?', '+', '=', 'backspace'],
    ['letters', 'space', 'clear'],
  ];

  let target = null;
  let remoteSession = null;
  let remoteKind = null;
  let layoutName = 'text';
  let shifted = false;
  let usingNumbers = false;

  function isRemotePlexamp() {
    return remoteSession !== null;
  }

  function isRemoteSearch() {
    return isRemotePlexamp() && remoteKind === 'search';
  }

  function hasTarget() {
    return Boolean(target || remoteSession);
  }

  function keyLabel(key) {
    const command = {
      backspace: '⌫',
      clear: 'Clear',
      space: 'Space',
      shift: 'Shift',
      numbers: '123',
      letters: 'ABC',
      submit: 'Search',
    }[key];
    if (command) return command;
    if (shifted && /^[a-z]$/.test(key)) return key.toUpperCase();
    return key;
  }

  function buttonForKey(key) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `touch-key ${key.length > 1 ? 'is-command' : ''}`;
    button.dataset.key = key;
    button.textContent = keyLabel(key);
    if (key === 'shift') {
      button.setAttribute('aria-pressed', shifted ? 'true' : 'false');
      button.classList.toggle('is-active', shifted);
    }
    button.addEventListener('pointerdown', (event) => event.preventDefault());
    button.addEventListener('click', () => pressKey(key));
    return button;
  }

  function rowsForCurrentTarget() {
    const layout = layouts[layoutName] || layouts.text;
    const sourceRows = usingNumbers && layoutName === 'text' ? numberRows : layout.rows;
    return sourceRows.map((row) => Array.from(row));
  }

  function renderKeyboard() {
    const layout = layouts[layoutName] || layouts.text;
    label.textContent = '';
    label.hidden = true;
    keyGrid.replaceChildren();
    quickRow.replaceChildren();
    quickRow.hidden = !layout.quick.length;

    layout.quick.forEach((text) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'touch-key touch-quick-key';
      button.textContent = text;
      button.addEventListener('pointerdown', (event) => event.preventDefault());
      button.addEventListener('click', () => insertText(text));
      quickRow.appendChild(button);
    });

    rowsForCurrentTarget().forEach((row) => {
      const rowElement = document.createElement('div');
      rowElement.className = 'touch-key-row';
      row.forEach((key) => rowElement.appendChild(buttonForKey(key)));
      keyGrid.appendChild(rowElement);
    });
  }

  function markOpen(scope, kind = null) {
    const plexampText = scope === 'plexamp-text';
    document.body.classList.add('keyboard-open');
    document.body.classList.toggle('plexamp-text-keyboard-open', plexampText);
    // Keep the old class for Search so an older cached stylesheet still gives
    // the already accepted Search keyboard its elevated stacking context.
    document.body.classList.toggle('plexamp-search-keyboard-open', plexampText && kind === 'search');
    keyboard.dataset.scope = scope;
    if (kind) keyboard.dataset.plexampKind = kind;
    else delete keyboard.dataset.plexampKind;
    keyboard.setAttribute('aria-hidden', 'false');
    renderKeyboard();
  }

  function openKeyboard(input) {
    target = input;
    remoteSession = null;
    remoteKind = null;
    layoutName = input.dataset.keyboard || 'text';
    shifted = false;
    usingNumbers = false;
    markOpen('local');
    window.setTimeout(() => input.focus({ preventScroll: true }), 0);
  }

  function plexampFrame() {
    return document.getElementById('persistent-plexamp-frame');
  }

  function plexampTargetOrigin() {
    const frame = plexampFrame();
    if (!frame?.contentWindow) return null;
    try {
      const origin = new URL(frame.src, window.location.href).origin;
      return PLEXAMP_ORIGINS.has(origin) ? origin : null;
    } catch (_error) {
      return null;
    }
  }

  function plexampIsVisible() {
    const shell = document.getElementById('persistent-plexamp');
    return Boolean(
      shell
      && shell.getAttribute('aria-hidden') !== 'true'
      && (shell.classList.contains('is-open') || document.body.classList.contains('plexamp-overlay-open'))
    );
  }

  function postRemote(command, text = undefined, session = remoteSession) {
    if (!session || !SAFE_REMOTE_SESSION.test(session) || !REMOTE_COMMANDS.has(command)) return false;
    if (command === 'insert') {
      if (typeof text !== 'string' || Array.from(text).length !== 1 || /[\u0000-\u001f\u007f]/.test(text)) return false;
    } else if (text !== undefined) {
      return false;
    }
    const frame = plexampFrame();
    const origin = plexampTargetOrigin();
    if (!frame?.contentWindow || !origin) return false;
    const payload = {
      type: PLEXAMP_TEXT_EDIT_TYPE,
      session_id: session,
      command,
    };
    if (text !== undefined) payload.text = text;
    frame.contentWindow.postMessage(payload, origin);
    return true;
  }

  function openRemoteText(sessionId, kind) {
    if (!SAFE_REMOTE_SESSION.test(sessionId) || !PLEXAMP_TEXT_KINDS.has(kind) || !plexampIsVisible()) return;
    target = null;
    remoteSession = sessionId;
    remoteKind = kind;
    layoutName = 'text';
    shifted = false;
    usingNumbers = false;
    markOpen('plexamp-text', kind);
  }

  function closeKeyboard(options = {}) {
    const session = remoteSession;
    if (session && options.notifyRemote === true) {
      postRemote('done', undefined, session);
    }
    document.body.classList.remove(
      'keyboard-open',
      'plexamp-text-keyboard-open',
      'plexamp-search-keyboard-open',
    );
    keyboard.setAttribute('aria-hidden', 'true');
    delete keyboard.dataset.scope;
    delete keyboard.dataset.plexampKind;
    target = null;
    remoteSession = null;
    remoteKind = null;
    shifted = false;
    usingNumbers = false;
  }

  function insertLocalText(text) {
    if (!target) return;
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? target.value.length;
    const before = target.value.slice(0, start);
    const after = target.value.slice(end);
    target.value = `${before}${text}${after}`;
    const cursor = start + text.length;
    target.setSelectionRange(cursor, cursor);
    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.focus({ preventScroll: true });
  }

  function insertText(text) {
    if (isRemotePlexamp()) {
      for (const character of Array.from(String(text))) {
        postRemote('insert', character);
      }
      return;
    }
    insertLocalText(text);
  }

  function backspace() {
    if (isRemotePlexamp()) {
      postRemote('backspace');
      return;
    }
    if (!target) return;

    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? target.value.length;

    if (start !== end) {
      target.value = `${target.value.slice(0, start)}${target.value.slice(end)}`;
      target.setSelectionRange(start, start);
    } else if (start > 0) {
      target.value = `${target.value.slice(0, start - 1)}${target.value.slice(start)}`;
      target.setSelectionRange(start - 1, start - 1);
    }

    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.focus({ preventScroll: true });
  }

  function clearTarget() {
    if (isRemotePlexamp()) {
      postRemote('clear');
      return;
    }
    if (!target) return;
    target.value = '';
    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.focus({ preventScroll: true });
  }

  function pressKey(key) {
    if (!hasTarget() && key !== 'done') return;

    if (key === 'backspace') {
      backspace();
      return;
    }

    if (key === 'clear') {
      clearTarget();
      return;
    }

    if (key === 'space') {
      insertText(' ');
      return;
    }

    if (key === 'shift') {
      shifted = !shifted;
      renderKeyboard();
      return;
    }

    if (key === 'numbers') {
      shifted = false;
      usingNumbers = true;
      renderKeyboard();
      return;
    }

    if (key === 'letters') {
      shifted = false;
      usingNumbers = false;
      renderKeyboard();
      return;
    }

    // Kept only for rolling compatibility with the first Search bridge. The
    // shared keyboard no longer renders this key because Search is live.
    if (key === 'submit') {
      if (isRemoteSearch()) postRemote('submit');
      return;
    }

    const letterKey = /^[a-z]$/.test(key);
    insertText(shifted && letterKey ? key.toUpperCase() : key);
    if (shifted && letterKey) {
      shifted = false;
      renderKeyboard();
    }
  }

  document.addEventListener('focusin', (event) => {
    const input = event.target.closest?.('input[data-keyboard]');
    if (input && input !== target) openKeyboard(input);
  });

  document.addEventListener('pointerdown', (event) => {
    const input = event.target.closest?.('input[data-keyboard]');
    if (input) openKeyboard(input);
  });

  keyboard.addEventListener('pointerdown', (event) => event.preventDefault());
  keyboard.addEventListener('click', (event) => {
    const command = event.target.closest('[data-action]');
    if (command?.dataset.action === 'done') {
      closeKeyboard({ notifyRemote: isRemoteSearch() || isRemotePlexamp() });
    }
  });

  window.addEventListener('message', (event) => {
    const frame = plexampFrame();
    const origin = plexampTargetOrigin();
    if (!frame?.contentWindow || !origin) return;
    if (event.source !== frame.contentWindow || event.origin !== origin) return;
    const payload = event.data;
    if (!payload || payload.type !== PLEXAMP_TEXT_FOCUS_TYPE) return;
    if (
      !PLEXAMP_TEXT_KINDS.has(payload.kind)
      || typeof payload.session_id !== 'string'
      || !SAFE_REMOTE_SESSION.test(payload.session_id)
      || !['focused', 'blurred'].includes(payload.state)
    ) return;

    if (payload.state === 'focused') {
      openRemoteText(payload.session_id, payload.kind);
    } else if (payload.state === 'blurred' && payload.session_id === remoteSession) {
      closeKeyboard({ notifyRemote: false });
    }
  });

  const shell = document.getElementById('persistent-plexamp');
  if (shell && typeof MutationObserver !== 'undefined') {
    new MutationObserver(() => {
      if (remoteSession && !plexampIsVisible()) closeKeyboard({ notifyRemote: false });
    }).observe(shell, { attributes: true, attributeFilter: ['class', 'aria-hidden'] });
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('keyboard-open')) {
      closeKeyboard({ notifyRemote: isRemoteSearch() || isRemotePlexamp() });
    }
  });

  window.ACPTouchKeyboard = {
    close: () => closeKeyboard({ notifyRemote: isRemoteSearch() || isRemotePlexamp() }),
    isOpen: () => document.body.classList.contains('keyboard-open'),
    openLocal: openKeyboard,
  };
})();
