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


class GameOverSavePromptTest(unittest.TestCase):
    def rendered_text(self, save_status, retry_available=False):
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
                "",
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

    def rendered_text(self, summary):
        dino_game = importlib.import_module("dino_game")
        renderer = dino_game.Renderer.__new__(dino_game.Renderer)
        renderer.scr = self.FakeScreen()

        with mock.patch.object(dino_game.curses, "color_pair", side_effect=lambda value: value):
            renderer.draw_dashboard(summary, now=0.0)

        return "\n".join(text for _, _, text, _ in renderer.scr.calls)

    def test_draw_dashboard_renders_banner_and_mode_totals(self):
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
        ])

        self.assertIn("DINO", text)
        self.assertIn("▄███▄", text)
        self.assertIn("Today", text)
        self.assertIn("All time", text)
        self.assertIn("manual", text)
        self.assertIn("llm", text)
        self.assertIn("1.5K", text)
        self.assertIn("2.5M", text)
        self.assertIn("Q 退出", text)

    def test_draw_dashboard_renders_empty_state(self):
        text = self.rendered_text([
            {"label": "Today", "modes": {}},
            {"label": "All time", "modes": {}},
        ])

        self.assertIn("No completed games recorded yet.", text)
