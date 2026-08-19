(() => {
  const root = typeof window !== 'undefined' ? window : globalThis;
  if (root.ACPAirPlayMediaKind) return;

  const spokenAppPattern = /\b(prologue|podcasts?|apple podcasts|overcast|pocket casts?|audible|audiobooks?|bookplayer|castro|downcast|libby|borrowbox)\b/i;
  const strongMusicAppPattern = /\b(plexamp|apple music|spotify|tidal|qobuz|deezer)\b/i;
  const genericMusicLabelPattern = /\bmusic\b/i;
  const spokenTextPattern = /\b(podcast|pod|audiobook|audio book|spoken word|chapter|episode|part\s+\d+|book\s+\d+|narrated by|unabridged)\b/i;
  const explicitSpokenPattern = /\b(podcast|audiobook|audio book|spoken word|prologue|audible|overcast|pocket casts?)\b/i;
  const LONG_SPOKEN_SECONDS = 30 * 60;
  const VERY_LONG_SPOKEN_SECONDS = 40 * 60;
  const LONGFORM_OVERRIDE_SECONDS = 60 * 60;

  function textFromValues(values) {
    return values
      .map((value) => String(value || '').trim())
      .filter(Boolean)
      .join(' · ');
  }

  function secondsFromProgress(progress) {
    const value = Number(progress?.duration_seconds);
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  function looksLikeSpokenAudio(payload) {
    const state = payload?.state || {};
    const airplay = state.airplay || {};
    const metadata = airplay.metadata || {};
    const appText = textFromValues([
      metadata.source_name,
      metadata.player_name,
      metadata.source_model,
      metadata.source_user_agent,
    ]);
    const mediaText = textFromValues([
      metadata.genre,
      metadata.format,
      metadata.album,
      metadata.title,
      metadata.artist,
      metadata.album_artist,
      metadata.composer,
    ]);
    const duration = secondsFromProgress(metadata.progress);
    const strongMusicApp = strongMusicAppPattern.test(appText);
    const genericMusicLabel = genericMusicLabelPattern.test(appText);
    const spokenMediaHint = spokenTextPattern.test(mediaText);

    // Strong spoken identity always wins, whether it arrived as an app/source
    // identity or as the media metadata itself.
    if (explicitSpokenPattern.test(appText) || explicitSpokenPattern.test(mediaText)) {
      return true;
    }

    // Named music players are deliberate evidence for track navigation. A long
    // DJ mix or classical work in Spotify/Plexamp should not become a podcast
    // merely because it runs for an hour.
    if (strongMusicApp && !spokenMediaHint) {
      return false;
    }

    // Shairport/iOS can expose the generic source label "Music" even for
    // spoken-audio clients. Do not let that weak label veto unmistakably
    // long-form material. One hour is intentionally conservative enough to
    // avoid changing ordinary long tracks while fixing podcast/audiobook cases.
    if (duration !== null && duration >= LONGFORM_OVERRIDE_SECONDS && !strongMusicApp) {
      return true;
    }

    // Below the long-form override a generic Music label remains a useful hint
    // toward track navigation unless the metadata itself looks spoken.
    if (genericMusicLabel && !spokenMediaHint) {
      return false;
    }

    let score = 0;

    if (spokenAppPattern.test(appText)) {
      score += 5;
    }
    if (spokenMediaHint) {
      score += 2;
    }
    if (duration !== null && duration >= LONG_SPOKEN_SECONDS && !strongMusicApp && !genericMusicLabel) {
      score += 3;
    }
    if (duration !== null && duration >= VERY_LONG_SPOKEN_SECONDS && !strongMusicApp && !genericMusicLabel) {
      score += 1;
    }
    if (duration !== null && duration >= 20 * 60 && spokenMediaHint) {
      score += 2;
    }
    if (duration !== null && duration >= 35 * 60 && !metadata.artist) {
      score += 1;
    }

    return score >= 3;
  }

  root.ACPAirPlayMediaKind = Object.freeze({
    looksLikeSpokenAudio,
    classify(payload) {
      return looksLikeSpokenAudio(payload) ? 'spoken' : 'track';
    },
  });
})();