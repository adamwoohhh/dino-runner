import importlib
import json
import os
import pathlib
import re
import tempfile
import tomllib
import unittest
from unittest import mock


class CliContractTest(unittest.TestCase):
    def dino_game(self):
        return importlib.import_module("dino_game")

    def test_main_help_groups_subcommands_and_public_options(self):
        dino_game = self.dino_game()

        help_text = dino_game.render_main_help()

        self.assertIn("Usage: dino <command> [options]", help_text)
        self.assertIn("Core", help_text)
        self.assertIn("play", help_text)
        self.assertIn("Start a manual or LLM game", help_text)
        self.assertNotIn("auto", help_text.lower())
        self.assertIn("dashboard", help_text)
        self.assertIn("View score and token totals", help_text)
        self.assertIn("Replay", help_text)
        self.assertIn("replay", help_text)
        self.assertIn("Play, inspect, or clear replay records", help_text)
        self.assertIn("Competition", help_text)
        self.assertIn("Config", help_text)
        self.assertIn("config", help_text)
        self.assertIn("View or update LLM configuration", help_text)
        self.assertIn("setup", help_text)
        self.assertIn("Interactively configure config.json", help_text)
        self.assertIn("Help", help_text)
        self.assertIn("help", help_text)
        self.assertIn("--help, -H", help_text)
        self.assertIn("--version, -V", help_text)
        self.assertNotIn("--record", help_text)
        self.assertNotIn("--agent", help_text)
        self.assertNotIn("agent", help_text)
        self.assertNotIn("llm", help_text)
        self.assertNotRegex(help_text, r"[\u4e00-\u9fff]")
        self.assertLess(help_text.index("Replay"), help_text.index("Competition"))
        self.assertLess(help_text.index("Competition"), help_text.index("Config"))
        self.assertLess(help_text.index("Config"), help_text.index("Help"))

    def test_subcommand_help_includes_command_specific_arguments(self):
        dino_game = self.dino_game()

        play_help = dino_game.render_command_help("play")
        replay_help = dino_game.render_command_help("replay")
        compete_help = dino_game.render_command_help("compete")
        config_help = dino_game.render_command_help("config")
        setup_help = dino_game.render_command_help("setup")
        dashboard_help = dino_game.render_command_help("dashboard")

        self.assertIn("Usage: dino play [--llm [api|codex]] [--debug]", play_help)
        self.assertNotIn("--auto", play_help)
        self.assertIn("--llm", play_help)
        self.assertIn("--debug", play_help)
        self.assertIn("logs/*.jsonl", play_help)
        self.assertNotIn("--record", play_help)
        self.assertIn("Usage: dino replay [FILE]", replay_help)
        self.assertIn("dino replay +list", replay_help)
        self.assertIn("dino replay +clear", replay_help)
        self.assertIn("FILE", replay_help)
        self.assertIn("Usage: dino compete [FILE]", compete_help)
        self.assertNotIn("--record", compete_help)
        self.assertIn("Usage: dino config", config_help)
        self.assertIn("+setup", config_help)
        self.assertIn("+reset", config_help)
        self.assertIn("Usage: dino setup", setup_help)
        self.assertIn("API LLM settings", setup_help)
        self.assertIn("Usage: dino dashboard", dashboard_help)
        self.assertIn("Q", dashboard_help)
        self.assertNotRegex(
            play_help + replay_help + compete_help + config_help + setup_help + dashboard_help,
            r"[\u4e00-\u9fff]",
        )

    def test_parse_cli_args_uses_new_subcommands_only(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args([]).command, "play")
        self.assertEqual(dino_game.parse_cli_args(["play"]).mode, "manual")
        self.assertEqual(dino_game.parse_cli_args(["play", "--auto"]).mode, "agent")
        self.assertEqual(dino_game.parse_cli_args(["play", "--llm"]).mode, "llm")
        self.assertIsNone(dino_game.parse_cli_args(["play", "--llm"]).llm_mode)
        self.assertEqual(dino_game.parse_cli_args(["play", "--llm", "api"]).llm_mode, "API")
        self.assertEqual(dino_game.parse_cli_args(["play", "--llm", "codex"]).llm_mode, "CODEX")
        self.assertTrue(dino_game.parse_cli_args(["play", "--llm", "bad"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["play", "--llm", "--debug"]).llm_debug)
        self.assertTrue(dino_game.parse_cli_args(["play", "--llm", "codex", "--debug"]).llm_debug)
        self.assertFalse(dino_game.parse_cli_args(["play", "--debug"]).llm_debug)
        self.assertTrue(dino_game.parse_cli_args(["play", "--debug"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["play", "--auto", "--debug"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["play", "--auto", "--llm"]).show_help)
        self.assertEqual(dino_game.parse_cli_args(["replay", "run.json"]).replay_path, "run.json")
        self.assertEqual(dino_game.parse_cli_args(["replay", "+list"]).replay_action, "list")
        self.assertEqual(dino_game.parse_cli_args(["replay", "+clear"]).replay_action, "clear")
        self.assertTrue(dino_game.parse_cli_args(["replay", "+unknown"]).show_help)
        self.assertEqual(dino_game.parse_cli_args(["compete", "run.json"]).competition_path, "run.json")
        self.assertEqual(dino_game.parse_cli_args(["config"]).config_action, "show")
        self.assertEqual(dino_game.parse_cli_args(["config", "+setup"]).config_action, "setup")
        self.assertEqual(dino_game.parse_cli_args(["config", "+reset"]).config_action, "reset")
        self.assertEqual(dino_game.parse_cli_args(["setup"]).command, "setup")
        self.assertEqual(dino_game.parse_cli_args(["setup"]).config_action, "setup")
        self.assertEqual(dino_game.parse_cli_args(["dashboard"]).command, "dashboard")
        self.assertTrue(dino_game.parse_cli_args(["dashboard", "extra"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["setup", "extra"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["config", "+unknown"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["play", "--record", "run.json"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["compete", "--record", "run.json"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["agent"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["llm"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["--agent"]).show_help)
        self.assertTrue(dino_game.parse_cli_args(["--replay", "run.json"]).show_help)

    def test_help_flags_work_after_subcommands_and_unknown_falls_back_to_help(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args(["help"]).help_text, dino_game.render_main_help())
        self.assertEqual(dino_game.parse_cli_args(["play", "-H"]).help_text, dino_game.render_command_help("play"))
        self.assertEqual(dino_game.parse_cli_args(["config", "-H"]).help_text, dino_game.render_command_help("config"))
        self.assertEqual(dino_game.parse_cli_args(["setup", "-H"]).help_text, dino_game.render_command_help("setup"))
        self.assertEqual(dino_game.parse_cli_args(["foo"]).help_text, dino_game.render_main_help())
        self.assertEqual(dino_game.parse_cli_args(["help", "play"]).help_text, dino_game.render_command_help("play"))
        self.assertEqual(dino_game.parse_cli_args(["help", "play", "extra"]).help_text, dino_game.render_main_help())

    def test_version_flags_return_project_version(self):
        dino_game = self.dino_game()
        pyproject = tomllib.loads((pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
        expected_version = pyproject["project"]["version"]

        self.assertEqual(dino_game.VERSION, expected_version)
        self.assertEqual(dino_game.parse_cli_args(["--version"]).version, expected_version)
        self.assertEqual(dino_game.parse_cli_args(["play", "-V"]).version, expected_version)

    def test_constants_do_not_hardcode_project_version(self):
        constants_source = (
            pathlib.Path(__file__).resolve().parents[1]
            / "dino_game"
            / "constants.py"
        ).read_text()

        self.assertIsNone(re.search(r"^VERSION\s*=\s*['\"]\d", constants_source, re.MULTILINE))

    def test_version_helper_reads_pyproject_version(self):
        constants = importlib.import_module("dino_game.constants")
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject_path = pathlib.Path(temp_dir) / "pyproject.toml"
            pyproject_path.write_text('[project]\nversion = "9.8.7"\n')

            self.assertEqual(constants._version_from_pyproject(pyproject_path), "9.8.7")

    def test_project_version_falls_back_to_installed_metadata(self):
        constants = importlib.import_module("dino_game.constants")

        with mock.patch("dino_game.constants._version_from_pyproject", return_value=None), \
                mock.patch("dino_game.constants.metadata.version", return_value="7.6.5"):
            self.assertEqual(constants._project_version(), "7.6.5")

    def test_setup_keyboard_interrupt_exits_without_traceback(self):
        dino_game = self.dino_game()
        messages = []

        with mock.patch("sys.argv", ["dino", "setup"]), \
                mock.patch("builtins.print", messages.append), \
                mock.patch("dino_game.cli.run_config_setup", side_effect=KeyboardInterrupt):
            dino_game.cli()

        self.assertEqual(messages, ["Setup cancelled."])

    def test_llm_config_keyboard_interrupt_exits_without_traceback(self):
        dino_game = self.dino_game()
        messages = []

        with mock.patch("sys.argv", ["dino", "play", "--llm"]), \
                mock.patch("builtins.print", messages.append), \
                mock.patch(
                    "dino_game.cli.resolve_llm_config_for_run",
                    side_effect=KeyboardInterrupt,
                ):
            dino_game.cli()

        self.assertEqual(messages, ["Setup cancelled."])

    def test_llm_mode_argument_is_passed_to_config_resolution(self):
        dino_game = self.dino_game()
        config = dino_game.LLMConfig(llm_mode="CODEX")

        with mock.patch("sys.argv", ["dino", "play", "--llm", "codex"]), \
                mock.patch("dino_game.cli.resolve_llm_config_for_run", return_value=config) as resolve, \
                mock.patch("dino_game.cli.curses.wrapper") as wrapper:
            dino_game.cli()

        resolve.assert_called_once_with(llm_mode="CODEX")
        self.assertEqual(wrapper.call_args.args[1].llm_config, config)

    def test_config_error_exits_without_traceback(self):
        dino_game = self.dino_game()
        messages = []

        with mock.patch("sys.argv", ["dino", "play", "--llm"]), \
                mock.patch("builtins.print", messages.append), \
                mock.patch(
                    "dino_game.cli.resolve_llm_config_for_run",
                    side_effect=dino_game.LLMConfigError("Codex CLI is not installed."),
                ):
            dino_game.cli()

        self.assertEqual(messages, ["Codex CLI is not installed."])
