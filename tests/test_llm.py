import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class LLMConfigTest(unittest.TestCase):
    def dino_game(self):
        return importlib.import_module("dino_game")

    def test_config_file_path_uses_user_config_directory(self):
        dino_game = self.dino_game()

        self.assertEqual(
            dino_game.config_file_path("/tmp/home"),
            os.path.join("/tmp/home", ".config", "ai-dino-in-terminal", "config.json"),
        )

    def test_load_save_reset_and_render_llm_config(self):
        dino_game = self.dino_game()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            config = dino_game.LLMConfig(
                api_key="sk-abcdefghijklmnopqrstuvwxyz",
                base_url="https://example.test/v1",
                model="gpt-test",
                llm_window_frames=720,
            )

            dino_game.save_llm_config(config, config_path)

            self.assertEqual(dino_game.load_llm_config(config_path), config)
            stored = json.loads(config_path.read_text())
            self.assertEqual(stored["llm_mode"], "API")
            self.assertEqual(stored["api_key"], "sk-abcdefghijklmnopqrstuvwxyz")
            self.assertEqual(stored["llm_window_frames"], 720)

            rendered = dino_game.render_llm_config(config)
            self.assertIn("llm_mode: API", rendered)
            self.assertIn("api_key: sk-a...wxyz", rendered)
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", rendered)
            self.assertIn("base_url: https://example.test/v1", rendered)
            self.assertIn("model: gpt-test", rendered)
            self.assertIn("llm_window_frames: 720", rendered)

            self.assertTrue(dino_game.reset_llm_config(config_path))
            self.assertFalse(config_path.exists())
            self.assertFalse(dino_game.reset_llm_config(config_path))

    def test_missing_config_does_not_render_api_endpoint_defaults(self):
        dino_game = self.dino_game()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "missing.json"

            config = dino_game.load_llm_config(config_path)
            rendered = dino_game.render_llm_config(config, config_path)

            self.assertEqual(config.llm_mode, "API")
            self.assertFalse(config.is_complete())
            self.assertIn("base_url: (not set)", rendered)
            self.assertIn("model: (not set)", rendered)

    def test_api_config_missing_endpoint_fields_is_incomplete(self):
        dino_game = self.dino_game()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({
                "llm_mode": "API",
                "api_key": "sk-test",
            }))

            config = dino_game.load_llm_config(config_path)

            self.assertEqual(config.base_url, "")
            self.assertEqual(config.model, "")
            self.assertFalse(config.is_complete())

    def test_prompt_for_llm_config_defaults_and_optional_persistence(self):
        dino_game = self.dino_game()
        answers = iter(["", "sk-test", "", "", "", ""])
        messages = []

        config, persist = dino_game.prompt_for_llm_config(
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
            ask_persist=True,
        )

        self.assertEqual(config.api_key, "sk-test")
        self.assertEqual(config.llm_mode, "API")
        self.assertEqual(config.base_url, dino_game.DEFAULT_OPENAI_BASE_URL)
        self.assertEqual(config.model, dino_game.DEFAULT_OPENAI_MODEL)
        self.assertEqual(config.llm_window_frames, dino_game.DEFAULT_LLM_ACTION_WINDOW_FRAMES)
        self.assertFalse(persist)

    def test_setup_flow_writes_without_asking_for_persistence(self):
        dino_game = self.dino_game()
        answers = iter(["", "sk-test", "", "https://example.test/v1", "", "gpt-test", "720"])
        messages = []
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"

            config = dino_game.run_config_setup(
                config_path=config_path,
                input_func=lambda prompt: next(answers),
                output_func=messages.append,
            )

            self.assertEqual(config.model, "gpt-test")
            self.assertEqual(config.llm_mode, "API")
            self.assertEqual(config.base_url, "https://example.test/v1")
            self.assertEqual(config.llm_window_frames, 720)
            self.assertEqual(dino_game.load_llm_config(config_path), config)
            self.assertTrue(any("Base URL is required." in message for message in messages))
            self.assertTrue(any("Model is required." in message for message in messages))
            self.assertTrue(any("Saved config" in message for message in messages))

    def test_setup_flow_can_select_codex_mode_without_api_values(self):
        dino_game = self.dino_game()
        answers = iter(["2", "360"])
        messages = []
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"

            config = dino_game.run_config_setup(
                config_path=config_path,
                input_func=lambda prompt: next(answers),
                output_func=messages.append,
            )

            self.assertEqual(config.llm_mode, "CODEX")
            self.assertEqual(config.api_key, "")
            self.assertEqual(config.base_url, "")
            self.assertEqual(config.model, "")
            self.assertEqual(config.llm_window_frames, 360)
            self.assertTrue(config.is_complete())
            self.assertEqual(dino_game.load_llm_config(config_path), config)
            stored = json.loads(config_path.read_text())
            self.assertEqual(stored["llm_mode"], "CODEX")
            self.assertEqual(stored["api_key"], "")
            self.assertEqual(stored["base_url"], "")
            self.assertEqual(stored["model"], "")

    def test_load_llm_config_defaults_missing_mode_to_api(self):
        dino_game = self.dino_game()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({
                "api_key": "sk-legacy",
                "base_url": "https://example.test/v1",
                "model": "gpt-test",
            }))

            config = dino_game.load_llm_config(config_path)

            self.assertEqual(config.llm_mode, "API")
            self.assertTrue(config.is_complete())

    def test_api_mode_requires_endpoint_values_but_codex_mode_does_not(self):
        dino_game = self.dino_game()

        self.assertFalse(dino_game.LLMConfig(llm_mode="API").is_complete())
        self.assertTrue(dino_game.LLMConfig(llm_mode="CODEX").is_complete())

    def test_codex_mode_does_not_render_or_save_api_defaults(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(llm_mode="CODEX")

        rendered = dino_game.render_llm_config(config)

        self.assertIn("llm_mode: CODEX", rendered)
        self.assertIn("api_key: (not set)", rendered)
        self.assertIn("base_url: (not set)", rendered)
        self.assertIn("model: (not set)", rendered)
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            dino_game.save_llm_config(config, config_path)

            stored = json.loads(config_path.read_text())

        self.assertEqual(stored["api_key"], "")
        self.assertEqual(stored["base_url"], "")
        self.assertEqual(stored["model"], "")

    def test_prompt_for_llm_config_reprompts_invalid_window_frames(self):
        dino_game = self.dino_game()
        answers = iter(["", "sk-test", "", "", "abc", "0", "180"])
        messages = []

        config, _ = dino_game.prompt_for_llm_config(
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(config.llm_window_frames, 180)
        self.assertTrue(any("positive integer" in message for message in messages))

    def test_resolve_llm_config_without_file_uses_setup_flow_and_persists(self):
        dino_game = self.dino_game()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            answers = iter(["", "sk-session", "", "https://example.test/v1", "", "gpt-test", "720"])
            messages = []

            config = dino_game.resolve_llm_config_for_run(
                config_path=config_path,
                input_func=lambda prompt: next(answers),
                output_func=messages.append,
            )

            self.assertEqual(config.api_key, "sk-session")
            self.assertEqual(config.base_url, "https://example.test/v1")
            self.assertEqual(config.model, "gpt-test")
            self.assertEqual(config.llm_window_frames, 720)
            self.assertEqual(dino_game.load_llm_config(config_path), config)
            self.assertTrue(any("Base URL is required." in message for message in messages))
            self.assertTrue(any("Model is required." in message for message in messages))
            self.assertTrue(any("Saved config" in message for message in messages))


class LLMAgentOpenAITest(unittest.TestCase):
    def dino_game(self):
        return importlib.import_module("dino_game")

    def test_parse_llm_action_window_reads_json_actions_for_future_frames(self):
        dino_game = self.dino_game()

        actions = dino_game.parse_llm_action_window(
            '{"start_frame": 10, "actions": ["none", "jump", "duck"]}',
            requested_start_frame=10,
        )

        self.assertEqual(actions, {
            10: "none",
            11: "jump",
            12: "duck",
        })

    def test_parse_llm_action_window_truncates_extra_actions_without_dropping_jump(self):
        dino_game = self.dino_game()
        response_actions = ["none"] * 84 + ["jump"] + ["none"] * 245

        actions = dino_game.parse_llm_action_window(
            json.dumps({"start_frame": 601, "actions": response_actions}),
            requested_start_frame=601,
            expected_action_count=300,
        )

        self.assertEqual(len(actions), 300)
        self.assertEqual(actions[685], "jump")
        self.assertEqual(actions[900], "none")
        self.assertNotIn(901, actions)

    def test_parse_llm_action_window_pads_short_actions_with_none(self):
        dino_game = self.dino_game()

        actions = dino_game.parse_llm_action_window(
            '{"start_frame": 10, "actions": ["jump"]}',
            requested_start_frame=10,
            expected_action_count=2,
        )

        self.assertEqual(actions, {
            10: "jump",
            11: "none",
        })

    def test_llm_action_window_text_format_constrains_start_and_action_count(self):
        dino_game = self.dino_game()

        text_format = dino_game.llm_action_window_text_format(42, 5)

        self.assertEqual(text_format["type"], "json_schema")
        self.assertEqual(text_format["name"], "dino_action_window")
        self.assertTrue(text_format["strict"])
        schema = text_format["schema"]
        self.assertEqual(schema["properties"]["start_frame"]["enum"], [42])
        self.assertEqual(schema["properties"]["actions"]["minItems"], 5)
        self.assertEqual(schema["properties"]["actions"]["maxItems"], 5)
        self.assertEqual(
            schema["properties"]["actions"]["items"]["enum"],
            ["jump", "duck", "none"],
        )

    def test_parse_llm_action_window_rejects_wrong_start_frame_and_bad_actions(self):
        dino_game = self.dino_game()

        self.assertEqual(
            dino_game.parse_llm_action_window(
                '{"start_frame": 11, "actions": ["jump"]}',
                requested_start_frame=10,
            ),
            {},
        )
        self.assertEqual(
            dino_game.parse_llm_action_window(
                '{"start_frame": 10, "actions": ["jump", "spin"]}',
                requested_start_frame=10,
            ),
            {},
        )

    def test_llm_agent_waits_when_current_frame_has_no_buffered_action(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)

        self.assertTrue(agent.needs_loading(5))

        with agent.lock:
            agent.planned_actions[5] = "jump"

        self.assertFalse(agent.needs_loading(5))
        self.assertEqual(agent.decide({
            "dino_y": 0.0,
            "jumping": False,
            "ducking": False,
            "speed": 1.0,
            "score": 0,
            "obstacles": [],
        }, frame=5), "jump")
        self.assertTrue(agent.needs_loading(5))

    def test_llm_action_window_uses_default_frame_window(self):
        dino_game = self.dino_game()

        self.assertEqual(
            dino_game.LLM_ACTION_WINDOW_FRAMES,
            600,
        )

    def test_llm_agent_skips_api_when_window_state_has_no_obstacles(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        empty_state = {
            "dino_y": 0.0,
            "jumping": False,
            "ducking": False,
            "speed": 1.0,
            "score": 0,
            "obstacles": [],
        }

        with mock.patch("threading.Thread") as thread_class:
            agent.ensure_plan(empty_state, 10)

        thread_class.assert_not_called()
        with agent.lock:
            self.assertEqual(agent.planned_actions[10], "none")
            self.assertEqual(
                agent.planned_actions[10 + dino_game.LLM_ACTION_WINDOW_FRAMES - 1],
                "none",
            )
            self.assertEqual(
                agent.requested_until_frame,
                10 + dino_game.LLM_ACTION_WINDOW_FRAMES - 1,
            )
            self.assertFalse(agent.request_in_flight)

    def test_llm_agent_ignores_forecast_frames_when_top_level_has_no_obstacles(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        forecast_state = {
            "dino_y": 0.0,
            "jumping": False,
            "ducking": False,
            "speed": 1.0,
            "score": 0,
            "obstacles": [],
            "frames": [{
                "frame": 10,
                "obstacles": [{"kind": "cactus_group", "distance": 100}],
            }],
        }

        with mock.patch("threading.Thread") as thread_class:
            agent.ensure_plan(forecast_state, 10)

        thread_class.assert_not_called()

    def test_openai_responses_request_uses_config_and_parses_action_window(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({
                    "output_text": json.dumps({
                        "start_frame": 7,
                        "actions": ["jump", "none"],
                    }),
                }).encode()

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["payload"] = json.loads(req.data.decode())
            captured["timeout"] = timeout
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            agent._call_llm(
                {
                    "dino_y": 0.0,
                    "jumping": False,
                    "ducking": False,
                    "speed": 1.0,
                    "score": 0,
                    "obstacles": [{"kind": "cactus_group", "distance": 42}],
                },
                start_frame=7,
                window_frames=2,
            )

        self.assertEqual(captured["url"], "https://example.test/v1/responses")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(captured["payload"]["model"], "gpt-test")
        self.assertIn("input", captured["payload"])
        self.assertIn('"start_frame": 7', captured["payload"]["input"])
        self.assertIn("2 actions", captured["payload"]["input"])
        self.assertNotIn("未来 2 帧状态", captured["payload"]["input"])
        self.assertNotIn('"frames"', captured["payload"]["input"])
        text_format = captured["payload"]["text"]["format"]
        self.assertEqual(text_format["type"], "json_schema")
        self.assertEqual(text_format["name"], "dino_action_window")
        self.assertTrue(text_format["strict"])
        schema = text_format["schema"]
        self.assertEqual(schema["required"], ["start_frame", "actions"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["start_frame"],
            {"type": "integer", "enum": [7]},
        )
        actions_schema = schema["properties"]["actions"]
        self.assertEqual(actions_schema["type"], "array")
        self.assertEqual(actions_schema["minItems"], 2)
        self.assertEqual(actions_schema["maxItems"], 2)
        self.assertEqual(
            actions_schema["items"],
            {"type": "string", "enum": ["jump", "duck", "none"]},
        )
        self.assertEqual(captured["timeout"], 60)
        with agent.lock:
            self.assertEqual(agent.planned_actions[7], "jump")
            self.assertEqual(agent.planned_actions[8], "none")

    def test_openai_responses_request_reports_actual_current_frame_for_prefetch(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({
                    "output_text": json.dumps({
                        "start_frame": 601,
                        "actions": ["none", "jump"],
                    }),
                }).encode()

        def fake_urlopen(req, timeout):
            captured["payload"] = json.loads(req.data.decode())
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            agent._call_llm(
                {
                    "dino_y": 0.0,
                    "jumping": False,
                    "ducking": False,
                    "speed": 2.04,
                    "score": 579,
                    "obstacles": [{"kind": "cactus_group", "distance": 232.9}],
                },
                start_frame=601,
                current_frame=580,
                window_frames=2,
            )

        prompt = captured["payload"]["input"]
        self.assertIn("当前帧: 580", prompt)
        self.assertIn("需要返回的第一帧 start_frame: 601", prompt)
        self.assertIn("start_frame 距当前状态还有 21 帧", prompt)
        self.assertNotIn("当前帧: 600", prompt)
        self.assertIn("一次 jump 约持续 17 帧", prompt)
        self.assertIn("重复 jump 不会延长滞空", prompt)
        self.assertIn("速度每帧增加 0.0005", prompt)
        self.assertIn("最大速度 3.8", prompt)
        self.assertIn("distance <= 6", prompt)
        self.assertIn("estimated_overlap_frame=690", prompt)
        self.assertIn("recommended_jump_window=676-688", prompt)
        self.assertIn("optimal_jump_frame=682", prompt)
        self.assertNotIn("recommended_jump_start", prompt)

    def test_llm_planning_guidance_delays_window_for_wide_tall_obstacles(self):
        dino_game = self.dino_game()

        first_crash_guidance = dino_game.llm_planning_guidance({
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "cactus_group",
                "distance": 137.3,
                "height": 0,
                "width": 5,
                "h": 6,
            }],
        }, current_frame=0)
        self.assertIn("width=5", first_crash_guidance)
        self.assertIn("estimated_overlap_frame=75", first_crash_guidance)
        self.assertIn("estimated_clear_frame=78", first_crash_guidance)
        self.assertIn("recommended_jump_window=65-73", first_crash_guidance)
        self.assertIn("optimal_jump_frame=69", first_crash_guidance)
        self.assertNotIn("recommended_jump_start", first_crash_guidance)

        wide_tail_guidance = dino_game.llm_planning_guidance({
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "cactus_group",
                "distance": 419.3,
                "height": 0,
                "width": 9,
                "h": 6,
            }],
        }, current_frame=0)
        self.assertIn("width=9", wide_tail_guidance)
        self.assertIn("estimated_overlap_frame=229", wide_tail_guidance)
        self.assertIn("estimated_clear_frame=234", wide_tail_guidance)
        self.assertIn("recommended_jump_window=221-227", wide_tail_guidance)
        self.assertIn("optimal_jump_frame=224", wide_tail_guidance)

    def test_llm_state_uses_large_obstacle_window_with_forecast_obstacles(self):
        dino_game = self.dino_game()
        game = dino_game.DinoGame()
        game.obstacles = [
            dino_game.Obstacle(
                "cactus_group",
                dino_game.DINO_COL + dino_game.LLM_STATE_LOOKAHEAD - 1,
            )
        ]

        state = game.get_llm_state()

        self.assertNotIn("frames", state)
        self.assertGreaterEqual(len(state["obstacles"]), 1)
        self.assertTrue(any(
            obstacle["x"] == dino_game.DINO_COL + dino_game.LLM_STATE_LOOKAHEAD - 1
            for obstacle in state["obstacles"]
        ))
        self.assertTrue(any(
            obstacle.get("forecast") is True
            for obstacle in state["obstacles"]
        ))
        self.assertTrue(any(
            "spawn_frame" in obstacle
            for obstacle in state["obstacles"]
            if obstacle.get("forecast") is True
        ))
        self.assertFalse(any(
            "frame" in obstacle
            for obstacle in state["obstacles"]
            if obstacle.get("forecast") is True
        ))
        self.assertGreaterEqual(
            dino_game.LLM_STATE_LOOKAHEAD,
            dino_game.MAX_SPEED * dino_game.LLM_ACTION_WINDOW_FRAMES,
        )

    def test_llm_request_ranges_are_recorded_without_overlap_or_gaps(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        obstacle_state = {
            "dino_y": 0.0,
            "jumping": False,
            "ducking": False,
            "speed": 1.0,
            "score": 0,
            "obstacles": [{"kind": "cactus_group", "distance": 100}],
        }

        with mock.patch("threading.Thread"):
            agent.ensure_plan(obstacle_state, 10)
        with agent.lock:
            agent.request_in_flight = False
            agent.requested_until_frame = 10 + dino_game.LLM_ACTION_WINDOW_FRAMES - 1
        with mock.patch("threading.Thread"):
            agent.ensure_plan(
                obstacle_state,
                10 + dino_game.LLM_ACTION_WINDOW_FRAMES - dino_game.LLM_PREFETCH_THRESHOLD_FRAMES,
            )

        self.assertEqual(agent.requested_frame_ranges, [
            (10, 10 + dino_game.LLM_ACTION_WINDOW_FRAMES - 1),
            (
                10 + dino_game.LLM_ACTION_WINDOW_FRAMES,
                10 + dino_game.LLM_ACTION_WINDOW_FRAMES * 2 - 1,
            ),
        ])

    def test_llm_prefetches_next_window_immediately_after_previous_response(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        agent.requested_until_frame = dino_game.LLM_ACTION_WINDOW_FRAMES
        obstacle_state = {
            "dino_y": 0.0,
            "jumping": False,
            "ducking": False,
            "speed": 1.0,
            "score": 0,
            "obstacles": [{"kind": "cactus_group", "distance": 100}],
        }

        with mock.patch("threading.Thread") as thread_class:
            agent.ensure_plan(obstacle_state, 1)

        thread_class.assert_called_once()
        thread_kwargs = thread_class.call_args.kwargs["kwargs"]
        self.assertEqual(
            thread_kwargs["start_frame"],
            dino_game.LLM_ACTION_WINDOW_FRAMES + 1,
        )
        self.assertEqual(thread_kwargs["current_frame"], 0)
        self.assertEqual(agent.requested_frame_ranges, [
            (
                dino_game.LLM_ACTION_WINDOW_FRAMES + 1,
                dino_game.LLM_ACTION_WINDOW_FRAMES * 2,
            ),
        ])

    def test_llm_cached_frame_summary_reports_current_cached_ranges(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)

        self.assertIsNone(agent.cached_frame_summary())

        with agent.lock:
            agent.planned_actions.update({
                10: "none",
                11: "jump",
                12: "none",
                20: "duck",
            })

        self.assertEqual(
            agent.cached_frame_summary(),
            "Cached frames: 10-12, 20 (4)",
        )

    def test_llm_cached_frame_window_uses_action_symbols_and_statuses(self):
        dino_game = self.dino_game()

        window = dino_game.cached_frame_window(
            planned_actions={
                10: "none",
                11: "jump",
                12: "duck",
            },
            consumed_actions={
                8: "jump",
                9: "none",
            },
            current_frame=10,
            radius=2,
        )

        self.assertEqual(window.current_frame, 10)
        self.assertEqual(
            [(cell.frame, cell.symbol, cell.status) for cell in window.cells],
            [
                (8, "↑", "consumed"),
                (9, "-", "consumed"),
                (10, "-", "current"),
                (11, "↑", "future"),
                (12, "↓", "future"),
            ],
        )

    def test_llm_cached_frame_window_tracks_consumed_actions(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        with agent.lock:
            agent.planned_actions.update({
                10: "jump",
                11: "duck",
            })
            agent.requested_until_frame = 100

        self.assertEqual(agent.decide({"obstacles": []}, frame=10), "jump")

        window = agent.cached_frame_window(current_frame=11, radius=1)
        self.assertEqual(
            [(cell.frame, cell.symbol, cell.status) for cell in window.cells],
            [
                (10, "↑", "consumed"),
                (11, "↓", "current"),
                (12, " ", "missing"),
            ],
        )

    def test_llm_loading_text_is_dino_thinking_message(self):
        dino_game = self.dino_game()

        self.assertEqual(
            dino_game.LLM_LOADING_TEXT,
            "Dino is thinking seriously...",
        )

    def test_llm_prefetch_passes_actual_current_frame_to_background_request(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        agent.requested_until_frame = 600
        obstacle_state = {
            "dino_y": 0.0,
            "jumping": False,
            "ducking": False,
            "speed": 2.0,
            "score": 579,
            "obstacles": [{"kind": "cactus_group", "distance": 232.9}],
        }

        with mock.patch("threading.Thread") as thread_class:
            agent.ensure_plan(obstacle_state, 581)

        thread_kwargs = thread_class.call_args.kwargs["kwargs"]
        self.assertEqual(thread_kwargs["start_frame"], 601)
        self.assertEqual(thread_kwargs["current_frame"], 580)

    def test_llm_discard_plan_after_ignores_stale_background_response(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        agent.planned_actions = {5: "jump", 6: "duck", 30: "jump"}
        agent.consumed_actions = {4: "none", 6: "duck"}
        stale_generation = agent.plan_generation

        agent.discard_plan_after(5)
        agent.planner = mock.Mock()
        agent.planner.build_request.return_value = (
            {"obstacles": [{"kind": "cactus_group"}]},
            "prompt",
            {"format": "json"},
        )
        agent.client = mock.Mock()
        agent.client.create_response.return_value = mock.Mock(
            request_payload={"input": "prompt"},
            response_text=json.dumps({
                "start_frame": 6,
                "actions": ["jump", "jump"],
            }),
            raw_response={"ok": True},
        )
        agent.planner.parse_response.return_value = {6: "jump", 7: "jump"}

        agent._call_llm(
            {"obstacles": [{"kind": "cactus_group"}]},
            start_frame=6,
            current_frame=5,
            window_frames=2,
            generation=stale_generation,
        )

        self.assertEqual(agent.planned_actions, {5: "jump"})
        self.assertEqual(agent.consumed_actions, {4: "none"})
        self.assertEqual(agent.requested_until_frame, 5)

    def test_llm_debug_writes_request_and_response_json_lines_to_file(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = pathlib.Path(temp_dir) / "logs" / "run.json"
            agent = dino_game.LLMAgent(config, debug=True, debug_path=log_path)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return json.dumps({
                        "output_text": json.dumps({
                            "start_frame": 3,
                            "actions": ["none", "jump"],
                        }),
                    }).encode()

            with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
                agent._call_llm(
                    {
                        "dino_y": 0.0,
                        "jumping": False,
                        "ducking": False,
                        "speed": 1.0,
                        "score": 0,
                        "obstacles": [{"kind": "cactus_group", "distance": 42}],
                    },
                    start_frame=3,
                    window_frames=2,
                )

            self.assertTrue(log_path.exists())
            lines = [json.loads(line) for line in log_path.read_text().splitlines()]
        self.assertEqual(lines[0]["event"], "llm_request")
        self.assertEqual(lines[0]["start_frame"], 3)
        self.assertEqual(lines[0]["window_frames"], 2)
        self.assertEqual(lines[0]["state"]["obstacles"][0]["distance"], 42)
        self.assertIn("payload", lines[0])
        self.assertEqual(lines[1]["event"], "llm_response")
        self.assertEqual(lines[1]["planned_actions"], {"3": "none", "4": "jump"})
        self.assertIn("raw_response", lines[1])

    def test_llm_request_filters_obstacles_that_clear_before_start_frame(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({
                    "output_text": json.dumps({
                        "start_frame": 301,
                        "actions": ["none", "none"],
                    }),
                }).encode()

        def fake_urlopen(req, timeout):
            captured["payload"] = json.loads(req.data.decode())
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            agent._call_llm(
                {
                    "dino_y": 0.0,
                    "jumping": False,
                    "ducking": False,
                    "speed": dino_game.INITIAL_SPEED,
                    "score": 0,
                    "obstacles": [
                        {
                            "kind": "cactus_group",
                            "distance": 132.0,
                            "height": 0,
                            "width": 5,
                            "h": 6,
                            "spawn_frame": 33,
                            "forecast": True,
                        },
                        {
                            "kind": "bird",
                            "distance": 578.0,
                            "height": 4,
                            "width": 4,
                            "h": 2,
                            "spawn_frame": 277,
                            "forecast": True,
                        },
                    ],
                },
                start_frame=301,
                current_frame=0,
                window_frames=2,
            )

        prompt = captured["payload"]["input"]
        self.assertNotIn('"distance": 132.0', prompt)
        self.assertNotIn("recommended_jump_window=62-70", prompt)
        self.assertIn('"distance": 578.0', prompt)
        self.assertIn("recommended_action=duck", prompt)

    def test_llm_debug_logs_game_over_collision_details(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = pathlib.Path(temp_dir) / "logs" / "run.json"
            agent = dino_game.LLMAgent(config, debug=True, debug_path=log_path)
            game = dino_game.DinoGame()
            game.spawn_timer = 9999
            game.obstacles = [
                dino_game.Obstacle("cactus_group", dino_game.DINO_COL + 4, plants=("tall",)),
            ]

            game.update()
            dino_game.debug_log_llm_game_over(agent, game, frame=1, action="none")

            lines = [json.loads(line) for line in log_path.read_text().splitlines()]

        self.assertEqual(lines[0]["event"], "game_over")
        self.assertEqual(lines[0]["frame"], 1)
        self.assertEqual(lines[0]["action"], "none")
        self.assertEqual(lines[0]["collision"]["obstacle"]["kind"], "cactus_group")
        self.assertEqual(lines[0]["collision"]["obstacle"]["plants"], ["tall"])
        self.assertIn("dino_hitbox", lines[0]["collision"])
        self.assertIn("obstacle_hitbox", lines[0]["collision"])

    def test_debug_log_path_uses_logs_directory_and_replay_filename(self):
        dino_game = self.dino_game()

        self.assertEqual(
            dino_game.debug_log_path_for_replay("replays/20260527-llm-123.json"),
            os.path.join("logs", "20260527-llm-123.json"),
        )

    def test_llm_fallback_window_becomes_the_requested_coverage(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(
            api_key="sk-test",
            base_url="https://example.test/v1",
            model="gpt-test",
        )
        agent = dino_game.LLMAgent(config)
        agent.requested_until_frame = 60

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({"output_text": "not json"}).encode()

        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
            agent._call_llm(
                {
                    "dino_y": 0.0,
                    "jumping": False,
                    "ducking": False,
                    "speed": 1.0,
                    "score": 0,
                    "obstacles": [],
                },
                start_frame=1,
                window_frames=60,
            )

        self.assertEqual(
            agent.requested_until_frame,
            60,
        )

    def test_extract_response_text_supports_structured_output(self):
        dino_game = self.dino_game()

        text = dino_game.extract_response_text({
            "output": [{
                "content": [
                    {"type": "output_text", "text": "duck"},
                ],
            }],
        })

        self.assertEqual(text, "duck")
