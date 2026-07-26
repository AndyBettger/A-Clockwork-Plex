from __future__ import annotations

try:
    from . import main as dashboard
    from .application_state import (
        build_default_application_state_hub,
        register_application_state_api,
    )
    from .audio_eq import register_audio_eq
    from .playback_coordinator import PlaybackCoordinator
    from .playback_transport import (
        promote_playback_transport,
        register_playback_command_api,
    )
except ImportError:  # Supports direct execution with: python app/runner.py
    import main as dashboard
    from application_state import (
        build_default_application_state_hub,
        register_application_state_api,
    )
    from audio_eq import register_audio_eq
    from playback_coordinator import PlaybackCoordinator
    from playback_transport import (
        promote_playback_transport,
        register_playback_command_api,
    )

app = dashboard.app
application_state_hub = build_default_application_state_hub(dashboard)
playback_coordinator = promote_playback_transport(application_state_hub, dashboard)
register_application_state_api(app, application_state_hub)
register_playback_command_api(app, application_state_hub)
master_equalizer = register_audio_eq(app)


if __name__ == '__main__':
    config = dashboard.load_config()
    dashboard_config = config.get('dashboard', {})
    dashboard.alarm_scheduler.start()
    dashboard.alarm_audio.start()
    if isinstance(playback_coordinator, PlaybackCoordinator):
        playback_coordinator.start()
    try:
        app.run(
            host=dashboard_config.get('host', '0.0.0.0'),
            port=int(dashboard_config.get('port', 8088)),
            debug=False,
            use_reloader=False,
        )
    finally:
        if isinstance(playback_coordinator, PlaybackCoordinator):
            playback_coordinator.shutdown()
        dashboard.alarm_audio.shutdown()
        dashboard.alarm_scheduler.stop()
