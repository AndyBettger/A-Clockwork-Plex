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

  function commitSurface(surface) {
    if (surface === 'airplay') markAirPlayUnresolved();

    mounted.forEach((record, name) => {
      record.wrapper.hidden = name !== surface;
    });
  }

  surfaces.forEach((surface) => {
    surfaceHost.register(surface, {
      async prepare() {
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
