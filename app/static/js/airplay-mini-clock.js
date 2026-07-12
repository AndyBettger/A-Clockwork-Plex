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

  // Editable path geometry for the 14/16-segment display cell.
  // Source file: docs/airplay-segment-cell.svg
  // It is fine if Inkscape converts the editable polygons to paths; copy each
  // segment path's `d` value back into this map. Keep any `transform` value too.
  const SEGMENT_PATHS = {
    a: {
      d: 'M 16.961276,1.9065286 16.048949,0.5792982 4.0119027,0.56681617 3.1383003,1.8940466 4.6757439,3.739281 15.462556,3.7517631 Z',
      transform: 'matrix(1.1281637,0,0,1,-1.2800763,0)',
    },
    b: { d: 'M 16.373201,14.053358 18.327194,15.5961 19.494667,14.511214 19.464533,3.7344232 18.193471,2.3327149 16.379442,4.1900172 Z' },
    c: { d: 'm 16.355396,27.745659 1.884424,1.938512 1.235573,-1.580296 0.0088,-12.943672 -3.136134,3.095201 z' },
    d: { d: 'm 16.992268,31.278305 0.960954,-1.272392 -2.020089,-2.013786 -11.919223,0.0088 -1.8170874,1.969656 1.5169991,1.316523 z' },
    e: { d: 'M 0.63052074,28.580485 1.8940865,29.717961 3.6872198,27.733177 3.8813945,17.622692 0.59506866,14.4201 Z' },
    f: { d: 'M 0.6228415,13.767158 2.4992811,15.549569 3.7141732,14.466152 3.6642451,4.0339918 1.9625539,2.2515817 0.63532353,3.7718693 Z' },
    g1: { d: 'm 8.3066108,17.590132 1.508173,-1.61661 -1.9759577,-1.669568 -3.2452132,-0.03013 -1.8104028,1.670194 1.6572224,1.654945 z' },
    g2: { d: 'm 16.362745,17.634263 1.711174,-1.68722 -1.99361,-1.607784 -4.051527,-0.02648 -1.764131,1.678394 1.702348,1.634264 z' },
    h: { d: 'M 7.8406443,14.002515 7.8324816,9.6530167 4.1869428,4.1867271 4.1778378,8.723679 Z' },
    i: { d: 'm 11.837572,9.9401588 0.01287,4.1153132 4.088818,-5.822374 0.0048,-4.0005737 z' },
    j: { d: 'm 7.8270345,22.465843 -0.00253,-4.653923 -3.6313731,5.416588 -0.031265,4.424228 z' },
    k: { d: 'm 11.815136,18.015137 0.01361,4.591924 4.168252,5.08098 0.01287,-4.521316 z' },
    m: { d: 'M 8.2509973,14.194872 10,15.632436 11.41361,14.291959 V 5.4642189 L 9.9911739,3.9736981 8.2774757,5.4642189 Z' },
    n: { d: 'm 8.295128,25.758019 1.740177,2.021151 1.334174,-1.459908 10e-7,-8.642989 L 10,16.341085 8.3127802,18.14843 Z' },
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

    for (const [name, shape] of Object.entries(SEGMENT_PATHS)) {
      const segment = document.createElementNS(SVG_NS, 'path');
      segment.setAttribute('d', shape.d);
      if (shape.transform) {
        segment.setAttribute('transform', shape.transform);
      }
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