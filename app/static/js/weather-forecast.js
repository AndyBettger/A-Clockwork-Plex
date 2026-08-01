(() => {
  if (document.body?.dataset.activePage !== 'weather') {
    return;
  }

  const anchor = document.querySelector('.weather-detail-page');
  if (!anchor || document.querySelector('[data-weather-forecast-console]')) {
    return;
  }

  const toneIcons = {
    clear: '☀',
    'mostly-clear': '◐',
    'partly-cloudy': '◒',
    cloudy: '☁',
    fog: '≋',
    drizzle: '⌁',
    rain: '☂',
    'heavy-rain': '☂',
    showers: '☔',
    'heavy-showers': '☔',
    'freezing-rain': '◆',
    snow: '❄',
    'heavy-snow': '❄',
    'snow-showers': '❄',
    thunderstorm: 'ϟ',
    'thunderstorm-hail': 'ϟ',
    unknown: '·',
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function parseLocalDate(value, dateOnly = false) {
    const text = String(value || '').trim();
    if (!text) {
      return null;
    }
    const normalised = dateOnly && /^\d{4}-\d{2}-\d{2}$/.test(text)
      ? `${text}T12:00:00`
      : text;
    const parsed = new Date(normalised);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function temperature(value, unit) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return '—';
    }
    const rounded = Math.abs(numeric) < 10 ? numeric.toFixed(1) : Math.round(numeric).toString();
    return `${rounded}${unit || '°C'}`;
  }

  function probability(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${Math.round(numeric)}% rain` : 'Rain —';
  }

  function condition(item) {
    return item?.condition && typeof item.condition === 'object'
      ? item.condition
      : { label: 'Unknown conditions', tone: 'unknown' };
  }

  function iconFor(item) {
    return toneIcons[condition(item).tone] || toneIcons.unknown;
  }

  function hourlyLabel(value) {
    const parsed = parseLocalDate(value);
    if (!parsed) {
      return String(value || 'Later');
    }
    return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function dayLabel(value, index) {
    if (index === 0) {
      return 'Today';
    }
    if (index === 1) {
      return 'Tomorrow';
    }
    const parsed = parseLocalDate(value, true);
    return parsed
      ? parsed.toLocaleDateString([], { weekday: 'short', day: 'numeric' })
      : String(value || 'Later');
  }

  function futureHourly(items) {
    const cutoff = Date.now() - (45 * 60 * 1000);
    const future = items.filter((item) => {
      const parsed = parseLocalDate(item?.valid_at);
      return parsed === null || parsed.getTime() >= cutoff;
    });
    return (future.length ? future : items).slice(0, 8);
  }

  function hourlyCard(item) {
    const card = element('article', 'weather-forecast-card');
    card.append(
      element('span', 'weather-forecast-time', hourlyLabel(item.valid_at)),
      element('span', 'weather-forecast-icon', iconFor(item)),
      element('strong', 'weather-forecast-temperature', temperature(item.temperature, currentUnits.temperature)),
      element('span', 'weather-forecast-condition', condition(item).label),
      element('span', 'weather-forecast-rain', probability(item.precipitation_probability)),
    );
    return card;
  }

  function dailyCard(item, index) {
    const card = element('article', `weather-forecast-card${index === 0 ? ' is-today' : ''}`);
    card.append(
      element('span', 'weather-forecast-time', dayLabel(item.date, index)),
      element('span', 'weather-forecast-icon', iconFor(item)),
      element(
        'strong',
        'weather-forecast-temperature',
        `${temperature(item.temperature_max, currentUnits.temperature)} / ${temperature(item.temperature_min, currentUnits.temperature)}`,
      ),
      element('span', 'weather-forecast-condition', condition(item).label),
      element('span', 'weather-forecast-rain', probability(item.precipitation_probability_max)),
    );
    return card;
  }

  function group(title, className, items, renderer) {
    const section = element('section', 'weather-forecast-group');
    const heading = element('h3', '', title);
    const strip = element('div', `weather-forecast-strip ${className}`.trim());
    items.forEach((item, index) => strip.appendChild(renderer(item, index)));
    section.append(heading, strip);
    return section;
  }

  let currentUnits = {};

  function render(payload) {
    if (payload?.enabled !== true || !payload.forecast) {
      return;
    }

    const forecast = payload.forecast;
    const hourly = Array.isArray(forecast.hourly) ? futureHourly(forecast.hourly) : [];
    const daily = Array.isArray(forecast.daily) ? forecast.daily.slice(0, 7) : [];
    if (!hourly.length && !daily.length) {
      return;
    }

    currentUnits = forecast.units && typeof forecast.units === 'object'
      ? forecast.units
      : {};

    const outer = element('section', 'weather-forecast-console');
    outer.dataset.weatherForecastConsole = '';
    outer.setAttribute('aria-label', 'Online weather forecast');

    const panel = element('div', 'weather-forecast-panel');
    const heading = element('header', 'weather-forecast-heading');
    const headingCopy = element('div');
    headingCopy.append(
      element('h2', '', 'Forecast outlook'),
      element(
        'p',
        '',
        'Online model guidance from Open-Meteo. The instrument panels below remain live Ecowitt observations from your own station.',
      ),
    );

    const stale = payload.stale === true || payload.status === 'stale';
    const status = element(
      'span',
      `weather-forecast-status${stale ? ' is-stale' : ''}`,
      stale ? 'Cached forecast' : 'Forecast ready',
    );
    heading.append(headingCopy, status);
    panel.appendChild(heading);

    if (hourly.length) {
      panel.appendChild(group('Next hours', '', hourly, hourlyCard));
    }
    if (daily.length) {
      panel.appendChild(group('Daily outlook', 'is-daily', daily, dailyCard));
    }

    const foot = element('footer', 'weather-forecast-foot');
    const attribution = element('p', 'weather-forecast-footnote');
    attribution.append('Weather data by ');
    const attributionLink = element('a', '', 'Open-Meteo.com');
    attributionLink.href = forecast.attribution?.url || 'https://open-meteo.com/';
    attributionLink.target = '_blank';
    attributionLink.rel = 'noopener noreferrer';
    attribution.append(attributionLink, ' · CC BY 4.0');
    foot.appendChild(attribution);

    if (stale) {
      foot.appendChild(
        element(
          'p',
          'weather-forecast-stale-note',
          payload.last_error
            ? `Using the last good forecast: ${payload.last_error}`
            : 'Using the last good cached forecast.',
        ),
      );
    } else if (forecast.fetched_at) {
      const fetchedAt = parseLocalDate(forecast.fetched_at);
      foot.appendChild(
        element(
          'p',
          'weather-forecast-footnote',
          fetchedAt ? `Updated ${fetchedAt.toLocaleString()}` : `Updated ${forecast.fetched_at}`,
        ),
      );
    }

    panel.appendChild(foot);
    outer.appendChild(panel);
    anchor.parentNode.insertBefore(outer, anchor);
  }

  fetch('/api/weather/forecast', { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Forecast returned HTTP ${response.status}`);
      }
      return response.json();
    })
    .then(render)
    .catch(() => {
      // The station console remains fully usable without the optional provider.
    });
})();
