// Run the real preparation hook and content modules with controlled I/O.
// This checks ordering/completion and bounded fallback, never rendered pixels.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const read = (name) => fs.readFileSync(path.join(__dirname, '../../app/static/js', name), 'utf8');
const source = read('acp-application-surfaces.js');
const preparation = source.slice(source.indexOf('  async function settleContentBeforeSnapshot('),
  source.indexOf('  initialMount();'));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
};
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };

function fixture({ enabled = true } = {}) {
  const calls = [], registry = new Map(), timers = new Map();
  const refresh = deferred(), forecast = deferred(), completion = deferred(), image = deferred();
  let now = 0, timerId = 0;
  const logo = { hidden: false, decode: () => { calls.push('decode'); return image.promise; } };
  const page = { dataset: { acpForecastSettled: 'true' } };
  const wrapper = { querySelector: (selector) => selector === '[data-news-logo]' ? logo : page };
  const window = {
    __acpWebkitContentReadyTrial: enabled,
    ACPWeatherSurface: { refresh: () => { calls.push('weather-refresh'); return refresh.promise; } },
    ACPNewsSurface: { refresh: () => { calls.push('news-refresh'); return refresh.promise; } },
    ACPWeatherForecast: { ready: forecast.promise },
    ACPWeatherForecastCompletion: { ready: completion.promise },
    ACPAirPlayHydration: { waitForReady: async () => { calls.push('airplay-ready'); } },
    setTimeout: (callback, ms) => { const id = ++timerId; timers.set(id, { callback, ms }); return id; },
    clearTimeout: (id) => timers.delete(id),
  };
  const context = {
    window, performance: { now: () => now },
    document: { dispatchEvent: (event) => calls.push(event.type) },
    CustomEvent: class { constructor(type, { detail }) { this.type = type; this.detail = detail; } },
    surfaces: new Set(['clock', 'weather', 'news', 'settings', 'airplay']),
    surfaceHost: { register: (surface, lifecycle) => registry.set(surface, lifecycle) },
    screen: { getBoundingClientRect: () => { calls.push('layout'); return {}; } },
    ensureMounted: async () => ({ wrapper, title: 'Page', scripts: ['page.js'] }),
    ensureScripts: async () => { calls.push('scripts'); },
    syncLogicalMode: async () => { calls.push('logical-mode'); },
  };
  vm.createContext(context);
  vm.runInContext(preparation, context);
  return { window, registry, calls, timers, refresh, forecast, completion, image,
    tick: (value) => { now = value; } };
}

test('Weather waits for refresh, forecast and completion before the incoming snapshot', async () => {
  const f = fixture();
  const prepared = await f.registry.get('weather').prepare({ from: 'clock' });
  let done = false;
  const pending = prepared.beforeSnapshot().then(() => { done = true; });
  await flush();
  assert.deepEqual(f.calls, ['scripts', 'acp:surface-activated', 'weather-refresh']);
  f.refresh.resolve(true); f.forecast.resolve();
  await flush();
  assert.equal(done, false, 'legacy forecast completion still owns content work');
  f.tick(750); f.completion.resolve();
  await pending;
  const status = f.window.__acpWebkitContentReadyLast;
  assert.equal(status.state, 'settled');
  assert.equal(status.forecastSettled, true);
  assert.equal(status.refreshUpdated, true);
  assert.equal(status.elapsedMs, 750);
  assert.equal(f.calls.at(-1), 'layout');
  assert.equal(f.timers.size, 0);
  await prepared.activate();
  assert.equal(f.calls.filter((x) => x === 'acp:surface-activated').length, 1,
    'normal activate must not start a second content refresh');
});

test('News waits for its refresh and branding decode; failed images do not trap navigation', async () => {
  const f = fixture();
  const prepared = await f.registry.get('news').prepare({ from: 'weather' });
  let done = false;
  const pending = prepared.beforeSnapshot().then(() => { done = true; });
  await flush();
  f.refresh.resolve(true);
  await flush();
  assert.ok(f.calls.includes('decode'));
  assert.equal(done, false);
  f.image.reject(new Error('logo unavailable'));
  await pending;
  assert.equal(f.window.__acpWebkitContentReadyLast.state, 'settled');
  assert.equal(f.window.__acpWebkitContentReadyLast.logoDecoded, false);
  await prepared.activate();
  assert.equal(f.calls.filter((x) => x === 'acp:surface-activated').length, 1);
});

test('a stalled provider exits at the deadline and late completion cannot claim success', async () => {
  const f = fixture();
  const prepared = await f.registry.get('weather').prepare({ from: 'clock' });
  const pending = prepared.beforeSnapshot();
  await flush();
  const deadline = [...f.timers.values()][0];
  assert.equal(deadline.ms, 1800);
  f.tick(1800); deadline.callback();
  await pending;
  const status = f.window.__acpWebkitContentReadyLast;
  assert.equal(status.state, 'timed-out');
  assert.equal(f.timers.size, 0);
  f.refresh.resolve(true); f.forecast.resolve(); f.completion.resolve();
  await flush();
  assert.equal(status.state, 'timed-out');
  assert.equal(status.forecastSettled, undefined);
});

test('readiness failures are explicit and release the native update callback', async () => {
  const f = fixture();
  const prepared = await f.registry.get('weather').prepare({ from: 'clock' });
  const pending = prepared.beforeSnapshot();
  await flush();
  f.forecast.reject(new Error('forecast module failed'));
  await pending;
  assert.equal(f.window.__acpWebkitContentReadyLast.state, 'failed');
  assert.match(f.window.__acpWebkitContentReadyLast.error, /forecast module failed/);
  assert.equal(f.timers.size, 0);
});

test('default Weather/News activation ordering stays unchanged without the opt-in', async () => {
  for (const surface of ['weather', 'news']) {
    const f = fixture({ enabled: false });
    const prepared = await f.registry.get(surface).prepare({ from: 'clock' });
    await prepared.beforeSnapshot();
    assert.deepEqual(f.calls, []);
    await prepared.activate();
    assert.deepEqual(f.calls, ['scripts', 'logical-mode', 'acp:surface-activated']);
    assert.equal(f.window.__acpWebkitContentReadyLast, undefined);
  }
});

test('the opt-in leaves Clock and the existing AirPlay hydration path alone', async () => {
  const f = fixture();
  await (await f.registry.get('clock').prepare({ from: 'news' })).beforeSnapshot();
  assert.deepEqual(f.calls, []);
  const airplay = await f.registry.get('airplay').prepare({ from: 'clock' });
  await airplay.beforeSnapshot();
  await airplay.activate();
  assert.equal(f.calls.filter((x) => x === 'airplay-ready').length, 1);
  assert.equal(f.calls.filter((x) => x === 'acp:surface-activated').length, 1);
  assert.equal(f.window.__acpWebkitContentReadyLast, undefined);
});

function moduleFixture(surface) {
  const requests = [], listeners = new Map();
  const window = {
    addEventListener() {}, setTimeout: () => 1, clearTimeout() {},
    setInterval: () => 1, clearInterval() {}, requestAnimationFrame: () => 1,
  };
  const context = {
    window, document: { body: { dataset: { activePage: surface } }, hidden: false,
      querySelector: () => null,
      addEventListener: (type, callback) => listeners.set(type, callback),
    },
    fetch: () => { const request = deferred(); requests.push(request); return request.promise; },
  };
  vm.createContext(context);
  return { context, window, requests, listeners };
}

test('Weather activation and snapshot waiter join the same refresh and allow retry', async () => {
  const f = moduleFixture('weather');
  vm.runInContext(read('weather-surface.js'), f.context);
  f.listeners.get('acp:surface-activated')({ detail: { surface: 'weather' } });
  const first = f.window.ACPWeatherSurface.refresh();
  assert.equal(first, f.window.ACPWeatherSurface.refresh());
  assert.equal(f.requests.length, 1);
  assert.equal(f.window.ACPWeatherSurface.isRefreshing(), true);
  f.requests[0].resolve({ ok: false, status: 503 });
  assert.equal(await first, false);
  assert.equal(f.window.ACPWeatherSurface.isRefreshing(), false);
  const retry = f.window.ACPWeatherSurface.refresh();
  assert.notEqual(first, retry);
  assert.equal(f.requests.length, 2);
  f.requests[1].reject(new Error('offline'));
  assert.equal(await retry, false);
});

test('News script load, activation and snapshot waiter share one request then permit refresh', async () => {
  const f = moduleFixture('news');
  vm.runInContext(read('news.js'), f.context);
  f.listeners.get('acp:surface-activated')({ detail: { surface: 'news' } });
  const first = f.window.ACPNewsSurface.refresh();
  assert.equal(first, f.window.ACPNewsSurface.refresh());
  assert.equal(f.requests.length, 1);
  f.requests[0].resolve({ ok: true, json: async () => ({ ok: true, settings: { enabled_categories: [] } }) });
  assert.equal(await first, true);
  const retry = f.window.ACPNewsSurface.refresh();
  assert.notEqual(first, retry);
  assert.equal(f.requests.length, 2);
  f.requests[1].reject(new Error('offline'));
  assert.equal(await retry, false);
});

test('forecast readiness resolves only after the provider result is handled, including disabled mode', async () => {
  const f = moduleFixture('weather');
  const anchor = { dataset: {} };
  f.context.document.querySelector = (selector) => selector === '.weather-detail-page' ? anchor : null;
  vm.runInContext(read('weather-forecast.js'), f.context);
  let done = false;
  const ready = f.window.ACPWeatherForecast.ready.then(() => { done = true; });
  await flush();
  assert.equal(done, false);
  f.requests[0].resolve({ ok: true, json: async () => ({ enabled: false }) });
  await ready;
  assert.equal(anchor.dataset.acpForecastSettled, 'true');
});

test('forecast completion settles without extra fetches when the optional console is unavailable', async () => {
  const f = moduleFixture('weather');
  const anchor = { dataset: {} };
  let wake;
  f.context.document.readyState = 'complete';
  f.context.document.querySelector = (selector) => {
    if (selector === '.weather-detail-page') return anchor;
    if (selector === 'script[data-rain-history-scroll-loader]') return {};
    return null;
  };
  f.window.setTimeout = (callback) => { wake = callback; return 1; };
  vm.runInContext(read('weather-forecast-completion.js'), f.context);
  anchor.dataset.acpForecastSettled = 'true';
  wake();
  await f.window.ACPWeatherForecastCompletion.ready;
  assert.equal(f.requests.length, 0);
});
