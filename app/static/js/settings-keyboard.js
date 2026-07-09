(() => {
  const keyboard = document.getElementById('touch-keyboard');
  const keyGrid = document.getElementById('touch-keyboard-keys');
  const quickRow = document.getElementById('touch-keyboard-quick');
  const label = document.getElementById('touch-keyboard-label');

  if (!keyboard || !keyGrid || !quickRow || !label) {
    return;
  }

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
  let layoutName = 'text';
  let shifted = false;
  let usingNumbers = false;

  function specialLabel(key) {
    return {
      backspace: '⌫',
      clear: 'Clear',
      space: 'Space',
      shift: shifted ? 'ABC' : 'Shift',
      numbers: '123',
      letters: 'ABC',
    }[key] || key;
  }

  function buttonForKey(key) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `touch-key ${key.length > 1 ? 'is-command' : ''}`;
    button.dataset.key = key;
    button.textContent = specialLabel(key);
    button.addEventListener('pointerdown', (event) => event.preventDefault());
    button.addEventListener('click', () => pressKey(key));
    return button;
  }

  function renderKeyboard() {
    const layout = layouts[layoutName] || layouts.text;
    label.textContent = layout.label;
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

    const rows = usingNumbers && layoutName === 'text' ? numberRows : layout.rows;
    rows.forEach((row) => {
      const rowElement = document.createElement('div');
      rowElement.className = 'touch-key-row';
      row.forEach((key) => rowElement.appendChild(buttonForKey(key)));
      keyGrid.appendChild(rowElement);
    });
  }

  function openKeyboard(input) {
    target = input;
    layoutName = input.dataset.keyboard || 'text';
    shifted = false;
    usingNumbers = false;
    document.body.classList.add('keyboard-open');
    keyboard.setAttribute('aria-hidden', 'false');
    renderKeyboard();
    window.setTimeout(() => input.focus({ preventScroll: true }), 0);
  }

  function closeKeyboard() {
    document.body.classList.remove('keyboard-open');
    keyboard.setAttribute('aria-hidden', 'true');
    target = null;
  }

  function insertText(text) {
    if (!target) {
      return;
    }

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

  function backspace() {
    if (!target) {
      return;
    }

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

  function pressKey(key) {
    if (!target && key !== 'done') {
      return;
    }

    if (key === 'backspace') {
      backspace();
      return;
    }

    if (key === 'clear') {
      target.value = '';
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.focus({ preventScroll: true });
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
      usingNumbers = true;
      renderKeyboard();
      return;
    }

    if (key === 'letters') {
      usingNumbers = false;
      renderKeyboard();
      return;
    }

    insertText(shifted && key.length === 1 ? key.toUpperCase() : key);
  }

  document.querySelectorAll('input[data-keyboard]').forEach((input) => {
    input.addEventListener('focus', () => openKeyboard(input));
    input.addEventListener('pointerdown', () => openKeyboard(input));
  });

  keyboard.addEventListener('pointerdown', (event) => event.preventDefault());

  keyboard.addEventListener('click', (event) => {
    const command = event.target.closest('[data-action]');
    if (command?.dataset.action === 'done') {
      closeKeyboard();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('keyboard-open')) {
      closeKeyboard();
    }
  });
})();
