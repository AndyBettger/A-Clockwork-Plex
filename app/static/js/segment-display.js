(() => {
  const SVG_NS = 'http://www.w3.org/2000/svg';

  const SEGMENT_PATHS = {
    a: {
      d: 'm 17.001147,1.9000002 -1.240955,-1.40000004 -11.5231512,-4e-8 -1.240954,1.40000018 1.4182339,1.5999999 4.9638186,0 0.6204773,-0.7 0.6204774,0.7 4.963819,0 z',
      transform: 'matrix(1.1281637,0,0,1,-1.2800763,0)',
    },
    b: { d: 'm 16.5,14.3 1.6,1.600001 h 1.4 V 3.5000017 l -1.4,-1.4000015 -1.6,1.6 z' },
    c: { d: 'm 16.5,28.300001 1.6,1.6 1.401324,-1.4 L 19.5,16.09 18.1,16.1 16.5,17.7 Z' },
    d: { d: 'm 16.5,31.500001 1.401324,-1.4 -1.601324,-1.6 h -5.6 l -0.7,0.7 -0.7,-0.7 H 3.7 l -1.6,1.6 1.4000001,1.4 z' },
    e: { d: 'm 0.5,28.500001 1.4,1.4 1.6000001,-1.6 v -10.6 L 1.9,16.100001 H 0.5 Z' },
    f: { d: 'M 0.5,15.900001 H 1.9 L 3.5000001,14.3 3.5,3.7000002 l -1.6,-1.6 -1.4,1.4000012 z' },
    g1: { d: 'M 9.8,16.000001 7.3,14.5 H 3.7 L 2.2,16.000001 3.6923826,17.500002 7.3,17.500001 Z' },
    g2: { d: 'm 16.3,17.500001 1.5,-1.5 L 16.3,14.5 H 12.7 L 10.199888,16 12.7,17.500001 Z' },
    h: { d: 'M 7.5,14.3 9.8,15.800001 8.3,10.6 4.5,3.7000002 H 3.7 v 3.9000001 z' },
    i: { d: 'M 11.7,10.6 10.2,15.800001 12.5,14.3 16.3,7.6000003 V 3.7000002 h -0.8 z' },
    j: { d: 'm 8.3,21.600001 1.5,-5.4 -2.2761393,1.5 -3.8238607,6.7 v 3.9 h 0.8 z' },
    k: { d: 'm 10.2,16.200001 1.5,5.4 3.8,6.7 h 0.800001 l -1e-6,-3.9 -3.8,-6.7 z' },
    m: { d: 'M 8.5,10.4 10,15.800001 11.5,10.4 V 4.6000002 l -1.5,-1.5 -1.5,1.5 z' },
    n: { d: 'M 8.5,27.400001 10.000662,28.888992 11.5,27.400001 v -5.6 l -1.5,-5.6 -1.5,5.6 z' },
  };

  const SEGMENTS = {
    '0': ['a', 'b', 'c', 'd', 'e', 'f', 'i', 'j'],
    '1': ['b', 'c'],
    '2': ['a', 'b', 'g1', 'g2', 'e', 'd'],
    '3': ['a', 'b', 'g1', 'g2', 'c', 'd'],
    '4': ['f', 'g1', 'g2', 'b', 'c'],
    '5': ['a', 'f', 'g1', 'g2', 'c', 'd'],
    '6': ['a', 'f', 'e', 'd', 'c', 'g1', 'g2'],
    '7': ['a', 'b', 'c'],
    '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g1', 'g2'],
    '9': ['a', 'b', 'c', 'd', 'f', 'g1', 'g2'],
    A: ['a', 'b', 'c', 'e', 'f', 'g1', 'g2'],
    B: ['f', 'e', 'd', 'c', 'g1', 'g2'],
    C: ['a', 'd', 'e', 'f'],
    // Full top/right/bottom outline with the two centre stems. This keeps D
    // distinct from O while giving it a more conventional capital silhouette.
    D: ['a', 'b', 'c', 'd', 'm', 'n'],
    E: ['a', 'd', 'e', 'f', 'g1', 'g2'],
    F: ['a', 'e', 'f', 'g1', 'g2'],
    G: ['a', 'c', 'd', 'e', 'f', 'g2'],
    H: ['b', 'c', 'e', 'f', 'g1', 'g2'],
    I: ['a', 'd', 'm', 'n'],
    J: ['b', 'c', 'd', 'e'],
    K: ['e', 'f', 'g1', 'i', 'k'],
    L: ['d', 'e', 'f'],
    M: ['b', 'c', 'e', 'f', 'h', 'i'],
    N: ['b', 'c', 'e', 'f', 'h', 'k'],
    O: ['a', 'b', 'c', 'd', 'e', 'f'],
    P: ['a', 'b', 'e', 'f', 'g1', 'g2'],
    Q: ['a', 'b', 'c', 'd', 'e', 'f', 'k'],
    R: ['a', 'b', 'e', 'f', 'g1', 'g2', 'k'],
    S: ['a', 'f', 'g1', 'g2', 'c', 'd'],
    T: ['a', 'm', 'n'],
    U: ['b', 'c', 'd', 'e', 'f'],
    V: ['e', 'f', 'j', 'i'],
    W: ['b', 'c', 'e', 'f', 'j', 'k'],
    X: ['h', 'i', 'j', 'k'],
    Y: ['h', 'i', 'n'],
    Z: ['a', 'i', 'j', 'd'],
    '/': ['i', 'j'],
    '-': ['g1', 'g2'],
    '+': ['g1', 'g2', 'm', 'n'],
  };

  function createCharacter(character, options = {}) {
    const value = String(character || ' ').toUpperCase();
    const wrapper = document.createElement('span');
    wrapper.className = options.wrapperClass || 'alpha-character';
    wrapper.setAttribute('aria-hidden', 'true');

    if (value === ' ') {
      wrapper.classList.add('is-space');
    }

    if (value === '.') {
      wrapper.classList.add('is-decimal');
    }

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 20 32');
    svg.setAttribute('focusable', 'false');
    svg.setAttribute('aria-hidden', 'true');

    if (value === '.') {
      const dot = document.createElementNS(SVG_NS, 'circle');
      dot.setAttribute('cx', '10');
      dot.setAttribute('cy', '28.5');
      dot.setAttribute('r', options.decimalRadius || '3.4');
      dot.classList.add(options.punctuationClass || 'segment-readout-punctuation');
      svg.appendChild(dot);
      wrapper.appendChild(svg);
      return wrapper;
    }

    const activeSegments = new Set(SEGMENTS[value] || []);
    for (const [name, shape] of Object.entries(SEGMENT_PATHS)) {
      const segment = document.createElementNS(SVG_NS, 'path');
      segment.setAttribute('d', shape.d);
      if (shape.transform) {
        segment.setAttribute('transform', shape.transform);
      }
      segment.classList.add(options.segmentClass || 'alpha-segment');
      if (activeSegments.has(name)) {
        segment.classList.add(options.activeClass || 'is-on');
      }
      svg.appendChild(segment);
    }

    wrapper.appendChild(svg);
    return wrapper;
  }

  function setCharacters(element, value, options = {}) {
    if (!element) {
      return;
    }

    const text = String(value || '').toUpperCase();
    if (element.dataset.segmentText === text && element.firstElementChild) {
      return;
    }

    element.dataset.segmentText = text;
    element.replaceChildren(...text.split('').map((character) => createCharacter(character, options)));
  }

  window.AClockworkSegments = {
    paths: SEGMENT_PATHS,
    map: SEGMENTS,
    createCharacter,
    setCharacters,
  };
})();
