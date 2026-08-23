(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const latitude = document.querySelector('[data-setting-path="weather.forecast.latitude"]');
  const longitude = document.querySelector('[data-setting-path="weather.forecast.longitude"]');
  const timezone = document.querySelector('[data-setting-path="weather.forecast.timezone"]');
  const latitudeField = latitude?.closest('.setting-field');
  const longitudeField = longitude?.closest('.setting-field');
  const grid = latitudeField?.parentElement;
  if (!latitude || !longitude || !timezone || !latitudeField || !grid) return;
  if (grid.querySelector('[data-forecast-location-search]')) return;

  const latitudeLabel = latitudeField.querySelector('span');
  const longitudeLabel = longitudeField?.querySelector('span');
  if (latitudeLabel) latitudeLabel.textContent = 'Latitude (advanced)';
  if (longitudeLabel) longitudeLabel.textContent = 'Longitude (advanced)';

  const block = document.createElement('div');
  block.className = 'setting-field wide';
  block.dataset.forecastLocationSearch = 'true';

  const label = document.createElement('span');
  label.textContent = 'Find forecast location';

  const row = document.createElement('div');
  row.className = 'settings-action-row';

  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.inputMode = 'none';
  searchInput.autocomplete = 'off';
  searchInput.dataset.keyboard = 'text';
  searchInput.placeholder = 'Town, city or postcode';
  searchInput.setAttribute('aria-label', 'Town, city or postcode');
  searchInput.style.flex = '1 1 260px';
  searchInput.style.minWidth = '0';

  const searchButton = document.createElement('button');
  searchButton.type = 'button';
  searchButton.className = 'button settings-secondary';
  searchButton.textContent = 'Search';

  const message = document.createElement('small');
  message.className = 'muted small';
  message.dataset.forecastLocationMessage = 'true';
  message.textContent = 'Choose a match to fill the coordinates and timezone below. Save Changes still controls persistence.';

  const results = document.createElement('div');
  results.className = 'settings-subpage-overview';
  results.dataset.forecastLocationResults = 'true';
  results.hidden = true;

  row.append(searchInput, searchButton);
  block.append(label, row, message, results);
  grid.insertBefore(block, latitudeField);

  function locationLabel(item) {
    return [item.name, item.admin1, item.country].filter(Boolean).join(', ');
  }

  function locationDetails(item) {
    const postcode = Array.isArray(item.postcodes) ? item.postcodes[0] : '';
    const coordinates = `${Number(item.latitude).toFixed(4)}, ${Number(item.longitude).toFixed(4)}`;
    return [postcode, coordinates, item.timezone].filter(Boolean).join(' · ');
  }

  function stageLocation(item) {
    latitude.value = String(item.latitude);
    longitude.value = String(item.longitude);
    if (item.timezone) timezone.value = String(item.timezone);
    [latitude, longitude, timezone].forEach((control) => {
      control.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const chosen = locationLabel(item) || 'location';
    message.textContent = `${chosen} selected. Save Changes to apply this forecast location.`;
    results.hidden = true;
    results.replaceChildren();
  }

  function renderResults(items) {
    results.replaceChildren();
    if (!items.length) {
      results.hidden = true;
      message.textContent = 'No matching locations found. Try a nearby town, city or a fuller postcode.';
      return;
    }

    items.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'settings-subpage-row';

      const text = document.createElement('span');
      const title = document.createElement('strong');
      const detail = document.createElement('small');
      title.textContent = locationLabel(item) || 'Unnamed location';
      detail.textContent = locationDetails(item);
      text.append(title, detail);

      const chevron = document.createElement('span');
      chevron.setAttribute('aria-hidden', 'true');
      chevron.textContent = '›';

      button.append(text, chevron);
      button.addEventListener('click', () => stageLocation(item));
      results.appendChild(button);
    });

    results.hidden = false;
    message.textContent = `${items.length} match${items.length === 1 ? '' : 'es'} found. Choose one, then Save Changes.`;
  }

  async function search() {
    const query = searchInput.value.trim();
    if (query.length < 2) {
      results.hidden = true;
      results.replaceChildren();
      message.textContent = 'Enter at least 2 characters of a town, city or postcode.';
      return;
    }

    searchButton.disabled = true;
    searchButton.textContent = 'Searching…';
    message.textContent = 'Searching forecast locations…';
    try {
      const response = await fetch(`/api/weather/forecast/locations?q=${encodeURIComponent(query)}`, {
        cache: 'no-store',
        credentials: 'same-origin',
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok !== true) {
        throw new Error(payload.error || `Location search failed with HTTP ${response.status}.`);
      }
      renderResults(Array.isArray(payload.results) ? payload.results : []);
    } catch (error) {
      results.hidden = true;
      results.replaceChildren();
      message.textContent = error.message || 'Could not search forecast locations.';
    } finally {
      searchButton.disabled = false;
      searchButton.textContent = 'Search';
    }
  }

  searchButton.addEventListener('click', search);
  searchInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    search();
  });
})();
