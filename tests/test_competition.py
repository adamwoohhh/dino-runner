import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class CompetitionModeTest(unittest.TestCase):
    def make_replay_player(self, *, frames=1, obstacles=None, actions=None):
        dino_game = importlib.import_module("dino_game")
        return dino_game.ReplayPlayer(
            seed=99,
            actions=actions or [],
            obstacles=obstacles or [],
            frames=frames,
        )

    def test_competition_run_feeds_source_obstacles_to_both_lanes(self):
        dino_game = importlib.import_module("dino_game")
        replay = self.make_replay_player(
            frames=1,
            obstacles=[{
                "frame": 1,
                "action": {
                    "kind": "bird",
                    "x": 82,
                    "height": 4,
                },
            }],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            recorder_path = pathlib.Path(tmpdir) / "competition.json"
            run = dino_game.CompetitionRun(
                replay,
                source_replay="replays/source.json",
                record_path=recorder_path,
            )

            self.assertEqual(run.recorder.mode, "competitive")
            run.step("jump")

            self.assertEqual(run.history_game.obstacles[0].kind, "bird")
            self.assertEqual(run.player_game.obstacles[0].kind, "bird")
            self.assertEqual(run.recorder.actions, [
                {"frame": 1, "action": {"value": "jump"}},
            ])
            self.assertEqual(run.recorder.obstacles, [{
                "frame": 1,
                "action": {
                    "kind": "bird",
                    "x": 82.0,
                    "height": 4,
                },
            }])

    def test_competition_run_uses_seeded_generation_after_source_frames(self):
        dino_game = importlib.import_module("dino_game")
        replay = self.make_replay_player(frames=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            recorder_path = pathlib.Path(tmpdir) / "competition.json"
            run = dino_game.CompetitionRun(
                replay,
                source_replay="replays/source.json",
                record_path=recorder_path,
            )
            run.player_game.spawn_timer = 0

            run.step("none")

            self.assertEqual(len(run.recorder.obstacles), 1)
            self.assertEqual(run.recorder.obstacles[0]["frame"], 1)

    def test_competition_run_finishes_only_after_history_and_player_end(self):
        dino_game = importlib.import_module("dino_game")
        replay = self.make_replay_player(frames=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            recorder_path = pathlib.Path(tmpdir) / "competition.json"
            run = dino_game.CompetitionRun(
                replay,
                source_replay="replays/source.json",
                record_path=recorder_path,
            )

            run.step("none")

            self.assertTrue(run.history_finished)
            self.assertFalse(run.player_finished)
            self.assertFalse(run.finished)

            run.player_game.game_over = True
            run.step("none")

            self.assertTrue(run.player_finished)
            self.assertTrue(run.finished)
            data = dino_game.load_replay_file(recorder_path)
            self.assertTrue(data["competitive"])
            self.assertEqual(data["mode"], "competitive")
            self.assertEqual(data["source_replay"], "replays/source.json")
