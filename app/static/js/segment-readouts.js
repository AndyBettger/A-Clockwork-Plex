(() => {
  const segments = window.AClockworkSegments;
  if (!segments) {
    return;
  }

  const READOUT_SELECTOR = [
    '.weather-value',
    '.weather-subvalue',
    '.conditions-table td',
    '.mini-reading strong',
    '.wind-degrees',
    '.wind-readings strong',
    '.barometer-reading-card strong',
    '.rain-gauge-text strong',
    '#airplay-outside-now',
  ].join(',');

  let refreshQueued = false;

  function makeNumberToken(value) {
    const token = document.createElement('span');
    token.className = 'segment-readout-number';
    token.append(...String(value).split('').map((character) => segments.createCharacter(character, {
      wrapperClass: 'segment-readout-cell',
      segmentClass: 'segment-readout-segment',
      activeClass: 'is-on',
      punctuationClass: 'segment-readout-punctuation',
      decimalRadius: '3.4',
    })));
    return token;
  }

  function makeUnitToken(value) {
    const token = document.createElement('span');
    token.className = 'segment-readout-unit';
    token.textContent = String(value || '').trim();
    return token;
  }

  function makeSeparatorToken() {
    const token = document.createElement('span');
    token.className = 'segment-readout-separator';
    token.textContent = '·';
    return token;
  }

  function textTokens(value) {
    const tokens = [];
    String(value || '').split(/(·)/g).forEach((piece) => {
      if (piece === '·') {
        tokens.push(makeSeparatorToken());
      } else if (piece.trim()) {
        tokens.push(makeUnitToken(piece));
      }
    });
    return tokens;
  }

  function renderReadout(element) {
    if (!(element instanceof HTMLElement)) {
      return;
    }

    const existing = element.querySelector(':scope > .segment-readout-inner');
    if (existing) {
      return;
    }

    const rawValue = String(element.textContent || '').trim();
    if (!/\d/.test(rawValue)) {
      element.classList.remove('segment-readout');
      element.removeAttribute('data-segment-source');
      return;
    }

    const pieces = rawValue.split(/([+-]?\d+(?:\.\d+)?)/g).filter((piece) => piece !== '');
    const inner = document.createElement('span');
    inner.className = 'segment-readout-inner';

    pieces.forEach((piece) => {
      if (/^[+-]?\d+(?:\.\d+)?$/.test(piece)) {
        inner.appendChild(makeNumberToken(piece));
      } else {
        inner.append(...textTokens(piece));
      }
    });

    element.dataset.segmentSource = rawValue;
    element.setAttribute('aria-label', rawValue);
    element.classList.add('segment-readout');
    element.replaceChildren(inner);
  }

  function unrenderReadout(element, value) {
    if (!element) {
      return;
    }
    element.classList.remove('segment-readout');
    element.removeAttribute('data-segment-source');
    element.textContent = value;
  }

  function compactClockBarometers(root = document) {
    const cards = [];
    if (root instanceof HTMLElement && root.matches('.weather-card')) {
      cards.push(root);
    }
    cards.push(...(root.querySelectorAll?.('.weather-card') || []));

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
        unrenderReadout(value, compactValue);
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
      unrenderReadout(value, forecast);
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
    targets.push(...(root.querySelectorAll?.(READOUT_SELECTOR) || []));
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
