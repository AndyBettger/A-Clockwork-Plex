// Execute the production F10 helper without browser/GPU dependencies.
// These tests establish geometry/lifecycle contracts, never Pi paint quality.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname,
  '../../app/static/js/acp-application-surfaces.js'), 'utf8');
const helpers = source.slice(source.indexOf('  function frameStripProgress('),
  source.indexOf('  async function spatialLiveCommit('));

function fixture({ duration = 100, reduced = false, rejectFrame = 0,
  visibility = '', gaps = [] } = {}) {
  const events = [];
  const created = [];
  const screen = { style: { visibility, transform: 'unchanged' } };
  const element = () => {
    const values = {};
    const node = {
      className: '', children: [], parent: null, inert: false,
      setAttribute(name, value) { this[name] = value; },
      appendChild(child) { child.parent = this; this.children.push(child); },
      remove() {
        events.push({ kind: 'remove', name: this.className,
          left: this.children[0]?.style.left, visibility: screen.style.visibility });
        if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1);
        this.parent = null;
      },
      getBoundingClientRect() { return { width: 853, height: 480 }; },
      animate() { throw new Error('F10 must not create a Web Animation'); },
    };
    node.style = new Proxy(values, {
      get(target, name) {
        if (name === 'setProperty') return (key, value) => { target[key] = value; };
        return target[name];
      },
      set(target, name, value) {
        target[name] = value;
        if (name === 'left') events.push({ kind: 'position', name: node.className, value });
        return true;
      },
    });
    created.push(node);
    return node;
  };
  const classes = new Set();
  const body = element();
  body.classList = { add: (name) => classes.add(name), remove: (name) => classes.delete(name) };
  const liveParent = { identity: 'original live parent' };
  screen.parent = liveParent;
  screen.cloneNode = () => {
    events.push({ kind: 'destination-copy', visibility: screen.style.visibility });
    return element();
  };
  let frame = 0;
  let time = 0;
  const context = {
    document: { createElement: element, body, documentElement: { clientWidth: 853 } },
    window: { matchMedia: () => ({ matches: reduced }) },
    screen,
    applicationTransitionDurationMs: () => duration,
    copyBodyBackground: () => {},
    prepareSpatialLayer: (layer, surface) => {
      layer.surface = surface;
      layer.inert = true;
      return layer;
    },
    nextFrame: async () => {
      frame += 1;
      if (frame === rejectFrame) throw new Error('frame interrupted');
      time += gaps[frame - 1] ?? 16;
      return time;
    },
  };
  vm.createContext(context);
  vm.runInContext(helpers, context);
  // Callers pass presentation layers already prepared by prepareSpatialLayer.
  const layers = (count) => Array.from({ length: count }, () => {
    const layer = element();
    layer.inert = true;
    return layer;
  });
  const cleanup = () => {
    assert.equal(body.children.length, 0, 'no retained viewport or copies');
    assert.equal(classes.size, 0, 'transition marker released');
    assert.equal(screen.style.visibility, visibility);
    assert.equal(screen.style.transform, 'unchanged');
    assert.equal(screen.parent, liveParent, 'live DOM never reparented');
  };
  return { ...context, context, created, events, layers, cleanup };
}

for (const [direction, distance] of [['forward', 1], ['reverse', 2], ['forward', 3]]) {
  test(`${direction} ${distance}-page movement retains a joined row and its final position`, async () => {
    const f = fixture({ gaps: [16, 16, 40, 16] });
    const outgoing = f.layers(distance);
    let commits = 0;
    await f.context.frameStripLiveCommit(direction, 'source', 'target', outgoing, async () => {
      commits += 1;
      assert.equal(f.screen.style.visibility, 'hidden');
      assert.equal(f.document.body.children.length, 1, 'source already covered');
    });
    assert.equal(commits, 1);
    const sign = direction === 'reverse' ? -1 : 1;
    const viewport = f.created.find((node) => node.className === 'acp-webkit-frame-strip-viewport');
    const strip = viewport.children[0];
    assert.equal(strip.children.length, distance + 1);
    strip.children.forEach((panel, index) => {
      assert.equal(panel.style.left, `${sign * index * 853}px`);
      assert.equal(panel.style.position, 'absolute');
      assert.equal(panel.style.transform, 'none');
      assert.equal(panel.style['will-change'], 'auto');
      assert.equal(panel.inert, true);
    });
    const positions = f.events.filter((e) => e.kind === 'position'
      && e.name === 'acp-webkit-frame-strip').map((e) => Number.parseFloat(e.value));
    positions.forEach((x, i) => { if (i) assert.ok(sign * x <= sign * positions[i - 1]); });
    assert.equal(positions.at(-1), -sign * distance * 853);
    const retired = f.events.find((e) => e.kind === 'remove');
    assert.equal(Number.parseFloat(retired.left), positions.at(-1), 'no reset before removal');
    assert.equal(retired.visibility, '');
    const metrics = f.window.__acpWebkitFrameStripLast;
    assert.equal(metrics.distance, distance);
    assert.ok(metrics.elapsedMs >= 100 && metrics.elapsedMs < 140);
    assert.equal(metrics.maxFrameGapMs, 40);
    assert.ok(metrics.frames > 1);
    assert.equal(f.window.__acpWebkitFrameStripApplied, 1);
    f.cleanup();
  });
}

test('configured zero duration and reduced motion both settle without frame loops', async () => {
  for (const options of [{ duration: 0 }, { reduced: true }]) {
    const f = fixture(options);
    await f.context.frameStripLiveCommit('forward', 'clock', 'weather', f.layers(1), async () => {});
    assert.equal(f.window.__acpWebkitFrameStripLast.frames, 1);
    assert.equal(f.window.__acpWebkitFrameStripLast.elapsedMs, 0);
    f.cleanup();
  }
});

test('commit rejection removes the covered row and restores prior visibility', async () => {
  const f = fixture({ visibility: 'hidden' });
  await assert.rejects(f.context.frameStripLiveCommit('forward', 'clock', 'weather', f.layers(1),
    async () => { throw new Error('commit failed'); }), /commit failed/);
  assert.equal(f.window.__acpWebkitFrameStripApplied, undefined);
  f.cleanup();
});

test('an interrupted frame releases copies and live visibility', async () => {
  const f = fixture({ rejectFrame: 3 });
  await assert.rejects(f.context.frameStripLiveCommit('reverse', 'news', 'clock', f.layers(2),
    async () => {}), /frame interrupted/);
  assert.equal(f.window.__acpWebkitFrameStripApplied, undefined);
  f.cleanup();
});

test('row easing has exact endpoints, is monotonic, and matches the configured curve', () => {
  const f = fixture();
  const progress = f.context.frameStripProgress;
  assert.equal(progress(0), 0);
  assert.equal(progress(1), 1);
  let previous = 0;
  for (let i = 1; i <= 100; i += 1) {
    const value = progress(i / 100);
    assert.ok(value >= previous && value <= 1);
    previous = value;
  }
  // At t=.5 the configured Bezier has x=.275 and y=.815.
  assert.ok(Math.abs(progress(.275) - .815) < .00001);
});
