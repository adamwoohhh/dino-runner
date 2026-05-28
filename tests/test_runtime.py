import unittest
from unittest import mock

from dino_game import runtime
from dino_game.cli import CliArgs


class RuntimeTest(unittest.TestCase):
    def test_main_selects_and_runs_session(self):
        session = mock.Mock()
        stdscr = object()
        cli_args = CliArgs()

        with mock.patch("dino_game.sessions.session_for_cli_args", return_value=session) as select:
            runtime.main(stdscr, cli_args)

        select.assert_called_once_with(stdscr, cli_args)
        session.run.assert_called_once_with()

