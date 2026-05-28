"""Keyboard input and pause state helpers."""

import curses
import math
from dataclasses import dataclass

from .constants import PAUSE_COUNTDOWN_SECONDS

class ManualInputState:
    """跟踪终端手动输入中需要跨帧保持的状态。"""

    def __init__(self):
        self.ducking = False

    def should_duck(self, key: int) -> bool:
        """方向下锁定蹲下；下一个其他输入解除蹲下。"""
        if key == curses.KEY_DOWN:
            self.ducking = True
        elif key != -1:
            self.ducking = False

        return self.ducking

def should_reset_after_game_over(key: int, agent_active: bool = False) -> bool:
    """Game Over 后只允许玩家显式按 R 重开。"""
    return key == ord('r') or key == ord('R')

@dataclass(frozen=True)
class PauseState:
    """游戏暂停状态。"""

    status: str = "running"
    countdown_started_at: float | None = None

def is_enter_key(key: int) -> bool:
    """判断按键是否为 Enter。"""
    return key in (10, 13, getattr(curses, "KEY_ENTER", 343))

def countdown_remaining_seconds(pause_state: PauseState, now: float) -> int:
    """返回倒计时剩余秒数，向上取整用于显示。"""
    if pause_state.countdown_started_at is None:
        return PAUSE_COUNTDOWN_SECONDS
    elapsed = now - pause_state.countdown_started_at
    return max(0, math.ceil(PAUSE_COUNTDOWN_SECONDS - elapsed))

def next_pause_state(pause_state: PauseState, key: int, now: float) -> PauseState:
    """根据当前按键和时间推进暂停状态机。"""
    if pause_state.status == "countdown" and countdown_remaining_seconds(pause_state, now) <= 0:
        return PauseState()
    if pause_state.status == "running" and is_enter_key(key):
        return PauseState(status="paused")
    if pause_state.status == "paused" and is_enter_key(key):
        return PauseState(status="countdown", countdown_started_at=now)
    return pause_state

def pause_allows_game_update(pause_state: PauseState, now: float) -> bool:
    """判断当前暂停状态是否允许推进游戏帧。"""
    return next_pause_state(pause_state, -1, now).status == "running"

def pause_overlay_lines(pause_state: PauseState, now: float) -> list[str]:
    """返回暂停/倒计时居中提示文案。"""
    if pause_state.status == "paused":
        return ["PAUSED", "Press Enter to resume"]
    if pause_state.status == "countdown":
        remaining = countdown_remaining_seconds(pause_state, now)
        return [str(max(1, remaining)), "Get ready"]
    return []

def manual_action_from_key(input_state: ManualInputState, key: int) -> str:
    """把当前键盘输入转换为手动玩家动作，不直接修改游戏状态。"""
    if key == ord(' ') or key == curses.KEY_UP:
        input_state.should_duck(key)
        return "jump"
    ducking = input_state.should_duck(key)
    return "duck" if ducking else "none"
