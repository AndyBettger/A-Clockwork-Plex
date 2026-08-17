(() => {
  if (document.body?.dataset.activePage !== 'weather') {
    return;
  }

  const strip = document.querySelector('.rain-history-scroll');
  if (!strip || document.querySelector('[data-rain-history-scrollbar]')) {
    return;
  }

  const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
  const trackInset = 1;

  if (!strip.id) {
    strip.id = 'rain-history-scroll';
  }

  const rail = document.createElement('div');
  rail.className = 'weather-forecast-scrollbar rain-history-scrollbar';
  rail.dataset.rainHistoryScrollbar = '';
  rail.setAttribute('role', 'scrollbar');
  rail.setAttribute('aria-label', 'Rainy Day Fund horizontal scroll');
  rail.setAttribute('aria-controls', strip.id);
  rail.setAttribute('aria-orientation', 'horizontal');
  rail.tabIndex = 0;

  const thumb = document.createElement('div');
  thumb.className = 'weather-forecast-scrollbar-thumb';
  rail.appendChild(thumb);
  strip.insertAdjacentElement('afterend', rail);

  let drag = null;

  function measurements() {
    const maxScroll = Math.max(0, strip.scrollWidth - strip.clientWidth);
    const availableWidth = Math.max(0, rail.clientWidth - (trackInset * 2));
    const proportionalWidth = strip.scrollWidth > 0
      ? availableWidth * (strip.clientWidth / strip.scrollWidth)
      : availableWidth;
    const thumbWidth = Math.min(availableWidth, Math.max(42, proportionalWidth));
    const maxThumbTravel = Math.max(0, availableWidth - thumbWidth);
    return { maxScroll, availableWidth, thumbWidth, maxThumbTravel };
  }

  function update() {
    const metrics = measurements();
    const scrollable = metrics.maxScroll > 1 && metrics.availableWidth > 0;
    rail.hidden = !scrollable;
    rail.setAttribute('aria-hidden', scrollable ? 'false' : 'true');
    rail.tabIndex = scrollable ? 0 : -1;

    if (!scrollable) {
      thumb.style.width = '100%';
      thumb.style.transform = 'translate3d(0, 0, 0)';
      rail.setAttribute('aria-valuenow', '0');
      return;
    }

    const ratio = clamp(strip.scrollLeft / metrics.maxScroll, 0, 1);
    const thumbOffset = ratio * metrics.maxThumbTravel;
    thumb.style.width = `${metrics.thumbWidth}px`;
    thumb.style.transform = `translate3d(${thumbOffset}px, 0, 0)`;
    rail.setAttribute('aria-valuemin', '0');
    rail.setAttribute('aria-valuemax', String(Math.round(metrics.maxScroll)));
    rail.setAttribute('aria-valuenow', String(Math.round(strip.scrollLeft)));
  }

  function setFromRailPointer(clientX) {
    const metrics = measurements();
    if (metrics.maxScroll <= 0 || metrics.maxThumbTravel <= 0) {
      return;
    }
    const rect = rail.getBoundingClientRect();
    const pointer = clientX - rect.left - trackInset;
    const target = clamp(pointer - (metrics.thumbWidth / 2), 0, metrics.maxThumbTravel);
    strip.scrollLeft = (target / metrics.maxThumbTravel) * metrics.maxScroll;
  }

  rail.addEventListener('pointerdown', (event) => {
    if (event.target === thumb) {
      return;
    }
    setFromRailPointer(event.clientX);
    event.preventDefault();
  });

  thumb.addEventListener('pointerdown', (event) => {
    const metrics = measurements();
    drag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScroll: strip.scrollLeft,
      maxScroll: metrics.maxScroll,
      maxThumbTravel: metrics.maxThumbTravel,
    };
    thumb.setPointerCapture?.(event.pointerId);
    rail.classList.add('is-dragging');
    event.preventDefault();
    event.stopPropagation();
  });

  thumb.addEventListener('pointermove', (event) => {
    if (!drag || drag.pointerId !== event.pointerId || drag.maxThumbTravel <= 0) {
      return;
    }
    const delta = event.clientX - drag.startX;
    strip.scrollLeft = drag.startScroll + ((delta / drag.maxThumbTravel) * drag.maxScroll);
    event.preventDefault();
  });

  function endDrag(event) {
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    thumb.releasePointerCapture?.(event.pointerId);
    drag = null;
    rail.classList.remove('is-dragging');
  }

  thumb.addEventListener('pointerup', endDrag);
  thumb.addEventListener('pointercancel', endDrag);

  rail.addEventListener('keydown', (event) => {
    const pageStep = Math.max(80, strip.clientWidth * 0.35);
    if (event.key === 'ArrowLeft') {
      strip.scrollLeft -= pageStep;
    } else if (event.key === 'ArrowRight') {
      strip.scrollLeft += pageStep;
    } else if (event.key === 'Home') {
      strip.scrollLeft = 0;
    } else if (event.key === 'End') {
      strip.scrollLeft = strip.scrollWidth;
    } else {
      return;
    }
    event.preventDefault();
  });

  strip.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update, { passive: true });
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(update);
    observer.observe(strip);
    observer.observe(rail);
  }

  window.requestAnimationFrame(update);
})();
