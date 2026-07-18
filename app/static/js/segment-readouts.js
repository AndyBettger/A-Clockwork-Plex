(() => {
  const SVG_NS = 'http://www.w3.org/2000/svg';

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
    '-': ['g1', 'g2'],
    '+': ['g1', 'g2', 'm', 'n'],
  };

  const READOUT_SELECTOR = [
    '.weather-value',
    '.conditions-table td',
    '.mini-reading strong',
    '.wind-direction',
    '.wind-readings strong',
    '.barometer-reading-card strong',
    '.rain-gauge-text strong',
    '#airplay-outside-now',
  ].join(',');

  let refreshQueued = false;

  function makeSegmentCell(character) {
    const cell = document.createElement('span');
    cell.className = 'segment-readout-cell';

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 20 32');
    svg.setAttribute('focusable', 'false');
    svg.setAttribute('aria-hidden', 'true');

    if (character === '.') {
      cell.classList.add('is-decimal');
      const dot = document.createElementNS(SVG_NS, 'circle');
      dot.setAttribute('cx', '10');
      dot.setAttribute('cy', '29.5');
      dot.setAttribute('r', '2.2');
      dot.classList.add('segment-readout-punctuation');
      svg.appendChild(dot);
      cell.appendChild(svg);
      return cell;
    }

    const activeSegments = new Set(SEGMENTS[character] || []);
    for (const [name, shape] of Object.entries(SEGMENT_PATHS)) {
      const segment = document.createElementNS(SVG_NS, 'path');
      segment.setAttribute('d', shape.d);
      if (shape.transform) {
        segment.setAttribute('transform', shape.transform);
      }
      segment.classList.add('segment-readout-segment');
      if (activeSegments.has(name)) {
        segment.classList.add('is-on');
      }
      svg.appendChild(segment);
    }

    cell.appendChild(svg);
    return cell;
  }

  function makeNumberToken(value) {
    const token = document.createElement('span');
    token.className = 'segment-readout-token';
    token.append(...String(value).split('').map(makeSegmentCell));
    return token;
  }

  function makeUnitToken(value) {
    const token = document.createElement('span');
    token.className = 'segment-readout-unit';
    token.textContent = value;
    return token;
  }

  function renderReadout(element) {
    if (!(element instanceof HTMLElement)) {
      return;
    }

    if (element.querySelector(':scope > .segment-readout-token, :scope > .segment-readout-unit')) {
      return;
    }

    const rawValue = String(element.textContent || '').trim();
    if (!/\d/.test(rawValue)) {
      element.classList.remove('segment-readout');
      element.removeAttribute('data-segment-source');
      return;
    }

    const pieces = rawValue.split(/([+-]?\d+(?:\.\d+)?)/g).filter((piece) => piece !== '');
    const nodes = pieces.map((piece) => /^[+-]?\d+(?:\.\d+)?$/.test(piece)
      ? makeNumberToken(piece)
      : makeUnitToken(piece));

    element.dataset.segmentSource = rawValue;
    element.setAttribute('aria-label', rawValue);
    element.classList.add('segment-readout');
    element.replaceChildren(...nodes);
  }

  function compactClockBarometers(root = document) {
    const cards = [];
    if (root instanceof HTMLElement && root.matches('.weather-card')) {
      cards.push(root);
    }
    cards.push(...root.querySelectorAll?.('.weather-card') || []);

    cards.forEach((card) => {
      const label = card.querySelector('.weather-label');
      const value = card.querySelector('.weather-value');
      if (!label || !value || label.textContent.trim().toLowerCase() !== 'barometer') {
        return;
      }

      card.classList.add('is-barometer');
      const rawValue = value.dataset.segmentSource || value.textContent.trim();
      const compactValue = rawValue.split('·')[0].trim();
      if (compactValue && value.textContent.trim() !== compactValue) {
        value.classList.remove('segment-readout');
        value.removeAttribute('data-segment-source');
        value.textContent = compactValue;
      }
    });
  }

  function compactAirPlayBarometer() {
    const label = document.getElementById('airplay-barometer-label');
    const value = document.getElementById('airplay-barometer-now');
    const detail = document.getElementById('airplay-barometer-detail');
    if (!label || !value) {
      return;
    }

    const labelText = label.textContent.trim();
    const forecast = labelText.includes('·') ? labelText.split('·').slice(1).join('·').trim() : '';
    if (forecast) {
      label.textContent = 'Barometer';
      value.classList.remove('segment-readout');
      value.removeAttribute('data-segment-source');
      value.textContent = forecast;
    }

    if (detail) {
      detail.hidden = true;
    }
  }

  function tidyBarometerTrend() {
    const trend = document.querySelector('.barometer-forecast-card .trend-pill');
    if (!trend) {
      return;
    }

    const rawValue = trend.dataset.rawTrend || trend.textContent.trim();
    trend.dataset.rawTrend = rawValue;
    const rate = rawValue.match(/[+-]\d+(?:\.\d+)?\s*hPa\s*\/\s*3h/i);
    const compactValue = rate ? `Trend ${rate[0]}` : rawValue.replace(/^Gathering history/i, 'Learning');
    if (trend.textContent.trim() !== compactValue) {
      trend.textContent = compactValue;
    }
  }

  function refresh(root = document) {
    compactClockBarometers(root);
    compactAirPlayBarometer();
    tidyBarometerTrend();

    const targets = [];
    if (root instanceof HTMLElement && root.matches(READOUT_SELECTOR)) {
      targets.push(root);
    }
    targets.push(...root.querySelectorAll?.(READOUT_SELECTOR) || []);
    targets.forEach(renderReadout);
  }

  function queueRefresh(root = document) {
    if (refreshQueued) {
      return;
    }
    refreshQueued = true;
    window.requestAnimationFrame(() => {
      refreshQueued = false;
      refresh(root);
    });
  }

  const observer = new MutationObserver((mutations) => {
    const changedRoot = mutations
      .map((mutation) => mutation.target instanceof HTMLElement ? mutation.target : mutation.target.parentElement)
      .find(Boolean) || document;
    queueRefresh(changedRoot.closest?.('.weather-card, .airplay-info-card, .detail-panel') || document);
  });

  window.addEventListener('DOMContentLoaded', () => {
    refresh(document);
    observer.observe(document.body, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  });

  window.AClockworkSegmentReadouts = {
    refresh: () => refresh(document),
  };
})();
