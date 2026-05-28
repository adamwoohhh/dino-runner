import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class PackagingTest(unittest.TestCase):
    def project_root(self):
        return pathlib.Path(__file__).resolve().parents[1]

    def load_pyproject(self):
        return tomllib.loads((self.project_root() / "pyproject.toml").read_text())

    def test_distribution_name_is_ai_dino_in_terminal(self):
        pyproject = self.load_pyproject()

        self.assertEqual(pyproject["project"]["name"], "ai-dino-in-terminal")

    def test_dino_console_script_points_at_cli_entrypoint(self):
        pyproject = self.load_pyproject()

        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["dino"], "dino_game:cli")
        self.assertNotIn("trex", scripts)

        dino_game = importlib.import_module("dino_game")
        self.assertTrue(callable(dino_game.cli))

    def test_readme_documents_pip_and_pipx_installation(self):
        readme = (self.project_root() / "README.md").read_text()

        self.assertIn("pipx install ai-dino-in-terminal", readme)
        self.assertIn("pip install ai-dino-in-terminal", readme)
        self.assertIn("dino", readme)

    def test_makefile_publish_targets_build_and_check_fresh_artifacts(self):
        makefile = (self.project_root() / "Makefile").read_text()

        self.assertIn("build:\n\trm -rf dist\n\t$(SYSTEM_PYTHON) -m build", makefile)
        self.assertIn("check-dist: build\n\t$(SYSTEM_PYTHON) -m twine check dist/*", makefile)
        self.assertIn("publish-test: check-dist", makefile)
        self.assertIn("publish: check-dist", makefile)

    def test_dev_extra_declares_packaging_tools(self):
        pyproject = self.load_pyproject()

        dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
        self.assertTrue(any(dep.startswith("build>=") for dep in dev_dependencies))
        self.assertTrue(any(dep.startswith("twine>=") for dep in dev_dependencies))

    def test_developer_setup_installs_dev_extra(self):
        makefile = (self.project_root() / "Makefile").read_text()
        contributing = (self.project_root() / "CONTRIBUTING.md").read_text()

        self.assertIn('dev-install: venv\n\t$(PIP) install -e ".[dev]"', makefile)
        self.assertIn('python3 -m pip install -e ".[dev]"', contributing)
        self.assertNotIn("python3 -m pip install build twine", contributing)


class CliContractTest(unittest.TestCase):
    def dino_game(self):
        return importlib.import_module("dino_game")

    def test_main_help_groups_subcommands_and_public_options(self):
        dino_game = self.dino_game()

        help_text = dino_game.render_main_help()

        self.assertIn("Usage: dino <command> [options]", help_text)
        self.assertIn("Core", help_text)
        self.assertIn("play", help_text)
        self.assertIn("Start a manual game", help_text)
        self.assertIn("Replay", help_text)
        self.assertIn("replay", help_text)
        self.assertIn("Play, inspect, or clear replay records", help_text)
        self.assertIn("Competition", help_text)
        self.assertIn("Config", help_text)
        self.assertIn("config", help_text)
        self.assertIn("View or update LLM configuration", help_text)
        self.assertIn("Help", help_text)
        self.assertIn("help", help_text)
        self.assertIn("--help, -H", help_text)
        self.assertIn("--version, -V", help_text)
        self.assertNotIn("--record", help_text)
        self.assertNotIn("--agent", help_text)
        self.assertNotRegex(help_text, r"[\u4e00-\u9fff]")
        self.assertLess(help_text.index("play"), help_text.index("agent"))
        self.assertLess(help_text.index("Replay"), help_text.index("Competition"))
        self.assertLess(help_text.index("Competition"), help_text.index("Config"))
        self.assertLess(help_text.index("Config"), help_text.index("Help"))

    def test_subcommand_help_includes_command_specific_arguments(self):
        dino_game = self.dino_game()

        play_help = dino_game.render_command_help("play")
        replay_help = dino_game.render_command_help("replay")
        compete_help = dino_game.render_command_help("compete")
        config_help = dino_game.render_command_help("config")
        llm_help = dino_game.render_command_help("llm")

        self.assertIn("Usage: dino play [--record FILE]", play_help)
        self.assertIn("--record FILE", play_help)
        self.assertIn("Usage: dino replay [FILE]", replay_help)
        self.assertIn("dino replay +list", replay_help)
        self.assertIn("dino replay +clear", replay_help)
        self.assertIn("FILE", replay_help)
        self.assertIn("Usage: dino compete [FILE] [--record FILE]", compete_help)
        self.assertIn("--record FILE", compete_help)
        self.assertIn("Usage: dino config", config_help)
        self.assertIn("+setup", config_help)
        self.assertIn("+reset", config_help)
        self.assertIn("--debug", llm_help)
        self.assertNotRegex(play_help + replay_help + compete_help + config_help + llm_help, r"[\u4e00-\u9fff]")

    def test_parse_cli_args_uses_new_subcommands_only(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args([]).command, "play")
        self.assertEqual(dino_game.parse_cli_args(["play"]).mode, "manual")
        self.assertEqual(dino_game.parse_cli_args(["agent"]).mode, "agent")
        self.assertEqual(dino_game.parse_cli_args(["llm"]).mode, "llm")
        self.assertTrue(dino_game.parse_cli_args(["llm", "--debug"]).llm_debug)
        self.assertFalse(dino_game.parse_cli_args(["play", "--debug"]).llm_debug)
        self.assertTrue(dino_game.parse_cli_args(["play", "--debug"]).show_help)
        self.assertEqual(dino_game.parse_cli_args(["replay", "run.json"]).replay_path, "run.json")
        self.assertEqual(dino_game.parse_cli_args(["replay", "+list"]).replay_action, "list")
        self.assertEqual(dino_game.parse_cli_args(["replay", "+clear"]).replay_action, "clear")
        self.assertTrue(dino_game.parse_cli_args(["replay", "+unknown"]).show_help)
        self.assertEqual(dino_game.parse_cli_args(["compete", "run.json"]).competition_path, "run.json")
        self.assertEqual(dino_game.parse_cli_args(["config"]).config_action, "show")
        self.assertEqual(dino_game.parse_cli_args(["config", "+setup"]).config_action, "setup")
        self.assertEqual(dino_game.parse_cli_args(["config", "+reset"]).config_action, "reset")
        self.assertTrue(dino_game.parse_cli_args(["config", "+unknown"]).show_help)
        self.assertEqual(dino_game.parse_cli_args(["play", "--record", "run.json"]).record_path, "run.json")
        self.assertTrue(dino_game.parse_cli_args(["--agent"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["--replay", "run.json"]).show_help)

    def test_help_flags_work_after_subcommands_and_unknown_falls_back_to_help(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args(["help"]).help_text, dino_game.render_main_help())
        self.assertEqual(dino_game.parse_cli_args(["agent", "-H"]).help_text, dino_game.render_command_help("agent"))
        self.assertEqual(dino_game.parse_cli_args(["config", "-H"]).help_text, dino_game.render_command_help("config"))
        self.assertEqual(dino_game.parse_cli_args(["foo"]).help_text, dino_game.render_main_help())

    def test_version_flags_return_project_version(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args(["--version"]).version, "0.1.0")
        self.assertEqual(dino_game.parse_cli_args(["play", "-V"]).version, "0.1.0")


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
            )

            dino_game.save_llm_config(config, config_path)

            self.assertEqual(dino_game.load_llm_config(config_path), config)
            stored = json.loads(config_path.read_text())
            self.assertEqual(stored["api_key"], "sk-abcdefghijklmnopqrstuvwxyz")

            rendered = dino_game.render_llm_config(config)
            self.assertIn("api_key: sk-a...wxyz", rendered)
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", rendered)
            self.assertIn("base_url: https://example.test/v1", rendered)
            self.assertIn("model: gpt-test", rendered)

            self.assertTrue(dino_game.reset_llm_config(config_path))
            self.assertFalse(config_path.exists())
            self.assertFalse(dino_game.reset_llm_config(config_path))

    def test_prompt_for_llm_config_defaults_and_optional_persistence(self):
        dino_game = self.dino_game()
        answers = iter(["sk-test", "", "", ""])
        messages = []

        config, persist = dino_game.prompt_for_llm_config(
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
            ask_persist=True,
        )

        self.assertEqual(config.api_key, "sk-test")
        self.assertEqual(config.base_url, dino_game.DEFAULT_OPENAI_BASE_URL)
        self.assertEqual(config.model, dino_game.DEFAULT_OPENAI_MODEL)
        self.assertFalse(persist)

    def test_setup_flow_writes_without_asking_for_persistence(self):
        dino_game = self.dino_game()
        answers = iter(["sk-test", "https://example.test/v1", "gpt-test"])
        messages = []
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"

            config = dino_game.run_config_setup(
                config_path=config_path,
                input_func=lambda prompt: next(answers),
                output_func=messages.append,
            )

            self.assertEqual(config.model, "gpt-test")
            self.assertEqual(dino_game.load_llm_config(config_path), config)
            self.assertTrue(any("Saved config" in message for message in messages))

    def test_resolve_llm_config_prompts_and_only_persists_on_yes(self):
        dino_game = self.dino_game()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            answers = iter(["sk-session", "", "", "n"])

            config = dino_game.resolve_llm_config_for_run(
                config_path=config_path,
                input_func=lambda prompt: next(answers),
                output_func=lambda message: None,
            )

            self.assertEqual(config.api_key, "sk-session")
            self.assertFalse(config_path.exists())

            answers = iter(["sk-save", "", "", "y"])
            config = dino_game.resolve_llm_config_for_run(
                config_path=config_path,
                input_func=lambda prompt: next(answers),
                output_func=lambda message: None,
            )

            self.assertEqual(config.api_key, "sk-save")
            self.assertEqual(dino_game.load_llm_config(config_path), config)


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

    def test_llm_action_window_covers_ten_seconds(self):
        dino_game = self.dino_game()

        self.assertEqual(
            dino_game.LLM_ACTION_WINDOW_FRAMES,
            dino_game.FPS * 10,
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
        self.assertIn("recommended_jump_start=676-688", prompt)

    def test_llm_state_uses_large_obstacle_window_without_frames(self):
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
        self.assertEqual(len(state["obstacles"]), 1)
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

    def test_llm_game_spawns_obstacles_farther_ahead(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame(obstacle_spawn_x=dino_game.LLM_OBSTACLE_SPAWN_X)
        game.score = 0

        game._spawn_obstacle()

        self.assertEqual(game.obstacles[0].x, dino_game.LLM_OBSTACLE_SPAWN_X)
        self.assertGreater(game.obstacles[0].x, dino_game.NORMAL_OBSTACLE_SPAWN_X)

    def test_llm_state_includes_farther_obstacles_than_default_state(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()
        game.obstacles = [
            dino_game.Obstacle("cactus_group", dino_game.LLM_OBSTACLE_SPAWN_X),
        ]

        self.assertEqual(game.get_state()["obstacles"], [])
        self.assertEqual(
            game.get_llm_state()["obstacles"][0]["x"],
            dino_game.LLM_OBSTACLE_SPAWN_X,
        )

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

    def test_replay_recorder_writes_competition_metadata(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "run.json"
            recorder = dino_game.ReplayRecorder(
                path,
                seed=123,
                mode="manual",
                competitive=True,
                source_replay="replays/source.json",
            )

            recorder.record_action(1, "jump")
            recorder.save()

            data = dino_game.load_replay_file(path)
            self.assertTrue(data["competitive"])
            self.assertEqual(data["source_replay"], "replays/source.json")

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

    def test_clear_replay_files_removes_only_replay_json_files(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            replay_path = pathlib.Path(tmpdir) / "run.json"
            notes_path = pathlib.Path(tmpdir) / "notes.txt"
            replay_path.write_text("{}")
            notes_path.write_text("keep")

            removed = dino_game.clear_replay_files(tmpdir)

            self.assertEqual(removed, 1)
            self.assertFalse(replay_path.exists())
            self.assertTrue(notes_path.exists())

    def test_replay_metadata_reports_mode_frames_creation_and_competition_source(self):
        dino_game = importlib.import_module("dino_game")

        with tempfile.TemporaryDirectory() as tmpdir:
            replay_path = pathlib.Path(tmpdir) / "competition.json"
            replay_path.write_text(
                '{"version": 3, "seed": 99, "mode": "competitive", "frames": 12, '
                '"competitive": true, "source_replay": "replays/source.json", '
                '"actions": [], "obstacles": []}'
            )

            metadata = dino_game.replay_metadata(replay_path)
            lines = dino_game.render_replay_metadata(metadata)

            self.assertEqual(metadata["mode"], "competitive")
            self.assertEqual(metadata["frames"], 12)
            self.assertEqual(metadata["competitive"], True)
            self.assertEqual(metadata["source_replay"], "replays/source.json")
            self.assertIn("模式: competitive", lines)
            self.assertIn("帧数: 12", lines)
            self.assertIn("是否竞技模式: 是", lines)
            self.assertIn("竞技模式源记录: replays/source.json", lines)
            self.assertIn("创建时间:", lines)

    def test_move_replay_selection_wraps_with_arrow_keys(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.move_replay_selection(0, dino_game.curses.KEY_DOWN, 3), 1)
        self.assertEqual(dino_game.move_replay_selection(0, dino_game.curses.KEY_UP, 3), 2)
        self.assertEqual(dino_game.move_replay_selection(2, dino_game.curses.KEY_DOWN, 3), 0)

    def test_game_mode_from_args_tracks_manual_agent_and_llm(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.game_mode_from_args([]), "manual")
        self.assertEqual(dino_game.game_mode_from_args(["play"]), "manual")
        self.assertEqual(dino_game.game_mode_from_args(["agent"]), "agent")
        self.assertEqual(dino_game.game_mode_from_args(["llm"]), "llm")
        self.assertEqual(dino_game.game_mode_from_args(["compete"]), "competitive")

    def test_competition_source_path_accepts_positional_arg_only(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(
            dino_game.competition_source_path(["compete", "run.json"]),
            "run.json",
        )
        self.assertIsNone(dino_game.competition_source_path(["compete"]))
        self.assertIsNone(dino_game.competition_source_path(["--compete", "run.json"]))

    def test_replay_seed_and_actions_are_deterministic(self):
        dino_game = importlib.import_module("dino_game")
        actions = ["none"] * 20 + ["jump"] + ["none"] * 40

        first = dino_game.run_replay_simulation(seed=42, actions=actions)
        second = dino_game.run_replay_simulation(seed=42, actions=actions)

        self.assertEqual(first, second)


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


if __name__ == "__main__":
    unittest.main()
