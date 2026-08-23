(() => {
  if (window.__aClockworkPlexNavLayerLoaded) return;
  window.__aClockworkPlexNavLayerLoaded = true;

  const drawer = document.getElementById('nav-drawer');
  const handle = document.getElementById('nav-handle');
  if (!drawer || !handle) return;

  /* Page templates historically render navigation inside <main>. Moving the
     fixed controls to <body> lets their z-index sit above persistent Plexamp and
     future page layers without changing every template or duplicating IDs. */
  document.body.append(drawer, handle);
})();
