// Run the real preparation hook and content modules with controlled I/O.
// This checks ordering/completion and bounded fallback, never rendered pixels.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const read = (name) => fs.readFileSync(path.join(__dirname, '../../app/static/js', name), 'utf8');
const source = read('acp-application-surfaces.js');
const preparation = source.slice(source.indexOf('  function captureCoverScrollOffsets('),
  source.indexOf('  initialMount();'));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
};
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };

function fixture({ enabled = true, liveCover = false, duration = 2000 } = {}) {
  const calls = [], registry = new Map(), timers = new Map();
  const refresh = deferred(), forecast = deferred(), completion = deferred(), image = deferred();
  let now = 0, timerId = 0;
  const logo = { hidden: false, decode: () => { calls.push('decode'); return image.promise; } };
  const page = { dataset: { acpForecastSettled: 'true' } };
  const wrapper = { querySelector: (selector) => selector === '[data-news-logo]' ? logo : page };
  const guards = [], animations = [];
  const body = { children: [], appendChild(node) { this.children.push(node); } };
  function element() {
    const node = { children: [], style: { setProperty(key, value) { this[key] = value; } },
      classList: { add() {} }, setAttribute() {},
      appendChild(child) { this.children.push(child); child.parentNode = this; },
      querySelectorAll: () => [], getBoundingClientRect: () => ({}),
      animate(frames, timing) {
        const done = deferred();
        const animation = { frames, timing, finished: done.promise, resolve: done.resolve, reject: done.reject,
          cancel() {
            this.cancelled = true;
            this.cancelWidth = node.style.width;
            this.cancelVisibility = screen.style.visibility;
            done.reject(new Error('animation cancelled'));
          } };
        animations.push(animation);
        return animation;
      },
      remove() {
        const children = this.parentNode?.children || body.children;
        const index = children.indexOf(this);
        if (index >= 0) children.splice(index, 1);
      } };
    return node;
  }
  const scroller = { scrollTop: 0, scrollLeft: 0 };
  const screen = { style: { visibility: '' }, scrollTop: 0, scrollLeft: 0,
    querySelectorAll: () => [scroller],
    getBoundingClientRect: () => { calls.push('layout'); return {}; } };
  const window = {
    __acpWebkitContentReadyTrial: enabled,
    __acpWebkitNewsLiveCoverTrial: liveCover,
    innerWidth: 853, innerHeight: 480,
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
    document: { body, createElement: element, timeline: { currentTime: 50 },
      dispatchEvent: (event) => calls.push(event.type) },
    CustomEvent: class { constructor(type, { detail }) { this.type = type; this.detail = detail; } },
    surfaces: new Set(['clock', 'weather', 'news', 'settings', 'airplay']),
    surfaceHost: { register: (surface, lifecycle) => registry.set(surface, lifecycle) },
    screen,
    cloneCurrentSpatialLayer: (surface) => {
      const node = element();
      node.surface = surface;
      node.scroller = { scrollTop: 0, scrollLeft: 0 };
      node.querySelectorAll = () => [node.scroller];
      guards.push(node);
      return node;
    },
    nextFrame: async () => { calls.push('paint-frame'); },
    applicationTransitionDurationMs: () => duration,
    commitSurface: () => { calls.push('commit'); },
    ensureMounted: async () => ({ wrapper, title: 'Page', scripts: ['page.js'] }),
    ensureScripts: async () => { calls.push('scripts'); },
    syncLogicalMode: async () => { calls.push('logical-mode'); },
  };
  vm.createContext(context);
  vm.runInContext(preparation, context);
  return { window, registry, calls, timers, refresh, forecast, completion, image,
    context, guards, body, screen, scroller, animations,
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

test('staging keeps the source cover through async work and two paint ticks; native swap is synchronous', async () => {
  const f = fixture();
  const content = deferred();
  const prepared = await f.registry.get('news').prepare({ from: 'weather' });
  let commits = 0;
  const pending = prepared.stageViewTransition({ commit: async () => {
    commits++;
    assert.equal(f.body.children.length, 1, 'source covered before commit');
    assert.equal(f.screen.style.visibility, 'hidden');
    await content.promise;
  } });
  await flush();
  assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'preparing');
  assert.equal(f.calls.includes('paint-frame'), false);
  content.resolve();
  const stage = await pending;
  assert.equal(f.body.children.length, 1, 'guard remains for native old-state capture');
  assert.equal(f.screen.style.visibility, '');
  assert.equal(f.calls.filter((x) => x === 'paint-frame').length, 2);
  assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'prepared');
  assert.equal(stage.update(), undefined, 'no async content work in native callback');
  assert.equal(commits, 1);
  assert.equal(f.body.children.length, 0);
  stage.dispose();
  assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'released');
  assert.equal(f.window.__acpWebkitCoverStageApplied, 1);
});

test('a failed staging commit removes its guard and restores prior visibility', async () => {
  const f = fixture();
  f.screen.style.visibility = 'hidden';
  const prepared = await f.registry.get('weather').prepare({ from: 'clock' });
  await assert.rejects(prepared.stageViewTransition({ commit: async () => {
    throw new Error('content failed');
  } }), /content failed/);
  assert.equal(f.body.children.length, 0);
  assert.equal(f.screen.style.visibility, 'hidden');
  assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'failed');
});

test('an interrupted staging paint tick also frees the source cover', async () => {
  const f = fixture();
  f.context.nextFrame = async () => { throw new Error('paint interrupted'); };
  const prepared = await f.registry.get('news').prepare({ from: 'weather' });
  await assert.rejects(prepared.stageViewTransition({ commit: async () => {} }), /paint interrupted/);
  assert.equal(f.body.children.length, 0);
  assert.equal(f.screen.style.visibility, '');
});

test('default preparation adds no staging guard or extra commit without explicit opt-in', async () => {
  const f = fixture({ enabled: false });
  const prepared = await f.registry.get('news').prepare({ from: 'weather' });
  assert.equal(await prepared.stageViewTransition({ commit: () => assert.fail('unexpected commit') }), null);
  assert.equal(f.guards.length, 0);
  assert.equal(f.window.__acpWebkitCoverStageApplied, undefined);
});

function installRealHost(f, { throwNative = false } = {}) {
  const classes = new Set(['mode-clock']);
  f.body.dataset = { activePage: 'clock' };
  f.body.classList = { add: (name) => classes.add(name), remove: (name) => classes.delete(name),
    contains: (name) => classes.has(name), [Symbol.iterator]: () => classes.values() };
  f.context.document.documentElement = { dataset: { transitionStyle: 'cover-reveal' },
    classList: { contains: () => false } };
  f.context.document.querySelector = (selector) => selector === 'main.screen' ? f.screen : null;
  f.context.document.querySelectorAll = () => [];
  f.window.location = { pathname: '/clock' };
  const updated = deferred(), finished = deferred();
  let nativeUpdate = null;
  f.context.document.startViewTransition = (update) => {
    f.calls.push('native-start');
    if (throwNative) throw new Error('native start failed');
    nativeUpdate = update;
    return { updateCallbackDone: updated.promise, finished: finished.promise };
  };
  vm.runInContext(read('acp-surface-host.js'), f.context);
  f.context.surfaceHost = f.window.ACPSurfaceHost;
  vm.runInContext(preparation, f.context);
  return { updated, finished, nativeUpdate: () => nativeUpdate };
}

test('the real host commits and hydrates behind the guard BEFORE native capture, exactly once', async () => {
  const f = fixture({ liveCover: true });
  const native = installRealHost(f);
  const navigation = f.window.ACPSurfaceHost.navigate('weather', { history: false });
  await flush();
  assert.equal(f.body.dataset.activePage, 'weather');
  assert.equal(f.screen.style.visibility, 'hidden');
  assert.equal(f.body.children.length, 1);
  assert.equal(native.nativeUpdate(), null, 'native capture waits for content');
  f.refresh.resolve(true); f.forecast.resolve(); f.completion.resolve();
  await flush();
  assert.equal(typeof native.nativeUpdate(), 'function');
  assert.equal(f.calls.filter((x) => x === 'commit').length, 1);
  assert.equal(f.calls.filter((x) => x === 'acp:surface-activated').length, 1);
  assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'prepared');
  assert.equal(native.nativeUpdate()(), undefined);
  assert.equal(f.body.children.length, 0);
  native.updated.resolve();
  await flush();
  assert.equal(f.window.ACPSurfaceHost.isTransitioning(), true);
  native.finished.resolve();
  assert.equal((await navigation).accepted, true);
  assert.equal(f.calls.filter((x) => x === 'commit').length, 1);
  assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'released');
});

test('background animate:false navigation bypasses native capture and staging even with the trial enabled', async () => {
  const f = fixture();
  const native = installRealHost(f);
  const navigation = f.window.ACPSurfaceHost.navigate('weather', { history: false, animate: false });
  f.refresh.resolve(true); f.forecast.resolve(); f.completion.resolve();
  assert.equal((await navigation).accepted, true);
  assert.equal(native.nativeUpdate(), null);
  assert.equal(f.guards.length, 0);
  assert.equal(f.window.__acpWebkitCoverStageApplied, undefined);
  assert.equal(f.calls.filter((x) => x === 'commit').length, 1);
});

for (const failure of ['throw', 'reject-update']) {
  test(`the real host releases its prepared cover when native transition fails: ${failure}`, async () => {
    const f = fixture();
    const native = installRealHost(f, { throwNative: failure === 'throw' });
    const navigation = f.window.ACPSurfaceHost.navigate('weather', { history: false });
    f.refresh.resolve(true); f.forecast.resolve(); f.completion.resolve();
    await flush();
    if (failure === 'reject-update') native.updated.reject(new Error('native update failed'));
    assert.equal((await navigation).accepted, false);
    assert.equal(f.body.children.length, 0);
    assert.equal(f.screen.style.visibility, '');
    assert.equal(f.window.__acpWebkitCoverStageLast.phase, 'aborted');
    assert.equal(f.window.ACPSurfaceHost.isTransitioning(), false);
  });
}

test('live Cover hook is explicitly opt-in and restricted to News', async () => {
  const normal = fixture();
  assert.equal((await normal.registry.get('news').prepare()).coverCommit, undefined);
  const trial = fixture({ liveCover: true });
  for (const surface of ['clock', 'weather', 'airplay', 'settings']) {
    assert.equal((await trial.registry.get(surface).prepare()).coverCommit, undefined);
  }
  assert.equal(typeof (await trial.registry.get('news').prepare()).coverCommit, 'function');
  assert.equal(trial.body.children.length, 0, 'preparing the lifecycle alone adds no presentation');
});

test('News uses stationary full-size copies, preserves scroll and covers both async handoffs', async () => {
  const f = fixture({ liveCover: true });
  const parent = {};
  f.screen.parentNode = parent;
  f.scroller.scrollTop = 42; f.scroller.scrollLeft = 13;
  const content = deferred();
  const prepared = await f.registry.get('news').prepare({ from: 'weather' });
  let commits = 0;
  const pending = prepared.coverCommit({ commit: async () => {
    commits++;
    assert.equal(f.body.children.length, 1);
    assert.equal(f.screen.style.visibility, 'hidden');
    await content.promise;
    f.scroller.scrollTop = 180; f.scroller.scrollLeft = 0;
  } });
  await flush();
  assert.equal(f.window.__acpWebkitNewsLiveCoverLast.phase, 'preparing');
  assert.equal(f.animations.length, 0);
  const oldMask = f.body.children[0];
  assert.equal(oldMask.style.width, '853px');
  assert.equal(oldMask.style.right, '0');
  assert.equal(oldMask.style.overflow, 'hidden');
  assert.equal(oldMask.inert, true);
  assert.equal(f.guards[0].style.position, 'absolute');
  assert.equal(f.guards[0].style.right, '0');
  assert.equal(f.guards[0].scroller.scrollTop, 42);
  assert.equal(f.guards[0].scroller.scrollLeft, 13);
  content.resolve();
  await flush();
  assert.equal(f.animations.length, 2);
  assert.equal(f.window.__acpWebkitNewsLiveCoverLast.phase, 'animating');
  assert.equal(f.screen.style.visibility, 'hidden');
  assert.equal(f.screen.parentNode, parent, 'the real main remains mounted');
  assert.equal(f.guards[1].surface, 'news');
  assert.equal(f.guards[1].style.left, '0');
  assert.equal(f.guards[1].scroller.scrollTop, 180);
  for (const copy of f.guards) {
    assert.equal(copy.style.width, '853px');
    assert.equal(copy.style.height, '480px');
    assert.equal(copy.style.transform, undefined, 'no moving or scaling page');
  }
  assert.equal(f.body.children[1].style.left, '0');
  for (const animation of f.animations) {
    assert.equal(animation.timing.duration, 2000);
    assert.equal(animation.startTime, 50, 'both masks share the document clock');
    assert.equal(animation.frames[0].clipPath, undefined);
    animation.resolve();
  }
  await pending;
  assert.equal(commits, 1);
  assert.equal(f.animations[0].cancelWidth, '0px');
  assert.equal(f.animations[1].cancelWidth, '853px');
  assert.ok(f.animations.every((animation) => animation.cancelVisibility === 'hidden'));
  assert.equal(f.calls.filter((call) => call === 'paint-frame').length, 4);
  assert.equal(f.body.children.length, 0);
  assert.equal(f.screen.style.visibility, '');
  assert.equal(f.screen.parentNode, parent);
  assert.equal(f.window.__acpWebkitNewsLiveCoverLast.phase, 'released');
});

test('real host News entry bypasses native capture and stays busy until copy cleanup', async () => {
  const f = fixture({ liveCover: true });
  const native = installRealHost(f);
  const pending = f.window.ACPSurfaceHost.navigate('news', { history: false });
  f.refresh.resolve(true); f.image.resolve();
  await flush();
  assert.equal(native.nativeUpdate(), null);
  assert.equal(f.window.__acpWebkitCoverStageApplied, undefined);
  assert.equal(f.window.__acpWebkitNewsLiveCoverApplied, 1);
  assert.equal(f.window.ACPSurfaceHost.isTransitioning(), true);
  assert.equal(f.calls.includes('acp:surface-settled'), false);
  f.animations.forEach((animation) => animation.resolve());
  assert.equal((await pending).accepted, true);
  assert.equal(f.calls.filter((call) => call === 'commit').length, 1);
  assert.equal(f.calls.filter((call) => call === 'acp:surface-activated').length, 1);
  assert.equal(f.calls.at(-1), 'acp:surface-settled');
  assert.equal(f.body.children.length, 0);
  assert.equal(f.window.ACPSurfaceHost.isTransitioning(), false);
});

test('real host animate:false News entry bypasses the copy renderer', async () => {
  const f = fixture({ liveCover: true });
  const native = installRealHost(f);
  const pending = f.window.ACPSurfaceHost.navigate('news', { history: false, animate: false });
  f.refresh.resolve(true); f.image.resolve();
  assert.equal((await pending).accepted, true);
  assert.equal(native.nativeUpdate(), null);
  assert.equal(f.window.__acpWebkitNewsLiveCoverApplied, undefined);
  assert.equal(f.guards.length, 0);
  assert.equal(f.animations.length, 0);
});

for (const failure of ['commit', 'paint', 'second-animation']) {
  test(`News copy failure restores visibility and removes all masks: ${failure}`, async () => {
    const f = fixture({ liveCover: true });
    f.screen.style.visibility = 'visible';
    if (failure === 'paint') f.context.nextFrame = async () => { throw new Error('paint'); };
    if (failure === 'second-animation') {
      const create = f.context.document.createElement;
      f.context.document.createElement = () => {
        const mask = create();
        const animate = mask.animate;
        mask.animate = (...args) => {
          if (f.animations.length) throw new Error('second-animation');
          return animate(...args);
        };
        return mask;
      };
    }
    const prepared = await f.registry.get('news').prepare({ from: 'weather' });
    await assert.rejects(prepared.coverCommit({ commit: async () => {
      if (failure === 'commit') throw new Error('commit');
    } }), new RegExp(failure));
    assert.equal(f.screen.style.visibility, 'visible');
    assert.equal(f.body.children.length, 0);
    assert.ok(f.animations.every((animation) => animation.cancelled));
    assert.equal(f.window.__acpWebkitNewsLiveCoverLast.phase, 'failed');
  });
}

test('cancelled mask animations still hand off their final styles and clean up', async () => {
  const f = fixture({ liveCover: true });
  const prepared = await f.registry.get('news').prepare({ from: 'clock' });
  const pending = prepared.coverCommit({ commit: async () => {} });
  await flush();
  f.animations.forEach((animation) => animation.reject(new Error('cancelled')));
  await pending;
  assert.equal(f.animations[1].cancelWidth, '853px');
  assert.equal(f.body.children.length, 0);
  assert.equal(f.screen.style.visibility, '');
});

test('zero duration and reduced motion release copies without starting animations', async () => {
  for (const duration of [0, 2000]) {
    const f = fixture({ liveCover: true, duration });
    f.window.matchMedia = () => ({ matches: duration > 0 });
    const prepared = await f.registry.get('news').prepare({ from: 'weather' });
    await prepared.coverCommit({ commit: async () => {} });
    assert.equal(f.animations.length, 0);
    assert.equal(f.body.children.length, 0);
    assert.equal(f.screen.style.visibility, '');
    assert.equal(f.window.__acpWebkitNewsLiveCoverLast.durationMs, 0);
    assert.equal(f.window.__acpWebkitNewsLiveCoverLast.phase, 'released');
  }
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
  f.context.document.hidden = true;
  assert.equal(await f.window.ACPWeatherSurface.refresh(), false);
  assert.equal(f.requests.length, 2, 'a hidden page starts no further request');
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
  f.context.document.hidden = true;
  assert.equal(await f.window.ACPNewsSurface.refresh(), false);
  assert.equal(f.requests.length, 2, 'a hidden page starts no further request');
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
