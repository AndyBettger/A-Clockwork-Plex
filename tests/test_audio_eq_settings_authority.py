from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EQ_JS = (ROOT / "app/static/js/audio-eq.js").read_text(encoding="utf-8")
SETTINGS_HTML = (ROOT / "app/templates/settings.html").read_text(encoding="utf-8")


def test_live_eq_replaces_legacy_settings_subpage_card():
    assert "[data-settings-subpage=\"audio:eq\"]" in AUDIO_EQ_JS
    assert "querySelectorAll(':scope > .settings-card').forEach((card) => card.remove())" in AUDIO_EQ_JS
    assert "subpage.insertAdjacentHTML('beforeend', settingsMarkup())" in AUDIO_EQ_JS


def test_live_eq_controls_do_not_use_staged_setting_paths():
    assert 'data-eq-range="${band}"' in AUDIO_EQ_JS
    assert 'data-setting-path="audio.eq.enabled"' in SETTINGS_HTML
    assert 'data-setting-path="audio.eq.bands.{{ band }}"' in SETTINGS_HTML
    assert "data-eq-range" in AUDIO_EQ_JS


def test_unified_settings_submission_uses_live_eq_domain():
    assert "registerUnifiedSettingsDomain" in AUDIO_EQ_JS
    assert "settings.registerDomain('audio', { get: eqSettingsModel })" in AUDIO_EQ_JS
    assert "getSnapshot?.()?.status?.eq" in AUDIO_EQ_JS


def test_live_settings_copy_matches_music_only_route():
    assert "Plexamp + AirPlay · music only" in AUDIO_EQ_JS
    assert "Scheduled alarms bypass the music EQ." in AUDIO_EQ_JS
