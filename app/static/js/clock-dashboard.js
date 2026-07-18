(() => {
  const CLOCK_FORMAT_STORAGE_KEY = 'a-clockwork-plex.clock-format';
  const segmentDisplay = window.AClockworkSegments;

  const WEATHER_LABELS_BY_ID = {
    outdoor_temp: 'Outdoor temp',
    indoor_temp: 'Indoor temp',
    humidity: 'Humidity',
    indoor_humidity: 'Indoor humidity',
    wind_speed: 'Wind',
    wind_gust: 'Gust',
    max_daily_gust: 'Max gust today',
    daily_rain: 'Rain today',
    hourly_rain: 'Hourly rain',
    event_rain: 'Event rain',
    pressure: 'Pressure',
    barometer: 'Barometer',
    solar: 'Solar',
    uv: 'UV',
  };

  const COMPOSITE_CARD_DEFINITIONS = {
    temperature_summary: {
      members: ['outdoor_temp', 'indoor_temp'],
      label: 'Temperature',
      columns: [
        { heading: 'Outdoor temp', displayLabel: 'Outdoor temp' },
        { heading: 'Indoor', displayLabel: 'Indoor temp' },
      ],
    },
    humidity_summary: {
      members: ['humidity', 'indoor_humidity'],
      label: 'Humidity',
      columns: [
        { heading: 'Outdoor humidity', displayLabel: 'Humidity' },
        { heading: 'Indoor', displayLabel: 'Indoor humidity' },
      ],
    },
    wind_summary: {
      members: ['wind_speed', 'wind_gust'],
      label: 'Wind',
      columns: [
        { heading: 'Wind speed', displayLabel: 'Wind' },
        { heading: 'Gust', displayLabel: 'Gust' },
      ],
    },
    solar_uv_summary: {
      members: ['solar', 'uv'],
      label: 'Solar and UV',
      columns: [
        { heading: 'Solar', displayLabel: 'Solar' },
        { heading: 'UV', displayLabel: 'UV' },
      ],
    },
    rain_summary: {
      members: ['daily_rain', 'event_rain'],
      label: 'Rain',
      columns: [
        { heading: 'Rain today', displayLabel: 'Rain today' },
        { heading: 'Event rain', displayLabel: 'Event rain' },
      ],
    },
  };

  function normaliseClockFormat(value) {
    return String(value || '').toLowerCase() === '12h' ? '12h' : '24h';
  }

  function selectedClockFormat() {
    try {
      const saved = window.localStorage.getItem(CLOCK_FORMAT_STORAGE_KEY);
      if (saved === '12h' || saved === '24h') {
        return saved;
      }
    } catch (error) {
    }

    return normaliseClockFormat(document.getElementById('clock-time')?.dataset.clockFormat || '24h');
  }

  function updateClock() {
    if (!segmentDisplay) {
      return;
    }

    const now = new Date();
    const format = selectedClockFormat();
    const rawHours = now.getHours();
    const displayHours = format === '12h'
      ? String(((rawHours + 11) % 12) + 1).padStart(2, '0')
      : String(rawHours).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const suffix = rawHours >= 12 ? 'PM' : 'AM';
    const weekday = now.toLocaleDateString('en-GB', { weekday: 'long' });
    const day = String(now.getDate());
    const month = now.toLocaleDateString('en-GB', { month: 'long' });
    const year = String(now.getFullYear());
    const date = `${weekday} ${day} ${month} ${year}`.toUpperCase();

    segmentDisplay.setCharacters(document.getElementById('clock-hours'), displayHours);
    segmentDisplay.setCharacters(document.getElementById('clock-minutes'), minutes);
    segmentDisplay.setCharacters(document.getElementById('clock-seconds'), seconds);
    segmentDisplay.setCharacters(document.getElementById('clock-date'), date);
    document.getElementById('clock-time')?.setAttribute(
      'aria-label',
      `${displayHours}:${minutes}:${seconds}${format === '12h' ? ` ${suffix}` : ''}`,
    );
    document.getElementById('clock-date')?.setAttribute('aria-label', date);
  }

  function makeWeatherCard(cardData) {
    const card = document.createElement('div');
    card.className = 'weather-card';
    if (cardData.id) {
      card.dataset.cardId = cardData.id;
    }

    if (Array.isArray(cardData.columns)) {
      card.classList.add('is-composite');
      card.setAttribute('aria-label', cardData.label || 'Combined weather reading');

      const headingGrid = document.createElement('div');
      headingGrid.className = 'weather-composite-headings';
      cardData.columns.forEach((column) => {
        const heading = document.createElement('span');
        heading.className = 'weather-composite-heading';
        heading.textContent = column.heading;
        headingGrid.appendChild(heading);
      });

      const columnGrid = document.createElement('div');
      columnGrid.className = 'weather-subgrid';
      cardData.columns.forEach((column) => {
        const reading = document.createElement('div');
        reading.className = 'weather-subreading';

        const subValue = document.createElement('span');
        subValue.className = 'weather-subvalue';
        subValue.textContent = column.value || '—';

        reading.appendChild(subValue);
        columnGrid.appendChild(reading);
      });

      card.append(headingGrid, columnGrid);
      return card;
    }

    const labelElement = document.createElement('span');
    labelElement.className = 'weather-label';
    labelElement.textContent = cardData.label;

    const valueElement = document.createElement('span');
    valueElement.className = 'weather-value';
    valueElement.textContent = cardData.value;

    card.append(labelElement, valueElement);
    return card;
  }

  function detailReadingLookup(status) {
    const lookup = {};
    const detail = status?.weather_detail || {};
    const rows = Array.isArray(detail.condition_rows) ? detail.condition_rows : [];

    rows.forEach((row) => {
      const location = String(row?.location || '').toLowerCase();
      if (location === 'outdoor') {
        lookup['Outdoor temp'] = row?.temperature?.current;
        lookup.Humidity = row?.humidity?.current;
      } else if (location === 'indoor') {
        lookup['Indoor temp'] = row?.temperature?.current;
        lookup['Indoor humidity'] = row?.humidity?.current;
      }
    });

    const atmosphere = Array.isArray(detail.atmosphere) ? detail.atmosphere : [];
    atmosphere.forEach((item) => {
      if (item?.label && item?.value) {
        lookup[item.label] = item.value;
      }
    });

    const compass = detail.compass || {};
    if (compass.speed?.value) {
      lookup.Wind = compass.speed.value;
    }
    if (compass.gust?.value) {
      lookup.Gust = compass.gust.value;
    }

    return lookup;
  }

  function virtualCardId(fieldId) {
    const match = Object.entries(COMPOSITE_CARD_DEFINITIONS)
      .find(([, definition]) => definition.members.includes(fieldId));
    return match?.[0] || fieldId;
  }

  function weatherCardsFromStatus(status) {
    const display = { ...detailReadingLookup(status), ...(status?.weather_display || {}) };
    const configuredOrder = Array.isArray(status?.config?.weather?.clock_cards)
      ? status.config.weather.clock_cards
      : [];
    const virtualOrder = [];

    configuredOrder.forEach((fieldId) => {
      const virtualId = virtualCardId(fieldId);
      if (!virtualOrder.includes(virtualId)) {
        virtualOrder.push(virtualId);
      }
    });

    const cards = [];
    const usedLabels = new Set();

    virtualOrder.forEach((fieldId) => {
      const composite = COMPOSITE_CARD_DEFINITIONS[fieldId];
      if (composite) {
        const columns = composite.columns
          .map((column) => ({ ...column, value: display[column.displayLabel] }))
          .filter((column) => column.value);
        if (columns.length) {
          cards.push({ id: fieldId, label: composite.label, columns });
          composite.columns.forEach((column) => usedLabels.add(column.displayLabel));
        }
        return;
      }

      const label = WEATHER_LABELS_BY_ID[fieldId];
      if (!label || !(label in display)) {
        return;
      }
      const value = fieldId === 'barometer'
        ? String(display[label]).split('·')[0].trim()
        : display[label];
      cards.push({ id: fieldId, label, value });
      usedLabels.add(label);
    });

    Object.entries(status?.weather_display || {}).forEach(([label, value]) => {
      if (!usedLabels.has(label)) {
        cards.push({ label, value: label === 'Barometer' ? String(value).split('·')[0].trim() : value });
      }
    });

    return cards;
  }

  function renderWeatherCards(cards) {
    const content = document.getElementById('clock-weather-content');
    if (!content) {
      return;
    }

    if (!cards.length) {
      const waiting = document.createElement('div');
      waiting.id = 'clock-weather-waiting';
      waiting.innerHTML = '<p class="muted">Waiting for weather station data.</p><p class="muted small">Point Ecowitt/custom uploads at <code>/api/weather/ecowitt</code>.</p>';
      content.replaceChildren(waiting);
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'weather-grid';
    grid.id = 'clock-weather-grid';
    grid.replaceChildren(...cards.map(makeWeatherCard));
    content.replaceChildren(grid);
    window.AClockworkSegmentReadouts?.refresh?.();
  }

  async function updateClockWeather() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }

      const status = await response.json();
      const title = status?.config?.weather?.station_name;
      if (title) {
        document.getElementById('clock-weather-title').textContent = title;
      }

      renderWeatherCards(
        weatherCardsFromStatus(status).filter((card) => card.label && (card.value || card.columns?.length)),
      );
    } catch (error) {
      // Leave the last good readings on screen if a transient update fails.
    }
  }

  function startClockWeatherUpdates() {
    const panel = document.getElementById('clock-weather-panel');
    const refreshSeconds = Number(panel?.dataset.refreshSeconds || 60);
    const refreshMilliseconds = Math.max(15, Number.isFinite(refreshSeconds) ? refreshSeconds : 60) * 1000;

    updateClockWeather();
    window.setInterval(updateClockWeather, refreshMilliseconds);
  }

  window.addEventListener('storage', (event) => {
    if (event.key === CLOCK_FORMAT_STORAGE_KEY) {
      updateClock();
    }
  });

  window.setInterval(updateClock, 1000);
  updateClock();
  startClockWeatherUpdates();
})();
