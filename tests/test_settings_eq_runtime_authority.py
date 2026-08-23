from pathlib import Path

from app.settings_unified import eq_model_from_status


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_SERVICE = (ROOT / "app/settings_unified.py").read_text(encoding="utf-8")


def test_live_status_outranks_stale_saved_eq_config():
    config = {
        "audio": {
            "eq": {
                "enabled": False,
                "bands": {"bass": 0.0, "mid": 0.0, "treble": 0.0},
            }
        }
    }
    status = {
        "available": True,
        "bypassed": True,
        "bands": {
            "bass": {"db": 6.0, "stored_db": 6.0},
            "mid": {"db": 0.0, "stored_db": 0.0},
            "treble": {"db": -2.5, "stored_db": -2.5},
        },
    }

    assert eq_model_from_status(config, status) == {
        "enabled": False,
        "bands": {"bass": 6.0, "mid": 0.0, "treble": -2.5},
    }


def test_unified_settings_no_longer_applies_eq_changes():
    assert "self._apply_eq(" not in SETTINGS_SERVICE
    assert 'candidate.setdefault("audio", {})["eq"]' not in SETTINGS_SERVICE
    assert "self._remove_legacy_eq_config(candidate)" in SETTINGS_SERVICE
    assert '"eq_configuration": False' in SETTINGS_SERVICE
    assert '"eq_runtime_control": True' in SETTINGS_SERVICE
