(() => {
  const root = document.querySelector('[data-clock-card-settings]');
  if (!root) {
    return;
  }

  const optionsElement = document.getElementById('clock-card-options-data');
  const selectedElement = document.getElementById('clock-card-selected-data');
  const orderElement = document.getElementById('clock-card-order');
  const hiddenInputsElement = document.getElementById('clock-card-hidden-inputs');
  const toggleButtons = [...root.querySelectorAll('.clock-card-toggle')];

  if (!optionsElement || !selectedElement || !orderElement || !hiddenInputsElement) {
    return;
  }

  const options = JSON.parse(optionsElement.textContent || '[]');
  const allowedIds = new Set(options.map((option) => option.id));
  const labels = Object.fromEntries(options.map((option) => [option.id, option.label]));
  let selected = [...new Set(JSON.parse(selectedElement.textContent || '[]'))].filter((id) => allowedIds.has(id));

  function render() {
    orderElement.replaceChildren();
    hiddenInputsElement.replaceChildren();

    if (!selected.length) {
      const empty = document.createElement('p');
      empty.className = 'muted small clock-card-empty';
      empty.textContent = 'No cards selected yet. Tap cards below to add them.';
      orderElement.appendChild(empty);
    }

    selected.forEach((id, index) => {
      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'clock_cards';
      hidden.value = id;
      hiddenInputsElement.appendChild(hidden);

      const row = document.createElement('div');
      row.className = 'clock-card-row';
      row.dataset.cardId = id;

      const position = document.createElement('span');
      position.className = 'clock-card-position';
      position.textContent = String(index + 1);

      const label = document.createElement('span');
      label.className = 'clock-card-label';
      label.textContent = labels[id] || id;

      const up = document.createElement('button');
      up.type = 'button';
      up.className = 'clock-card-order-button';
      up.textContent = '↑';
      up.disabled = index === 0;
      up.setAttribute('aria-label', `Move ${label.textContent} up`);
      up.addEventListener('click', () => moveCard(index, -1));

      const down = document.createElement('button');
      down.type = 'button';
      down.className = 'clock-card-order-button';
      down.textContent = '↓';
      down.disabled = index === selected.length - 1;
      down.setAttribute('aria-label', `Move ${label.textContent} down`);
      down.addEventListener('click', () => moveCard(index, 1));

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'clock-card-remove-button';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove ${label.textContent}`);
      remove.addEventListener('click', () => {
        selected = selected.filter((cardId) => cardId !== id);
        render();
      });

      row.append(position, label, up, down, remove);
      orderElement.appendChild(row);
    });

    toggleButtons.forEach((button) => {
      const id = button.dataset.cardId;
      const isActive = selected.includes(id);
      button.classList.toggle('is-selected', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
  }

  function moveCard(index, direction) {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= selected.length) {
      return;
    }
    const next = [...selected];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    selected = next;
    render();
  }

  toggleButtons.forEach((button) => {
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => {
      const id = button.dataset.cardId;
      if (!allowedIds.has(id)) {
        return;
      }
      if (selected.includes(id)) {
        selected = selected.filter((cardId) => cardId !== id);
      } else {
        selected = [...selected, id];
      }
      render();
    });
  });

  render();
})();
