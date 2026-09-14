(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'news') return;

  const scrollMount = document.querySelector('[data-news-categories]');
  const scrollbar = document.querySelector('[data-news-category-scrollbar]');
  const thumb = document.querySelector('[data-news-category-scrollbar-thumb]');
  if (!scrollMount || !scrollbar || !thumb) return;
  if (scrollbar.dataset.bound === 'true') return;
  scrollbar.dataset.bound = 'true';

  const trackInset = 1;
  let drag = null;

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function measurements() {
    scrollbar.hidden = false;
    const maxScroll = Math.max(0, scrollMount.scrollHeight - scrollMount.clientHeight);
    const availableHeight = Math.max(0, scrollbar.clientHeight - (trackInset * 2));
    const proportionalHeight = scrollMount.scrollHeight > 0
      ? availableHeight * (scrollMount.clientHeight / scrollMount.scrollHeight)
      : availableHeight;
    const thumbHeight = Math.min(availableHeight, Math.max(42, proportionalHeight));
    const maxThumbTravel = Math.max(0, availableHeight - thumbHeight);
    return { maxScroll, availableHeight, thumbHeight, maxThumbTravel };
  }

  function update() {
    const metrics = measurements();
    const scrollable = metrics.maxScroll > 1 && metrics.availableHeight > 0;
    scrollbar.hidden = !scrollable;
    scrollbar.setAttribute('aria-hidden', scrollable ? 'false' : 'true');
    scrollbar.tabIndex = scrollable ? 0 : -1;

    if (!scrollable) {
      thumb.style.height = '100%';
      thumb.style.transform = 'translate3d(0, 0, 0)';
      scrollbar.setAttribute('aria-valuenow', '0');
      return;
    }

    const ratio = clamp(scrollMount.scrollTop / metrics.maxScroll, 0, 1);
    const thumbOffset = ratio * metrics.maxThumbTravel;
    thumb.style.height = `${metrics.thumbHeight}px`;
    thumb.style.transform = `translate3d(0, ${thumbOffset}px, 0)`;
    scrollbar.setAttribute('aria-valuemin', '0');
    scrollbar.setAttribute('aria-valuemax', String(Math.round(metrics.maxScroll)));
    scrollbar.setAttribute('aria-valuenow', String(Math.round(scrollMount.scrollTop)));
  }

  function setFromTrackPointer(clientY) {
    const metrics = measurements();
    if (metrics.maxScroll <= 0 || metrics.maxThumbTravel <= 0) return;
    const rect = scrollbar.getBoundingClientRect();
    const pointer = clientY - rect.top - trackInset;
    const target = clamp(pointer - (metrics.thumbHeight / 2), 0, metrics.maxThumbTravel);
    scrollMount.scrollTop = (target / metrics.maxThumbTravel) * metrics.maxScroll;
  }

  scrollbar.addEventListener('pointerdown', (event) => {
    if (event.target === thumb) return;
    setFromTrackPointer(event.clientY);
    event.preventDefault();
  });

  thumb.addEventListener('pointerdown', (event) => {
    const metrics = measurements();
    drag = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startScroll: scrollMount.scrollTop,
      maxScroll: metrics.maxScroll,
      maxThumbTravel: metrics.maxThumbTravel,
    };
    thumb.setPointerCapture?.(event.pointerId);
    scrollbar.classList.add('is-dragging');
    event.preventDefault();
    event.stopPropagation();
  });

  thumb.addEventListener('pointermove', (event) => {
    if (!drag || drag.pointerId !== event.pointerId || drag.maxThumbTravel <= 0) return;
    const delta = event.clientY - drag.startY;
    scrollMount.scrollTop = drag.startScroll + ((delta / drag.maxThumbTravel) * drag.maxScroll);
    event.preventDefault();
  });

  function endDrag(event) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    thumb.releasePointerCapture?.(event.pointerId);
    drag = null;
    scrollbar.classList.remove('is-dragging');
  }

  thumb.addEventListener('pointerup', endDrag);
  thumb.addEventListener('pointercancel', endDrag);

  scrollbar.addEventListener('keydown', (event) => {
    const pageStep = Math.max(80, scrollMount.clientHeight * 0.35);
    if (event.key === 'ArrowUp') {
      scrollMount.scrollTop -= pageStep;
    } else if (event.key === 'ArrowDown') {
      scrollMount.scrollTop += pageStep;
    } else if (event.key === 'PageUp') {
      scrollMount.scrollTop -= scrollMount.clientHeight * 0.8;
    } else if (event.key === 'PageDown') {
      scrollMount.scrollTop += scrollMount.clientHeight * 0.8;
    } else if (event.key === 'Home') {
      scrollMount.scrollTop = 0;
    } else if (event.key === 'End') {
      scrollMount.scrollTop = scrollMount.scrollHeight;
    } else {
      return;
    }
    event.preventDefault();
  });

  scrollMount.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update, { passive: true });

  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(update);
    observer.observe(scrollMount);
    observer.observe(scrollbar);
  }

  if ('MutationObserver' in window) {
    const observer = new MutationObserver(() => window.requestAnimationFrame(update));
    observer.observe(scrollMount, { childList: true });
  }

  window.requestAnimationFrame(update);
})();
