from __future__ import annotations

try:
    from . import main as dashboard
    from .audio_eq import register_audio_eq
except ImportError:  # Supports direct execution with: python app/runner.py
    import main as dashboard
    from audio_eq import register_audio_eq

app = dashboard.app
master_equalizer = register_audio_eq(app)


if __name__ == '__main__':
    config = dashboard.load_config()
    dashboard_config = config.get('dashboard', {})
    dashboard.alarm_scheduler.start()
    dashboard.alarm_audio.start()
    try:
        app.run(
            host=dashboard_config.get('host', '0.0.0.0'),
            port=int(dashboard_config.get('port', 8088)),
            debug=False,
            use_reloader=False,
        )
    finally:
        dashboard.alarm_audio.shutdown()
        dashboard.alarm_scheduler.stop()
