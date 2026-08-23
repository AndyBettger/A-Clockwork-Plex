from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_HTML = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
AUDIO_EQ_JS = (ROOT / "app/static/js/audio-eq.js").read_text(encoding="utf-8")
LEGACY_BACKEND_STATUS_JS = ROOT / "app/static/js/audio-eq-backend-status.js"


def test_base_loads_only_the_authoritative_eq_presenter():
    assert "filename='js/audio-eq.js', v='20260810-single-eq-presenter'" in BASE_HTML
    assert BASE_HTML.count("filename='js/audio-eq.js'") == 1
    assert "audio-eq-backend-status.js" not in BASE_HTML
    assert not LEGACY_BACKEND_STATUS_JS.exists()


def test_authoritative_presenter_distinguishes_installation_and_failback_state():
    assert "function eqHealthText(eq = {})" in AUDIO_EQ_JS
    assert "const installed = eq.installed === true;" in AUDIO_EQ_JS
    assert "if (installed && failback) return 'Direct failback';" in AUDIO_EQ_JS
    assert "if (installed) return 'Unavailable';" in AUDIO_EQ_JS
    assert "return 'Install required';" in AUDIO_EQ_JS


def test_no_backend_state_css_override_can_replace_authoritative_copy():
    assert "data-acp-eq-backend" not in BASE_HTML
    assert 'content: "Backend offline"' not in AUDIO_EQ_JS
    assert 'content: "Backend unavailable"' not in AUDIO_EQ_JS
