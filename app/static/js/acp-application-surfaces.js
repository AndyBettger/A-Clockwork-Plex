(() => {
  if (window.__aClockworkPlexApplicationSurfacesLoaded) return;
  window.__aClockworkPlexApplicationSurfacesLoaded = true;

  const surfaceHost = window.ACPSurfaceHost;
  const screen = document.querySelector('main.screen');
  const initialSurface = String(document.body?.dataset?.activePage || '').trim().toLowerCase();
  const surfaces = new Set(['clock', 'weather', 'news', 'settings', 'airplay']);

  if (!surfaceHost || !screen || !surfaces.has(initialSurface)) return;

  const mounted = new Map();
  const mounting = new Map();
  const loadedStyles = new Set(
    [...document.querySelectorAll('link[rel="stylesheet"][href]')]
      .map((node) => new URL(node.href, window.location.href).href),
  );
  const loadedScripts = new Set(
    [...document.querySelectorAll('script[src]')]
      .map((node) => new URL(node.src, window.location.href).href),
  );

  function absolute(url) {
    return new URL(url, window.location.href).href;
  }

  function surfaceFromPath(pathname = window.location.pathname) {
    const value = String(pathname || '').replace(/^\/+/, '').split('/', 1)[0].toLowerCase();
    return surfaces.has(value) ? value : null;
  }

  function initialMount() {
    const wrapper = document.createElement('section');
    wrapper.className = `acp-mounted-surface acp-mounted-surface-${initialSurface}`;
    wrapper.dataset.acpSurface = initialSurface;

    [...screen.childNodes].forEach((node) => wrapper.appendChild(node));
    screen.appendChild(wrapper);
    mounted.set(initialSurface, {
      surface: initialSurface,
      wrapper,
      title: document.title,
      scripts: [],
    });
  }

  function ensureStyle(href) {
    const resolved = absolute(href);
    if (loadedStyles.has(resolved)) return Promise.resolve();
    loadedStyles.add(resolved);

    return new Promise((resolve) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = resolved;
      link.dataset.acpSurfaceAsset = '';
      link.addEventListener('load', resolve, { once: true });
      link.addEventListener('error', resolve, { once: true });
      document.head.appendChild(link);
    });
  }

  async function ensureStyles(hrefs) {
    await Promise.all(hrefs.map(ensureStyle));
  }

  function ensureScript(src) {
    const resolved = absolute(src);
    if (loadedScripts.has(resolved)) return Promise.resolve();
    loadedScripts.add(resolved);

    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = resolved;
      script.async = false;
      script.dataset.acpSurfaceAsset = '';
      script.addEventListener('load', resolve, { once: true });
      script.addEventListener('error', () => reject(new Error(`Could not load ${resolved}`)), { once: true });
      document.body.appendChild(script);
    });
  }

  async function ensureScripts(sources) {
    for (const src of sources) {
      await ensureScript(src);
    }
  }

  async function fetchSurface(surface) {
    const response = await fetch(`/api/surfaces/${encodeURIComponent(surface)}`, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`Surface request returned HTTP ${response.status}`);
    }

    const payload = await response.json();
    if (payload?.ok !== true || !payload.html) {
      throw new Error('Surface response did not contain rendered HTML.');
    }

    const parsed = new DOMParser().parseFromString(String(payload.html), 'text/html');
    const parsedScreen = parsed.querySelector('main.screen');
    if (!parsedScreen) {
      throw new Error('Rendered surface document does not contain main.screen.');
    }

    const styleHrefs = [...parsed.querySelectorAll('link[rel="stylesheet"][href]')]
      .map((node) => node.getAttribute('href'))
      .filter(Boolean);
    await ensureStyles(styleHrefs);

    const scriptSources = [...parsed.querySelectorAll('script[src]')]
      .map((node) => node.getAttribute('src'))
      .filter(Boolean);

    const wrapper = document.createElement('section');
    wrapper.className = `acp-mounted-surface acp-mounted-surface-${surface}`;
    wrapper.dataset.acpSurface = surface;
    wrapper.hidden = true;

    [...parsedScreen.childNodes].forEach((node) => {
      wrapper.appendChild(document.importNode(node, true));
    });

    screen.appendChild(wrapper);
    return {
      surface,
      wrapper,
      title: parsed.title || `${surface} - A Clockwork Plex`,
      scripts: scriptSources,
    };
  }

  async function ensureMounted(surface) {
    if (mounted.has(surface)) return mounted.get(surface);
    if (mounting.has(surface)) return mounting.get(surface);

    const task = fetchSurface(surface)
      .then((record) => {
        mounted.set(surface, record);
        return record;
      })
      .finally(() => mounting.delete(surface));

    mounting.set(surface, task);
    return task;
  }

  async function syncLogicalMode(surface) {
    try {
      await fetch(`/api/mode/${encodeURIComponent(surface)}`, {
        method: 'POST',
        cache: 'no-store',
      });
    } catch (error) {
      // Screen projection will reconcile logical mode on its next pass.
    }
  }

  function markAirPlayUnresolved() {
    document.body.classList.remove(
      'airplay-session-active',
      'airplay-session-idle',
      'airplay-metadata-active',
      'airplay-remote-paused',
      'airplay-remote-playing',
    );
    document.body.classList.add('airplay-session-unresolved');
  }

  function presentMountedSurface(surface) {
    mounted.forEach((record, name) => {
      record.wrapper.hidden = name !== surface;
    });
  }

  function commitSurface(surface) {
    if (surface === 'airplay') markAirPlayUnresolved();
    presentMountedSurface(surface);
  }

  function applicationTransitionDurationMs() {
    const value = String(
      window.getComputedStyle(document.documentElement)
        .getPropertyValue('--acp-transition-duration')
        || '300ms',
    ).trim();
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) return 300;
    if (value.endsWith('s') && !value.endsWith('ms')) return Math.max(0, parsed * 1000);
    return Math.max(0, parsed);
  }

  function nextFrame() {
    return new Promise((resolve) => window.requestAnimationFrame(resolve));
  }

  function copyBodyBackground(target) {
    const style = window.getComputedStyle(document.body);
    [
      'background-color',
      'background-image',
      'background-position',
      'background-size',
      'background-repeat',
      'background-origin',
      'background-clip',
    ].forEach((property) => {
      target.style.setProperty(property, style.getPropertyValue(property));
    });
  }

  function freezeOutgoingScreenLayout(target) {
    const style = window.getComputedStyle(screen);

    // The destination commit changes body.mode-* / data-active-page before the
    // outgoing layer has finished travelling. Some surface CSS intentionally
    // changes main.screen geometry by body mode: Weather changes the grid row
    // template and AirPlay changes the screen from grid to block. Freeze the
    // outgoing screen's *current* computed formatting so a travelling clone
    // cannot relayout merely because the live destination changed body mode.
    [
      'display',
      'overflow',
      'grid-template-rows',
      'grid-template-columns',
      'grid-auto-flow',
      'grid-auto-rows',
      'grid-auto-columns',
      'align-content',
      'justify-content',
      'align-items',
      'justify-items',
      'row-gap',
      'column-gap',
      'padding-top',
      'padding-right',
      'padding-bottom',
      'padding-left',
    ].forEach((property) => {
      target.style.setProperty(property, style.getPropertyValue(property));
    });
  }

  const spatialSurfaceOrder = window.ACPWorkspaceTopology?.acpSurfaceOrder?.() || [];

  function spatialSurfaceDirection(from, to) {
    const fromIndex = spatialSurfaceOrder.indexOf(String(from || ''));
    const toIndex = spatialSurfaceOrder.indexOf(String(to || ''));
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return '';
    return toIndex > fromIndex ? 'forward' : 'reverse';
  }

  function spatialSurfacePath(from, to) {
    const fromIndex = spatialSurfaceOrder.indexOf(String(from || ''));
    const toIndex = spatialSurfaceOrder.indexOf(String(to || ''));
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return [];

    const step = toIndex > fromIndex ? 1 : -1;
    const path = [];
    for (let index = fromIndex; ; index += step) {
      path.push(spatialSurfaceOrder[index]);
      if (index === toIndex) break;
    }
    return path;
  }

  function captureBodyPresentationState() {
    return {
      activePage: document.body.dataset.activePage,
      modes: Array.from(document.body.classList).filter((name) => name.startsWith('mode-')),
    };
  }

  function applyBodyPresentationSurface(surface) {
    document.body.dataset.activePage = String(surface || '');
    Array.from(document.body.classList)
      .filter((name) => name.startsWith('mode-'))
      .forEach((name) => document.body.classList.remove(name));
    document.body.classList.add(`mode-${surface}`);
  }

  function restoreBodyPresentationState(state) {
    if (state.activePage) document.body.dataset.activePage = state.activePage;
    else delete document.body.dataset.activePage;

    Array.from(document.body.classList)
      .filter((name) => name.startsWith('mode-'))
      .forEach((name) => document.body.classList.remove(name));
    state.modes.forEach((name) => document.body.classList.add(name));
  }

  function prepareSpatialLayer(layer, surface) {
    layer.classList.add('acp-spatial-outgoing-live-clone');
    layer.dataset.acpSurfaceContext = String(surface || '');
    layer.setAttribute('aria-hidden', 'true');
    layer.inert = true;
    copyBodyBackground(layer);
    freezeOutgoingScreenLayout(layer);
    return layer;
  }

  function cloneCurrentSpatialLayer(surface) {
    return prepareSpatialLayer(screen.cloneNode(true), surface);
  }

  async function cloneMountedSpatialLayer(surface, restoreSurface) {
    const record = await ensureMounted(surface);

    // Hydrate script-owned AirPlay presentation while its mounted wrapper is
    // still hidden. Never expose a real intermediate surface across an await:
    // that could paint a pre-transition flash before the staged strip exists.
    if (surface === 'airplay') {
      await ensureScripts(record.scripts);
      await window.ACPAirPlayLive?.refreshForSpatialPreview?.();
      await (window.ACPAirPlayHydration?.waitForReady?.(700) || Promise.resolve());
    }

    const bodyState = captureBodyPresentationState();
    try {
      // Intermediate row members are presentation-only captures. Never call
      // commitSurface() here: restoring an AirPlay source through the real
      // commit path marks its session unresolved and destroys the exact
      // now-playing/route-ready geometry that the outgoing clone must preserve.
      presentMountedSurface(surface);
      applyBodyPresentationSurface(surface);
      if (surface === 'airplay') {
        window.ACPAirPlayLayoutV3?.calibrateForSpatialPreview?.();
        window.ACPAirPlayTitleMarquee?.measureForSpatialPreview?.();
      }
      screen.getBoundingClientRect();
      return prepareSpatialLayer(screen.cloneNode(true), surface);
    } finally {
      presentMountedSurface(restoreSurface);
      restoreBodyPresentationState(bodyState);
      window.ACPAirPlaySurfaceLifecycle?.publish?.({ force: true });
    }
  }

  function applicationTransitionStyle() {
    return String(
      window.ACPDashboardPreferences?.read?.().transitionStyle
      || document.documentElement.dataset.transitionStyle
      || 'grow-fade',
    ).trim().toLowerCase();
  }

  function ordinaryTransitionFrames(style) {
    const resolved = style === 'spatial-row' ? 'horizontal-slide' : style;
    const frames = {
      'grow-fade': {
        outgoing: [
          { opacity: 1, transform: 'none' },
          { opacity: 0, transform: 'translateY(-7px) scale(.985)' },
        ],
        incoming: [
          { opacity: 0, transform: 'translateY(10px) scale(.976)' },
          { opacity: 1, transform: 'none' },
        ],
      },
      crossfade: {
        outgoing: [{ opacity: 1 }, { opacity: 0 }],
        incoming: [{ opacity: 0 }, { opacity: 1 }],
      },
      'horizontal-slide': {
        outgoing: [
          { opacity: 1, transform: 'none' },
          { opacity: 0, transform: 'translateX(-4vw)' },
        ],
        incoming: [
          { opacity: 0, transform: 'translateX(5vw)' },
          { opacity: 1, transform: 'none' },
        ],
      },
      'vertical-lift': {
        outgoing: [
          { opacity: 1, transform: 'none' },
          { opacity: 0, transform: 'translateY(-4vh)' },
        ],
        incoming: [
          { opacity: 0, transform: 'translateY(5vh)' },
          { opacity: 1, transform: 'none' },
        ],
      },
      'cover-reveal': {
        outgoing: [
          { opacity: 1, clipPath: 'inset(0 0 0 0 round 0)' },
          { opacity: 0.15, clipPath: 'inset(0 0 0 100% round 22px)' },
        ],
        incoming: [
          { opacity: 0.65, clipPath: 'inset(0 100% 0 0 round 22px)' },
          { opacity: 1, clipPath: 'inset(0 0 0 0 round 0)' },
        ],
      },
      zoom: {
        outgoing: [
          { opacity: 1, transform: 'none' },
          { opacity: 0, transform: 'scale(1.045)' },
        ],
        incoming: [
          { opacity: 0, transform: 'scale(.91)' },
          { opacity: 1, transform: 'none' },
        ],
      },
      'blur-dissolve': {
        outgoing: [
          { opacity: 1, filter: 'blur(0)', transform: 'none' },
          { opacity: 0, filter: 'blur(12px)', transform: 'scale(1.008)' },
        ],
        incoming: [
          { opacity: 0, filter: 'blur(14px)', transform: 'scale(.992)' },
          { opacity: 1, filter: 'blur(0)', transform: 'none' },
        ],
      },
    };
    return frames[resolved] || frames['grow-fade'];
  }

  function applyInitialFrame(target, frame) {
    Object.entries(frame || {}).forEach(([property, value]) => {
      if (property === 'clipPath') target.style.clipPath = value;
      else target.style[property] = String(value);
    });
  }

  function clearOrdinaryTransitionStyles(target) {
    ['opacity', 'transform', 'filter', 'clipPath'].forEach((property) => {
      target.style[property] = '';
    });
  }

  async function ordinaryLiveCommit(from, commit) {
    const outgoing = cloneCurrentSpatialLayer(from);
    const frames = ordinaryTransitionFrames(applicationTransitionStyle());
    const duration = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
      ? 1
      : applicationTransitionDurationMs();
    const timing = {
      duration,
      easing: 'cubic-bezier(.16, .84, .24, 1)',
      fill: 'both',
    };
    const animations = [];

    document.body.classList.add('acp-spatial-live-commit');
    document.body.appendChild(outgoing);

    try {
      // Hide/stage the real screen underneath the exact outgoing clone before
      // committing the new mounted surface. Persistent shell chrome and the
      // night overlay never enter a browser snapshot and therefore remain live.
      applyInitialFrame(screen, frames.incoming[0]);
      await commit();

      screen.getBoundingClientRect();
      outgoing.getBoundingClientRect();
      await nextFrame();

      if (duration <= 0) {
        clearOrdinaryTransitionStyles(screen);
        return;
      }

      animations.push(outgoing.animate(frames.outgoing, timing));
      animations.push(screen.animate(frames.incoming, timing));
      await Promise.all(
        animations.map((animation) => animation.finished.catch(() => undefined)),
      );
    } finally {
      animations.forEach((animation) => animation.cancel());
      clearOrdinaryTransitionStyles(screen);
      outgoing.remove();
      document.body.classList.remove('acp-spatial-live-commit');
    }
  }

  function frameStripProgress(fraction) {
    if (fraction <= 0) return 0;
    if (fraction >= 1) return 1;
    // The same cubic-bezier(.16, .84, .24, 1) as the baseline. Solve x(t)
    // before evaluating y(t); using the clock fraction as t changes the easing.
    const cubic = (t, a, b) => 3 * (1 - t) ** 2 * t * a
      + 3 * (1 - t) * t ** 2 * b + t ** 3;
    let low = 0;
    let high = 1;
    for (let step = 0; step < 18; step += 1) {
      const mid = (low + high) / 2;
      if (cubic(mid, .16, .24) < fraction) low = mid;
      else high = mid;
    }
    return cubic((low + high) / 2, .84, 1);
  }

  async function frameStripLiveCommit(direction, from, to, layers, commit) {
    // Developer-only F10 comparison. One layout-positioned row replaces ALL
    // per-page WAAPI effects: no transform animation, fill mode or cancellation
    // can expose a starting position when the moving presentation is retired.
    const viewport = document.createElement('div');
    viewport.className = 'acp-webkit-frame-strip-viewport';
    viewport.setAttribute('aria-hidden', 'true');
    viewport.inert = true;
    Object.assign(viewport.style, {
      position: 'fixed', inset: '0', zIndex: '40', overflow: 'hidden',
      pointerEvents: 'none',
    });
    copyBodyBackground(viewport);
    const strip = document.createElement('div');
    strip.className = 'acp-webkit-frame-strip';
    Object.assign(strip.style, {
      position: 'absolute', top: '0', left: '0px', width: '100%', height: '100%',
    });
    viewport.appendChild(strip);

    const savedVisibility = screen.style.visibility;
    const sign = direction === 'reverse' ? -1 : 1;
    const width = document.documentElement.clientWidth;
    const distance = layers.length;
    const duration = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
      ? 0 : applicationTransitionDurationMs();
    const metrics = { from, to, distance, durationMs: duration,
      elapsedMs: 0, frames: 0, maxFrameGapMs: 0 };
    const addPanel = (layer, index) => {
      // Existing .screen styling preserves Lift's vertical translate, theme,
      // and frozen surface geometry. Only the containing row moves sideways.
      layer.style.setProperty('position', 'absolute', 'important');
      layer.style.setProperty('will-change', 'auto', 'important');
      layer.style.setProperty('transform', 'none', 'important');
      layer.style.left = `${sign * index * width}px`;
      layer.style.right = 'auto';
      layer.style.visibility = 'visible';
      strip.appendChild(layer);
    };

    try {
      layers.forEach(addPanel);
      document.body.classList.add('acp-spatial-live-commit');
      document.body.appendChild(viewport);
      // The actual main.screen never moves and is never reparented. In
      // particular, preserve mounted input/listener state and shell chrome.
      screen.style.visibility = 'hidden';
      await commit();
      addPanel(prepareSpatialLayer(screen.cloneNode(true), to), distance);
      viewport.getBoundingClientRect();
      const started = await nextFrame();
      let previous = started;
      let now = started;
      while (true) {
        const elapsed = now - started;
        const fraction = duration > 0 ? Math.min(1, elapsed / duration) : 1;
        strip.style.left = `${-sign * distance * width * frameStripProgress(fraction)}px`;
        metrics.frames += 1;
        metrics.maxFrameGapMs = Math.max(metrics.maxFrameGapMs, now - previous);
        if (fraction >= 1) break;
        previous = now;
        now = await nextFrame();
      }
      metrics.elapsedMs = Math.round(now - started);
      // Keep the final row position intact as the live destination paints
      // underneath it. Removing this row never resets its position to zero.
      screen.style.visibility = savedVisibility;
      await nextFrame();
      await nextFrame();
      window.__acpWebkitFrameStripLast = metrics;
      window.__acpWebkitFrameStripApplied =
        (window.__acpWebkitFrameStripApplied || 0) + 1;
    } finally {
      screen.style.visibility = savedVisibility;
      viewport.remove();
      document.body.classList.remove('acp-spatial-live-commit');
    }
  }

  async function spatialLiveCommit(direction, from, to, commit) {
    const path = spatialSurfacePath(from, to);
    if (path.length < 2) {
      await commit();
      return;
    }

    const intermediateSurfaces = path.slice(1, -1);
    for (const surface of intermediateSurfaces) {
      await ensureMounted(surface);
    }

    const layers = [cloneCurrentSpatialLayer(from)];
    for (const surface of intermediateSurfaces) {
      layers.push(await cloneMountedSpatialLayer(surface, from));
    }

    if (window.__acpWebkitFrameStripTrial === true) {
      await frameStripLiveCommit(direction, from, to, layers, commit);
      return;
    }

    document.body.classList.add('acp-spatial-live-commit');
    layers.forEach((layer) => document.body.appendChild(layer));

    const duration = applicationTransitionDurationMs();
    const distance = path.length - 1;
    const directionSign = direction === 'reverse' ? -1 : 1;
    const animations = [];

    try {
      // The row is spatially literal: each intermediate page occupies its own
      // neighbouring viewport. A two-position jump therefore moves the whole
      // strip by 200vw, while the configured duration remains the duration of
      // the complete movement rather than being applied once per page.
      layers.forEach((layer, index) => {
        layer.style.transform = `translateX(${directionSign * index * 100}vw)`;
      });
      screen.style.transform = `translateX(${directionSign * distance * 100}vw)`;

      await commit();

      screen.getBoundingClientRect();
      layers.forEach((layer) => layer.getBoundingClientRect());
      await nextFrame();

      if (duration <= 0) return;

      const timing = {
        duration,
        easing: 'cubic-bezier(.16, .84, .24, 1)',
        fill: 'both',
      };

      layers.forEach((layer, index) => {
        const start = directionSign * index * 100;
        const end = start - (directionSign * distance * 100);
        animations.push(layer.animate(
          [
            { transform: `translateX(${start}vw)` },
            { transform: `translateX(${end}vw)` },
          ],
          timing,
        ));
      });

      animations.push(screen.animate(
        [
          { transform: `translateX(${directionSign * distance * 100}vw)` },
          { transform: 'translateX(0)' },
        ],
        timing,
      ));

      await Promise.all(
        animations.map((animation) => animation.finished.catch(() => undefined)),
      );
    } finally {
      animations.forEach((animation) => animation.cancel());
      screen.style.transform = '';
      layers.forEach((layer) => layer.remove());
      document.body.classList.remove('acp-spatial-live-commit');
    }
  }

  function captureCoverScrollOffsets() {
    return [screen, ...screen.querySelectorAll('*')]
      .map((node, index) => ({ index, top: node.scrollTop, left: node.scrollLeft }))
      .filter(({ top, left }) => top || left);
  }

  function createCoverPresentation(surface, edge, width, height, className) {
    const offsets = captureCoverScrollOffsets();
    const layer = cloneCurrentSpatialLayer(surface);
    // Keep the full-size page stationary inside a changing-width mask. A fixed
    // clone would escape overflow clipping; an auto-width child would reflow.
    const properties = {
      position: 'absolute', inset: 'auto', top: '0', [edge]: '0',
      width: `${width}px`, height: `${height}px`,
      'will-change': 'auto', animation: 'none',
    };
    Object.entries(properties).forEach(([key, value]) => {
      layer.style.setProperty(key, value, 'important');
    });
    const mask = document.createElement('div');
    mask.className = className;
    mask.setAttribute('aria-hidden', 'true');
    mask.inert = true;
    Object.assign(mask.style, {
      position: 'fixed', top: '0', [edge]: '0', zIndex: '40',
      width: `${width}px`, height: `${height}px`, overflow: 'hidden', pointerEvents: 'none',
    });
    mask.appendChild(layer);
    return {
      mask,
      restoreScroll() {
        // cloneNode does not copy scroll offsets. Apply them after insertion
        // and layout, without scrolling or reparenting the actual live page.
        layer.getBoundingClientRect();
        const nodes = [layer, ...layer.querySelectorAll('*')];
        offsets.forEach(({ index, top, left }) => {
          if (nodes[index]) {
            nodes[index].scrollTop = top;
            nodes[index].scrollLeft = left;
          }
        });
      },
    };
  }

  async function preparedPageCopyCommit(from, to, style, commit) {
    // Developer-only copies with explicit final styles and a covered handoff.
    // Grow/fade avoids native snapshot teardown; Cover retains its width masks.
    const cover = style === 'cover-reveal';
    const className = cover ? 'acp-webkit-news-cover-viewport' : 'acp-webkit-page-copy-viewport';
    const width = window.innerWidth;
    const height = window.innerHeight;
    const duration = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
      ? 0 : applicationTransitionDurationMs();
    const previousVisibility = screen.style.visibility;
    const started = performance.now();
    const state = { from, to, style, phase: 'preparing', preparationMs: null, durationMs: duration };
    if (cover) {
      window.__acpWebkitNewsLiveCoverLast = state;
      window.__acpWebkitNewsLiveCoverApplied = (window.__acpWebkitNewsLiveCoverApplied || 0) + 1;
    } else {
      window.__acpWebkitPageCopiesLast = state;
      window.__acpWebkitPageCopiesApplied = (window.__acpWebkitPageCopiesApplied || 0) + 1;
    }
    const masks = [];
    const animations = [];
    const cancelAnimations = () => {
      animations.splice(0).forEach((animation) => animation.cancel());
    };
    try {
      const outgoing = createCoverPresentation(from, cover ? 'right' : 'left', width, height, className);
      masks.push(outgoing.mask);
      document.body.appendChild(outgoing.mask);
      outgoing.restoreScroll();
      screen.style.visibility = 'hidden';
      await commit();

      screen.style.visibility = previousVisibility;
      screen.getBoundingClientRect();
      await nextFrame();
      await nextFrame();
      const incoming = createCoverPresentation(to, 'left', width, height, className);
      masks.push(incoming.mask);
      if (cover) incoming.mask.style.width = '0px';
      else incoming.mask.style.opacity = '0';
      document.body.appendChild(incoming.mask);
      incoming.restoreScroll();
      screen.style.visibility = 'hidden';
      state.preparationMs = Math.round(performance.now() - started);
      state.phase = 'animating';

      const frames = cover ? null : ordinaryTransitionFrames(style);
      const outgoingFrames = cover ? [
        { width: `${width}px`, opacity: 1, borderRadius: '0px' },
        { width: '0px', opacity: .15, borderRadius: '22px' },
      ] : frames.outgoing;
      const incomingFrames = cover ? [
        { width: '0px', opacity: .65, borderRadius: '22px' },
        { width: `${width}px`, opacity: 1, borderRadius: '0px' },
      ] : frames.incoming;
      // Underlying styles are the FINAL state. Cancelling a filled animation
      // must never uncover a clipped starting frame during the live handoff.
      Object.assign(outgoing.mask.style, outgoingFrames[1]);
      Object.assign(incoming.mask.style, incomingFrames[1]);
      if (duration > 0) {
        const timing = { duration, easing: 'cubic-bezier(.16, .84, .24, 1)', fill: 'both' };
        const completions = [];
        for (const [mask, frames] of [[outgoing.mask, outgoingFrames], [incoming.mask, incomingFrames]]) {
          const animation = mask.animate(frames, timing);
          animations.push(animation);
          // Observe cancellation immediately, including when starting the
          // second effect throws before we reach the combined completion wait.
          completions.push(animation.finished.catch(() => undefined));
        }
        const startTime = document.timeline?.currentTime;
        if (Number.isFinite(startTime)) {
          animations.forEach((animation) => { animation.startTime = startTime; });
        }
        await Promise.all(completions);
      }
      cancelAnimations();
      // Paint the real destination under the complete incoming presentation
      // before retiring either copy. The original main.screen never moves.
      screen.style.visibility = previousVisibility;
      screen.getBoundingClientRect();
      await nextFrame();
      await nextFrame();
      state.phase = 'released';
    } catch (error) {
      state.phase = 'failed';
      throw error;
    } finally {
      cancelAnimations();
      screen.style.visibility = previousVisibility;
      masks.forEach((mask) => mask.remove());
    }
  }

  async function newsLiveCoverCommit(from, commit) {
    await preparedPageCopyCommit(from, 'news', 'cover-reveal', commit);
  }

  async function stagePreparedViewTransition(from, commit) {
    // Keep async page work OUTSIDE the native update callback. The Pi can
    // expose the new live page during that work, before its snapshot animates.
    // Capture the source once and keep it covering the destination until the
    // native old-state capture has completed and invokes our synchronous swap.
    const guard = cloneCurrentSpatialLayer(from);
    guard.classList.add('acp-webkit-cover-staging-guard');
    guard.style.setProperty('will-change', 'auto');
    guard.style.setProperty('animation', 'none', 'important');
    const previousVisibility = screen.style.visibility;
    const started = performance.now();
    const state = { from, phase: 'preparing', preparationMs: null };
    window.__acpWebkitCoverStageLast = state;
    window.__acpWebkitCoverStageApplied = (window.__acpWebkitCoverStageApplied || 0) + 1;
    let released = false;
    const release = (phase) => {
      if (released) return;
      released = true;
      screen.style.visibility = previousVisibility;
      guard.remove();
      state.phase = phase;
    };
    try {
      document.body.appendChild(guard);
      screen.style.visibility = 'hidden';
      await commit();
      // Lay out and paint the hydrated real destination underneath the opaque
      // guard before asking WebKit to capture either transition state. These
      // frame ticks run before startViewTransition, so rendering is not paused.
      screen.style.visibility = previousVisibility;
      screen.getBoundingClientRect();
      await nextFrame();
      await nextFrame();
      state.phase = 'prepared';
      state.preparationMs = Math.round(performance.now() - started);
      return {
        update() { release('released'); },
        dispose() { release('aborted'); },
      };
    } catch (error) {
      release('failed');
      throw error;
    }
  }

  async function settleContentBeforeSnapshot(surface, wrapper) {
    // Bounded WebKit experiment: wait for actual content work, with an explicit
    // deadline. The staging caller owns the native capture boundary.
    const started = performance.now();
    const status = { surface, state: 'waiting', elapsedMs: 0, limitMs: 1800 };
    window.__acpWebkitContentReadyLast = status;
    let timer;
    const work = async () => {
      if (surface === 'weather') {
        if (!window.ACPWeatherForecast?.ready || !window.ACPWeatherForecastCompletion?.ready) {
          throw new Error('Weather readiness modules unavailable');
        }
        const [updated] = await Promise.all([
          window.ACPWeatherSurface.refresh(),
          window.ACPWeatherForecast.ready,
          window.ACPWeatherForecastCompletion.ready,
        ]);
        return {
          refreshUpdated: updated === true,
          forecastSettled: wrapper.querySelector('.weather-detail-page')?.dataset.acpForecastSettled === 'true',
        };
      }
      const updated = await window.ACPNewsSurface.refresh();
      const logo = wrapper.querySelector('[data-news-logo]');
      let logoDecoded = null;
      if (logo && !logo.hidden && typeof logo.decode === 'function') {
        logoDecoded = await logo.decode().then(() => true, () => false);
      }
      return { refreshUpdated: updated === true, logoDecoded };
    };
    try {
      const result = await Promise.race([
        work().then(
          (detail) => ({ state: 'settled', ...detail }),
          (error) => ({ state: 'failed', error: String(error?.message || error) }),
        ),
        new Promise((resolve) => {
          timer = window.setTimeout(() => resolve({ state: 'timed-out' }), status.limitMs);
        }),
      ]);
      Object.assign(status, result, { elapsedMs: Math.round(performance.now() - started) });
      // Resolve layout under the preparation cover. The caller permits paint
      // ticks before starting native capture, outside its update callback.
      screen.getBoundingClientRect();
    } finally {
      window.clearTimeout(timer);
    }
  }

  surfaces.forEach((surface) => {
    surfaceHost.register(surface, {
      async prepare({ from } = {}) {
        const record = await ensureMounted(surface);
        let activatedBeforeSnapshot = false;

        const publishActivation = (options = {}) => {
          document.dispatchEvent(new CustomEvent('acp:surface-activated', {
            detail: {
              surface,
              source: String(options.source || 'application-surface'),
            },
          }));
        };

        return {
          title: record.title,
          commit() {
            commitSurface(surface);
          },
          async spatialCommit({ direction, commit } = {}) {
            const expectedDirection = spatialSurfaceDirection(from, surface);
            if (!expectedDirection || direction !== expectedDirection) {
              await commit();
              return;
            }
            await spatialLiveCommit(direction, from, surface, commit);
          },
          async liveCommit({ commit } = {}) {
            await ordinaryLiveCommit(from, commit);
          },
          ...(window.__acpWebkitGrowFadeCopyTrial === true && applicationTransitionStyle() === 'grow-fade'
            ? { copyCommit: ({ commit }) => preparedPageCopyCommit(from, surface, 'grow-fade', commit) }
            : {}),
          ...(surface === 'news' && window.__acpWebkitNewsLiveCoverTrial === true
            && applicationTransitionStyle() === 'cover-reveal'
            ? { coverCommit: ({ commit }) => newsLiveCoverCommit(from, commit) }
            : {}),
          async stageViewTransition({ commit } = {}) {
            if (window.__acpWebkitContentReadyTrial !== true) return null;
            return stagePreparedViewTransition(from, commit);
          },
          async beforeSnapshot({ options = {} } = {}) {
            if (window.__acpWebkitContentReadyTrial === true && ['weather', 'news'].includes(surface)) {
              await ensureScripts(record.scripts);
              publishActivation(options);
              activatedBeforeSnapshot = true;
              await settleContentBeforeSnapshot(surface, record.wrapper);
              return;
            }
            if (surface !== 'airplay') return;

            // AirPlay's segmented glance row and measured hero geometry are
            // script-owned. Load and settle them before View Transition captures
            // the incoming snapshot so the transition never freezes raw markup.
            await ensureScripts(record.scripts);
            const ready = window.ACPAirPlayHydration?.waitForReady?.(1400)
              || Promise.resolve();
            publishActivation(options);
            activatedBeforeSnapshot = true;
            await ready;
          },
          async activate({ options = {} } = {}) {
            await ensureScripts(record.scripts);
            await syncLogicalMode(surface);
            if (!activatedBeforeSnapshot) publishActivation(options);
          },
        };
      },
    });
  });

  initialMount();

  window.addEventListener('popstate', () => {
    const target = surfaceFromPath();
    if (!target || target === surfaceHost.activeSurface()) return;
    void surfaceHost.navigate(target, {
      history: false,
      source: 'browser-history',
    });
  });

  async function captureSpatialLayers(surfacesToCapture, restoreSurface, options = {}) {
    const requested = Array.isArray(surfacesToCapture)
      ? surfacesToCapture.map((value) => String(value || '').toLowerCase()).filter(Boolean)
      : [];
    const currentFirst = options.currentFirst === true;
    const layers = [];

    for (let index = 0; index < requested.length; index += 1) {
      const surface = requested[index];
      if (index === 0 && currentFirst) layers.push(cloneCurrentSpatialLayer(surface));
      else layers.push(await cloneMountedSpatialLayer(surface, restoreSurface));
    }
    return layers;
  }

  window.ACPApplicationSurfaces = {
    mounted: (surface) => mounted.has(String(surface || '').toLowerCase()),
    surfaces: () => [...mounted.keys()],
    captureSpatialLayers,
    screen: () => screen,
  };
})();
