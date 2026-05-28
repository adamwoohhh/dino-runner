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
