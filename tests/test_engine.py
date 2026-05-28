import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class GameTuningTest(unittest.TestCase):
    def test_jump_arc_returns_to_ground_in_chrome_like_window(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()

        game.jump()
        airborne_frames = 0
        max_height = 0.0
        while game.jumping and airborne_frames < dino_game.FPS * 2:
            game.update()
            airborne_frames += 1
            max_height = max(max_height, game.dino_y)

        airborne_seconds = airborne_frames / dino_game.FPS
        self.assertGreaterEqual(airborne_seconds, 0.45)
        self.assertLessEqual(airborne_seconds, 0.70)
        self.assertGreaterEqual(max_height, 7.5)
        self.assertLessEqual(max_height, 9.5)

    def test_initial_scroll_crosses_playfield_at_chrome_like_pace(self):
        dino_game = importlib.import_module("dino_game")
        playfield_cols = 82 - dino_game.DINO_COL
        crossing_seconds = playfield_cols / (
            dino_game.INITIAL_SPEED * dino_game.FPS
        )

        self.assertGreaterEqual(crossing_seconds, 1.1)
        self.assertLessEqual(crossing_seconds, 1.6)

    def test_llm_run_uses_normal_obstacle_spawn_position(self):
        dino_game = importlib.import_module("dino_game")
        with tempfile.TemporaryDirectory() as tmpdir:
            game, _ = dino_game.start_recording_run(
                "llm",
                None,
                1,
                directory=tmpdir,
                seed=123,
            )

            game.score = 0
            game._spawn_obstacle()

        self.assertEqual(game.obstacles[0].x, dino_game.NORMAL_OBSTACLE_SPAWN_X)

    def test_llm_state_forecasts_future_obstacles_without_changing_game_state(self):
        dino_game = importlib.import_module("dino_game")
        rng = dino_game.random.Random(123)
        game = dino_game.DinoGame(rng=rng)
        spawn_timer = game.spawn_timer
        rng_state = rng.getstate()

        llm_state = game.get_llm_state()

        self.assertEqual(game.obstacles, [])
        self.assertEqual(game.spawn_timer, spawn_timer)
        self.assertEqual(rng.getstate(), rng_state)
        self.assertEqual(game.get_state()["obstacles"], [])
        self.assertTrue(llm_state["obstacles"])
        self.assertGreater(
            llm_state["obstacles"][0]["x"],
            dino_game.NORMAL_OBSTACLE_SPAWN_X,
        )
        self.assertLessEqual(
            llm_state["obstacles"][-1]["x"],
            dino_game.LLM_FORECAST_MAX_X,
        )
        self.assertIn("spawn_frame", llm_state["obstacles"][0])
        self.assertNotIn("frame", llm_state["obstacles"][0])
        self.assertEqual(llm_state["obstacles"][0]["forecast"], True)

    def test_rule_agent_waits_until_jump_window_after_speed_tuning(self):
        dino_game = importlib.import_module("dino_game")
        agent = dino_game.RuleAgent()
        state = {
            "dino_y": 0.0,
            "jumping": False,
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "cactus_lg",
                "distance": 27.0,
                "height": 0,
                "width": 5,
                "h": 6,
            }],
        }

        self.assertEqual(agent.decide(state), "none")
        state["obstacles"][0]["distance"] = 19.0
        self.assertEqual(agent.decide(state), "jump")

    def test_rule_agent_waits_for_late_jump_window_on_wide_short_cactus_groups(self):
        dino_game = importlib.import_module("dino_game")
        agent = dino_game.RuleAgent()
        state = {
            "dino_y": 0.0,
            "jumping": False,
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "cactus_group",
                "distance": 30.0,
                "height": 0,
                "width": 15,
                "h": 4,
            }],
        }

        self.assertEqual(agent.decide(state), "none")
        state["obstacles"][0]["distance"] = 17.0
        self.assertEqual(agent.decide(state), "jump")


class CollisionTest(unittest.TestCase):
    def make_game_with_obstacle(self, obstacle, *, dino_y=0.0, ducking=False):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()
        game.spawn_timer = 9999
        game.dino_y = dino_y
        if ducking:
            game.duck(True)
        game.obstacles = [obstacle]
        return game

    def test_cactus_collides_with_standing_dino(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("cactus_lg", dino_game.DINO_COL + 4)
        )

        game.update()

        self.assertTrue(game.game_over)

    def test_cactus_collides_with_ducking_dino(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("cactus_lg", dino_game.DINO_COL + 4),
            ducking=True,
        )

        game.update()

        self.assertTrue(game.game_over)

    def test_cactus_group_collides_with_each_plant(self):
        dino_game = importlib.import_module("dino_game")
        group = dino_game.Obstacle(
            "cactus_group",
            dino_game.DINO_COL + 4,
            plants=("short", "tall"),
        )
        game = self.make_game_with_obstacle(group)

        game.update()

        self.assertTrue(game.game_over)

    def test_cactus_group_uses_per_plant_hitboxes(self):
        dino_game = importlib.import_module("dino_game")
        group = dino_game.Obstacle(
            "cactus_group",
            dino_game.DINO_COL + 4,
            plants=("short", "tall"),
        )

        self.assertEqual(len(group.hitboxes), 2)
        self.assertLess(group.hitboxes[0][3], group.hitboxes[1][3])

    def test_cactus_does_not_collide_when_dino_is_high_enough(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("cactus_lg", dino_game.DINO_COL + 4),
            dino_y=7.0,
        )

        game.update()

        self.assertFalse(game.game_over)

    def test_obstacle_does_not_collide_without_horizontal_overlap(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("cactus_lg", dino_game.DINO_COL + 12)
        )

        game.update()

        self.assertFalse(game.game_over)

    def test_low_bird_collides_with_standing_dino(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("bird", dino_game.DINO_COL + 4, height=0)
        )

        game.update()

        self.assertTrue(game.game_over)

    def test_low_bird_collides_with_ducking_dino(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("bird", dino_game.DINO_COL + 4, height=0),
            ducking=True,
        )

        game.update()

        self.assertTrue(game.game_over)

    def test_low_bird_does_not_collide_when_dino_is_high_enough(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("bird", dino_game.DINO_COL + 4, height=0),
            dino_y=5.0,
        )

        game.update()

        self.assertFalse(game.game_over)

    def test_mid_bird_collides_with_standing_dino_head(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("bird", dino_game.DINO_COL + 4, height=4)
        )

        game.update()

        self.assertTrue(game.game_over)

    def test_mid_bird_does_not_collide_with_ducking_dino(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("bird", dino_game.DINO_COL + 4, height=4),
            ducking=True,
        )

        game.update()

        self.assertFalse(game.game_over)

    def test_high_bird_does_not_collide_with_standing_dino(self):
        dino_game = importlib.import_module("dino_game")
        game = self.make_game_with_obstacle(
            dino_game.Obstacle("bird", dino_game.DINO_COL + 4, height=8)
        )

        game.update()

        self.assertFalse(game.game_over)

    def test_rule_agent_ducks_under_mid_bird(self):
        dino_game = importlib.import_module("dino_game")
        agent = dino_game.RuleAgent()
        state = {
            "dino_y": 0.0,
            "jumping": False,
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "bird",
                "distance": 19.0,
                "height": 4,
                "width": 4,
                "h": 2,
            }],
        }

        self.assertEqual(agent.decide(state), "duck")

    def test_rule_agent_ignores_high_bird(self):
        dino_game = importlib.import_module("dino_game")
        agent = dino_game.RuleAgent()
        state = {
            "dino_y": 0.0,
            "jumping": False,
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "bird",
                "distance": 19.0,
                "height": 8,
                "width": 4,
                "h": 2,
            }],
        }

        self.assertEqual(agent.decide(state), "none")


class CactusGenerationTest(unittest.TestCase):
    def test_difficulty_increases_with_score(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.difficulty_for_score(0), 0.0)
        self.assertGreater(dino_game.difficulty_for_score(300), 0.0)
        self.assertLess(dino_game.difficulty_for_score(300), 1.0)
        self.assertEqual(dino_game.difficulty_for_score(600), 1.0)

    def test_generated_cactus_group_has_one_to_four_plants(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(100):
            group = dino_game.generate_cactus_group()
            self.assertGreaterEqual(len(group), 1)
            self.assertLessEqual(len(group), 4)

    def test_generated_cactus_group_uses_short_and_tall_plants(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(100):
            group = dino_game.generate_cactus_group()
            self.assertTrue(set(group).issubset({"short", "tall"}))

    def test_generated_cactus_group_never_has_four_tall_plants(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(1000):
            self.assertNotEqual(
                dino_game.generate_cactus_group(),
                ("tall", "tall", "tall", "tall"),
            )

    def test_long_generated_cactus_groups_have_at_most_one_tall_plant(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(1000):
            group = dino_game.generate_cactus_group()
            if len(group) >= 3:
                self.assertLessEqual(group.count("tall"), 1)

    def test_low_difficulty_limits_cactus_groups_to_two_plants(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(1000):
            self.assertLessEqual(len(dino_game.generate_cactus_group(0.0)), 2)

    def test_medium_difficulty_limits_cactus_groups_to_three_plants(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(1000):
            self.assertLessEqual(len(dino_game.generate_cactus_group(0.5)), 3)

    def test_cactus_group_obstacle_uses_composed_art_width(self):
        dino_game = importlib.import_module("dino_game")

        obstacle = dino_game.Obstacle("cactus_group", 82, plants=("short", "tall"))

        self.assertEqual(obstacle.kind, "cactus_group")
        self.assertEqual(obstacle.plants, ("short", "tall"))
        self.assertGreater(obstacle.width, dino_game.Obstacle("cactus_sm", 82).width)

    def test_early_spawn_uses_random_cactus_group(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()
        game.score = 0

        game._spawn_obstacle()

        self.assertEqual(game.obstacles[0].kind, "cactus_group")
        self.assertGreaterEqual(len(game.obstacles[0].plants), 1)
        self.assertLessEqual(len(game.obstacles[0].plants), 4)

    def test_early_spawn_does_not_create_long_cactus_group(self):
        dino_game = importlib.import_module("dino_game")

        for _ in range(100):
            game = dino_game.DinoGame()
            game.score = 0
            game._spawn_obstacle()
            self.assertLessEqual(len(game.obstacles[0].plants), 2)
