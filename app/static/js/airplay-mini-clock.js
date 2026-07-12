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

  // Alphanumeric segment geometry with small centre gaps. The gaps keep the
  // unlit display from looking like a knot of crossed wires.
  const SEGMENT_POINTS = {
    a1: [4, 2, 9, 2],
    a2: [11, 2, 16, 2],
    b: [18, 4.4, 18, 13.4],
    c: [18, 18.6, 18, 27.6],
    d1: [4, 30, 9, 30],
    d2: [11, 30, 16, 30],
    e: [2, 18.6, 2, 27.6],
    f: [2, 4.4, 2, 13.4],
    g1: [4, 16, 8.7, 16],
    g2: [11.3, 16, 16, 16],
    h: [4.4, 4.6, 8.7, 14.2],
    i: [15.6, 4.6, 11.3, 14.2],
    j: [4.4, 27.4, 8.7, 17.8],
    k: [15.6, 27.4, 11.3, 17.8],
    m: [10, 4.8, 10, 13.3],
    n: [10, 18.7, 10, 27.2],
  };

  const SEGMENTS = {
    '0': ['a1', 'a2', 'b', 'c', 'd1', 'd2', 'e', 'f'],
    '1': ['b', 'c'],
    '2': ['a1', 'a2', 'b', 'g1', 'g2', 'e', 'd1', 'd2'],
    '3': ['a1', 'a2', 'b', 'g1', 'g2', 'c', 'd1', 'd2'],
    '4': ['f', 'g1', 'g2', 'b', 'c'],
    '5': ['a1', 'a2', 'f', 'g1', 'g2', 'c', 'd1', 'd2'],
    '6': ['a1', 'a2', 'f', 'e', 'd1', 'd2', 'c', 'g1', 'g2'],
    '7': ['a1', 'a2', 'b', 'c'],
    '8': ['a1', 'a2', 'b', 'c', 'd1', 'd2', 'e', 'f', 'g1', 'g2'],
    '9': ['a1', 'a2', 'b', 'c', 'd1', 'd2', 'f', 'g1', 'g2'],
    'A': ['a1', 'a2', 'b', 'c', 'e', 'f', 'g1', 'g2'],
    'B': ['f', 'e', 'd1', 'd2', 'c', 'g1', 'g2'],
    'C': ['a1', 'a2', 'd1', 'd2', 'e', 'f'],
    'D': ['b', 'c', 'd1', 'd2', 'e', 'g1'],
    'E': ['a1', 'a2', 'd1', 'd2', 'e', 'f', 'g1', 'g2'],
    'F': ['a1', 'a2', 'e', 'f', 'g1', 'g2'],
    'G': ['a1', 'a2', 'c', 'd1', 'd2', 'e', 'f', 'g2'],
    'H': ['b', 'c', 'e', 'f', 'g1', 'g2'],
    'I': ['a1', 'a2', 'd1', 'd2', 'm', 'n'],
    'J': ['b', 'c', 'd1', 'd2', 'e'],
    'K': ['e', 'f', 'g1', 'i', 'k'],
    'L': ['d1', 'd2', 'e', 'f'],
    'M': ['b', 'c', 'e', 'f', 'h', 'i'],
    'N': ['b', 'c', 'e', 'f', 'h', 'k'],
    'O': ['a1', 'a2', 'b', 'c', 'd1', 'd2', 'e', 'f'],
    'P': ['a1', 'a2', 'b', 'e', 'f', 'g1', 'g2'],
    'Q': ['a1', 'a2', 'b', 'c', 'd1', 'd2', 'e', 'f', 'k'],
    'R': ['a1', 'a2', 'b', 'e', 'f', 'g1', 'g2', 'k'],
    'S': ['a1', 'a2', 'f', 'g1', 'g2', 'c', 'd1', 'd2'],
    'T': ['a1', 'a2', 'm', 'n'],
    'U': ['b', 'c', 'd1', 'd2', 'e', 'f'],
    'V': ['e', 'f', 'j', 'i'],
    'W': ['b', 'c', 'd1', 'd2', 'e', 'f', 'j', 'k'],
    'X': ['h', 'i', 'j', 'k'],
    'Y': ['h', 'i', 'n'],
    'Z': ['a1', 'a2', 'i', 'j', 'd1', 'd2'],
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