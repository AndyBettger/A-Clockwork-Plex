from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from jinja2 import Environment


class SettingsIpadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = Path("app/templates/settings.html").read_text(encoding="utf-8")
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.client = Path("app/static/js/settings-ipad.js").read_text(encoding="utf-8")
        self.alarms = Path("app/static/js/settings-alarms.js").read_text(encoding="utf-8")
        self.transaction_guard = Path("app/static/js/settings-transaction-guard.js").read_text(encoding="utf-8")
        self.news_settings = Path("app/static/js/settings-news.js").read_text(encoding="utf-8")
        self.news_template = Path("app/templates/news.html").read_text(encoding="utf-8")
        self.news_client = Path("app/static/js/news.js").read_text(encoding="utf-8")

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
        self.assertIn("textContent = text(story.title)", self.news_client)
        self.assertIn("textContent = text(story.summary)", self.news_client)
        self.assertNotIn("window.open(", self.news_client)
        self.assertNotIn("window.location.assign", self.news_client)
        self.assertNotIn("location.href =", self.news_client)
        self.assertNotIn("<a ", self.news_template)
        self.assertIn("data-news-detail", self.news_template)
        self.assertIn("data-news-ticker", self.news_template)

    def test_news_settings_and_navigation_reuse_existing_owners(self):
        navigation = Path("app/templates/_nav.html").read_text(encoding="utf-8")
        transitions = Path("app/static/js/page-transitions.js").read_text(encoding="utf-8")
        news_ui = Path("app/news_ui.py").read_text(encoding="utf-8")

        self.assertIn("window.ACPUnifiedSettings.registerDomain('news'", self.news_settings)
        self.assertIn("window.ACPUnifiedSettings?.markDirty?.('news')", self.news_settings)
        self.assertNotIn("fetch(", self.news_settings)
        self.assertLess(self.base.index("settings-news.js"), self.base.index("{% block scripts %}"))
        self.assertIn('href="/news"', navigation)
        self.assertIn("'/news'", transitions)
        self.assertIn('MANUAL_LEASE_SCREENS.add("news")', news_ui)
        self.assertNotIn('IDLE_RETURN_SCREENS.add("news")', news_ui)

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
