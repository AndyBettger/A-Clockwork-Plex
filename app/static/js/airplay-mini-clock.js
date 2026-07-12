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
    date: document.getElementById('airplay-mini-date-segmented'),
  };

  const CLOCK_FORMAT_STORAGE_KEY = 'a-clockwork-plex.clock-format';
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const SEGMENT_THICKNESS = 2.28;

  // Point-to-point geometry for a compact 14/16-segment style display.
  // These are deliberately kept as simple co-ordinates so the cell can later be
  // tuned in Inkscape and copied back here without changing the renderer.
  const SEGMENT_POINTS = {
    a: [3.0, 2.1, 17.0, 2.1],
    b: [18.0, 3.35, 18.0, 15.25],
    c: [18.0, 16.75, 18.0, 28.65],
    d: [3.0, 29.9, 17.0, 29.9],
    e: [2.0, 16.75, 2.0, 28.65],
    f: [2.0, 3.35, 2.0, 15.25],
    g1: [3.25, 16.0, 9.55, 16.0],
    g2: [10.45, 16.0, 16.75, 16.0],
    h: [3.8, 3.65, 9.65, 15.45],
    i: [16.2, 3.65, 10.35, 15.45],
    j: [3.8, 28.35, 9.65, 16.55],
    k: [16.2, 28.35, 10.35, 16.55],
    m: [10.0, 3.4, 10.0, 15.35],
    n: [10.0, 16.65, 10.0, 28.6],
  };

  const SEGMENTS = {
    '0': ['a', 'b', 'c', 'd', 'e', 'f'],
    '1': ['b', 'c'],
    '2': ['a', 'b', 'g1', 'g2', 'e', 'd'],
    '3': ['a', 'b', 'g1', 'g2', 'c', 'd'],
    '4': ['f', 'g1', 'g2', 'b', 'c'],
    '5': ['a', 'f', 'g1', 'g2', 'c', 'd'],
    '6': ['a', 'f', 'e', 'd', 'c', 'g1', 'g2'],
    '7': ['a', 'b', 'c'],
    '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g1', 'g2'],
    '9': ['a', 'b', 'c', 'd', 'f', 'g1', 'g2'],
    'A': ['a', 'b', 'c', 'e', 'f', 'g1', 'g2'],
    'B': ['f', 'e', 'd', 'c', 'g1', 'g2'],
    'C': ['a', 'd', 'e', 'f'],
    'D': ['b', 'c', 'd', 'e', 'g1'],
    'E': ['a', 'd', 'e', 'f', 'g1', 'g2'],
    'F': ['a', 'e', 'f', 'g1', 'g2'],
    'G': ['a', 'c', 'd', 'e', 'f', 'g2'],
    'H': ['b', 'c', 'e', 'f', 'g1', 'g2'],
    'I': ['a', 'd', 'm', 'n'],
    'J': ['b', 'c', 'd', 'e'],
    'K': ['e', 'f', 'g1', 'i', 'k'],
    'L': ['d', 'e', 'f'],
    'M': ['b', 'c', 'e', 'f', 'h', 'i'],
    'N': ['b', 'c', 'e', 'f', 'h', 'k'],
    'O': ['a', 'b', 'c', 'd', 'e', 'f'],
    'P': ['a', 'b', 'e', 'f', 'g1', 'g2'],
    'Q': ['a', 'b', 'c', 'd', 'e', 'f', 'k'],
    'R': ['a', 'b', 'e', 'f', 'g1', 'g2', 'k'],
    'S': ['a', 'f', 'g1', 'g2', 'c', 'd'],
    'T': ['a', 'm', 'n'],
    'U': ['b', 'c', 'd', 'e', 'f'],
    'V': ['e', 'f', 'j', 'i'],
    'W': ['b', 'c', 'd', 'e', 'f', 'j', 'k'],
    'X': ['h', 'i', 'j', 'k'],
    'Y': ['h', 'i', 'n'],
    'Z': ['a', 'i', 'j', 'd'],
    '/': ['i', 'j'],
    '-': ['g1', 'g2'],
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

  function pointedSegment(points) {
    const [x1, y1, x2, y2] = points;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const length = Math.hypot(dx, dy) || 1;
    const ux = dx / length;
    const uy = dy / length;
    const px = -uy;
    const py = ux;
    const half = SEGMENT_THICKNESS / 2;
    const tip = Math.min(1.72, length * 0.38);
    const coords = [
      [x1, y1],
      [x1 + ux * tip + px * half, y1 + uy * tip + py * half],
      [x2 - ux * tip + px * half, y2 - uy * tip + py * half],
      [x2, y2],
      [x2 - ux * tip - px * half, y2 - uy * tip - py * half],
      [x1 + ux * tip - px * half, y1 + uy * tip - py * half],
    ];

    return coords.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  }

  function makeCharacter(character) {
    const value = String(character || ' ').toUpperCase();
    const wrapper = document.createElement('span');
    wrapper.className = 'alpha-character';
    wrapper.setAttribute('aria-hidden', 'true');

    if (value === ' ') {
      wrapper.classList.add('is-space');
    }

    const activeSegments = new Set(SEGMENTS[value] || []);
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 20 32');
    svg.setAttribute('focusable', 'false');

    for (const [name, points] of Object.entries(SEGMENT_POINTS)) {
      const segment = document.createElementNS(SVG_NS, 'polygon');
      segment.setAttribute('points', pointedSegment(points));
      segment.classList.add('alpha-segment');
      if (activeSegments.has(name)) {
        segment.classList.add('is-on');
      }
      svg.appendChild(segment);
    }

    wrapper.appendChild(svg);
    return wrapper;
  }

  function setCharacters(element, value) {
    if (!element) {
      return;
    }

    const text = String(value || '').toUpperCase();
    if (element.dataset.segmentText === text && element.firstElementChild) {
      return;
    }

    element.dataset.segmentText = text;
    element.replaceChildren(...text.split('').map(makeCharacter));
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
    const timeLabel = `${hours}:${minutes}:${seconds}${suffix ? ` ${suffix}` : ''}`;

    setCharacters(elements.hours, hours);
    setCharacters(elements.minutes, minutes);
    setCharacters(elements.seconds, seconds);
    setCharacters(elements.date, ` ${dateLabel}`);

    if (elements.meridiem) {
      elements.meridiem.hidden = !suffix;
      elements.meridiem.textContent = suffix;
    }

    root.classList.toggle('is-colon-off', now.getSeconds() % 2 === 1);
    root.setAttribute('aria-label', `${timeLabel} ${dateLabel}`);
    if (elements.date) {
      elements.date.setAttribute('aria-label', dateLabel);
    }
  }

  window.addEventListener('storage', (event) => {
    if (event.key === CLOCK_FORMAT_STORAGE_KEY) {
      updateClock();
    }
  });

  updateClock();
  window.setInterval(updateClock, 1000);
})();