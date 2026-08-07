from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EQ_JS = (ROOT / "app/static/js/audio-eq.js").read_text(encoding="utf-8")
SETTINGS_HTML = (ROOT / "app/templates/settings.html").read_text(encoding="utf-8")


def test_live_eq_settings_card_is_rendered_by_the_template():
    assert 'data-settings-subpage="audio:eq"' in SETTINGS_HTML
    assert 'id="acp-eq-settings-card"' in SETTINGS_HTML
    assert 'data-eq-range="{{ band }}"' in SETTINGS_HTML
    assert 'id="acp-eq-settings-bypass"' in SETTINGS_HTML
    assert 'id="acp-eq-settings-neutral"' in SETTINGS_HTML


def test_live_eq_controls_do_not_use_staged_setting_paths():
    assert 'data-setting-path="audio.eq.enabled"' not in SETTINGS_HTML
    assert 'data-setting-path="audio.eq.bands.{{ band }}"' not in SETTINGS_HTML
    assert 'data-eq-range="{{ band }}"' in SETTINGS_HTML
    assert 'data-eq-range="${band}"' in AUDIO_EQ_JS


def test_live_eq_mount_is_non_destructive_and_idempotent():
    assert "const candidate = template.content.firstElementChild" in AUDIO_EQ_JS
    assert "subpage.appendChild(candidate)" in AUDIO_EQ_JS
    assert "if (legacyCard !== card) legacyCard.remove()" in AUDIO_EQ_JS
    assert "card.dataset.eqInteractionsInstalled === 'true'" in AUDIO_EQ_JS
    assert "card.dataset.eqInteractionsInstalled = 'true'" in AUDIO_EQ_JS
    assert "querySelectorAll(':scope > .settings-card').forEach((card) => card.remove())" not in AUDIO_EQ_JS


def test_unified_settings_submission_uses_live_eq_domain():
    assert "registerUnifiedSettingsDomain" in AUDIO_EQ_JS
    assert "settings.registerDomain('audio', { get: eqSettingsModel })" in AUDIO_EQ_JS
    assert "getSnapshot?.()?.status?.eq" in AUDIO_EQ_JS


def test_live_settings_copy_matches_music_only_route():
    assert "Plexamp + AirPlay · music only" in AUDIO_EQ_JS
    assert "Scheduled alarms bypass the music EQ." in AUDIO_EQ_JS
    assert "Scheduled alarms bypass the music EQ." in SETTINGS_HTML
