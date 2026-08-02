from __future__ import annotations

"""Bind unified Settings to the promoted scheduled-alarm normaliser.

The preserved alarm_audio_core module deliberately keeps scheduled playback
locked for its historical explicit-test boundary. Production promotes that
boundary in alarm_audio_scheduled, so the unified Settings transaction must use
the promoted normaliser as well or every save would clear scheduled_enabled.
"""

try:
    from . import settings_unified as _base
    from .alarm_audio_scheduled import normalise_audio_settings
except ImportError:  # Supports direct execution imports.
    import settings_unified as _base
    from alarm_audio_scheduled import normalise_audio_settings


# UnifiedSettingsService resolves this module global at call time. Rebinding it
# here keeps all of the established transaction implementation and validators,
# while ensuring production Settings uses the same two-key safety policy as the
# promoted ScheduledAlarmAudioManager.
_base.normalise_audio_settings = normalise_audio_settings

UnifiedSettingsService = _base.UnifiedSettingsService
register_unified_settings_api = _base.register_unified_settings_api

__all__ = ["UnifiedSettingsService", "register_unified_settings_api"]
