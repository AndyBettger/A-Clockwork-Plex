from __future__ import annotations

try:
    from . import main as dashboard
    from .alarm_audio_preview import register_alarm_audio_preview_api
    from .alarm_audio_scheduled import promote_scheduled_alarm_audio
    from .alarm_audio_status_scheduled import register_scheduled_alarm_status_api
    from .application_state import (
        build_default_application_state_hub,
        register_application_state_api,
    )
    from .audio_devices import register_audio_devices_api
    from .audio_eq import register_audio_eq
    from .audio_mixer import live_audio_status, shared_audio_mixer
    from .configuration_backup import (
        ConfigurationBackupService,
        register_configuration_backup_api,
    )
    from .configuration_reset import (
        ConfigurationResetExecutor,
        ConfigurationResetPlanner,
        register_configuration_reset_apply_api,
        register_configuration_reset_preview_api,
    )
    from .configuration_restore import (
        ConfigurationRestoreExecutor,
        ConfigurationRestorePlanner,
        register_configuration_restore_apply_api,
        register_configuration_restore_preview_api,
    )
    from .input_activity import LinuxInputActivityMonitor
    from .news_feed import BBCNewsFeedService, register_news_api
    from .news_ui import register_news_ui
    from .playback_authority import promote_playback_authority
    from .playback_coordinator import PlaybackCoordinator
    from .playback_transport import register_playback_command_api
    from .plexamp_preferences import PlexampPreferenceManager
    from .screen_projection_activity import register_activity_screen_projection
    from .settings_weather_rainfall import UnifiedSettingsService, register_unified_settings_api
    from .shairport_name import ShairportNameManager
    from .time_formatting import promote_server_time_formatting
    from .weather_credentials import (
        WeatherUndergroundCredentialManager,
        register_weather_underground_credentials_api,
    )
    from .weather_forecast import WeatherForecastService, register_weather_forecast_api
    from .weather_forecast_settings import register_weather_forecast_settings_api
    from .weather_observation_store import (
        promote_ecowitt_observation_store,
        store_dashboard_observation,
    )
    from .weather_observations import WeatherObservationService, register_weather_observation_api
    from .weather_rainfall_history import WeatherRainfallHistoryService, register_weather_rainfall
    from .weather_rainfall_lifetime import (
        WeatherRainfallLifetimeService,
        register_weather_rainfall_lifetime,
    )
    from .weather_rainfall_total import register_calculated_rain_total
except ImportError:  # Supports direct execution with: python app/runner.py
    import main as dashboard
    from alarm_audio_preview import register_alarm_audio_preview_api
    from alarm_audio_scheduled import promote_scheduled_alarm_audio
    from alarm_audio_status_scheduled import register_scheduled_alarm_status_api
    from application_state import (
        build_default_application_state_hub,
        register_application_state_api,
    )
    from audio_devices import register_audio_devices_api
    from audio_eq import register_audio_eq
    from audio_mixer import live_audio_status, shared_audio_mixer
    from configuration_backup import (
        ConfigurationBackupService,
        register_configuration_backup_api,
    )
    from configuration_reset import (
        ConfigurationResetExecutor,
        ConfigurationResetPlanner,
        register_configuration_reset_apply_api,
        register_configuration_reset_preview_api,
    )
    from configuration_restore import (
        ConfigurationRestoreExecutor,
        ConfigurationRestorePlanner,
        register_configuration_restore_apply_api,
        register_configuration_restore_preview_api,
    )
    from input_activity import LinuxInputActivityMonitor
    from news_feed import BBCNewsFeedService, register_news_api
    from news_ui import register_news_ui
    from playback_authority import promote_playback_authority
    from playback_coordinator import PlaybackCoordinator
    from playback_transport import register_playback_command_api
    from plexamp_preferences import PlexampPreferenceManager
    from screen_projection_activity import register_activity_screen_projection
    from settings_weather_rainfall import UnifiedSettingsService, register_unified_settings_api
    from shairport_name import ShairportNameManager
    from time_formatting import promote_server_time_formatting
    from weather_credentials import (
        WeatherUndergroundCredentialManager,
        register_weather_underground_credentials_api,
    )
    from weather_forecast import WeatherForecastService, register_weather_forecast_api
    from weather_forecast_settings import register_weather_forecast_settings_api
    from weather_observation_store import (
        promote_ecowitt_observation_store,
        store_dashboard_observation,
    )
    from weather_observations import WeatherObservationService, register_weather_observation_api
    from weather_rainfall_history import WeatherRainfallHistoryService, register_weather_rainfall
    from weather_rainfall_lifetime import (
        WeatherRainfallLifetimeService,
        register_weather_rainfall_lifetime,
    )
    from weather_rainfall_total import register_calculated_rain_total


app = dashboard.app
register_news_ui(app, dashboard)
promote_server_time_formatting(dashboard)
scheduled_alarm_audio = promote_scheduled_alarm_audio(dashboard)
register_alarm_audio_preview_api(app, dashboard)
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
promote_ecowitt_observation_store(app, dashboard)
weather_observations = WeatherObservationService(
    dashboard.load_config,
    lambda observation: store_dashboard_observation(dashboard, observation),
)
register_weather_observation_api(app, weather_observations)
weather_rainfall = WeatherRainfallHistoryService(
    dashboard.load_config,
    dashboard.BASE_DIR / "weather-rainfall-history.json",
    current_weather=lambda: dashboard.load_state(dashboard.load_config()).get("weather", {}),
    dashboard_history=True,
)
register_weather_rainfall(app, dashboard, weather_rainfall)
weather_rainfall_lifetime = WeatherRainfallLifetimeService(
    dashboard.load_config,
    dashboard.BASE_DIR / "weather-rainfall-lifetime.json",
    recent_cache_path=dashboard.BASE_DIR / "weather-rainfall-history.json",
    current_weather=lambda: dashboard.load_state(dashboard.load_config()).get("weather", {}),
)
register_weather_rainfall_lifetime(app, weather_rainfall_lifetime)
register_calculated_rain_total(dashboard, weather_rainfall, weather_rainfall_lifetime)
weather_credentials = WeatherUndergroundCredentialManager(
    load_config=dashboard.load_config,
    observations=weather_observations,
    rainfall_wake=lambda: (weather_rainfall.wake(), weather_rainfall_lifetime.wake()),
)
register_weather_underground_credentials_api(app, weather_credentials)
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
bbc_news = BBCNewsFeedService(
    dashboard.load_config,
    dashboard.BASE_DIR / "bbc-news-cache.json",
)
register_news_api(app, bbc_news)
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
    observations=weather_observations,
    rainfall=weather_rainfall,
    news=bbc_news,
)
register_unified_settings_api(app, unified_settings)
configuration_backup = ConfigurationBackupService(
    settings_snapshot=unified_settings.snapshot,
    app_version_path=dashboard.BASE_DIR / "app" / "static" / "app-version.json",
    mixer_snapshot=lambda: live_audio_status().get("mixer", {}),
)
register_configuration_backup_api(app, configuration_backup)
plexamp_preferences = PlexampPreferenceManager()
configuration_restore = ConfigurationRestorePlanner(
    current_backup=configuration_backup.build,
    plexamp_preference_status=plexamp_preferences.status,
)
register_configuration_restore_preview_api(app, configuration_restore)
configuration_restore_executor = ConfigurationRestoreExecutor(
    planner=configuration_restore,
    current_backup=configuration_backup.build,
    settings_snapshot=unified_settings.snapshot,
    settings_apply=unified_settings.apply,
    eq_status=master_equalizer.status,
    eq_set_band=lambda band, value: master_equalizer.set_band(band, value, persist=True),
    eq_set_bypass=master_equalizer.set_bypass,
    mixer_status=shared_audio_mixer.status,
    mixer_set_volumes=lambda values: shared_audio_mixer.set_volumes(values, persist=True),
    plexamp_preference_status=plexamp_preferences.status,
    plexamp_preference_apply=plexamp_preferences.apply,
)
register_configuration_restore_apply_api(app, configuration_restore_executor)


def _reset_default_settings() -> dict:
    default_config = dashboard.load_json(dashboard.EXAMPLE_CONFIG_PATH, {})
    default_airplay = (
        default_config.get("airplay")
        if isinstance(default_config.get("airplay"), dict)
        else {}
    )
    eq_status = {
        "available": True,
        "installed": True,
        "bypassed": False,
        "bands": {
            band: {"db": 0.0, "stored_db": 0.0}
            for band in ("bass", "mid", "treble")
        },
    }
    receiver_status = {
        "available": True,
        "installed": True,
        "service_active": True,
        "receiver_name": str(default_airplay.get("display_name") or "Bedroom Plexamp"),
    }
    return unified_settings._public_settings(
        default_config,
        eq_status=eq_status,
        receiver_status=receiver_status,
    )


configuration_reset = ConfigurationResetPlanner(
    restore_planner=configuration_restore,
    current_backup=configuration_backup.build,
    default_settings=_reset_default_settings,
    eq_status=master_equalizer.status,
    mixer_status=shared_audio_mixer.status,
)
register_configuration_reset_preview_api(app, configuration_reset)
configuration_reset_executor = ConfigurationResetExecutor(
    planner=configuration_reset,
    restore_executor=configuration_restore_executor,
)
register_configuration_reset_apply_api(app, configuration_reset_executor)


if __name__ == "__main__":
    config = dashboard.load_config()
    dashboard_config = config.get("dashboard", {})
    dashboard.alarm_scheduler.start()
    dashboard.alarm_audio.start()
    weather_observations.start()
    weather_forecast.start()
    weather_rainfall.start()
    weather_rainfall_lifetime.start()
    bbc_news.start()
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
        bbc_news.shutdown()
        weather_rainfall_lifetime.shutdown()
        weather_rainfall.shutdown()
        weather_forecast.shutdown()
        weather_observations.shutdown()
        dashboard.alarm_audio.shutdown()
        dashboard.alarm_scheduler.stop()