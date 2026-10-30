(() => {
  if (window.ACPWorkspaceTopology) return;

  // Shell-owned product order. Renderer type is deliberately part of the
  // topology contract: spatial position must survive Plexamp's later move from
  // the persistent browser player to the native Wayland application.
  const entries = Object.freeze([
    Object.freeze({ id: 'clock', route: '/clock', label: 'Home', renderer: 'acp' }),
    Object.freeze({ id: 'weather', route: '/weather', label: 'Weather', renderer: 'acp' }),
    Object.freeze({ id: 'news', route: '/news', label: 'News', renderer: 'acp' }),
    Object.freeze({ id: 'airplay', route: '/airplay', label: 'AirPlay', renderer: 'acp' }),
    Object.freeze({ id: 'plexamp', route: '/plexamp', label: 'Plexamp', renderer: 'plexamp' }),
  ]);

  // Reserved product order once Astronomy exists. Keep this here as topology
  // metadata only; Astronomy is not routable/active until its own feature gate.
  const futureOrder = Object.freeze([
    'clock',
    'weather',
    'astronomy',
    'news',
    'airplay',
    'plexamp',
  ]);

  const byId = new Map(entries.map((entry) => [entry.id, entry]));
  const byRoute = new Map(entries.map((entry) => [entry.route, entry]));

  function normalise(value) {
    const raw = String(value || '').trim().toLowerCase();
    if (!raw) return '';
    if (byId.has(raw)) return raw;
    return byRoute.get(raw)?.id || '';
  }

  function entry(value) {
    return byId.get(normalise(value)) || null;
  }

  function route(value) {
    return entry(value)?.route || '';
  }

  function index(value) {
    const id = normalise(value);
    return id ? entries.findIndex((item) => item.id === id) : -1;
  }

  function direction(from, to) {
    const fromIndex = index(from);
    const toIndex = index(to);
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return '';
    return toIndex > fromIndex ? 'forward' : 'reverse';
  }

  function path(from, to) {
    const fromIndex = index(from);
    const toIndex = index(to);
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return [];

    const step = toIndex > fromIndex ? 1 : -1;
    const result = [];
    for (let current = fromIndex; ; current += step) {
      result.push(entries[current]);
      if (current === toIndex) break;
    }
    return result;
  }

  function renderer(value) {
    return entry(value)?.renderer || '';
  }

  function acpSurfaceOrder() {
    return entries
      .filter((item) => item.renderer === 'acp')
      .map((item) => item.id);
  }

  function isRoute(value) {
    return byRoute.has(String(value || '').trim().toLowerCase());
  }

  window.ACPWorkspaceTopology = Object.freeze({
    entries,
    futureOrder,
    normalise,
    entry,
    route,
    index,
    direction,
    path,
    renderer,
    acpSurfaceOrder,
    isRoute,
  });
})();
