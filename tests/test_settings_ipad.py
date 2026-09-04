from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from jinja2 import Environment

from app.configuration_reset import ConfigurationResetExecutor, ConfigurationResetPlanner


class SettingsIpadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = Path("app/templates/settings.html").read_text(encoding="utf-8")
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.client = Path("app/static/js/settings-ipad.js").read_text(encoding="utf-8")
        self.advanced = Path("app/static/js/settings-advanced.js").read_text(encoding="utf-8")
        self.alarms = Path("app/static/js/settings-alarms.js").read_text(encoding="utf-8")
        self.transaction_guard = Path("app/static/js/settings-transaction-guard.js").read_text(encoding="utf-8")
        self.news_settings = Path("app/static/js/settings-news.js").read_text(encoding="utf-8")
        self.news_template = Path("app/templates/news.html").read_text(encoding="utf-8")
        self.news_client = Path("app/static/js/news.js").read_text(encoding="utf-8")
        self.news_css = Path("app/static/css/news.css").read_text(encoding="utf-8")
        self.screen_projection = Path("app/static/js/screen-projection.js").read_text(encoding="utf-8")
        self.dashboard_preferences = Path("app/static/js/dashboard-preferences-bootstrap.js").read_text(encoding="utf-8")
        self.runner = Path("app/runner.py").read_text(encoding="utf-8")
        self.reset_owner = Path("app/configuration_reset.py").read_text(encoding="utf-8")

    def test_template_uses_persistent_sidebar_and_right_detail_pane(self):
        self.assertIn("settings-ipad-shell", self.template)
        self.assertIn("settings-sidebar", self.template)
        self.assertIn("settings-detail", self.template)
        categories = {
            "general": "General",
            "display": "Display",
            "weather": "Weather",
            "alarms": "Alarms",
            "airplay": "AirPlay",
            "audio": "Audio",
            "plexamp": "Plexamp",
            "advanced": "Advanced",
            "about": "About",
        }
        self.assertIn('data-settings-section-target="{{ item[0] }}"', self.template)
        for section, label in categories.items():
            self.assertIn(f"('{section}', '{label}'", self.template)
            self.assertIn(f'data-settings-section="{section}"', self.template)
        self.assertNotIn("data-settings-tabs", self.template)
        self.assertNotIn("settings-tabs.js", self.template)
        Environment().parse(self.template)

    def test_sections_use_subpages_to_reduce_vertical_scrolling(self):
        for subpage in (
            "weather:station",
            "weather:units",
            "weather:forecast",
            "weather:clock-cards",
            "alarms:schedule",
            "alarms:defaults",
            "alarms:sound",
            "airplay:receiver",
            "airplay:starting-volume",
            "airplay:handoff",
            "audio:trims",
            "audio:eq",
            "audio:hardware",
            "plexamp:connection",
            "plexamp:service",
            "advanced:alarm",
            "advanced:audio",
            "advanced:authorities",
            "advanced:services",
        ):
            self.assertIn(f'data-settings-subpage="{subpage}"', self.template)
        self.assertIn("data-settings-back", self.template)

    def test_one_save_bar_owns_staged_configuration(self):
        self.assertEqual(self.template.count("Save Changes"), 1)
        self.assertIn('id="settings-unified-form"', self.template)
        self.assertIn("/api/settings", self.client)
        self.assertIn("revision: snapshot.revision", self.client)
        self.assertIn("confirm_airplay_restart", self.client)
        self.assertNotIn("settings-autosave.js", self.base)
        self.assertNotIn("settings-dashboard-preferences.js", self.base)
        self.assertNotIn("settings-alarm-workspace.js", self.base)
        self.assertNotIn("settings-alarm-scheduled.js", self.base)
        self.assertNotIn("settings-alarm-scheduler.js", self.base)

    def test_confirmed_airplay_retry_cannot_accept_a_duplicate_submit(self):
        self.assertIn("settings-transaction-guard.js", self.base)
        self.assertIn("20260802-single-transaction", self.base)
        self.assertIn("activeTransactions", self.transaction_guard)
        self.assertIn("/api/settings", self.transaction_guard)
        self.assertIn("event.stopImmediatePropagation()", self.transaction_guard)
        self.assertIn("aria-busy", self.transaction_guard)

    def test_weather_presets_keep_individual_unit_controls(self):
        self.assertIn('data-unit-preset="uk"', self.template)
        self.assertIn('data-unit-preset="metric"', self.template)
        self.assertIn('data-unit-preset="imperial"', self.template)
        self.assertIn('data-unit-preset="custom"', self.template)
        for path in (
            "weather.units.temperature",
            "weather.units.pressure",
            "weather.units.rain",
            "weather.units.wind",
        ):
            self.assertIn(f'data-setting-path="{path}"', self.template)
        self.assertIn("currentUnitPreset", self.client)
        self.assertIn("markDirty('weather')", self.client)

    def test_receiver_management_and_live_eq_remain_first_class_settings(self):
        self.assertIn('data-setting-path="airplay.receiver_name"', self.template)
        self.assertIn("Save and restart AirPlay", self.template)
        self.assertIn("automatic rollback", self.template)
        self.assertIn('id="acp-eq-settings-card"', self.template)
        self.assertIn("{% for band in ['bass','mid','treble'] %}", self.template)
        self.assertIn('data-eq-range="{{ band }}"', self.template)
        self.assertIn('id="acp-eq-settings-bypass"', self.template)
        self.assertIn('id="acp-eq-settings-neutral"', self.template)
        self.assertNotIn('data-setting-path="audio.eq.enabled"', self.template)
        self.assertNotIn('data-setting-path="audio.eq.bands.{{ band }}"', self.template)
        self.assertIn("Production ready", self.client)

    def test_alarm_editor_registers_with_transaction_instead_of_saving_itself(self):
        self.assertIn("registerDomain?.('alarms'", self.alarms)
        self.assertIn("validatedModel", self.alarms)
        self.assertNotIn("method: 'POST'", self.alarms)
        self.assertNotIn("saveAlarmModel", self.alarms)
        self.assertNotIn("HTMLFormElement.prototype.submit", self.alarms)

    def test_clock_card_editor_participates_in_save_and_discard(self):
        clock_cards = Path("app/static/js/settings-clock-cards.js").read_text(encoding="utf-8")
        self.assertIn("window.ACPClockCards", clock_cards)
        self.assertIn("applyStoredIds", clock_cards)
        self.assertIn("storedIds", clock_cards)
        self.assertIn("window.ACPClockCards?.storedIds?.()", self.client)
        self.assertIn("applyClockCards(loadedSettings)", self.client)
        self.assertNotIn("new MutationObserver", self.client)

    def test_actions_are_explicitly_separate_from_configuration(self):
        for action in (
            "refresh-forecast",
            "refresh-mixer",
            "alarm-audio-test",
            "alarm-audio-stop",
            "refresh-authorities",
            "refresh-services",
        ):
            self.assertIn(f'data-action="{action}"', self.template)
        self.assertIn("Applied immediately", self.template)
        self.assertIn("Live controls and tests act immediately", self.template)

    def test_news_page_is_cache_only_and_cannot_navigate_to_articles(self):
        self.assertIn("const API = '/api/news';", self.news_client)
        self.assertEqual(self.news_client.count("fetch("), 1)
        self.assertIn("const MAX_VISIBLE_STORIES = 24;", self.news_client)
        self.assertIn("const MAX_TICKER_STORIES = 12;", self.news_client)
        self.assertIn("return text(story?.title).toLocaleLowerCase('en-GB');", self.news_client)
        self.assertIn("textContent = text(story.title)", self.news_client)
        self.assertIn("textContent = text(story.summary)", self.news_client)
        self.assertNotIn("window.open(", self.news_client)
        self.assertNotIn("window.location.assign", self.news_client)
        self.assertNotIn("location.href =", self.news_client)
        self.assertNotIn("<a ", self.news_template)
        self.assertIn("data-news-detail", self.news_template)
        self.assertIn("data-news-ticker", self.news_template)
        self.assertNotIn("data-news-updated", self.news_template)
        self.assertIn('class="news-page is-ticker-hidden"', self.news_template)
        self.assertIn("page?.classList.add('is-ticker-hidden')", self.news_client)
        self.assertIn("page?.classList.remove('is-ticker-hidden')", self.news_client)
        self.assertIn(".news-page.is-ticker-hidden", self.news_css)
        self.assertIn(".news-ticker[hidden]", self.news_css)
        self.assertIn("display: none;", self.news_css)

    def test_news_feed_time_and_story_scroll_use_dashboard_chrome(self):
        self.assertIn('class="news-source-time news-source-pill"', self.news_template)
        self.assertIn("data-news-story-scrollbar", self.news_template)
        self.assertIn('aria-orientation="vertical"', self.news_template)
        self.assertIn("bindStoryScrollbar", self.news_client)
        self.assertIn("storyMount.scrollTop", self.news_client)
        self.assertIn("storyMount.addEventListener('scroll', update", self.news_client)
        self.assertIn("scrollbar-width: none", self.news_css)
        self.assertIn(".news-story-scrollbar-thumb", self.news_css)
        self.assertIn("linear-gradient(180deg, var(--accent), var(--accent-strong))", self.news_css)

    def test_news_settings_and_navigation_reuse_existing_owners(self):
        navigation = Path("app/templates/_nav.html").read_text(encoding="utf-8")
        transitions = Path("app/static/js/page-transitions.js").read_text(encoding="utf-8")
        news_ui = Path("app/news_ui.py").read_text(encoding="utf-8")

        self.assertIn("window.ACPUnifiedSettings.registerDomain('news'", self.news_settings)
        self.assertIn("window.ACPUnifiedSettings?.markDirty?.('news')", self.news_settings)
        self.assertNotIn("fetch(", self.news_settings)
        self.assertIn('data-settings-overview="news"', self.news_settings)
        self.assertIn('data-settings-subpage-target="news:sections"', self.news_settings)
        self.assertIn('data-settings-subpage-target="news:presentation"', self.news_settings)
        self.assertIn('data-settings-subpage="news:sections"', self.news_settings)
        self.assertIn('data-settings-subpage="news:presentation"', self.news_settings)
        self.assertIn('data-settings-back="news"', self.news_settings)
        self.assertLess(self.base.index("settings-news.js"), self.base.index("{% block scripts %}"))
        self.assertIn('href="/news"', navigation)
        self.assertIn("'/news'", transitions)
        self.assertIn("news: '/news'", self.screen_projection)
        self.assertIn('MANUAL_LEASE_SCREENS.add("news")', news_ui)
        self.assertIn('IDLE_RETURN_SCREENS.add("news")', news_ui)
        self.assertIn('_settings_unified.VALID_MODES.add("news")', news_ui)
        self.assertIn('_install_news_settings_mode_option(dashboard)', news_ui)
        self.assertIn('core = getattr(dashboard, "core", None)', news_ui)
        self.assertIn('_wrap_news_settings_mode_option(core)', news_ui)
        self.assertIn('{"id": "news", "label": "News"}', news_ui)

    def test_news_is_rendered_in_both_production_settings_destination_lists(self):
        script = "\n".join(
            [
                "from app import runner",
                "from app import dashboard_core as core",
                "core.set_mode = lambda _mode: {}",
                "response = runner.app.test_client().get('/settings')",
                "assert response.status_code == 200, response.status_code",
                "html = response.get_data(as_text=True)",
                "assert html.count('<option value=\"news\">News</option>') == 2, html.count('<option value=\"news\">News</option>')",
            ]
        )
        result = subprocess.run(
            ["python", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_news_is_valid_during_startup_bootstrap(self):
        self.assertIn(
            "new Set(['clock', 'weather', 'news', 'airplay', 'plexamp'])",
            self.dashboard_preferences,
        )
        self.assertIn("window.location.replace(`/${preferences.startupMode}`)", self.dashboard_preferences)

    def test_reset_to_defaults_is_separate_advanced_workflow(self):
        self.assertIn("advanced:reset", self.advanced)
        self.assertIn("Reset to defaults", self.advanced)
        self.assertIn("This is not a factory wipe.", self.advanced)
        self.assertIn("Plexamp Home customisation", self.advanced)
        self.assertIn("Preserved for now", self.advanced)
        self.assertIn("settingsHaveUnsavedChanges", self.advanced)
        self.assertIn("Preview reset", self.advanced)
        self.assertIn("Review reset", self.advanced)
        self.assertIn("Confirm &amp; reset", self.advanced)
        self.assertIn("/api/settings/reset/preview", self.advanced)
        self.assertIn("/api/settings/reset/apply", self.advanced)
        self.assertIn("reset_token: plan.reset_token", self.advanced)
        self.assertIn("confirm_reset: true", self.advanced)

    def test_reset_owner_reuses_restore_transaction_and_never_resets_plexamp_auth(self):
        captured = {}

        class FakeRestorePlanner:
            def plan(self, target):
                captured["target"] = target
                return {
                    "server_changed_paths": [
                        "a_clockwork_plex.settings.dashboard.startup_mode",
                        "a_clockwork_plex.audio.eq.bands.bass",
                    ],
                    "sections": {"settings.dashboard": 1, "audio.eq": 1},
                    "warnings": [],
                    "confirmations_required": [],
                    "preview_token": "a" * 32,
                }

        defaults = {
            "dashboard": {"startup_mode": "clock", "idle_return_mode": "clock", "idle_timeout_seconds": 180},
            "display": {"clock_format": "24h"},
            "weather": {},
            "alarms": {},
            "airplay": {"receiver_name": "Bedroom Plexamp"},
            "news": {"enabled_categories": ["top"], "default_category": "top", "show_summaries": True, "ticker": {"enabled": True, "speed": "normal"}},
            "plexamp": {"url": "http://should-not-be-reset.invalid", "service_name": "must-be-preserved"},
        }
        current = {
            "source": {"app_version": "0.4.0"},
            "plexamp": {
                "source_version": "4.13.2",
                "headless_preferences": {"autoPlayEnabled": False},
                "browser_preferences": {"schema_version": 1, "home": {"order": ["one"], "hidden": []}},
            },
        }
        planner = ConfigurationResetPlanner(
            restore_planner=FakeRestorePlanner(),
            current_backup=lambda: current,
            default_settings=lambda: defaults,
            eq_status=lambda: {"available": True},
            mixer_status=lambda: {"available": True, "configured": True},
        )

        result = planner.plan()
        target = captured["target"]
        self.assertTrue(result["read_only"])
        self.assertFalse(result["apply_enabled"])
        self.assertTrue(result["reset_available"])
        self.assertEqual(result["reset_token"], "a" * 32)
        self.assertEqual(target["plexamp"], {})
        self.assertNotIn("plexamp", target["a_clockwork_plex"]["settings"])
        self.assertEqual(target["a_clockwork_plex"]["audio"]["eq"]["bands"], {"bass": 0.0, "mid": 0.0, "treble": 0.0})
        # Reset intentionally restores the persistent mixer baseline to full scale.
        self.assertEqual(target["a_clockwork_plex"]["audio"]["mixer"], {"master": 100, "plexamp": 100, "airplay": 100, "alarm": 100})
        self.assertTrue(any("Plex/Plexamp login" in item for item in result["preserved"]))

    def test_reset_executor_rebuilds_target_and_delegates_to_restore_executor(self):
        calls = []

        class FakeRestorePlanner:
            def plan(self, target):
                return {
                    "server_changed_paths": ["a_clockwork_plex.settings.dashboard.startup_mode"],
                    "sections": {"settings.dashboard": 1},
                    "warnings": [],
                    "confirmations_required": [],
                    "preview_token": "b" * 32,
                }

        class FakeRestoreExecutor:
            def apply(self, target, **kwargs):
                calls.append((target, kwargs))
                return {"applied_change_count": 1, "applied_sections": ["settings.dashboard"]}

        planner = ConfigurationResetPlanner(
            restore_planner=FakeRestorePlanner(),
            current_backup=lambda: {"source": {"app_version": "0.4.0"}},
            default_settings=lambda: {
                "dashboard": {"startup_mode": "clock", "idle_return_mode": "clock", "idle_timeout_seconds": 180},
                "display": {},
                "weather": {},
                "alarms": {},
                "airplay": {},
            },
            eq_status=lambda: {"available": False},
            mixer_status=lambda: {"available": False, "configured": False},
        )
        executor = ConfigurationResetExecutor(planner=planner, restore_executor=FakeRestoreExecutor())
        result = executor.apply(reset_token="b" * 32, confirm_reset=True)

        self.assertTrue(result["reset"])
        self.assertTrue(result["credentials_preserved"])
        self.assertTrue(result["plexamp_auth_preserved"])
        self.assertFalse(result["plexamp_home_reset"])
        self.assertEqual(len(calls), 1)
        target, kwargs = calls[0]
        self.assertEqual(target["plexamp"], {})
        self.assertEqual(target["a_clockwork_plex"]["audio"], {})
        self.assertEqual(kwargs["preview_token"], "b" * 32)
        self.assertTrue(kwargs["confirm_restore"])

    def test_production_reset_preview_is_read_only_and_server_owned(self):
        script = "\n".join(
            [
                "from app import runner",
                "response = runner.app.test_client().post('/api/settings/reset/preview', json={})",
                "assert response.status_code == 200, response.get_data(as_text=True)",
                "payload = response.get_json()",
                "assert payload['ok'] is True",
                "assert payload['read_only'] is True",
                "assert payload['apply_enabled'] is False",
                "assert payload['defaults_source'].startswith('config.example.json')",
                "assert payload['plexamp_home']['included'] is False",
                "assert 'no-store' in response.headers.get('Cache-Control', '')",
            ]
        )
        result = subprocess.run(
            ["python", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("ConfigurationResetPlanner", self.runner)
        self.assertIn("register_configuration_reset_preview_api(app, configuration_reset)", self.runner)
        self.assertIn("register_configuration_reset_apply_api(app, configuration_reset_executor)", self.runner)
        self.assertIn("dashboard.load_json(dashboard.EXAMPLE_CONFIG_PATH, {})", self.runner)
        self.assertIn('"plexamp": {}', self.reset_owner)

    def test_new_clients_have_valid_javascript_syntax(self):
        for path in (
            "app/static/js/settings-transaction-guard.js",
            "app/static/js/settings-ipad.js",
            "app/static/js/settings-advanced.js",
            "app/static/js/settings-alarms.js",
            "app/static/js/settings-news.js",
            "app/static/js/news.js",
        ):
            result = subprocess.run(
                ["node", "--check", path],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
