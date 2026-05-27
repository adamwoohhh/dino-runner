import importlib
import os
import pathlib
import tempfile
import tomllib
import unittest


class PackagingTest(unittest.TestCase):
    def test_trex_console_script_points_at_cli_entrypoint(self):
        project_root = pathlib.Path(__file__).resolve().parents[1]
        pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())

        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["trex"], "dino_game:cli")

        dino_game = importlib.import_module("dino_game")
        self.assertTrue(callable(dino_game.cli))


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

        self.assertNotIn("切换", manual_hint)
        self.assertNotIn("切换", agent_hint)
        self.assertNotIn("切换", replay_hint)
        self.assertIn("Q 退出", manual_hint)
        self.assertIn("Q 退出", agent_hint)
        self.assertIn("Q 退出", replay_hint)


class ReplayTest(unittest.TestCase):
    def test_replay_recorder_writes_actions_and_obstacles_without_none_actions(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "run.json"
            recorder = dino_game.ReplayRecorder(path, seed=123, mode="agent")
            recorder.record_action(1, "none")
            recorder.record_obstacle(
                2,
                dino_game.Obstacle(
                    "cactus_group",
                    82,
                    plants=("short", "tall"),
                ),
            )
            recorder.record_action(2, "jump")
            recorder.save()

            data = dino_game.load_replay_file(path)
            self.assertEqual(data["seed"], 123)
            self.assertEqual(data["mode"], "agent")
            self.assertEqual(data["version"], 3)
            self.assertEqual(data["frames"], 2)
            self.assertEqual(data["actions"], [
                {"frame": 2, "action": {"value": "jump"}},
            ])
            self.assertEqual(data["obstacles"], [
                {
                    "frame": 2,
                    "action": {
                        "kind": "cactus_group",
                        "x": 82.0,
                        "height": 0,
                        "plants": ["short", "tall"],
                    },
                },
            ])

    def test_replay_player_returns_recorded_mode_actions_and_obstacles_by_frame(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "run.json"
            path.write_text(
                '{"version": 3, "seed": 99, "mode": "llm", "frames": 3, '
                '"actions": [{"frame": 1, "action": {"value": "jump"}}], '
                '"obstacles": [{"frame": 2, "action": {"kind": "bird", '
                '"x": 82, "height": 4}}]}'
            )

            player = dino_game.ReplayPlayer.from_file(path)
            self.assertEqual(player.seed, 99)
            self.assertEqual(player.mode, "llm")
            self.assertEqual(player.action_for_frame(1), "jump")
            self.assertEqual(player.action_for_frame(2), "none")
            self.assertEqual(player.action_for_frame(3), "none")
            self.assertEqual(player.obstacles_for_frame(2), [{
                "kind": "bird",
                "x": 82,
                "height": 4,
            }])
            self.assertTrue(player.has_frame(3))
            self.assertFalse(player.has_frame(4))

    def test_replay_player_converts_legacy_events_to_actions_and_obstacles(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "run.json"
            path.write_text(
                '{"version": 2, "seed": 99, "mode": "llm", "events": ['
                '{"frame": 1, "action": {"type": "input", "value": "jump"}},'
                '{"frame": 2, "action": {"type": "obstacle", "kind": "bird", '
                '"x": 82, "height": 4}},'
                '{"frame": 2, "action": {"type": "input", "value": "none"}}'
                ']}'
            )

            player = dino_game.ReplayPlayer.from_file(path)

            self.assertEqual(player.action_for_frame(1), "jump")
            self.assertEqual(player.action_for_frame(2), "none")
            self.assertEqual(player.obstacles_for_frame(2), [{
                "kind": "bird",
                "x": 82,
                "height": 4,
            }])

    def test_replay_player_converts_legacy_actions_to_frame_events(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "run.json"
            path.write_text(
                '{"version": 1, "seed": 99, "actions": ["jump", "none"]}'
            )

            player = dino_game.ReplayPlayer.from_file(path)

            self.assertEqual(player.action_for_frame(1), "jump")
            self.assertEqual(player.action_for_frame(2), "none")
            self.assertEqual(player.next_action(), "jump")
            self.assertIsNone(player.next_action())

    def test_obstacle_data_round_trips_to_obstacle(self):
        dino_game = importlib.import_module("dino_game")
        obstacle = dino_game.Obstacle(
            "cactus_group",
            82,
            plants=("short", "tall"),
        )

        data = dino_game.obstacle_to_action_data(obstacle)
        restored = dino_game.obstacle_from_action_data(data)

        self.assertEqual(restored.kind, "cactus_group")
        self.assertEqual(restored.x, 82)
        self.assertEqual(restored.height, 0)
        self.assertEqual(restored.plants, ("short", "tall"))

    def test_game_update_uses_replay_obstacles_instead_of_random_spawn(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()
        game.spawn_timer = 0

        spawned = game.update(replay_obstacles=[{
            "kind": "bird",
            "x": 82,
            "height": 4,
        }])

        self.assertEqual(len(spawned), 1)
        self.assertEqual(game.obstacles[0].kind, "bird")
        self.assertEqual(game.obstacles[0].height, 4)

    def test_default_replay_path_uses_replay_directory_and_mode(self):
        dino_game = importlib.import_module("dino_game")

        path = dino_game.default_replay_path("manual", seed=123456, directory="runs")

        self.assertTrue(path.startswith("runs" + os.sep))
        self.assertIn("-manual-", pathlib.Path(path).name)
        self.assertTrue(path.endswith(".json"))

    def test_explicit_record_path_adds_run_suffix_after_first_game(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(
            dino_game.record_path_for_run("run.json", "manual", 123, 1),
            "run.json",
        )
        self.assertEqual(
            dino_game.record_path_for_run("run.json", "manual", 123, 2),
            "run-2.json",
        )

    def test_finish_recording_saves_once_at_game_over(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "run.json"
            recorder = dino_game.ReplayRecorder(path, seed=123, mode="manual")

            dino_game.finish_recording(recorder)
            dino_game.finish_recording(recorder)

            data = dino_game.load_replay_file(path)
            self.assertEqual(data["seed"], 123)

    def test_start_recording_run_creates_new_default_file_per_game(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            _, first = dino_game.start_recording_run(
                "manual",
                None,
                1,
                directory=tmpdir,
                seed=111,
            )
            _, second = dino_game.start_recording_run(
                "manual",
                None,
                2,
                directory=tmpdir,
                seed=222,
            )

            self.assertNotEqual(first.path, second.path)
            self.assertIn("-manual-", pathlib.Path(first.path).name)
            self.assertIn("-manual-", pathlib.Path(second.path).name)

    def test_list_replay_files_returns_json_files_newest_first(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = pathlib.Path(tmpdir) / "old.json"
            new_path = pathlib.Path(tmpdir) / "new.json"
            ignored_path = pathlib.Path(tmpdir) / "notes.txt"
            old_path.write_text("{}")
            new_path.write_text("{}")
            ignored_path.write_text("ignore")
            os.utime(old_path, (10, 10))
            os.utime(new_path, (20, 20))

            self.assertEqual(
                dino_game.list_replay_files(tmpdir),
                [str(new_path), str(old_path)],
            )

    def test_move_replay_selection_wraps_with_arrow_keys(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.move_replay_selection(0, dino_game.curses.KEY_DOWN, 3), 1)
        self.assertEqual(dino_game.move_replay_selection(0, dino_game.curses.KEY_UP, 3), 2)
        self.assertEqual(dino_game.move_replay_selection(2, dino_game.curses.KEY_DOWN, 3), 0)

    def test_game_mode_from_args_tracks_manual_agent_and_llm(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.game_mode_from_args([]), "manual")
        self.assertEqual(dino_game.game_mode_from_args(["--agent"]), "agent")
        self.assertEqual(dino_game.game_mode_from_args(["--llm"]), "llm")

    def test_replay_seed_and_actions_are_deterministic(self):
        dino_game = importlib.import_module("dino_game")
        actions = ["none"] * 20 + ["jump"] + ["none"] * 40

        first = dino_game.run_replay_simulation(seed=42, actions=actions)
        second = dino_game.run_replay_simulation(seed=42, actions=actions)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
