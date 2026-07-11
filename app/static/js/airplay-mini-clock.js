(() => {
  const root = document.getElementById('airplay-mini-clock-segmented');
  if (!root) {
    return;
  }

  const elements = {
    hours: document.getElementById('airplay-mini-hours'),
    minutes: document.getElementById('airplay-mini-minutes'),
    seconds: document.getElementById('airplay-mini-seconds'),
    meridiem: document.getElementById('airplay-mini-meridiem'),
    date: document.getElementById('airplay-mini-date'),
  };

  const CLOCK_FORMAT_STORAGE_KEY = 'a-clockwork-plex.clock-format';
  const SEGMENTS = {
    '0': ['a', 'b', 'c', 'd', 'e', 'f'],
    '1': ['b', 'c'],
    '2': ['a', 'b', 'g', 'e', 'd'],
    '3': ['a', 'b', 'g', 'c', 'd'],
    '4': ['f', 'g', 'b', 'c'],
    '5': ['a', 'f', 'g', 'c', 'd'],
    '6': ['a', 'f', 'g', 'e', 'c', 'd'],
    '7': ['a', 'b', 'c'],
    '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    '9': ['a', 'b', 'c', 'd', 'f', 'g'],
  };

  function normaliseClockFormat(value) {
    return String(value || '').toLowerCase() === '12h' ? '12h' : '24h';
  }

  function currentClockFormat() {
    try {
      const localFormat = window.localStorage.getItem(CLOCK_FORMAT_STORAGE_KEY);
      if (localFormat === '12h' || localFormat === '24h') {
        return localFormat;
      }
    } catch (error) {
    }

    return normaliseClockFormat(root.dataset.clockFormat || '24h');
  }

  function makeDigit(value) {
    const digit = document.createElement('span');
    digit.className = 'digital-digit';
    digit.setAttribute('aria-hidden', 'true');

    for (const segment of ['a', 'b', 'c', 'd', 'e', 'f', 'g']) {
      const element = document.createElement('span');
      element.className = `segment segment-${segment}`;
      if ((SEGMENTS[value] || []).includes(segment)) {
        element.classList.add('is-on');
      }
      digit.appendChild(element);
    }

    return digit;
  }

  function setDigits(element, value) {
    if (!element) {
      return;
    }

    const text = String(value || '').replace(/\D/g, '');
    element.replaceChildren(...text.split('').map(makeDigit));
  }

  function updateClock() {
    const now = new Date();
    const rawHours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const format = currentClockFormat();
    let hours;
    let suffix = '';

    if (format === '12h') {
      suffix = rawHours >= 12 ? 'PM' : 'AM';
      hours = String(((rawHours + 11) % 12) + 1).padStart(2, '0');
    } else {
      hours = String(rawHours).padStart(2, '0');
    }

    const weekday = now.toLocaleDateString('en-GB', { weekday: 'short' });
    const day = String(now.getDate()).padStart(2, '0');
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const year = now.getFullYear();
    const label = `${hours}:${minutes}:${seconds}${suffix ? ` ${suffix}` : ''}`;

    setDigits(elements.hours, hours);
    setDigits(elements.minutes, minutes);
    setDigits(elements.seconds, seconds);

    if (elements.meridiem) {
      elements.meridiem.hidden = !suffix;
      elements.meridiem.textContent = suffix;
    }

    if (elements.date) {
      elements.date.textContent = `${weekday} ${day}/${month}/${year}`;
    }

    root.setAttribute('aria-label', label);
  }

  window.addEventListener('storage', (event) => {
    if (event.key === CLOCK_FORMAT_STORAGE_KEY) {
      updateClock();
    }
  });

  updateClock();
  window.setInterval(updateClock, 1000);
})();
