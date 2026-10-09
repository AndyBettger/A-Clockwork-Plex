from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
NAV_TEMPLATE = ROOT / "app" / "templates" / "_nav.html"
NAV_DRAWER = ROOT / "app" / "static" / "js" / "nav-drawer.js"
NAV_LIFECYCLE = ROOT / "app" / "static" / "js" / "nav-drawer-lifecycle.js"
AUDIO_EQ = ROOT / "app" / "static" / "js" / "audio-eq.js"
AUDIO_EQ_LAYOUT = ROOT / "app" / "static" / "js" / "audio-eq-drawer-layout.js"
HOST = ROOT / "app" / "static" / "js" / "acp-surface-host.js"
TRANSITIONS = ROOT / "app" / "static" / "js" / "page-transitions.js"
APPLICATION_SURFACES = ROOT / "app" / "static" / "js" / "acp-application-surfaces.js"
WEATHER_SURFACE = ROOT / "app" / "static" / "js" / "weather-surface.js"
AIRPLAY_LIFECYCLE = ROOT / "app" / "static" / "js" / "airplay-surface-lifecycle.js"
AIRPLAY_LIVE = ROOT / "app" / "static" / "js" / "airplay-live.js"
DASHBOARD = ROOT / "app" / "dashboard_core.py"
TRANSITION_CSS = ROOT / "app" / "static" / "css" / "page-transitions.css"
NAV_CSS = ROOT / "app" / "static" / "css" / "nav.css"
PLEXAMP_CSS = ROOT / "app" / "static" / "css" / "plexamp-persistent.css"
PLEXAMP_JS = ROOT / "app" / "static" / "js" / "plexamp-persistent.js"
WORKSPACE_TOPOLOGY = ROOT / "app" / "static" / "js" / "workspace-topology.js"


class AcpSurfaceHostTests(unittest.TestCase):
    def test_surface_host_loads_before_legacy_page_transition_owner(self):
        base = BASE.read_text(encoding="utf-8")
        host_index = base.index("js/acp-surface-host.js")
        transitions_index = base.index("js/page-transitions.js")

        self.assertLess(host_index, transitions_index)

    def test_b6_shell_workspace_topology_is_authoritative_above_renderers(self):
        base = BASE.read_text(encoding="utf-8")
        topology = WORKSPACE_TOPOLOGY.read_text(encoding="utf-8")
        surfaces = APPLICATION_SURFACES.read_text(encoding="utf-8")
        transitions = TRANSITIONS.read_text(encoding="utf-8")

        topology_index = base.index("js/workspace-topology.js")
        self.assertLess(topology_index, base.index("js/plexamp-persistent.js"))
        self.assertLess(topology_index, base.index("js/page-transitions.js"))
        self.assertLess(topology_index, base.index("js/acp-application-surfaces.js"))

        expected_order = [
            "id: 'clock'",
            "id: 'weather'",
            "id: 'news'",
            "id: 'airplay'",
            "id: 'plexamp'",
        ]
        positions = [topology.index(value) for value in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("label: 'Home'", topology)
        self.assertIn("renderer: 'acp'", topology)
        self.assertIn("renderer: 'plexamp'", topology)
        self.assertIn("'astronomy'", topology)
        self.assertIn("function direction(from, to)", topology)
        self.assertIn("function path(from, to)", topology)
        self.assertIn("function acpSurfaceOrder()", topology)

        self.assertIn("window.ACPWorkspaceTopology?.acpSurfaceOrder?.() || []", surfaces)
        self.assertNotIn("const spatialSurfaceOrder = ['clock', 'weather', 'news', 'airplay']", surfaces)

        self.assertIn("const topology = window.ACPWorkspaceTopology", transitions)
        self.assertIn("topology?.path?.(activeRoute()", transitions)
        self.assertIn("path.every((entry) => entry.renderer === 'acp')", transitions)
        self.assertIn("adjacentCrossRenderer", transitions)
        self.assertNotIn("const spatialRowRoutes =", transitions)

    def test_primary_navigation_is_owned_once_by_the_base_shell(self):
        base = BASE.read_text(encoding="utf-8")
        navigation = NAV_TEMPLATE.read_text(encoding="utf-8")
        loader = APPLICATION_SURFACES.read_text(encoding="utf-8")

        self.assertEqual(base.count('{% include "_nav.html" %}'), 1)
        self.assertIn('id="nav-drawer"', navigation)
        self.assertIn('id="nav-handle"', navigation)
        self.assertNotIn("js/nav-layer.js", base)
        self.assertNotIn("['nav-drawer', 'nav-handle']", loader)

        for name in ("clock", "weather", "news", "settings", "airplay", "plexamp"):
            template = (ROOT / "app" / "templates" / f"{name}.html").read_text(encoding="utf-8")
            self.assertNotIn('{% include "_nav.html" %}', template)

    def test_b5_navigation_separates_workspaces_from_svg_utilities(self):
        navigation = NAV_TEMPLATE.read_text(encoding="utf-8")
        styles = NAV_CSS.read_text(encoding="utf-8")
        drawer = NAV_DRAWER.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn('class="nav-workspaces"', navigation)
        self.assertIn('role="group" aria-label="Workspaces"', navigation)
        self.assertIn('class="nav-utilities"', navigation)
        self.assertIn('role="group" aria-label="Utilities"', navigation)

        workspace = navigation[navigation.index('class="nav-workspaces"'):navigation.index('class="nav-utilities"')]
        self.assertLess(workspace.index('href="/clock"'), workspace.index('href="/weather"'))
        self.assertLess(workspace.index('href="/weather"'), workspace.index('href="/news"'))
        self.assertLess(workspace.index('href="/news"'), workspace.index('href="/airplay"'))
        self.assertLess(workspace.index('href="/airplay"'), workspace.index('href="/plexamp"'))
        self.assertNotIn('href="/settings"', workspace)
        self.assertNotIn('id="nav-audio-button"', workspace)

        utilities = navigation[navigation.index('class="nav-utilities"'):]
        self.assertIn('id="nav-audio-button"', utilities)
        self.assertIn('href="/settings"', utilities)
        self.assertIn('aria-label="Audio"', utilities)
        self.assertIn('aria-label="Settings"', utilities)
        self.assertGreaterEqual(utilities.count('class="nav-utility-icon"'), 2)
        self.assertIn('viewBox="0 0 24 24"', utilities)

        self.assertIn(".nav-workspaces", styles)
        self.assertIn(".nav-utilities", styles)
        self.assertIn("margin-inline-start: auto", styles)
        self.assertIn("border-inline-start: 1px solid var(--acp-border-control-neutral)", styles)
        self.assertIn(".nav-utility-button", styles)
        self.assertIn(".nav-utility-icon", styles)
        self.assertIn("stroke: currentColor", styles)
        self.assertIn("vector-effect: non-scaling-stroke", styles)
        self.assertIn("--acp-nav-control-size", styles)
        self.assertIn("height: var(--acp-nav-control-size)", styles)
        self.assertIn("border-radius: var(--acp-radius-control)", styles)
        self.assertIn("border-radius: 50%", styles)
        self.assertIn("border-radius: var(--acp-radius-card)", styles)
        self.assertIn("font-size: clamp(1.17rem, 2.9vmin, 1.36rem)", styles)
        self.assertIn('href="/clock">Home</a>', navigation)
        self.assertNotIn('href="/clock">Clock</a>', navigation)
        self.assertIn("rgba(6, 12, 22, 0.42)", styles)
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        self.assertIn('{"id": "clock", "label": "Home"}', dashboard)
        self.assertIn("state.mode == 'clock' %}Home", base)
        self.assertIn("surface === 'clock'\n      ? 'Home'", HOST.read_text(encoding="utf-8"))
        self.assertIn('@app.route("/clock")', dashboard)

        self.assertIn("mainNav.querySelector('.nav-utilities') || mainNav", drawer)
        self.assertIn("nav-utility-button nav-audio-button", drawer)
        self.assertIn("20261009-b5-labels-v3", base)
        self.assertIn("20261007-nav-shell-v8", base)

    def test_shell_navigation_interactions_survive_surface_dom_changes(self):
        navigation = NAV_TEMPLATE.read_text(encoding="utf-8")
        drawer = NAV_DRAWER.read_text(encoding="utf-8")
        lifecycle = NAV_LIFECYCLE.read_text(encoding="utf-8")
        audio_eq = AUDIO_EQ.read_text(encoding="utf-8")
        audio_layout = AUDIO_EQ_LAYOUT.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn('id="nav-audio-button"', navigation)
        self.assertIn("__aClockworkPlexNavDrawerLoaded", drawer)
        self.assertIn("document.addEventListener('click'", drawer)
        self.assertIn("event.target.closest?.('#nav-handle')", drawer)
        self.assertIn("document.addEventListener('touchstart'", drawer)
        self.assertIn("document.addEventListener('touchend'", drawer)
        self.assertIn("suppressHandleClickUntil", drawer)
        self.assertIn("ACPNavDrawerController", drawer)
        self.assertIn("acp:surface-settled", drawer)
        self.assertNotIn("handle.addEventListener('click'", drawer)

        self.assertIn("ACPNavDrawerController", lifecycle)
        self.assertIn("ensureAudioPanel", lifecycle)
        self.assertIn("acp:surface-settled", audio_eq)
        self.assertIn("acp:surface-settled", audio_layout)
        self.assertNotIn("js/audio-polish.js", base)

    def test_home_indicator_gesture_target_supports_cross_app_up_and_down_swipes(self):
        drawer = NAV_DRAWER.read_text(encoding="utf-8")
        styles = NAV_CSS.read_text(encoding="utf-8")
        plexamp = PLEXAMP_CSS.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn("const deltaY =", drawer)
        self.assertIn("!open && deltaY > SWIPE_THRESHOLD_PX", drawer)
        self.assertIn("open && deltaY < -SWIPE_THRESHOLD_PX", drawer)
        self.assertIn("document.addEventListener('touchcancel'", drawer)

        self.assertIn("width: min(22vw, 200px)", styles)
        self.assertIn("min-width: 180px", styles)
        self.assertIn("height: 22px", styles)
        self.assertIn("background: transparent", styles)
        self.assertIn("width: 140px", styles)
        self.assertIn("pointer-events: none", styles)

        # The shell gesture target must sit above the persistent Plexamp iframe
        # without becoming a full-width transparent interception layer.
        self.assertIn("z-index: 90", styles)
        self.assertIn("z-index: 30", plexamp)
        self.assertIn("20261009-b5-labels-v3", base)

    def test_navigation_mode_lifts_live_surface_under_shell_backdrop(self):
        navigation = NAV_TEMPLATE.read_text(encoding="utf-8")
        drawer = NAV_DRAWER.read_text(encoding="utf-8")
        styles = NAV_CSS.read_text(encoding="utf-8")
        plexamp = PLEXAMP_CSS.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn('id="nav-backdrop"', navigation)
        self.assertIn("classList.toggle('nav-mode', expanded)", drawer)
        self.assertIn("document.getElementById('nav-backdrop')", drawer)
        self.assertIn("event.target.closest?.('#nav-backdrop')", drawer)

        self.assertIn(".nav-backdrop", styles)
        self.assertIn("z-index: 70", styles)
        self.assertIn("body.nav-mode .nav-backdrop", styles)
        self.assertIn("background: rgba(2, 5, 10, 0.34)", styles)
        self.assertIn('html[data-navigation-presentation="lift"] body.nav-mode .screen', styles)
        self.assertIn('html[data-navigation-presentation="lift"] body.nav-mode .persistent-plexamp.is-open', styles)
        self.assertIn("scale: 1", styles)
        self.assertNotIn("scale: 0.84", styles)
        self.assertIn("translate: 0 calc(0px - var(--acp-navigation-reveal-height, 74px))", styles)
        self.assertIn("border-radius: 22px", styles)
        self.assertIn("--acp-navigation-transition-duration: 180ms", styles)
        self.assertIn("var(--acp-navigation-transition-duration)", styles)
        self.assertNotIn("translate: 0 -28px", styles)
        self.assertNotIn("translate: 0 -90px", styles)

        self.assertIn("function syncNavigationRevealHeight()", drawer)
        self.assertIn("mainNav.getBoundingClientRect().height", drawer)
        self.assertIn("style.paddingTop", drawer)
        self.assertIn("style.paddingBottom", drawer)
        self.assertIn("style.borderTopWidth", drawer)
        self.assertIn("style.borderBottomWidth", drawer)
        self.assertIn("style.bottom", drawer)
        self.assertIn("'--acp-navigation-reveal-height'", drawer)
        self.assertIn("if (expanded) syncNavigationRevealHeight()", drawer)
        self.assertIn("window.addEventListener('resize', syncNavigationRevealHeight)", drawer)
        self.assertIn("prefers-reduced-motion", styles)
        self.assertIn("view-transition-name: acp-nav-backdrop", styles)
        self.assertIn("view-transition-name: acp-nav-drawer", styles)
        self.assertIn("view-transition-name: acp-nav-handle", styles)
        self.assertIn("::view-transition-group(acp-nav-drawer)", styles)
        self.assertIn("animation: none !important", styles)
        self.assertIn('data-server-navigation-presentation="{{ config.dashboard.navigation_presentation | default(\'overlay\') }}"', base)
        self.assertIn('data-server-navigation-inactivity-seconds="{{ config.dashboard.navigation_inactivity_seconds | default(6) }}"', base)

        # The visible home indicator is physically attached to the live surface:
        # same measured distance and same easing, with no historical fixed offset.
        self.assertIn("translate: -50% 0", styles)
        self.assertIn(
            "translate: -50% calc(0px - var(--acp-navigation-reveal-height, 74px))",
            styles,
        )
        self.assertIn(
            "translate var(--acp-navigation-transition-duration) cubic-bezier(.16, .84, .24, 1)",
            styles,
        )
        self.assertIn(
            "translate: -50% var(--acp-navigation-reveal-height, 74px)",
            styles,
        )
        self.assertIn("body.nav-open .nav-drawer", styles)
        self.assertIn("translate: -50% 0", styles)
        self.assertIn("visibility: hidden", styles)
        self.assertIn("visibility: visible", styles)
        self.assertNotIn("opacity: 0;\n  pointer-events: none;\n  transition:\n    translate", styles)
        self.assertNotIn("transform: translate(-50%, calc(100% + 18px))", styles)
        self.assertNotIn("translate(-50%, -64px)", styles)
        self.assertNotIn("translate(-50%, -56px)", styles)

        # Individual transform properties deliberately coexist with ACP's
        # existing transform-based View Transitions/Plexamp handoff.
        self.assertIn("scale: 1", styles)
        self.assertIn("translate: 0 0", styles)
        self.assertIn("scale var(--acp-navigation-transition-duration)", plexamp)
        self.assertIn("translate var(--acp-navigation-transition-duration)", plexamp)
        self.assertIn("border-radius var(--acp-navigation-transition-duration)", plexamp)
        self.assertIn("--plexamp-app-transition-in-duration: var(--acp-transition-in-duration)", plexamp)
        self.assertIn("opacity var(--plexamp-app-transition-in-duration)", plexamp)
        self.assertIn('html[data-transition-style="none"] .persistent-plexamp.is-closing', plexamp)
        self.assertIn("20261009-b5-labels-v3", base)

    def test_audio_is_overlay_above_live_surface_and_uses_page_transition_duration(self):
        drawer = NAV_DRAWER.read_text(encoding="utf-8")
        styles = NAV_CSS.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn("body.nav-audio-open .nav-live-mixer", styles)
        self.assertIn("position: fixed", styles)
        self.assertIn("z-index: 78", styles)
        self.assertIn("var(--acp-transition-duration)", styles)
        self.assertNotIn("body.nav-audio-open .nav-drawer", styles)
        self.assertIn("document.body.appendChild(panel)", drawer)
        self.assertIn("const opening = !mixerOpen()", drawer)
        self.assertIn("panel.setAttribute('aria-hidden'", drawer)
        self.assertNotIn("panel.hidden =", drawer)
        self.assertIn("#nav-drawer, #nav-live-mixer", drawer)
        self.assertIn("function navigationInactivitySeconds()", drawer)
        self.assertIn("if (mixerOpen()) return", drawer)
        self.assertIn("if (seconds <= 0) return", drawer)
        self.assertIn("seconds * 1000", drawer)
        self.assertNotIn("MIXER_AUTO_HIDE_MS", drawer)
        self.assertNotIn("NORMAL_AUTO_HIDE_MS", drawer)
        self.assertNotIn("js/audio-polish.js", base)

    def test_navigation_mode_persists_across_manual_plexamp_handoffs(self):
        transitions = TRANSITIONS.read_text(encoding="utf-8")
        plexamp = PLEXAMP_JS.read_text(encoding="utf-8")
        drawer = NAV_DRAWER.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn("function shouldPreserveNavigation(options = {})", transitions)
        self.assertIn("!isAutomaticNavigation(options) && navigationModeOpen()", transitions)
        self.assertIn("preserveNavigation: shouldPreserveNavigation(options)", transitions)
        self.assertIn("rememberNavigationMode(target)", transitions)
        self.assertIn("prepareNavigation?.({ preserveNavigation })", transitions)
        self.assertIn("window.ACPSurfaceHost?.canNavigate?.(target.pathname)", transitions)
        self.assertIn("animate: false", transitions)
        self.assertIn("'plexamp-mounted-handoff'", transitions)
        self.assertIn("window.ACPPlexamp.hide?.({", transitions)

        self.assertIn("options.preserveNavigation !== true", plexamp)
        self.assertIn("function prepareNavigation(options = {})", plexamp)

        self.assertIn("a-clockwork-plex.navigation-mode-transfer", drawer)
        self.assertIn("function consumeNavigationModeTransfer()", drawer)
        self.assertIn("const restoreNavigationMode = consumeNavigationModeTransfer()", drawer)
        self.assertIn("setExpanded(restoreNavigationMode)", drawer)

        self.assertIn("20261009-b5-labels-v3", base)

    def test_surface_host_has_prepare_commit_and_view_transition_contract(self):
        source = HOST.read_text(encoding="utf-8")

        self.assertIn("function register(surface, lifecycle)", source)
        self.assertIn("typeof lifecycle.prepare !== 'function'", source)
        self.assertIn("prepared = await lifecycle.prepare", source)
        self.assertIn("typeof prepared.commit !== 'function'", source)
        self.assertIn("document.startViewTransition(commit)", source)
        self.assertIn("const commit = async () =>", source)
        self.assertIn("typeof prepared.beforeSnapshot === 'function'", source)
        self.assertIn("await prepared.beforeSnapshot", source)
        self.assertIn("await commit()", source)
        self.assertIn("transition.finished.catch", source)
        self.assertIn("acp:surface-changed", source)
        self.assertIn("acp:surface-settled", source)
        self.assertIn("surface-not-registered", source)

    def test_clicking_current_acp_nav_destination_is_consumed_without_reload(self):
        source = TRANSITIONS.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn("const mainNavLink = Boolean(link.closest('.main-nav'))", source)
        self.assertIn(
            "if (mainNavLink && !plexampVisiblyOpen() && target.pathname === activeRoute())",
            source,
        )
        self.assertIn("event.preventDefault();\n      return;", source)
        self.assertNotIn("target.href === window.location.href && !plexampVisiblyOpen()", source)
        self.assertIn("20261009-b6-topology-v1", base)

    def test_spatial_row_b4_adds_airplay_as_fourth_acp_surface(self):
        transitions = TRANSITIONS.read_text(encoding="utf-8")
        host = HOST.read_text(encoding="utf-8")
        surfaces = APPLICATION_SURFACES.read_text(encoding="utf-8")
        styles = TRANSITION_CSS.read_text(encoding="utf-8")
        surface_styles = (ROOT / "app" / "static" / "css" / "acp-surfaces.css").read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")

        self.assertIn("function spatialPrototypeDirection", transitions)
        self.assertIn("preferences().transitionStyle", transitions)
        self.assertIn("'spatial-row'", transitions)
        self.assertIn("const topology = window.ACPWorkspaceTopology", transitions)
        self.assertIn("const fromRoute = visibleWorkspaceRoute()", transitions)
        self.assertIn("topology?.path?.(fromRoute, toRoute)", transitions)
        self.assertIn("path.every((entry) => entry.renderer === 'acp')", transitions)
        self.assertNotIn("Math.abs(targetIndex - currentIndex) !== 1", transitions)
        self.assertNotIn("exitNavigationForSpatialCommit", transitions)
        self.assertIn("Navigation is persistent shell chrome", transitions)

        self.assertIn("function motionEnabled", host)
        self.assertIn("['forward', 'reverse'].includes(options.spatialCommitDirection)", host)
        self.assertIn("typeof prepared.spatialCommit === 'function'", host)
        self.assertIn("await prepared.spatialCommit", host)
        self.assertIn("document.startViewTransition(commit)", host)
        self.assertNotIn("dataset.acpSpatialCommit", host)

        self.assertIn("const spatialSurfaceOrder = window.ACPWorkspaceTopology?.acpSurfaceOrder?.() || []", surfaces)
        self.assertIn("function spatialSurfaceDirection", surfaces)
        self.assertIn("return toIndex > fromIndex ? 'forward' : 'reverse'", surfaces)
        self.assertNotIn("Math.abs(toIndex - fromIndex) !== 1", surfaces)
        self.assertIn("function spatialSurfacePath", surfaces)
        self.assertIn("const intermediateSurfaces = path.slice(1, -1)", surfaces)
        self.assertIn("await ensureMounted(surface)", surfaces)
        self.assertIn("function presentMountedSurface(surface)", surfaces)
        self.assertIn("function cloneMountedSpatialLayer", surfaces)
        self.assertIn("presentMountedSurface(surface)", surfaces)
        self.assertIn("presentMountedSurface(restoreSurface)", surfaces)
        self.assertIn("applyBodyPresentationSurface(surface)", surfaces)
        self.assertIn("restoreBodyPresentationState(bodyState)", surfaces)
        clone_start = surfaces.index("function cloneMountedSpatialLayer")
        clone_end = surfaces.index("async function spatialLiveCommit", clone_start)
        clone_block = surfaces[clone_start:clone_end]
        self.assertNotIn("commitSurface(surface)", clone_block)
        self.assertNotIn("commitSurface(restoreSurface)", clone_block)
        self.assertIn("marks its session unresolved", clone_block)
        self.assertIn("async function spatialLiveCommit(direction, from, to, commit)", surfaces)
        self.assertIn("const layers = [cloneCurrentSpatialLayer(from)]", surfaces)
        self.assertIn("layers.push(cloneMountedSpatialLayer(surface, from))", surfaces)
        self.assertIn("copyBodyBackground(layer)", surfaces)
        self.assertIn("function freezeOutgoingScreenLayout", surfaces)
        self.assertIn("'display'", surfaces)
        self.assertIn("'overflow'", surfaces)
        self.assertIn("'grid-template-rows'", surfaces)
        self.assertIn("'grid-template-columns'", surfaces)
        self.assertIn("'row-gap'", surfaces)
        self.assertIn("'padding-top'", surfaces)
        self.assertIn("AirPlay changes the screen from grid to block", surfaces)
        self.assertIn("freezeOutgoingScreenLayout(layer)", surfaces)
        self.assertIn("const duration = applicationTransitionDurationMs()", surfaces)
        self.assertIn("const distance = path.length - 1", surfaces)
        self.assertIn("const directionSign = direction === 'reverse' ? -1 : 1", surfaces)
        self.assertIn("directionSign * index * 100", surfaces)
        self.assertIn("directionSign * distance * 100", surfaces)
        self.assertIn("the complete movement rather than being applied once per page", surfaces)
        self.assertIn("await commit()", surfaces)
        self.assertIn("animations.map((animation) => animation.finished.catch", surfaces)
        self.assertIn("screen.style.transform = ''", surfaces)
        self.assertIn("layers.forEach((layer) => layer.remove())", surfaces)
        self.assertIn("const expectedDirection = spatialSurfaceDirection(from, surface)", surfaces)
        self.assertIn("direction !== expectedDirection", surfaces)
        self.assertIn("await spatialLiveCommit(direction, from, surface, commit)", surfaces)

        self.assertIn(".acp-spatial-outgoing-live-clone", surface_styles)
        self.assertIn("z-index: 40", surface_styles)
        self.assertIn("pointer-events: none", surface_styles)
        self.assertNotIn("translate: 0 0 !important", surface_styles)
        self.assertIn("share the live screen's shell-owned vertical offset", surface_styles)
        self.assertNotIn("data-acp-spatial-commit", styles)
        self.assertNotIn("@keyframes acp-in-spatial-forward", styles)
        self.assertNotIn("@keyframes acp-out-spatial-forward", styles)

        self.assertIn("20261009-b6-topology-v1", base)


    def test_b6_adjacent_airplay_plexamp_uses_cross_renderer_spatial_adapter(self):
        base = BASE.read_text(encoding="utf-8")
        transitions = TRANSITIONS.read_text(encoding="utf-8")
        plexamp = PLEXAMP_JS.read_text(encoding="utf-8")

        self.assertIn("function visibleWorkspaceRoute()", transitions)
        self.assertIn("const adjacentCrossRenderer = path.length === 2", transitions)
        self.assertIn("entry.renderer === 'plexamp'", transitions)
        self.assertIn("window.ACPPlexamp.spatialShow", transitions)
        self.assertIn("window.ACPPlexamp.spatialHide", transitions)
        self.assertIn("options.spatialCommitDirection === 'forward'", transitions)
        self.assertIn("options.spatialCommitDirection === 'reverse'", transitions)
        self.assertIn("path?.('/plexamp', target.pathname)?.length === 2", transitions)

        self.assertIn("function spatialDurationMs()", plexamp)
        self.assertIn("function spatialShow(options = {})", plexamp)
        self.assertIn("function spatialHide(options = {})", plexamp)
        self.assertIn("translateX(100vw)", plexamp)
        self.assertIn("translateX(-100vw)", plexamp)
        self.assertIn("cubic-bezier(.16, .84, .24, 1)", plexamp)
        self.assertIn("spatialAnimations", plexamp)
        self.assertIn("spatialShow,", plexamp)
        self.assertIn("spatialHide,", plexamp)
        self.assertIn("preserveNavigation", plexamp)

        self.assertIn("20261009-b6-adjacent-v1", base)
        self.assertIn("20261009-b6-topology-v1", base)

    def test_page_navigation_delegates_only_registered_routes_and_keeps_route_fallback(self):
        source = TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("window.ACPSurfaceHost?.canNavigate?.(target.pathname)", source)
        self.assertIn("await window.ACPSurfaceHost.navigate(target.pathname", source)
        self.assertIn("if (result?.handled) return;", source)

        # Until a destination surface has explicitly registered with the host,
        # the accepted multi-document route remains the fail-safe.
        self.assertGreaterEqual(source.count("window.location.assign(target.href)"), 3)

    def test_surface_host_does_not_register_product_surfaces_itself(self):
        source = HOST.read_text(encoding="utf-8")

        self.assertNotIn("register('clock'", source)
        self.assertNotIn('register("clock"', source)
        self.assertNotIn("register('weather'", source)
        self.assertNotIn('register("weather"', source)
        self.assertNotIn("register('news'", source)
        self.assertNotIn('register("news"', source)

    def test_application_surface_set_includes_physically_accepted_surfaces_and_airplay_candidate(self):
        source = APPLICATION_SURFACES.read_text(encoding="utf-8")

        self.assertIn("const surfaces = new Set(['clock', 'weather', 'news', 'settings', 'airplay'])", source)
        self.assertIn("surfaceHost.register(surface", source)
        self.assertIn("/api/surfaces/", source)
        self.assertIn("record.wrapper.hidden = name !== surface", source)
        self.assertIn("/api/mode/", source)
        self.assertIn("'settings'", source)
        self.assertIn("'airplay'", source)

    def test_surface_document_endpoint_is_read_only_for_mode(self):
        source = DASHBOARD.read_text(encoding="utf-8")
        start = source.index('@app.route("/api/surfaces/<surface>")')
        end = source.index('@app.route("/airplay")', start)
        endpoint = source[start:end]

        self.assertIn('"clock": "clock.html"', endpoint)
        self.assertIn('"weather": "weather.html"', endpoint)
        self.assertIn('"news": "news.html"', endpoint)
        self.assertIn('"settings": "settings.html"', endpoint)
        self.assertIn('"airplay": "airplay.html"', endpoint)
        self.assertIn("context = settings_page_context(config)", endpoint)
        self.assertIn("render_template(template, **context)", endpoint)
        self.assertNotIn("set_mode(", endpoint)

    def test_airplay_surface_lifecycle_distinguishes_mounted_from_visible(self):
        lifecycle = AIRPLAY_LIFECYCLE.read_text(encoding="utf-8")
        live = AIRPLAY_LIVE.read_text(encoding="utf-8")
        template = (ROOT / "app" / "templates" / "airplay.html").read_text(encoding="utf-8")

        self.assertLess(
            template.index("airplay-surface-lifecycle.js"),
            template.index("airplay-live.js"),
        )
        self.assertIn("dataset?.activePage", lifecycle)
        self.assertIn("=== 'airplay'", lifecycle)
        self.assertIn("!document.hidden", lifecycle)
        self.assertIn("ACPPlexamp?.isVisiblyOpen", lifecycle)
        self.assertIn("function subscribe(subscriber)", lifecycle)
        self.assertIn("acp:surface-activated", lifecycle)
        self.assertIn("acp:surface-settled", lifecycle)
        self.assertIn("surfaceLifecycle.isVisible()", live)
        self.assertIn("surfaceLifecycle?.subscribe?.", live)
        self.assertNotIn("setInterval(refreshStatus", live)

    def test_surface_host_activation_is_part_of_navigation_busy_state(self):
        transitions = TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("window.ACPSurfaceHost?.isTransitioning?.() === true", transitions)

    def test_weather_settings_autosave_invalidates_mounted_weather_surface(self):
        source = WEATHER_SURFACE.read_text(encoding="utf-8")

        self.assertIn("acp:settings-saved", source)
        self.assertIn("sections.includes('weather')", source)
        self.assertIn("settingsRefreshPending = true", source)
        self.assertIn("if (weatherIsVisible())", source)
        self.assertIn("void refresh().finally(schedule)", source)
        self.assertIn("if (updated) settingsRefreshPending = false", source)

    def test_weather_presentation_refresh_cadence_is_shell_owned(self):
        source = WEATHER_SURFACE.read_text(encoding="utf-8")
        settings = (ROOT / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
        weather = (ROOT / "app" / "templates" / "weather.html").read_text(encoding="utf-8")
        clock = (ROOT / "app" / "templates" / "clock.html").read_text(encoding="utf-8")

        self.assertIn("PRESENTATION_REFRESH_MS = 60_000", source)
        self.assertNotIn("refreshMilliseconds()", source)
        self.assertNotIn("data-refresh-seconds", weather)
        self.assertNotIn("data-refresh-seconds", clock)
        self.assertNotIn("weather.auto_refresh_seconds", settings)

    def test_same_document_view_transition_uses_configured_acp_motion(self):
        styles = TRANSITION_CSS.read_text(encoding="utf-8")

        self.assertIn("::view-transition-old(root)", styles)
        self.assertIn("::view-transition-new(root)", styles)
        self.assertIn("--acp-transition-duration", styles)
        for style, outgoing, incoming in (
            ("grow-fade", "acp-out-grow-fade", "acp-in-grow-fade"),
            ("crossfade", "acp-out-crossfade", "acp-in-crossfade"),
            ("horizontal-slide", "acp-out-horizontal-slide", "acp-in-horizontal-slide"),
            ("vertical-lift", "acp-out-vertical-lift", "acp-in-vertical-lift"),
            ("cover-reveal", "acp-out-cover-reveal", "acp-in-cover-reveal"),
            ("zoom", "acp-out-zoom", "acp-in-zoom"),
            ("blur-dissolve", "acp-out-blur-dissolve", "acp-in-blur-dissolve"),
            ("spatial-row", "acp-out-horizontal-slide", "acp-in-horizontal-slide"),
        ):
            self.assertIn(f':root[data-transition-style="{style}"]', styles)
            self.assertIn(f"--acp-view-transition-old: {outgoing};", styles)
            self.assertIn(f"--acp-view-transition-new: {incoming};", styles)


if __name__ == "__main__":
    unittest.main()
