(() => {
  if (window.__aClockworkPlexWeatherSurfaceLoaded) return;
  window.__aClockworkPlexWeatherSurfaceLoaded = true;

  const PRESENTATION_REFRESH_MS = 60_000;
  let refreshTimer = null;
  let refreshInFlight = false;
  let settingsRefreshPending = false;

  function weatherIsVisible() {
    const active = String(document.body?.dataset?.activePage || '').toLowerCase() === 'weather';
    const plexampOpen = window.ACPPlexamp?.isVisiblyOpen?.() === true;
    return active && !document.hidden && !plexampOpen;
  }

  function directionName(degrees) {
    const names = [
      'North',
      'North-northeast',
      'Northeast',
      'East-northeast',
      'East',
      'East-southeast',
      'Southeast',
      'South-southeast',
      'South',
      'South-southwest',
      'Southwest',
      'West-southwest',
      'West',
      'West-northwest',
      'Northwest',
      'North-northwest',
    ];
    return names[Math.round(degrees / 22.5) % 16] || 'North';
  }

  function renderWindDirection() {
    const element = document.querySelector(
      '[data-acp-surface="weather"] #wind-direction-word, body.mode-weather #wind-direction-word',
    );
    const segments = window.AClockworkSegments;
    if (!element || !segments) return;

    const raw = Number(element.dataset.windDegrees);
    const degrees = Number.isFinite(raw) ? ((raw % 360) + 360) % 360 : 0;
    const name = directionName(degrees);
    element.classList.toggle('is-long', name.length > 10);
    element.setAttribute('aria-label', `${Math.round(degrees)} degrees, ${name}`);
    segments.setCharacters(element, name);
  }

  function capturePosition() {
    return {
      vertical: document.querySelector('.weather-detail-page')?.scrollTop || 0,
      rain: document.querySelector('.rain-overview-scroll')?.scrollLeft || 0,
    };
  }

  function restorePosition(position) {
    window.requestAnimationFrame(() => {
      const page = document.querySelector('.weather-detail-page');
      const rain = document.querySelector('.rain-overview-scroll');
      if (page) page.scrollTop = position.vertical;
      if (rain) rain.scrollLeft = position.rain;
      rain?.dispatchEvent(new Event('scroll'));
    });
  }

  async function fetchWeatherDocument() {
    const response = await fetch('/api/surfaces/weather', {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) throw new Error(`Weather surface returned HTTP ${response.status}`);
    const payload = await response.json();
    if (payload?.ok !== true || !payload.html) {
      throw new Error('Weather surface response was incomplete.');
    }
    return new DOMParser().parseFromString(String(payload.html), 'text/html');
  }

  function updateFromDocument(parsed) {
    const currentPage = document.querySelector('.weather-detail-page');
    const nextPage = parsed.querySelector('.weather-detail-page');
    if (!currentPage || !nextPage) return false;

    const position = capturePosition();
    const currentGrid = currentPage.querySelector('.weather-detail-grid');
    const nextGrid = nextPage.querySelector('.weather-detail-grid');

    const nextTitle = parsed.querySelector('.weather-detail-title-main');
    const currentTitle = document.querySelector('.weather-detail-title-main');
    if (nextTitle && currentTitle) currentTitle.textContent = nextTitle.textContent;

    if (currentGrid && nextGrid) {
      currentGrid.replaceWith(document.importNode(nextGrid, true));
    } else {
      const forecast = currentPage.querySelector('[data-weather-forecast-console]');
      currentPage.replaceChildren(
        ...[...nextPage.childNodes].map((node) => document.importNode(node, true)),
      );
      if (forecast) currentPage.insertBefore(forecast, currentPage.firstChild);
    }

    renderWindDirection();
    document.dispatchEvent(new CustomEvent('acp:weather-grid-refreshed'));
    restorePosition(position);
    return true;
  }

  async function refresh() {
    if (refreshInFlight || !weatherIsVisible()) return false;
    refreshInFlight = true;
    try {
      const parsed = await fetchWeatherDocument();
      const updated = updateFromDocument(parsed);
      if (updated) settingsRefreshPending = false;
      return updated;
    } catch (error) {
      return false;
    } finally {
      refreshInFlight = false;
    }
  }

  function schedule() {
    window.clearTimeout(refreshTimer);
    if (!weatherIsVisible()) return;
    refreshTimer = window.setTimeout(async () => {
      if (weatherIsVisible()) await refresh();
      schedule();
    }, PRESENTATION_REFRESH_MS);
  }

  function activate() {
    renderWindDirection();
    void refresh();
    schedule();
  }

  document.addEventListener('acp:surface-activated', (event) => {
    if (String(event?.detail?.surface || '').toLowerCase() === 'weather') activate();
    else schedule();
  });

  document.addEventListener('acp:settings-saved', (event) => {
    const sections = Array.isArray(event?.detail?.sections) ? event.detail.sections : [];
    if (!sections.includes('weather')) return;
    settingsRefreshPending = true;
    if (weatherIsVisible()) {
      void refresh().finally(schedule);
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (weatherIsVisible()) activate();
    else schedule();
  });

  window.addEventListener('pagehide', () => window.clearTimeout(refreshTimer), { once: true });

  window.ACPWeatherSurface = {
    refresh,
    renderWindDirection,
    isRefreshing: () => refreshInFlight,
    settingsRefreshPending: () => settingsRefreshPending,
  };

  if (String(document.body?.dataset?.activePage || '').toLowerCase() === 'weather') {
    renderWindDirection();
    schedule();
  }
})();
