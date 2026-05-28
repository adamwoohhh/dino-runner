import importlib
import json
import os
import pathlib
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
        self.assertIn("Start a manual, auto, or LLM game", help_text)
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

        self.assertIn("Usage: dino play [--auto|--llm] [--debug]", play_help)
        self.assertIn("--auto", play_help)
        self.assertIn("--llm", play_help)
        self.assertIn("--debug", play_help)
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
        self.assertNotRegex(play_help + replay_help + compete_help + config_help, r"[\u4e00-\u9fff]")

    def test_parse_cli_args_uses_new_subcommands_only(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args([]).command, "play")
        self.assertEqual(dino_game.parse_cli_args(["play"]).mode, "manual")
        self.assertEqual(dino_game.parse_cli_args(["play", "--auto"]).mode, "agent")
        self.assertEqual(dino_game.parse_cli_args(["play", "--llm"]).mode, "llm")
        self.assertTrue(dino_game.parse_cli_args(["play", "--llm", "--debug"]).llm_debug)
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
        self.assertEqual(dino_game.parse_cli_args(["foo"]).help_text, dino_game.render_main_help())

    def test_version_flags_return_project_version(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.parse_cli_args(["--version"]).version, "0.1.0")
        self.assertEqual(dino_game.parse_cli_args(["play", "-V"]).version, "0.1.0")
