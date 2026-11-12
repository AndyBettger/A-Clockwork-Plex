const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../../app/static/js/nav-pointer-feedback.js'), 'utf8');

function fixture({ hasDrawer = true, hasPointer = true } = {}) {
  const listeners = new Map(), windowListeners = new Map();
  const classList = (...initial) => {
    const values = new Set(initial);
    return { add: (v) => values.add(v), remove: (v) => values.delete(v), contains: (v) => values.has(v) };
  };
  const button = (href, active = false) => ({
    classList: classList(...(active ? ['is-active'] : [])),
    getAttribute: (name) => name === 'href' ? href : null,
    closest() { return this; },
  });
  const home = button('/clock', true), plexamp = button('/plexamp'), outside = button('/outside');
  const body = { classList: classList() }, root = { classList: classList() };
  const drawer = { contains: (node) => node === home || node === plexamp };
  let hit = plexamp, observer;
  const register = (map, name, fn) => map.set(name, [...(map.get(name) || []), fn]);
  const window = { addEventListener: (name, fn) => register(windowListeners, name, fn) };
  if (hasPointer) window.PointerEvent = class {};
  const context = {
    window,
    document: { body, documentElement: root,
      getElementById: () => hasDrawer ? drawer : null,
      elementFromPoint: () => hit,
      addEventListener: (name, fn) => register(listeners, name, fn),
    },
    MutationObserver: class { constructor(fn) { observer = fn; } observe() {} },
  };
  vm.createContext(context);
  const run = () => vm.runInContext(source, context);
  run();
  const emit = (name, detail = {}) => {
    const event = { pointerType: 'mouse', buttons: 0, clientX: 600, clientY: 460, ...detail,
      preventDefault: () => assert.fail('hover handling must not consume input') };
    for (const fn of listeners.get(name) || []) fn(event);
  };
  return { window, root, home, plexamp, outside, listeners, run, emit,
    open(value) {
      if (value) body.classList.add('nav-open');
      else body.classList.remove('nav-open');
      observer?.();
    },
    mutate: () => observer?.(),
    hit: (node) => { hit = node; },
    blur: () => windowListeners.get('blur').forEach((fn) => fn()),
    status: () => window.ACPNavPointerFeedback.status(),
  };
}

test('opening under a stationary pointer and repeated same-coordinate events do not hover', () => {
  const f = fixture();
  f.emit('pointerdown'); // The handle click records the resting pointer.
  f.open(true);
  for (let i = 0; i < 5; i++) f.emit('pointermove');
  f.emit('pointerenter'); // Enter caused by moving drawer geometry is ignored.
  assert.equal(f.status().armed, false);
  assert.equal(f.status().hovered, null);
  assert.equal(f.plexamp.classList.contains('is-pointer-hover'), false);
});

test('fresh movement enables only the hit button, keeping the selected page intact', () => {
  const f = fixture();
  f.emit('pointerdown'); f.open(true);
  f.emit('pointermove', { clientX: 601 });
  assert.equal(f.status().armed, false, 'ignore sub-threshold pointer jitter');
  f.emit('pointermove', { clientX: 604 });
  assert.equal(f.status().hovered, '/plexamp');
  assert.ok(f.plexamp.classList.contains('is-pointer-hover'));
  assert.ok(f.home.classList.contains('is-active'));
  assert.equal(f.plexamp.classList.contains('is-active'), false);
  f.hit(f.home); f.emit('pointermove', { clientX: 610 });
  assert.equal(f.plexamp.classList.contains('is-pointer-hover'), false);
  assert.equal(f.status().hovered, '/clock');
  f.hit(f.outside); f.emit('pointermove', { clientX: 620 });
  assert.equal(f.status().hovered, null, 'outside links never receive navigation hover');
});

test('each reopening clears intent; unrelated body changes do not erase intentional hover', () => {
  const f = fixture();
  f.emit('pointerdown'); f.open(true);
  f.emit('pointermove', { clientX: 610 });
  f.mutate();
  assert.equal(f.status().hovered, '/plexamp');
  f.open(false);
  assert.equal(f.status().hovered, null);
  f.open(true); f.emit('pointermove', { clientX: 610 });
  assert.equal(f.status().armed, false);
  assert.equal(f.status().hovered, null);
});

test('touch and compatibility input clear hover without blocking the press/click path', () => {
  const f = fixture();
  f.emit('pointerdown'); f.open(true);
  f.emit('pointermove', { clientX: 610 });
  f.emit('pointerdown', { pointerType: 'touch', buttons: 1 });
  f.emit('pointermove', { pointerType: 'touch', clientX: 640 });
  assert.equal(f.status().hovered, null);
  f.emit('pointermove', { clientX: 800, sourceCapabilities: { firesTouchEvents: true } });
  assert.equal(f.status().armed, false);
  assert.equal(f.listeners.has('click'), false);
  assert.equal(f.listeners.has('keydown'), false, 'keyboard focus/activation remains native');
});

test('pen hover works while pen contact clears hover', () => {
  const f = fixture();
  f.open(true);
  f.emit('pointermove', { pointerType: 'pen' });
  f.emit('pointermove', { pointerType: 'pen', clientX: 610 });
  assert.equal(f.status().hovered, '/plexamp');
  f.emit('pointerdown', { pointerType: 'pen', buttons: 1 });
  assert.equal(f.status().hovered, null);
  f.emit('pointermove', { pointerType: 'pen', buttons: 1, clientX: 620 });
  assert.equal(f.status().armed, false);
});

test('window leave, blur and pointer cancellation clear stale feedback', () => {
  for (const action of ['leave', 'blur', 'cancel']) {
    const f = fixture();
    f.emit('pointermove'); f.open(true);
    f.emit('pointermove', { clientX: 610 });
    f.emit('pointerout', { relatedTarget: f.home });
    assert.equal(f.status().hovered, '/plexamp');
    if (action === 'leave') f.emit('pointerout', { relatedTarget: null });
    if (action === 'blur') f.blur();
    if (action === 'cancel') f.emit('pointercancel');
    assert.equal(f.status().hovered, null);
    assert.equal(f.status().armed, false);
  }
});

test('closed movement cannot hover; missing capabilities retain CSS fallback; installation is idempotent', () => {
  const f = fixture();
  f.emit('pointermove'); f.emit('pointermove', { clientX: 620 });
  assert.equal(f.status().hovered, null);
  f.run();
  assert.equal(f.listeners.get('pointermove').length, 1);
  assert.equal(f.root.classList.contains('acp-nav-pointer-intent'), true);
  for (const options of [{ hasPointer: false }, { hasDrawer: false }]) {
    const missing = fixture(options);
    assert.equal(missing.root.classList.contains('acp-nav-pointer-intent'), false);
    assert.equal(missing.window.ACPNavPointerFeedback, undefined);
  }
});
