import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class ManualInputTest(unittest.TestCase):
    def test_down_key_latches_ducking_across_empty_frames(self):
        dino_game = importlib.import_module("dino_game")
        input_state = dino_game.ManualInputState()

        self.assertTrue(input_state.should_duck(dino_game.curses.KEY_DOWN))
        self.assertTrue(input_state.should_duck(-1))
        self.assertTrue(input_state.should_duck(-1))

    def test_next_non_down_key_releases_ducking(self):
        dino_game = importlib.import_module("dino_game")
        input_state = dino_game.ManualInputState()

        self.assertTrue(input_state.should_duck(dino_game.curses.KEY_DOWN))
        self.assertFalse(input_state.should_duck(ord(" ")))
        self.assertFalse(input_state.should_duck(-1))


class PauseFlowTest(unittest.TestCase):
    def test_enter_key_pauses_running_game(self):
        dino_game = importlib.import_module("dino_game")

        pause = dino_game.PauseState()
        paused = dino_game.next_pause_state(pause, 10, now=100.0)

        self.assertEqual(paused.status, "paused")
        self.assertFalse(dino_game.pause_allows_game_update(paused, now=100.0))

    def test_enter_key_starts_countdown_from_paused_game(self):
        dino_game = importlib.import_module("dino_game")

        pause = dino_game.PauseState(status="paused")
        countdown = dino_game.next_pause_state(pause, 10, now=100.0)

        self.assertEqual(countdown.status, "countdown")
        self.assertEqual(countdown.countdown_started_at, 100.0)
        self.assertEqual(dino_game.pause_overlay_lines(countdown, now=100.1)[0], "3")
        self.assertFalse(dino_game.pause_allows_game_update(countdown, now=102.9))

    def test_countdown_finishes_after_three_seconds(self):
        dino_game = importlib.import_module("dino_game")

        pause = dino_game.PauseState(status="countdown", countdown_started_at=100.0)
        running = dino_game.next_pause_state(pause, -1, now=103.0)

        self.assertEqual(running.status, "running")
        self.assertTrue(dino_game.pause_allows_game_update(running, now=103.0))


class GameOverFlowTest(unittest.TestCase):
    def test_agent_mode_does_not_auto_reset_after_game_over(self):
        dino_game = importlib.import_module("dino_game")

        self.assertFalse(dino_game.should_reset_after_game_over(-1, agent_active=True))

    def test_r_key_resets_after_game_over(self):
        dino_game = importlib.import_module("dino_game")

        self.assertTrue(dino_game.should_reset_after_game_over(ord("r"), agent_active=True))
        self.assertTrue(dino_game.should_reset_after_game_over(ord("R"), agent_active=False))
