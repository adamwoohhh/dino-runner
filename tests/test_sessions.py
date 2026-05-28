import unittest
from unittest import mock

from dino_game import sessions
from dino_game.cli import CliArgs


class SessionsTest(unittest.TestCase):
    def test_replay_list_command_uses_replay_list_session_without_renderer(self):
        stdscr = object()
        cli_args = CliArgs(command="replay", replay_action="list")

        with mock.patch("dino_game.sessions.Renderer") as renderer_class:
            session = sessions.session_for_cli_args(stdscr, cli_args)

        self.assertIsInstance(session, sessions.ReplayListSession)
        renderer_class.assert_not_called()

    def test_manual_session_next_action_uses_manual_input_helper(self):
        renderer = mock.Mock()
        session = sessions.ManualSession(
            stdscr=mock.Mock(),
            renderer=renderer,
            cli_args=CliArgs(command="play", mode="manual"),
        )

        action = session._next_action(ord(" "))

        self.assertEqual(action, "jump")
        self.assertEqual(session.event_frame, 1)
        self.assertTrue(session.game.jumping)
