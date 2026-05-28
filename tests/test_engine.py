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


class LoadingDinoSpriteTest(unittest.TestCase):
    def test_loading_dino_sprites_keep_existing_footprint(self):
        dino_game = importlib.import_module("dino_game")

        for sprite in (
            dino_game.DINO_LOADING_STAND,
            dino_game.DINO_LOADING_JUMP,
            dino_game.DINO_LOADING_DUCK,
        ):
            self.assertEqual(len(sprite), 6)
            self.assertLessEqual(max(len(line) for line in sprite), 10)

        self.assertEqual(dino_game.DINO_LOADING_DUCK[:2], ["          ", "          "])

    def test_loading_dino_open_frames_use_original_side_facing_sprites(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.DINO_LOADING_STAND, dino_game.DINO_RUN_1)
        self.assertEqual(dino_game.DINO_LOADING_JUMP_OPEN, dino_game.DINO_JUMP)
        self.assertEqual(dino_game.DINO_LOADING_DUCK_OPEN, dino_game.DINO_DUCK)

    def test_loading_dino_blink_frames_only_change_the_eye_line(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.DINO_LOADING_STAND_BLINK[0], dino_game.DINO_RUN_1[0])
        self.assertNotEqual(dino_game.DINO_LOADING_STAND_BLINK[1], dino_game.DINO_RUN_1[1])
        self.assertEqual(dino_game.DINO_LOADING_STAND_BLINK[2:], dino_game.DINO_RUN_1[2:])

        self.assertEqual(dino_game.DINO_LOADING_JUMP[0], dino_game.DINO_JUMP[0])
        self.assertNotEqual(dino_game.DINO_LOADING_JUMP[1], dino_game.DINO_JUMP[1])
        self.assertEqual(dino_game.DINO_LOADING_JUMP[2:], dino_game.DINO_JUMP[2:])

        self.assertEqual(dino_game.DINO_LOADING_DUCK[:3], dino_game.DINO_DUCK[:3])
        self.assertNotEqual(dino_game.DINO_LOADING_DUCK[3], dino_game.DINO_DUCK[3])
        self.assertEqual(dino_game.DINO_LOADING_DUCK[4:], dino_game.DINO_DUCK[4:])

    def test_loading_dino_art_animates_in_each_pose(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()

        standing_open = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=0.0,
        )
        standing_blink = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=dino_game.LOADING_DINO_ANIM_INTERVAL,
        )
        self.assertNotEqual(standing_open, standing_blink)

        game.jumping = True
        jumping_open = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=0.0,
        )
        jumping_blink = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=dino_game.LOADING_DINO_ANIM_INTERVAL,
        )
        self.assertNotEqual(jumping_open, jumping_blink)

        game.jumping = False
        game.ducking = True
        ducking_open = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=0.0,
        )
        ducking_blink = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=dino_game.LOADING_DINO_ANIM_INTERVAL,
        )
        self.assertNotEqual(ducking_open, ducking_blink)


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
