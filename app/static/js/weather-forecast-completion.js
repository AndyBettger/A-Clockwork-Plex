(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'weather') return;

  if (!document.querySelector('script[data-rain-history-scroll-loader]')) {
    const rainScrollScript = document.createElement('script');
    rainScrollScript.src = '/static/js/weather-rain-history-scroll.js?v=20260817-forecast-style-scroll-v1';
    rainScrollScript.dataset.rainHistoryScrollLoader = '';
    document.head.appendChild(rainScrollScript);
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

  function parseDate(value, dateOnly = false) {
    const text = String(value || '').trim();
    if (!text) return null;
    const parsed = new Date(dateOnly && /^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text}T12:00:00` : text);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function temperature(value, unit) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '—';
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

  function dayLabel(value, index) {
    if (index === 0) return 'Today';
    if (index === 1) return 'Tomorrow';
    const parsed = parseDate(value, true);
    return parsed
      ? parsed.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric' })
      : String(value || 'Later');
  }

  function futureHourly(items) {
    const cutoff = Date.now() - (45 * 60 * 1000);
    const future = items.filter((item) => {
      const parsed = parseDate(item?.valid_at);
      return parsed === null || parsed.getTime() >= cutoff;
    });
    return (future.length ? future : items).slice(0, 8);
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function dailyCard(item, index, units) {
    const card = make('article', `weather-forecast-card${index === 0 ? ' is-today' : ''}`);
    card.dataset.forecastDate = String(item.date || '');
    const state = condition(item);
    card.append(
      make('span', 'weather-forecast-time', dayLabel(item.date, index)),
      make('span', 'weather-forecast-icon', toneIcons[state.tone] || toneIcons.unknown),
      make(
        'strong',
        'weather-forecast-temperature',
        `${temperature(item.temperature_max, units.temperature)} / ${temperature(item.temperature_min, units.temperature)}`,
      ),
      make('span', 'weather-forecast-condition', state.label),
      make('span', 'weather-forecast-rain', probability(item.precipitation_probability_max)),
    );
    return card;
  }

  function update(payload) {
    const forecast = payload?.forecast;
    if (!forecast) return;

    const groups = [...document.querySelectorAll('.weather-forecast-group')];
    const hourlyStrip = groups.find((group) => group.querySelector('h3')?.textContent.trim() === 'Next hours')
      ?.querySelector('.weather-forecast-strip');
    const dailyStrip = groups.find((group) => group.querySelector('h3')?.textContent.trim() === 'Daily outlook')
      ?.querySelector('.weather-forecast-strip');

    const hourly = Array.isArray(forecast.hourly) ? futureHourly(forecast.hourly) : [];
    hourlyStrip?.querySelectorAll('.weather-forecast-card').forEach((card, index) => {
      const item = hourly[index];
      const time = card.querySelector('.weather-forecast-time');
      if (time && item?.valid_at) time.textContent = window.ACPTime?.formatTime?.(item.valid_at) || time.textContent;
    });

    const daily = Array.isArray(forecast.daily) ? forecast.daily : [];
    if (dailyStrip && daily.length) {
      const existingDates = new Set(
        [...dailyStrip.querySelectorAll('[data-forecast-date]')]
          .map((card) => String(card.dataset.forecastDate || '').trim())
          .filter(Boolean),
      );
      let renderedDays = existingDates.size;
      daily.forEach((item, index) => {
        if (condition(item).tone === 'unknown') return;
        const forecastDate = String(item?.date || '').trim();
        if (forecastDate && existingDates.has(forecastDate)) return;
        dailyStrip.appendChild(dailyCard(item, index, forecast.units || {}));
        if (forecastDate) existingDates.add(forecastDate);
        renderedDays += 1;
      });
      dailyStrip.dataset.forecastDaysRendered = String(renderedDays);
      dailyStrip.dispatchEvent(new Event('scroll'));
      window.dispatchEvent(new Event('resize'));
    }

    const fetchedAt = payload?.fetched_at || forecast.fetched_at;
    if (fetchedAt) {
      const footnotes = [...document.querySelectorAll('.weather-forecast-footnote')];
      const updated = footnotes.find((node) => node.textContent.trim().startsWith('Updated '));
      if (updated) updated.textContent = `Updated ${window.ACPTime?.formatDateTime?.(fetchedAt, { seconds: false, weekday: '' }) || fetchedAt}`;
    }
  }

  function run(attempts = 60) {
    if (!document.querySelector('[data-weather-forecast-console]')) {
      if (attempts > 0) window.setTimeout(() => run(attempts - 1), 100);
      return;
    }
    fetch('/api/weather/forecast', { cache: 'no-store' })
      .then((response) => response.ok ? response.json() : null)
      .then(update)
      .catch(() => {});
  }

  window.addEventListener('acp:clock-format-changed', () => run(1));
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => run(), { once: true });
  else run();
})();
