"""Runtime session controllers for each game mode."""

from __future__ import annotations

import random
import time

from .agents import RuleAgent
from .cli import CliArgs
from .competition import CompetitionRun, run_competition_loop
from .constants import LLM_LOADING_TEXT
from .engine import DinoGame, apply_game_action
from .input import (
    ManualInputState,
    PauseState,
    manual_action_from_key,
    next_pause_state,
    should_reset_after_game_over,
)
from .llm import LLMAgent, cached_frames_view_for_agent, debug_log_llm_game_over
from .rendering import Renderer
from .replay import (
    ReplayPlayer,
    browse_replay_files,
    debug_log_path_for_replay,
    default_replay_path,
    finish_recording,
    list_replay_files,
    select_replay_file,
    start_recording_run,
)


class ReplayListSession:
    def __init__(self, stdscr):
        self.stdscr = stdscr

    def run(self):
        browse_replay_files(self.stdscr, list_replay_files())


class CompetitionSession:
    def __init__(self, stdscr, renderer: Renderer, cli_args: CliArgs, replay_path: str):
        self.stdscr = stdscr
        self.renderer = renderer
        self.cli_args = cli_args
        self.replay_path = replay_path

    def run(self):
        replay_player = ReplayPlayer.from_file(self.replay_path)
        record_path = (
            self.cli_args.record_path
            or default_replay_path("competitive", replay_player.seed)
        )
        competition = CompetitionRun(
            replay_player,
            source_replay=self.replay_path,
            record_path=record_path,
        )
        run_competition_loop(self.stdscr, self.renderer, competition)


class PlaySession:
    def __init__(
            self,
            stdscr,
            renderer: Renderer,
            cli_args: CliArgs,
            replay_player: ReplayPlayer | None = None):
        self.stdscr = stdscr
        self.renderer = renderer
        self.cli_args = cli_args
        self.replay_player = replay_player
        self.mode = cli_args.mode
        self.run_index = 1
        self.manual_input = ManualInputState()
        self.pause_state = PauseState()
        self.event_frame = 0
        self.game, self.recorder = self._new_game()
        self.agent, self.agent_name = self._new_agent()

    def _new_game(self):
        if self.replay_player:
            return DinoGame(rng=random.Random(self.replay_player.seed)), None
        return start_recording_run(
            self.mode,
            self.cli_args.record_path,
            self.run_index,
        )

    def _new_agent(self):
        if self.replay_player:
            return None, "Replay"
        if self.cli_args.mode == "llm":
            try:
                debug_path = (
                    debug_log_path_for_replay(self.recorder.path)
                    if self.cli_args.llm_debug and self.recorder
                    else None
                )
                return (
                    LLMAgent(
                        self.cli_args.llm_config,
                        debug=self.cli_args.llm_debug,
                        debug_path=debug_path,
                    ),
                    "LLM Agent (OpenAI)",
                )
            except ValueError:
                return RuleAgent(), "Rule Agent (LLM config unavailable)"
        if self.cli_args.mode == "agent":
            return RuleAgent(), "Rule Agent"
        return None, ""

    def run(self):
        try:
            while True:
                key = self.stdscr.getch()
                if key == ord('q') or key == ord('Q'):
                    break
                now = time.monotonic()
                self.pause_state = next_pause_state(self.pause_state, key, now)

                if self.game.game_over:
                    self._handle_game_over(key)
                    continue

                if self.pause_state.status != "running":
                    self.renderer.draw(
                        self.game,
                        self.agent_name,
                        self.pause_state,
                        now,
                        cached_frames_view=cached_frames_view_for_agent(
                            self.agent,
                            self.event_frame + 1,
                        ),
                    )
                    continue

                action = self._next_action(key)
                if action is None:
                    continue

                if self.recorder:
                    self.recorder.record_action(self.event_frame, action)

                self._update_game(action)
                self.renderer.draw(
                    self.game,
                    self.agent_name,
                    cached_frames_view=cached_frames_view_for_agent(
                        self.agent,
                        self.event_frame + 1,
                    ),
                )
        except KeyboardInterrupt:
            return

    def _handle_game_over(self, key: int):
        if self.replay_player:
            self.event_frame += 1
            if not self.replay_player.has_frame(self.event_frame):
                self.renderer.draw(self.game, self.agent_name)
                return
            action = self.replay_player.action_for_frame(self.event_frame)
            if action == "reset":
                self.game.reset()
            self.renderer.draw(
                self.game,
                self.agent_name,
                cached_frames_view=cached_frames_view_for_agent(
                    self.agent,
                    self.event_frame + 1,
                ),
            )
            return

        if should_reset_after_game_over(key, agent_active=bool(self.agent)):
            self.run_index += 1
            self.game, self.recorder = self._new_game()
            self.manual_input = ManualInputState()
            self.pause_state = PauseState()
            self.event_frame = 0
            if isinstance(self.agent, LLMAgent):
                self.agent.reset_plan()
                if self.cli_args.llm_debug and self.recorder:
                    self.agent.set_debug_path(
                        debug_log_path_for_replay(self.recorder.path)
                    )
        self.renderer.draw(
            self.game,
            self.agent_name,
            cached_frames_view=cached_frames_view_for_agent(
                self.agent,
                self.event_frame + 1,
            ),
        )

    def _next_action(self, key: int) -> str | None:
        next_frame = self.event_frame + 1
        if self.replay_player:
            self.event_frame = next_frame
            if not self.replay_player.has_frame(self.event_frame):
                self.renderer.draw(self.game, self.agent_name)
                return None
            action = self.replay_player.action_for_frame(self.event_frame)
            apply_game_action(self.game, action)
            return action

        if isinstance(self.agent, LLMAgent):
            state = self.game.get_llm_state()
            self.agent.ensure_plan(state, next_frame)
            if self.agent.needs_loading(next_frame):
                self.renderer.draw(
                    self.game,
                    self.agent_name,
                    loading_text=LLM_LOADING_TEXT,
                    cached_frames_view=cached_frames_view_for_agent(
                        self.agent,
                        next_frame,
                    ),
                )
                return None
            self.event_frame = next_frame
            action = self.agent.decide(state, frame=self.event_frame)
            apply_game_action(self.game, action)
            return action

        self.event_frame = next_frame
        if self.agent:
            action = self.agent.decide(self.game.get_state())
            apply_game_action(self.game, action)
            return action

        action = manual_action_from_key(self.manual_input, key)
        apply_game_action(self.game, action)
        return action

    def _update_game(self, action: str):
        if self.replay_player:
            self.game.update(
                replay_obstacles=self.replay_player.obstacles_for_frame(self.event_frame),
            )
            return

        spawned_obstacles = self.game.update()
        if not self.recorder:
            return
        for obstacle in spawned_obstacles:
            self.recorder.record_obstacle(self.event_frame, obstacle)
        if self.game.game_over:
            debug_log_llm_game_over(
                self.agent,
                self.game,
                frame=self.event_frame,
                action=action,
            )
            finish_recording(self.recorder)


class ManualSession(PlaySession):
    pass


class AgentSession(PlaySession):
    pass


class ReplaySession(PlaySession):
    pass


def session_for_cli_args(stdscr, cli_args: CliArgs):
    if cli_args.command == "replay" and cli_args.replay_action == "list":
        return ReplayListSession(stdscr)

    renderer = Renderer(stdscr)
    if cli_args.command == "compete":
        replay_path = cli_args.competition_path or select_replay_file(
            stdscr,
            list_replay_files(),
        )
        if not replay_path:
            return None
        return CompetitionSession(stdscr, renderer, cli_args, replay_path)

    if cli_args.command == "replay":
        replay_path = cli_args.replay_path or select_replay_file(
            stdscr,
            list_replay_files(),
        )
        if not replay_path:
            return None
        return ReplaySession(
            stdscr,
            renderer,
            cli_args,
            ReplayPlayer.from_file(replay_path),
        )

    if cli_args.mode == "manual":
        return ManualSession(stdscr, renderer, cli_args)
    return AgentSession(stdscr, renderer, cli_args)
