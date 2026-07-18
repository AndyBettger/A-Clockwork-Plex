(() => {
  const root = document.querySelector('[data-clock-card-settings]');
  if (!root) {
    return;
  }

  const optionsElement = document.getElementById('clock-card-options-data');
  const selectedElement = document.getElementById('clock-card-selected-data');
  const orderElement = document.getElementById('clock-card-order');
  const hiddenInputsElement = document.getElementById('clock-card-hidden-inputs');
  const palette = root.querySelector('.clock-card-palette');

  if (!optionsElement || !selectedElement || !orderElement || !hiddenInputsElement || !palette) {
    return;
  }

  const VIRTUAL_CARDS = {
    temperature_summary: {
      label: 'Temperature',
      members: ['outdoor_temp', 'indoor_temp'],
    },
    humidity_summary: {
      label: 'Humidity',
      members: ['humidity', 'indoor_humidity'],
    },
    wind_summary: {
      label: 'Wind speed and gust',
      members: ['wind_speed', 'wind_gust'],
    },
    solar_uv_summary: {
      label: 'Solar and UV',
      members: ['solar', 'uv'],
    },
    rain_summary: {
      label: 'Rain today and event rain',
      members: ['daily_rain', 'event_rain'],
    },
  };

  const rawOptions = JSON.parse(optionsElement.textContent || '[]');
  const rawSelected = [...new Set(JSON.parse(selectedElement.textContent || '[]'))];
  const memberToVirtual = {};

  Object.entries(VIRTUAL_CARDS).forEach(([virtualId, definition]) => {
    definition.members.forEach((member) => {
      memberToVirtual[member] = virtualId;
    });
  });

  function collapseIds(ids) {
    const collapsed = [];
    ids.forEach((id) => {
      const displayId = memberToVirtual[id] || id;
      if (!collapsed.includes(displayId)) {
        collapsed.push(displayId);
      }
    });
    return collapsed;
  }

  const options = [];
  rawOptions.forEach((option) => {
    const virtualId = memberToVirtual[option.id];
    if (virtualId) {
      if (!options.some((item) => item.id === virtualId)) {
        options.push({ id: virtualId, label: VIRTUAL_CARDS[virtualId].label });
      }
      return;
    }
    options.push(option);
  });

  const allowedIds = new Set(options.map((option) => option.id));
  const labels = Object.fromEntries(options.map((option) => [option.id, option.label]));
  let selected = collapseIds(rawSelected).filter((id) => allowedIds.has(id));

  function createPaletteButton(option) {
    const button = document.createElement('button');
    button.className = 'settings-pill clock-card-toggle';
    button.type = 'button';
    button.dataset.cardId = option.id;
    button.dataset.cardLabel = option.label;

    const label = document.createElement('span');
    label.textContent = option.label;
    button.appendChild(label);

    button.addEventListener('click', () => {
      if (selected.includes(option.id)) {
        selected = selected.filter((cardId) => cardId !== option.id);
      } else {
        selected = [...selected, option.id];
      }
      render();
    });

    return button;
  }

  palette.replaceChildren(...options.map(createPaletteButton));

  function appendHiddenInputs(id) {
    const ids = VIRTUAL_CARDS[id]?.members || [id];
    ids.forEach((storedId) => {
      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'clock_cards';
      hidden.value = storedId;
      hiddenInputsElement.appendChild(hidden);
    });
  }

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
      appendHiddenInputs(id);

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

    [...palette.querySelectorAll('.clock-card-toggle')].forEach((button) => {
      const isActive = selected.includes(button.dataset.cardId);
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

  render();
})();
