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
    // changes main.screen geometry by body mode (Weather changes the grid row
    // template). Freeze the outgoing screen's *current* computed layout so the
    // Clock clone cannot relayout into Weather geometry mid-animation.
    [
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

  const spatialSurfaceOrder = ['clock', 'weather', 'news', 'airplay'];

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

  function cloneMountedSpatialLayer(surface, restoreSurface) {
    const bodyState = captureBodyPresentationState();
    try {
      // Intermediate row members are presentation-only captures. Never call
      // commitSurface() here: restoring an AirPlay source through the real
      // commit path marks its session unresolved and destroys the exact
      // now-playing/route-ready geometry that the outgoing clone must preserve.
      presentMountedSurface(surface);
      applyBodyPresentationSurface(surface);
      screen.getBoundingClientRect();
      return prepareSpatialLayer(screen.cloneNode(true), surface);
    } finally {
      presentMountedSurface(restoreSurface);
      restoreBodyPresentationState(bodyState);
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
    intermediateSurfaces.forEach((surface) => {
      layers.push(cloneMountedSpatialLayer(surface, from));
    });

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
          async beforeSnapshot({ options = {} } = {}) {
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

  window.ACPApplicationSurfaces = {
    mounted: (surface) => mounted.has(String(surface || '').toLowerCase()),
    surfaces: () => [...mounted.keys()],
  };
})();
