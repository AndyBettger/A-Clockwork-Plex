(() => {
  if (window.ACPNightBurnInMotion) return;

  const TARGET_SELECTORS = [
    '#clock-burn-in-cluster',
  ];
  const SAFE_MARGIN_PX = 20;
  const PERIODIC_INTERVAL_MS = 300000;
  const PERIODIC_OFFSETS = [
    [0, 0],
    [3, -2],
    [-3, 2],
    [2, 3],
    [-2, -3],
    [4, 1],
    [-4, -1],
    [1, -4],
    [-1, 4],
  ];
  const INITIAL_ANGLE_RADIANS = 37 * (Math.PI / 180);

  let requestedActive = false;
  let requestedMode = 'periodic';
  let requestedSpeed = 40;
  let effectiveMode = 'off';
  let frame = null;
  let lastTimestamp = null;
  let x = 0;
  let y = 0;
  let velocityX = Math.cos(INITIAL_ANGLE_RADIANS) * requestedSpeed;
  let velocityY = Math.sin(INITIAL_ANGLE_RADIANS) * requestedSpeed;
  let bounds = null;
  let boundsDirty = true;
  let targets = [];
  let resizeObserver = null;

  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null;

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function normaliseMode(value) {
    const candidate = String(value || '').trim().toLowerCase();
    return ['off', 'periodic', 'bounce'].includes(candidate) ? candidate : 'periodic';
  }

  function normaliseSpeed(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? clamp(parsed, 1, 120) : 40;
  }

  function setPosition(nextX, nextY) {
    x = Number.isFinite(nextX) ? nextX : 0;
    y = Number.isFinite(nextY) ? nextY : 0;
    const root = document.documentElement;
    root.style.setProperty('--acp-night-motion-x', `${x.toFixed(3)}px`);
    root.style.setProperty('--acp-night-motion-y', `${y.toFixed(3)}px`);
  }

  function resetPosition() {
    setPosition(0, 0);
  }

  function resolveTargets() {
    const next = TARGET_SELECTORS
      .map((selector) => document.querySelector(selector))
      .filter(Boolean);

    const changed = next.length !== targets.length
      || next.some((target, index) => target !== targets[index]);
    if (!changed) return targets;

    targets = next;
    boundsDirty = true;
    resizeObserver?.disconnect();
    resizeObserver = typeof ResizeObserver === 'function'
      ? new ResizeObserver(() => { boundsDirty = true; })
      : null;
    targets.forEach((target) => resizeObserver?.observe(target));
    return targets;
  }

  function axisBounds(minimum, maximum) {
    if (minimum <= maximum) return { minimum, maximum };
    const centre = (minimum + maximum) / 2;
    return { minimum: centre, maximum: centre };
  }

  function measureBounds() {
    const currentTargets = resolveTargets();
    if (currentTargets.length !== TARGET_SELECTORS.length) {
      bounds = null;
      return null;
    }

    const rects = currentTargets.map((target) => target.getBoundingClientRect());
    const baseLeft = Math.min(...rects.map((rect) => rect.left)) - x;
    const baseRight = Math.max(...rects.map((rect) => rect.right)) - x;
    const baseTop = Math.min(...rects.map((rect) => rect.top)) - y;
    const baseBottom = Math.max(...rects.map((rect) => rect.bottom)) - y;

    const horizontal = axisBounds(
      SAFE_MARGIN_PX - baseLeft,
      window.innerWidth - SAFE_MARGIN_PX - baseRight,
    );
    const vertical = axisBounds(
      SAFE_MARGIN_PX - baseTop,
      window.innerHeight - SAFE_MARGIN_PX - baseBottom,
    );

    bounds = {
      minX: horizontal.minimum,
      maxX: horizontal.maximum,
      minY: vertical.minimum,
      maxY: vertical.maximum,
    };
    boundsDirty = false;

    x = clamp(x, bounds.minX, bounds.maxX);
    y = clamp(y, bounds.minY, bounds.maxY);
    setPosition(x, y);
    return bounds;
  }

  function reflectedStep(position, delta, minimum, maximum) {
    if (maximum - minimum <= 0.01) {
      return { position: minimum, reflected: false };
    }

    let next = position + delta;
    let reflected = false;
    let guard = 0;
    while ((next < minimum || next > maximum) && guard < 8) {
      if (next < minimum) {
        next = minimum + (minimum - next);
        reflected = !reflected;
      }
      if (next > maximum) {
        next = maximum - (next - maximum);
        reflected = !reflected;
      }
      guard += 1;
    }
    return {
      position: clamp(next, minimum, maximum),
      reflected,
    };
  }

  function stopFrame() {
    if (frame !== null) window.cancelAnimationFrame(frame);
    frame = null;
    lastTimestamp = null;
  }

  function applyClasses(mode) {
    if (!document.body) return;
    document.body.classList.toggle('acp-night-burn-periodic', mode === 'periodic');
    document.body.classList.toggle('acp-night-burn-bounce', mode === 'bounce');
  }

  function applyPeriodic() {
    stopFrame();
    const phase = Math.floor(Date.now() / PERIODIC_INTERVAL_MS) % PERIODIC_OFFSETS.length;
    const [nextX, nextY] = PERIODIC_OFFSETS[phase];
    setPosition(nextX, nextY);
  }

  function refreshVelocityMagnitude() {
    const magnitude = Math.hypot(velocityX, velocityY);
    if (magnitude > 0.001) {
      const scale = requestedSpeed / magnitude;
      velocityX *= scale;
      velocityY *= scale;
      return;
    }
    velocityX = Math.cos(INITIAL_ANGLE_RADIANS) * requestedSpeed;
    velocityY = Math.sin(INITIAL_ANGLE_RADIANS) * requestedSpeed;
  }

  function tick(timestamp) {
    frame = null;
    if (!requestedActive || effectiveMode !== 'bounce' || document.hidden) return;
    if (!document.body?.classList.contains('acp-night-clock-mode')) return;

    if (boundsDirty || !bounds) measureBounds();
    if (!bounds) return;

    if (lastTimestamp === null) {
      lastTimestamp = timestamp;
      frame = window.requestAnimationFrame(tick);
      return;
    }

    // Clamp long gaps after tab suspension or renderer stalls so one delayed
    // frame cannot teleport the clock through several edges.
    const deltaSeconds = Math.min(0.05, Math.max(0, (timestamp - lastTimestamp) / 1000));
    lastTimestamp = timestamp;

    const horizontal = reflectedStep(x, velocityX * deltaSeconds, bounds.minX, bounds.maxX);
    const vertical = reflectedStep(y, velocityY * deltaSeconds, bounds.minY, bounds.maxY);
    if (horizontal.reflected) velocityX *= -1;
    if (vertical.reflected) velocityY *= -1;

    setPosition(horizontal.position, vertical.position);
    frame = window.requestAnimationFrame(tick);
  }

  function startBounce() {
    resolveTargets();
    boundsDirty = true;
    measureBounds();
    refreshVelocityMagnitude();
    stopFrame();
    frame = window.requestAnimationFrame(tick);
  }

  function effectiveRequestedMode() {
    if (!requestedActive || requestedMode === 'off') return 'off';
    if (requestedMode === 'bounce' && reducedMotion?.matches) return 'periodic';
    return requestedMode;
  }

  function update(options = {}) {
    requestedActive = options.active === true;
    requestedMode = normaliseMode(options.mode ?? requestedMode);
    requestedSpeed = normaliseSpeed(options.speed ?? requestedSpeed);

    const nextMode = effectiveRequestedMode();
    const modeChanged = nextMode !== effectiveMode;
    effectiveMode = nextMode;
    applyClasses(effectiveMode);

    if (effectiveMode === 'off') {
      stopFrame();
      resetPosition();
      return status();
    }

    if (effectiveMode === 'periodic') {
      applyPeriodic();
      return status();
    }

    refreshVelocityMagnitude();
    if (modeChanged || frame === null) startBounce();
    return status();
  }

  function stop({ reset = true } = {}) {
    requestedActive = false;
    effectiveMode = 'off';
    stopFrame();
    applyClasses('off');
    if (reset) resetPosition();
  }

  function status() {
    return {
      active: requestedActive,
      requestedMode,
      effectiveMode,
      speedPxPerSecond: requestedSpeed,
      x,
      y,
      bounds: bounds ? { ...bounds } : null,
      reducedMotion: reducedMotion?.matches === true,
    };
  }

  window.addEventListener('resize', () => {
    boundsDirty = true;
    if (effectiveMode === 'bounce') measureBounds();
  }, { passive: true });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopFrame();
      return;
    }
    boundsDirty = true;
    update({
      active: requestedActive,
      mode: requestedMode,
      speed: requestedSpeed,
    });
  });

  reducedMotion?.addEventListener?.('change', () => {
    update({
      active: requestedActive,
      mode: requestedMode,
      speed: requestedSpeed,
    });
  });

  window.ACPNightBurnInMotion = Object.freeze({
    update,
    stop,
    status,
  });
})();
