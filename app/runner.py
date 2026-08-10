from __future__ import annotations

try:
    from . import main as dashboard
    from .alarm_audio_scheduled import promote_scheduled_alarm_audio
    from .alarm_audio_status_scheduled import register_scheduled_alarm_status_api
    from .application_state import (
        build_default_application_state_hub,
        register_application_state_api,
    )
    from .audio_devices import register_audio_devices_api
    from .audio_eq import register_audio_eq
    from .input_activity import LinuxInputActivityMonitor
    from .playback_authority import promote_playback_authority
    from .playback_coordinator import PlaybackCoordinator
    from .playback_transport import register_playback_command_api
    from .screen_projection_activity import register_activity_screen_projection
    from .settings_unified_scheduled import UnifiedSettingsService, register_unified_settings_api
    from .shairport_name import ShairportNameManager
    from .time_formatting import promote_server_time_formatting
    from .weather_forecast import WeatherForecastService, register_weather_forecast_api
    from .weather_forecast_settings import register_weather_forecast_settings_api
    from .weather_observation_store import store_dashboard_observation
    from .weather_observations import WeatherObservationService, register_weather_observation_api
except ImportError:  # Supports direct execution with: python app/runner.py
    import main as dashboard
    from alarm_audio_scheduled import promote_scheduled_alarm_audio
    from alarm_audio_status_scheduled import register_scheduled_alarm_status_api
    from application_state import (
        build_default_application_state_hub,
        register_application_state_api,
    )
    from audio_devices import register_audio_devices_api
    from audio_eq import register_audio_eq
    from input_activity import LinuxInputActivityMonitor
    from playback_authority import promote_playback_authority
    from playback_coordinator import PlaybackCoordinator
    from playback_transport import register_playback_command_api
    from screen_projection_activity import register_activity_screen_projection
    from settings_unified_scheduled import UnifiedSettingsService, register_unified_settings_api
    from shairport_name import ShairportNameManager
    from time_formatting import promote_server_time_formatting
    from weather_forecast import WeatherForecastService, register_weather_forecast_api
    from weather_forecast_settings import register_weather_forecast_settings_api
    from weather_observation_store import store_dashboard_observation
    from weather_observations import WeatherObservationService, register_weather_observation_api


app = dashboard.app
promote_server_time_formatting(dashboard)
scheduled_alarm_audio = promote_scheduled_alarm_audio(dashboard)
register_scheduled_alarm_status_api(dashboard)
application_state_hub = build_default_application_state_hub(dashboard)
playback_coordinator = promote_playback_authority(application_state_hub, dashboard)
screen_projection = register_activity_screen_projection(app, application_state_hub, dashboard)
_initial_settings_config = dashboard.load_config()
_initial_dashboard_config = (
    _initial_settings_config.get("dashboard")
    if isinstance(_initial_settings_config.get("dashboard"), dict)
    else {}
)
screen_projection.set_idle_return_mode(
    _initial_dashboard_config.get(
        "idle_return_mode",
        _initial_dashboard_config.get("default_mode", "clock"),
    )
)
input_activity_monitor = application_state_hub.service("input_activity")
register_application_state_api(app, application_state_hub)
register_playback_command_api(app, application_state_hub)
register_audio_devices_api(app, config_loader=dashboard.load_config)
master_equalizer = register_audio_eq(app)
weather_observations = WeatherObservationService(
    dashboard.load_config,
    lambda observation: store_dashboard_observation(dashboard, observation),
)
register_weather_observation_api(app, weather_observations)
weather_forecast = WeatherForecastService(
    dashboard.load_config,
    dashboard.BASE_DIR / "weather-forecast-cache.json",
)
register_weather_forecast_api(app, weather_forecast)
register_weather_forecast_settings_api(
    app,
    weather_forecast,
    dashboard.load_config,
    lambda config: dashboard.save_json(dashboard.CONFIG_PATH, config),
)
shairport_name = ShairportNameManager()
unified_settings = UnifiedSettingsService(
    load_config=dashboard.load_config,
    save_config=lambda config: dashboard.save_json(dashboard.CONFIG_PATH, config),
    tone_manifest=dashboard.alarm_tone_manifest,
    clock_card_ids=set(dashboard.CLOCK_CARD_FIELD_IDS),
    forecast=weather_forecast,
    equalizer=master_equalizer,
    shairport_name=shairport_name,
    alarm_scheduler=dashboard.alarm_scheduler,
    alarm_audio=dashboard.alarm_audio,
    screen_idle_mode=screen_projection.set_idle_return_mode,
)
register_unified_settings_api(app, unified_settings)


if __name__ == "__main__":
    config = dashboard.load_config()
    dashboard_config = config.get("dashboard", {})
    dashboard.alarm_scheduler.start()
    dashboard.alarm_audio.start()
    weather_observations.start()
    weather_forecast.start()
    if isinstance(input_activity_monitor, LinuxInputActivityMonitor):
        input_activity_monitor.start()
    if isinstance(playback_coordinator, PlaybackCoordinator):
        playback_coordinator.start()
    try:
        app.run(
            host=dashboard_config.get("host", "0.0.0.0"),
            port=int(dashboard_config.get("port", 8088)),
            debug=False,
            use_reloader=False,
        )
    finally:
        if isinstance(playback_coordinator, PlaybackCoordinator):
            playback_coordinator.shutdown()
        if isinstance(input_activity_monitor, LinuxInputActivityMonitor):
            input_activity_monitor.shutdown()
        weather_forecast.shutdown()
        weather_observations.shutdown()
        dashboard.alarm_audio.shutdown()
        dashboard.alarm_scheduler.stop()
