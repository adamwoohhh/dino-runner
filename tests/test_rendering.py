import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class RendererHintTest(unittest.TestCase):
    def test_footer_hints_do_not_offer_runtime_mode_toggle(self):
        dino_game = importlib.import_module("dino_game")

        manual_hint = dino_game.footer_hint(agent_name="", speed=1.75)
        agent_hint = dino_game.footer_hint(agent_name="Rule Agent", speed=1.75)
        replay_hint = dino_game.footer_hint(agent_name="Replay", speed=1.75)
        competition_hint = dino_game.footer_hint(agent_name="Competition", speed=1.75)

        self.assertNotIn("切换", manual_hint)
        self.assertNotIn("切换", agent_hint)
        self.assertNotIn("切换", replay_hint)
        self.assertNotIn("切换", competition_hint)
        self.assertIn("Q 退出", manual_hint)
        self.assertIn("Q 退出", agent_hint)
        self.assertIn("Q 退出", replay_hint)
        self.assertIn("Q 退出", competition_hint)
        self.assertIn("速度 1.8x", manual_hint)
        self.assertIn("竞技", competition_hint)


class CachedFrameRendererTest(unittest.TestCase):
    def test_draw_cached_frame_window_uses_distinct_attrs_for_current_frame(self):
        dino_game = importlib.import_module("dino_game")

        class FakeScreen:
            def __init__(self):
                self.calls = []

            def getmaxyx(self):
                return (24, 120)

            def addstr(self, y, x, text, attr):
                self.calls.append((y, x, text, attr))

        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = FakeScreen()
        window = dino_game.cached_frame_window(
            planned_actions={10: "none", 11: "jump"},
            consumed_actions={9: "duck"},
            current_frame=10,
            radius=1,
        )

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value * 100):
            renderer.draw_cached_frame_window(20, 2, window)

        segments = {text: attr for _, _, text, attr in renderer.scr.calls}
        self.assertIn("Frame    10  ", segments)
        self.assertIn(" ↓ ", segments)
        self.assertIn("[-]", segments)
        self.assertIn(" ↑ ", segments)
        self.assertNotEqual(segments["[-]"], segments[" ↓ "])
        self.assertNotEqual(segments["[-]"], segments[" ↑ "])

    def test_draw_renders_llm_usage_text_above_footer(self):
        dino_game = importlib.import_module("dino_game")

        class FakeScreen:
            def __init__(self):
                self.calls = []

            def erase(self):
                pass

            def getmaxyx(self):
                return (24, 120)

            def addstr(self, y, x, text, attr=0):
                self.calls.append((y, x, text, attr))

            def refresh(self):
                pass

        game = dino_game.DinoGame()
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = FakeScreen()

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw(game, "LLM Agent", llm_usage_text="LLM tokens: 7,470")

        self.assertTrue(any(
            y == 22 and x == 2 and text == "LLM tokens: 7,470"
            for y, x, text, _ in renderer.scr.calls
        ))

    def test_draw_renders_celestial_background(self):
        dino_game = importlib.import_module("dino_game")

        class FakeScreen:
            def __init__(self):
                self.calls = []

            def erase(self):
                pass

            def getmaxyx(self):
                return (24, 120)

            def addstr(self, y, x, text, attr=0):
                self.calls.append((y, x, text, attr))

            def refresh(self):
                pass

        game = dino_game.DinoGame()
        game.celestial = {"kind": "moon", "x": 90.0, "y": 2}
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = FakeScreen()

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw(game, "")

        self.assertTrue(any(
            text in dino_game.MOON
            for _, _, text, _ in renderer.scr.calls
        ))


class GameOverSavePromptTest(unittest.TestCase):
    def rendered_text(self, save_status, retry_available=False, agent_name=""):
        dino_game = importlib.import_module("dino_game")

        class FakeScreen:
            def __init__(self):
                self.calls = []

            def erase(self):
                pass

            def getmaxyx(self):
                return (24, 120)

            def addstr(self, y, x, text, attr=0):
                self.calls.append(text)

            def refresh(self):
                pass

        game = dino_game.DinoGame()
        game.game_over = True
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = FakeScreen()
        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw(
                game,
                agent_name,
                game_over_save_status=save_status,
                game_over_retry_available=retry_available,
            )
        return "\n".join(renderer.scr.calls)

    def test_game_over_prompt_shows_save_action_before_save(self):
        self.assertIn("S = 保存游戏记录", self.rendered_text("unsaved"))

    def test_game_over_prompt_shows_saved_message_after_save(self):
        self.assertIn("已保存记录", self.rendered_text("saved"))

    def test_llm_game_over_prompt_shows_recalculate_action(self):
        self.assertIn("C = 失败处重试", self.rendered_text("unsaved", retry_available=True))
        self.assertIn("R = 重新开始", self.rendered_text("unsaved", retry_available=True))

    def test_replay_game_over_prompt_only_shows_exit_action(self):
        text = self.rendered_text("unsaved", retry_available=True, agent_name="Replay")

        self.assertIn("Q = 退出", text)
        self.assertNotIn("S = 保存游戏记录", text)
        self.assertNotIn("C = 失败处重试", text)
        self.assertNotIn("R = 重新开始", text)


class DashboardRendererTest(unittest.TestCase):
    class FakeScreen:
        def __init__(self):
            self.calls = []

        def erase(self):
            pass

        def getmaxyx(self):
            return (32, 120)

        def addstr(self, y, x, text, attr=0):
            self.calls.append((y, x, text, attr))

        def refresh(self):
            pass

    def rendered_text(self, summary, active_mode=None):
        dino_game = importlib.import_module("dino_game")
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = self.FakeScreen()

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw_dashboard(summary, active_mode=active_mode, now=0.0)

        return "\n".join(text for _, _, text, _ in renderer.scr.calls)

    def test_draw_dashboard_renders_tabs_and_selected_mode_list(self):
        text = self.rendered_text([
            {
                "label": "Today",
                "modes": {
                    "manual": {"score": 12, "total_tokens": 0},
                    "llm": {"score": 34, "total_tokens": 1500},
                },
            },
            {
                "label": "All time",
                "modes": {
                    "llm": {"score": 56, "total_tokens": 2_500_000},
                },
            },
        ], active_mode="manual")

        self.assertIn(importlib.import_module("dino_game").DINO_LOGO[0], text)
        self.assertIn("▄███▄", text)
        self.assertIn("[manual]\tllm", text)
        self.assertIn("Today", text)
        self.assertIn("All time", text)
        self.assertIn("manual", text)
        self.assertIn("llm", text)
        self.assertIn("Today        | 累计得分     12", text)
        self.assertNotIn("累计消耗token 0", text)
        self.assertNotIn("1.5K", text)
        self.assertNotIn("2.5M", text)
        self.assertNotIn("Window", text)
        self.assertNotIn("Tokens", text)
        self.assertIn("Q 退出", text)

    def test_draw_dashboard_renders_token_only_when_selected_mode_has_usage(self):
        text = self.rendered_text([
            {
                "label": "Today",
                "modes": {
                    "manual": {"score": 12, "total_tokens": 0},
                    "llm": {"score": 34, "total_tokens": 1500},
                },
            },
            {
                "label": "All time",
                "modes": {
                    "llm": {"score": 56, "total_tokens": 2_500_000},
                },
            },
        ], active_mode="llm")

        self.assertIn("manual\t[llm]", text)
        self.assertIn("Today        | 累计得分     34 | 累计消耗token     1.5K", text)
        self.assertIn("All time     | 累计得分     56 | 累计消耗token     2.5M", text)
        self.assertNotIn("Today | 累计得分 12", text)

    def test_draw_dashboard_aligns_list_columns_and_shows_tab_hint(self):
        text = self.rendered_text([
            {
                "label": "Today",
                "modes": {"llm": {"score": 34, "total_tokens": 1500}},
            },
            {
                "label": "Last 90 days",
                "modes": {"llm": {"score": 1234, "total_tokens": 2_500_000}},
            },
        ], active_mode="llm")

        self.assertIn("Today        | 累计得分     34 | 累计消耗token     1.5K", text)
        self.assertIn("Last 90 days | 累计得分   1234 | 累计消耗token     2.5M", text)
        self.assertIn("←/→ 切换 tab | Q 退出", text)

    def test_draw_dashboard_banner_uses_six_row_pixel_logo_without_subtitle(self):
        dino_game = importlib.import_module("dino_game")
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = self.FakeScreen()

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw_dashboard([
                {"label": "Today", "modes": {"manual": {"score": 12, "total_tokens": 0}}},
            ], active_mode="manual", now=0.0)

        calls = renderer.scr.calls
        logo_rows = [y for y, _, text, _ in calls if text in dino_game.DINO_LOGO]
        sprite_rows = [y for y, _, text, _ in calls if "▄███▄" in text]

        self.assertEqual(len(dino_game.DINO_LOGO), 6)
        self.assertEqual(logo_rows, list(range(sprite_rows[0], sprite_rows[0] + 6)))
        self.assertNotIn("DINO", "\n".join(text for _, _, text, _ in calls))
        self.assertNotIn("Score Dashboard", "\n".join(text for _, _, text, _ in calls))

    def test_draw_dashboard_banner_places_dino_left_of_full_dino_logo(self):
        dino_game = importlib.import_module("dino_game")
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = self.FakeScreen()

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw_dashboard([
                {"label": "Today", "modes": {"manual": {"score": 12, "total_tokens": 0}}},
            ], active_mode="manual", now=0.0)

        calls = renderer.scr.calls
        logo_top = next((y, x, text) for y, x, text, _ in calls if text == dino_game.DINO_LOGO[0])
        dino_top = next((y, x, text) for y, x, text, _ in calls if "▄███▄" in text)

        self.assertLess(dino_top[1], logo_top[1])
        self.assertEqual(dino_game.DINO_LOGO[0], "████▄  █  █  █   ██   ")
        self.assertEqual(dino_game.DINO_LOGO[1], "█   █  █  ██ █  █  █  ")

    def test_draw_dashboard_renders_empty_state(self):
        text = self.rendered_text([
            {"label": "Today", "modes": {}},
            {"label": "All time", "modes": {}},
        ])

        self.assertIn("No completed games recorded yet.", text)
