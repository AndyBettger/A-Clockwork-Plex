// Exercise actual injected scripts with state/API doubles; no paint claim.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname,
  '../../scripts/try-webkit-gtk-shell.py'), 'utf8');
function script(name) {
  const marker = name + ' = r"""\n';
  const start = source.indexOf(marker);
  assert.ok(start >= 0);
  return source.slice(start + marker.length, source.indexOf('\n"""', start + marker.length));
}
const profile = script('COVER_REVEAL_TRIAL_SCRIPT');
const bridge = script('SURFACE_TRANSITION_TRIAL_SCRIPT');
const metrics = script('SURFACE_TRANSITION_METRICS_SCRIPT');
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
function fixture({ hasBridge = true, hasAPI = true } = {}) {
  const flags = new Set();
  const observers = [];
  const calls = [];
  let clock = 100;
  const dataset = { transitionStyle: 'spatial-row', serverTransitionStyle: 'spatial-row',
    transitionDurationMs: '2000', daytimeTheme: 'classic_dark' };
  const root = { dataset, classList: { add: (name) => flags.add(name), contains: (name) => flags.has(name) } };
  const document = { documentElement: root, body: { classList: { contains: () => false } },
    addEventListener: () => {} };
  const ready = deferred(), finished = deferred();
  const transition = { ready: ready.promise, finished: finished.promise,
    updateCallbackDone: Promise.resolve() };
  const original = function (...args) { calls.push({ receiver: this, args }); return transition; };
  if (hasAPI) document.startViewTransition = original;
  const window = hasBridge ? { __acpWebkitSurfaceTrial: { state: {} } } : {};
  Object.defineProperty(window, 'localStorage', { get() { throw new Error('No storage writes'); } });
  const context = { window, document, location: { href: 'http://preview/clock' },
    performance: { now: () => clock, getEntriesByType: () => [{ startTime: 0 }] },
    fetch() { throw new Error('No backend requests from profile'); },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; }
      observe(node, options) { observers.push({ callback: this.callback, node, options }); }
    },
  };
  vm.createContext(context);
  const run = () => vm.runInContext(profile, context);
  return { root, flags, observers, calls, document, window, context, original, transition,
    ready, finished, run, tick: (value) => { clock = value; } };
}

test('Cover profile changes only local style and enables accepted F11 navigation', () => {
  const f = fixture();
  f.run();
  assert.equal(f.root.dataset.transitionStyle, 'cover-reveal');
  assert.equal(f.root.dataset.serverTransitionStyle, 'spatial-row');
  assert.equal(f.root.dataset.transitionDurationMs, '2000');
  assert.equal(f.root.dataset.daytimeTheme, 'classic_dark');
  assert.ok(f.flags.has('acp-webkit-layout-nav-trial'));
  assert.equal(f.window.__acpWebkitFrameStripTrial, undefined, 'F10 is spatial-only');
  // Later publication of server preferences must not change this explicit
  // preview's style, including when an on-screen Settings surface is mounted.
  f.root.dataset.transitionStyle = 'spatial-row';
  f.observers[0].callback();
  assert.equal(f.root.dataset.transitionStyle, 'cover-reveal');
  assert.equal(f.root.dataset.serverTransitionStyle, 'spatial-row');
});

test('profile does nothing without explicit surface trial installation', () => {
  const f = fixture({ hasBridge: false });
  f.run();
  assert.equal(f.root.dataset.transitionStyle, 'spatial-row');
  assert.equal(f.flags.size, 0);
  assert.equal(f.observers.length, 0);
  assert.equal(f.document.startViewTransition, f.original);
});

test('native transition identity, this, arguments and promises are preserved', async () => {
  const f = fixture();
  f.run();
  const callback = () => {};
  const actual = f.document.startViewTransition(callback);
  assert.equal(actual, f.transition);
  assert.equal(f.calls[0].receiver, f.document);
  assert.equal(f.calls[0].args[0], callback);
  assert.equal(actual.ready, f.ready.promise);
  assert.equal(actual.finished, f.finished.promise);
  const stats = f.window.__acpWebkitCoverRevealTrial;
  assert.equal(stats.started, 1);
  f.ready.resolve();
  await actual.ready;
  assert.equal(stats.ready, 1);
  assert.equal(stats.finished, 0);
  f.tick(2140);
  f.finished.resolve();
  await actual.finished;
  assert.equal(stats.finished, 1);
  assert.equal(stats.lastElapsedMs, 2040);
  const receiver = { otherDocument: true };
  const options = { update: callback };
  assert.equal(f.document.startViewTransition.call(receiver, options), f.transition);
  assert.equal(f.calls[1].receiver, receiver);
  assert.equal(f.calls[1].args[0], options);
});

test('observation retains caller-visible native rejections', async () => {
  const f = fixture();
  f.run();
  const actual = f.document.startViewTransition(() => {});
  const callerReady = assert.rejects(actual.ready, /snapshot failed/);
  const callerFinished = assert.rejects(actual.finished, /transition aborted/);
  f.ready.reject(new Error('snapshot failed'));
  f.finished.reject(new Error('transition aborted'));
  await Promise.all([callerReady, callerFinished]);
  const stats = f.window.__acpWebkitCoverRevealTrial;
  assert.equal(stats.readyFailures, 1);
  assert.equal(stats.finishFailures, 1);
  assert.equal(stats.ready, 0);
  assert.equal(stats.finished, 0);
});

test('unavailable View Transition API is reported without inventing a renderer', () => {
  const f = fixture({ hasAPI: false });
  f.run();
  assert.equal(f.window.__acpWebkitCoverRevealTrial.apiAvailable, false);
  assert.equal(f.window.__acpWebkitCoverRevealTrial.started, 0);
  assert.equal(f.document.startViewTransition, undefined);
  assert.equal(f.root.dataset.transitionStyle, 'cover-reveal');
});

test('repeated installation does not reset counters or wrap the API twice', async () => {
  const f = fixture();
  f.run();
  const wrapper = f.document.startViewTransition;
  const stats = f.window.__acpWebkitCoverRevealTrial;
  f.run();
  assert.equal(f.document.startViewTransition, wrapper);
  assert.equal(f.window.__acpWebkitCoverRevealTrial, stats);
  assert.equal(f.observers.length, 1);
  const actual = wrapper(() => {});
  f.ready.resolve(); f.finished.resolve();
  await actual.finished;
  assert.equal(stats.started, 1);
});

test('Cover F-key navigation delegates directly, without a spatial direction or intermediate route', async () => {
  const f = fixture({ hasBridge: false });
  let active = 'clock';
  const requests = [];
  f.window.ACPSurfaceHost = { activeSurface: () => active,
    canNavigate: () => true, supportsViewTransitions: () => true,
    navigate: async (target, options) => {
      requests.push({ target, options }); active = target;
      return { handled: true, accepted: true };
    } };
  f.window.ACPWorkspaceTopology = { acpSurfaceOrder: () => ['clock', 'weather', 'news', 'airplay'] };
  vm.runInContext(bridge, f.context);
  f.run();
  await f.window.__acpWebkitSurfaceTrial.navigate('news', 'cover-reveal');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].target, 'news');
  assert.equal(requests[0].options.spatialCommitDirection, undefined);
  assert.equal(requests[0].options.history, false);
  const outcome = f.window.__acpWebkitSurfaceTrial.state.last;
  assert.equal(outcome.accepted, true);
  assert.equal(outcome.direction, 'none');
  assert.equal(outcome.configuredStyle, 'cover-reveal');
  assert.equal(outcome.sameDocument, true);
});

test('News geometry sampling is passive, excludes the source copy and caps card measurements', () => {
  const f = fixture();
  const before = { ...f.root.dataset };
  const measured = [];
  const node = (name, x, y, width, height) => ({
    getBoundingClientRect: () => { measured.push(name); return { x, y, width, height }; },
  });
  const cards = Array.from({ length: 4 }, (_, i) => {
    const card = node('card-' + i, 10, i * 100, 123.456, 90);
    const heading = node('heading-' + i, 15, i * 100 + 10, 110, 20);
    const summary = node('summary-' + i, 15, i * 100 + 35, 110, 35);
    card.querySelector = (selector) => selector === 'h2' ? heading : summary;
    return card;
  });
  const news = node('page', 4, 4, 845, 472);
  const rail = node('rail', 4, 4, 155, 420);
  const port = node('port', 170, 60, 670, 360);
  news.querySelector = (selector) => selector === '.news-rail' ? rail : port;
  news.querySelectorAll = () => cards;
  f.document.querySelector = (selector) => {
    if (selector.includes('.acp-mounted-surface-news')) {
      assert.ok(selector.includes('main.screen:not(.acp-spatial-outgoing-live-clone)'));
      assert.ok(selector.includes(':not([hidden])'));
      return news;
    }
    return null;
  };
  f.document.querySelectorAll = () => [];
  f.document.getElementById = () => null;
  f.context.getComputedStyle = () => ({ transform: 'matrix(1, 0, 0, 1, 0, 0)' });
  f.flags.add('acp-webkit-news-layer-trial');
  const actual = JSON.parse(vm.runInContext(metrics, f.context));
  assert.equal(actual.newsLayerTrial, true);
  assert.equal(actual.newsLayout.transform, 'matrix(1, 0, 0, 1, 0, 0)');
  assert.equal(actual.newsLayout.cards.length, 3);
  assert.equal(actual.newsLayout.cards[0].box.width, 123.5);
  assert.equal(actual.newsLayout.cards[0].summary.height, 35);
  assert.equal(measured.includes('card-3'), false);
  assert.deepEqual(f.root.dataset, before, 'no preference or DOM changes from telemetry');
  assert.equal(f.calls.length, 0, 'sampling does not start native transitions');
});
