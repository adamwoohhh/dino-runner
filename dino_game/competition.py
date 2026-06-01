"""Competition-mode domain logic and loop."""

from __future__ import annotations

import os
import random
import time

from .constants import NORMAL_OBSTACLE_SPAWN_X
from .engine import DinoGame, apply_game_action
from .input import ManualInputState, manual_action_from_key, next_pause_state, PauseState
from .replay import ReplayPlayer, ReplayRecorder, finish_recording
from .scores import append_game_record, load_high_score, save_high_score

class CompetitionRun:
    """协调竞技模式中的历史赛道和玩家赛道。"""

    def __init__(
            self,
            replay_player: ReplayPlayer,
            source_replay: str,
            record_path,
            obstacle_spawn_x: float = NORMAL_OBSTACLE_SPAWN_X):
        self.replay_player = replay_player
        self.source_replay = os.fspath(source_replay)
        self.history_game = DinoGame(
            rng=random.Random(replay_player.seed),
            obstacle_spawn_x=obstacle_spawn_x,
        )
        self.player_game = DinoGame(
            rng=random.Random(replay_player.seed),
            obstacle_spawn_x=obstacle_spawn_x,
        )
        self.player_game.high_score = load_high_score("competitive")
        self.recorder = ReplayRecorder(
            record_path,
            seed=replay_player.seed,
            mode="competitive",
            competitive=True,
            source_replay=self.source_replay,
            obstacle_spawn_x=obstacle_spawn_x,
        )
        self.frame = 0
        self.history_finished = replay_player.max_frame <= 0
        self.player_finished = False
        self.high_score_saved = False

    @property
    def finished(self) -> bool:
        return self.history_finished and self.player_finished

    def step(self, player_action: str):
        """推进竞技模式一帧。

        源 replay 范围内两条赛道使用同一组障碍物；玩家超过源 replay
        帧数后继续用源 seed 对玩家赛道实时生成新障碍物。
        """
        self.frame += 1

        if not self.history_finished:
            if self.replay_player.has_frame(self.frame):
                history_action = self.replay_player.action_for_frame(self.frame)
                apply_game_action(self.history_game, history_action)
                self.history_game.update(
                    replay_obstacles=self.replay_player.obstacles_for_frame(self.frame),
                )
            self.history_finished = (
                self.history_game.game_over
                or self.frame >= self.replay_player.max_frame
            )

        if self.player_game.game_over:
            self.player_finished = True
        elif not self.player_finished:
            apply_game_action(self.player_game, player_action)
            self.recorder.record_action(self.frame, player_action)
            if self.replay_player.has_frame(self.frame):
                spawned_obstacles = self.player_game.update(
                    replay_obstacles=self.replay_player.obstacles_for_frame(self.frame),
                )
            else:
                spawned_obstacles = self.player_game.update()
            for obstacle in spawned_obstacles:
                self.recorder.record_obstacle(self.frame, obstacle)
            self.player_finished = self.player_game.game_over

        if self.finished:
            if not self.high_score_saved:
                self.player_game.high_score = save_high_score(
                    "competitive",
                    self.player_game.score,
                )
                append_game_record(
                    "competitive",
                    self.player_game.score,
                    total_tokens=0,
                )
                self.high_score_saved = True
            finish_recording(self.recorder)

def run_competition_loop(stdscr, renderer: Renderer, competition: CompetitionRun):
    """运行竞技模式主循环。"""
    manual_input = ManualInputState()
    pause_state = PauseState()
    renderer.draw_competition(competition)

    while True:
        key = stdscr.getch()
        if key == ord('q') or key == ord('Q'):
            break
        now = time.monotonic()
        pause_state = next_pause_state(pause_state, key, now)

        if competition.finished:
            renderer.draw_competition(competition)
            continue

        if pause_state.status != "running":
            renderer.draw_competition(competition)
            renderer.draw_pause_overlay(pause_state, now)
            renderer.scr.refresh()
            continue

        action = "none"
        if not competition.player_finished:
            action = manual_action_from_key(manual_input, key)
        competition.step(action)
        renderer.draw_competition(competition)
