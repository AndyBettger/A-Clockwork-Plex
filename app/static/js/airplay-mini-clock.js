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
  const SVG_NS = 'http://www.w3.org/2000/svg';
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

  const ALPHA_SEGMENT_POINTS = {
    a: [3, 2, 17, 2],
    b: [18, 4, 18, 14],
    c: [18, 18, 18, 28],
    d: [3, 30, 17, 30],
    e: [2, 18, 2, 28],
    f: [2, 4, 2, 14],
    g1: [3, 16, 10, 16],
    g2: [10, 16, 17, 16],
    h: [3, 4, 10, 15],
    i: [17, 4, 10, 15],
    j: [3, 28, 10, 17],
    k: [17, 28, 10, 17],
    m: [10, 4, 10, 14],
    n: [10, 18, 10, 28],
  };

  const ALPHA_SEGMENTS = {
    '0': ['a', 'b', 'c', 'd', 'e', 'f'],
    '1': ['b', 'c'],
    '2': ['a', 'b', 'g1', 'g2', 'e', 'd'],
    '3': ['a', 'b', 'g2', 'c', 'd'],
    '4': ['f', 'g1', 'g2', 'b', 'c'],
    '5': ['a', 'f', 'g1', 'g2', 'c', 'd'],
    '6': ['a', 'f', 'e', 'd', 'c', 'g1', 'g2'],
    '7': ['a', 'b', 'c'],
    '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g1', 'g2'],
    '9': ['a', 'b', 'c', 'd', 'f', 'g1', 'g2'],
    'A': ['a', 'b', 'c', 'e', 'f', 'g1', 'g2'],
    'C': ['a', 'd', 'e', 'f'],
    'D': ['b', 'c', 'd', 'e', 'g1'],
    'E': ['a', 'd', 'e', 'f', 'g1', 'g2'],
    'F': ['a', 'e', 'f', 'g1', 'g2'],
    'H': ['b', 'c', 'e', 'f', 'g1', 'g2'],
    'I': ['a', 'd', 'm', 'n'],
    'M': ['b', 'c', 'e', 'f', 'h', 'i'],
    'N': ['b', 'c', 'e', 'f', 'h', 'k'],
    'O': ['a', 'b', 'c', 'd', 'e', 'f'],
    'R': ['a', 'b', 'e', 'f', 'g1', 'g2', 'k'],
    'S': ['a', 'c', 'd', 'f', 'g1', 'g2'],
    'T': ['a', 'm', 'n'],
    'U': ['b', 'c', 'd', 'e', 'f'],
    'W': ['b', 'c', 'd', 'e', 'f', 'j', 'k'],
    'Y': ['b', 'f', 'g1', 'g2', 'c', 'd'],
    '/': ['i', 'j'],
    '-': ['g1', 'g2'],
  };

  let renderingDate = false;

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

  function makeAlphaCharacter(character) {
    const value = String(character || ' ').toUpperCase();
    const wrapper = document.createElement('span');
    wrapper.className = 'alpha-character';
    wrapper.setAttribute('aria-hidden', 'true');

    if (value === ' ') {
      wrapper.classList.add('is-space');
      return wrapper;
    }

    const activeSegments = new Set(ALPHA_SEGMENTS[value] || []);
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 20 32');
    svg.setAttribute('focusable', 'false');

    for (const [name, points] of Object.entries(ALPHA_SEGMENT_POINTS)) {
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', points[0]);
      line.setAttribute('y1', points[1]);
      line.setAttribute('x2', points[2]);
      line.setAttribute('y2', points[3]);
      line.classList.add('alpha-segment');
      if (activeSegments.has(name)) {
        line.classList.add('is-on');
      }
      svg.appendChild(line);
    }

    wrapper.appendChild(svg);
    return wrapper;
  }

  function renderSegmentedDate(label) {
    if (!elements.date) {
      return;
    }

    const text = String(label || '').trim();
    if (elements.date.dataset.segmentedLabel === text && elements.date.firstElementChild) {
      return;
    }

    renderingDate = true;
    elements.date.dataset.segmentedLabel = text;
    elements.date.classList.add('is-alpha-segmented');
    elements.date.setAttribute('aria-label', text);
    elements.date.replaceChildren(...text.split('').map(makeAlphaCharacter));
    renderingDate = false;
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
    const dateLabel = `${weekday} ${day}/${month}/${year}`;
    const label = `${hours}:${minutes}:${seconds}${suffix ? ` ${suffix}` : ''}`;

    setDigits(elements.hours, hours);
    setDigits(elements.minutes, minutes);
    setDigits(elements.seconds, seconds);

    if (elements.meridiem) {
      elements.meridiem.hidden = !suffix;
      elements.meridiem.textContent = suffix;
    }

    renderSegmentedDate(dateLabel);
    root.setAttribute('aria-label', label);
  }

  if (elements.date) {
    const observer = new MutationObserver(() => {
      if (renderingDate) {
        return;
      }

      const text = elements.date.textContent;
      if (text && text !== elements.date.dataset.segmentedLabel) {
        renderSegmentedDate(text);
      }
    });
    observer.observe(elements.date, { childList: true, characterData: true, subtree: true });
  }

  window.addEventListener('storage', (event) => {
    if (event.key === CLOCK_FORMAT_STORAGE_KEY) {
      updateClock();
    }
  });

  updateClock();
  window.setInterval(updateClock, 1000);
})();