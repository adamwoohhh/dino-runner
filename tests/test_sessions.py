import unittest
from unittest import mock

import dino_game
from dino_game import sessions
from dino_game.cli import CliArgs


class SessionsTest(unittest.TestCase):
    class FakeScreen:
        def __init__(self, keys=None):
            self.keys = list(keys or [])
            self.nodelay_calls = []
            self.timeout_calls = []

        def nodelay(self, value):
            self.nodelay_calls.append(value)

        def timeout(self, value):
            self.timeout_calls.append(value)

        def getch(self):
            if self.keys:
                return self.keys.pop(0)
            return ord("q")

    def test_replay_selection_restores_nonblocking_game_input_before_playback(self):
        stdscr = self.FakeScreen()
        cli_args = CliArgs(command="replay")

        def select_replay_file(screen, paths):
            screen.nodelay(False)
            return "run.json"

        with (
            mock.patch("dino_game.sessions.Renderer") as renderer_class,
            mock.patch("dino_game.sessions.list_replay_files", return_value=["run.json"]),
            mock.patch("dino_game.sessions.select_replay_file", side_effect=select_replay_file),
            mock.patch(
                "dino_game.sessions.ReplayPlayer.from_file",
                return_value=dino_game.ReplayPlayer(seed=123, actions=[], obstacles=[]),
            ),
        ):
            renderer_class.return_value = mock.Mock()
            session = sessions.session_for_cli_args(stdscr, cli_args)

        self.assertIsInstance(session, sessions.ReplaySession)
        self.assertEqual(stdscr.nodelay_calls[-1], True)
        self.assertEqual(stdscr.timeout_calls[-1], dino_game.FRAME_MS)

    def test_competition_selection_restores_nonblocking_game_input_before_playback(self):
        stdscr = self.FakeScreen()
        cli_args = CliArgs(command="compete")

        def select_replay_file(screen, paths):
            screen.nodelay(False)
            return "run.json"

        with (
            mock.patch("dino_game.sessions.Renderer") as renderer_class,
            mock.patch("dino_game.sessions.list_replay_files", return_value=["run.json"]),
            mock.patch("dino_game.sessions.select_replay_file", side_effect=select_replay_file),
            mock.patch(
                "dino_game.sessions.ReplayPlayer.from_file",
                return_value=dino_game.ReplayPlayer(seed=123, actions=[], obstacles=[]),
            ),
        ):
            renderer_class.return_value = mock.Mock()
            session = sessions.session_for_cli_args(stdscr, cli_args)

        self.assertIsInstance(session, sessions.CompetitionSession)
        self.assertEqual(stdscr.nodelay_calls[-1], True)
        self.assertEqual(stdscr.timeout_calls[-1], dino_game.FRAME_MS)

    def test_replay_session_run_advances_frames_without_keypress(self):
        stdscr = self.FakeScreen(keys=[-1, -1, ord("q")])
        renderer = mock.Mock()
        replay_player = dino_game.ReplayPlayer(
            seed=123,
            actions=[{"frame": 1, "action": {"value": "jump"}}],
            obstacles=[],
            frames=2,
        )
        session = sessions.ReplaySession(
            stdscr=stdscr,
            renderer=renderer,
            cli_args=CliArgs(command="replay", mode="manual"),
            replay_player=replay_player,
        )

        session.run()

        self.assertEqual(session.event_frame, 2)
        self.assertGreaterEqual(renderer.draw.call_count, 2)

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

    def test_game_over_does_not_auto_save_replay_until_s_is_pressed(self):
        renderer = mock.Mock()
        session = sessions.ManualSession(
            stdscr=mock.Mock(),
            renderer=renderer,
            cli_args=CliArgs(command="play", mode="manual"),
        )
        session.recorder = mock.Mock()

        def end_game():
            session.game.game_over = True
            return []

        session.game.update = end_game
        with (
            mock.patch("dino_game.sessions.finish_recording") as finish_recording,
            mock.patch("dino_game.sessions.save_high_score", return_value=0),
        ):
            session._update_game("none")

            finish_recording.assert_not_called()
            session.recorder.save.assert_not_called()

            session._handle_game_over(ord("s"))

            finish_recording.assert_called_once_with(session.recorder)
            renderer.draw.assert_called_with(
                session.game,
                session.agent_name,
                cached_frames_view=None,
                game_over_save_status="saved",
            )

    def test_session_loads_and_persists_mode_high_score(self):
        renderer = mock.Mock()
        with (
            mock.patch("dino_game.sessions.load_high_score", return_value=41),
            mock.patch("dino_game.sessions.save_high_score", return_value=50) as save_high_score,
        ):
            session = sessions.ManualSession(
                stdscr=mock.Mock(),
                renderer=renderer,
                cli_args=CliArgs(command="play", mode="manual"),
            )

            self.assertEqual(session.game.high_score, 41)
            session.game.score = 50
            session.game.update = lambda: setattr(session.game, "game_over", True) or []
            session._update_game("none")

        save_high_score.assert_called_once_with("manual", 50)
        self.assertEqual(session.game.high_score, 50)

    def test_llm_game_over_waits_for_c_before_rewinding_lifeline(self):
        renderer = mock.Mock()
        config = dino_game.LLMConfig("key", "https://example.test/v1", "model")
        session = sessions.AgentSession(
            stdscr=mock.Mock(),
            renderer=renderer,
            cli_args=CliArgs(command="play", mode="llm", llm_config=config),
        )
        session.agent.reset_plan()
        session.recorder = mock.Mock(actions=[], obstacles=[], frames=0, input_count=0)

        for frame in range(25):
            session.event_frame = frame
            session.game.score = frame
            session.game.frame = frame
            session.game.game_over = False
            session._remember_rewind_frame()
        session.event_frame = 25
        session.game.score = 25
        session.game.frame = 25
        session.game.game_over = True
        session.agent.planned_actions = {
            5: "jump",
            6: "duck",
            26: "jump",
            40: "duck",
        }
        session.agent.consumed_actions = {4: "none", 5: "jump", 6: "none", 10: "duck"}
        session.agent.requested_until_frame = 40
        session.agent.requested_frame_ranges = [(5, 40)]
        with mock.patch("dino_game.sessions.save_high_score", return_value=25):
            session._update_game("none")

        self.assertTrue(session.game.game_over)
        self.assertEqual(session.event_frame, 25)
        self.assertEqual(session.game_over_save_status, "unsaved")
        self.assertEqual(session.llm_lifeline_state, "idle")
        self.assertIn(26, session.agent.planned_actions)

        session._handle_game_over(ord("c"))

        self.assertFalse(session.game.game_over)
        self.assertEqual(session.event_frame, 24)
        self.assertEqual(session.game.score, 24)
        self.assertEqual(session.llm_lifeline_state, "rewinding")
        self.assertEqual(len(session.llm_lifeline_rewind_frames), 19)
        self.assertIn(5, session.agent.planned_actions)
        self.assertNotIn(6, session.agent.planned_actions)
        self.assertIn(5, session.agent.consumed_actions)
        self.assertNotIn(6, session.agent.consumed_actions)
        self.assertEqual(session.agent.requested_until_frame, 5)
        self.assertEqual(session.agent.requested_frame_ranges, [])

        session._next_action(-1)

        self.assertEqual(session.event_frame, 23)
        renderer.draw.assert_called_with(
            session.game,
            session.agent_name,
            loading_text="Rewinding 20 frames...",
            cached_frames_view=session.agent.cached_frame_window(session.event_frame + 1),
            game_over_save_status=None,
            game_over_retry_available=False,
        )

    def test_llm_game_over_disables_lifeline_after_replay_is_saved(self):
        renderer = mock.Mock()
        config = dino_game.LLMConfig("key", "https://example.test/v1", "model")
        session = sessions.AgentSession(
            stdscr=mock.Mock(),
            renderer=renderer,
            cli_args=CliArgs(command="play", mode="llm", llm_config=config),
        )
        session.recorder = mock.Mock()
        session.game.game_over = True
        session.game_over_save_status = "unsaved"

        with mock.patch("dino_game.sessions.finish_recording"):
            session._handle_game_over(ord("s"))
        session._handle_game_over(ord("c"))

        self.assertEqual(session.game_over_save_status, "saved")
        self.assertEqual(session.llm_lifeline_state, "idle")
        renderer.draw.assert_called_with(
            session.game,
            session.agent_name,
            cached_frames_view=None,
            game_over_save_status="saved",
        )

    def test_llm_lifeline_waits_for_new_plan_after_rewind_animation(self):
        renderer = mock.Mock()
        config = dino_game.LLMConfig("key", "https://example.test/v1", "model")
        session = sessions.AgentSession(
            stdscr=mock.Mock(),
            renderer=renderer,
            cli_args=CliArgs(command="play", mode="llm", llm_config=config),
        )
        session.agent.reset_plan()
        session.llm_lifeline_state = "rewinding"
        session.llm_lifeline_animation_frames_remaining = 1
        session.event_frame = 5

        self.assertIsNone(session._next_action(-1))
        self.assertEqual(session.llm_lifeline_state, "loading")

        session.agent.planned_actions[6] = "jump"
        action = session._next_action(-1)

        self.assertEqual(action, "jump")
        self.assertEqual(session.llm_lifeline_state, "idle")
        self.assertEqual(session.event_frame, 6)
        self.assertTrue(session.game.jumping)
