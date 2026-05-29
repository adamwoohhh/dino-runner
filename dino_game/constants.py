"""Shared constants for the terminal dino game."""

import json
import math
import os

FPS = 30                  # 帧率，决定游戏流畅度 (30帧 = 每帧33ms)

FRAME_MS = 1000 // FPS    # 每帧毫秒数，传给 curses.timeout()

GROUND_ROW = 18           # 地面在终端的第几行（从上往下数）

DINO_COL = 8              # 恐龙固定在屏幕左侧第 8 列

CONFIG_DIR_NAME = "ai-dino-in-terminal"

CONFIG_FILE_NAME = "config.json"

DEFAULT_LLM_ACTION_WINDOW_FRAMES = 600


def _positive_int(value, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _config_file_path(home: str | None = None) -> str:
    home_dir = home if home is not None else os.path.expanduser("~")
    return os.path.join(home_dir, ".config", CONFIG_DIR_NAME, CONFIG_FILE_NAME)


def _configured_llm_action_window_default(default: int) -> int:
    try:
        with open(_config_file_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(data, dict):
        return default
    return _positive_int(data.get("llm_window_frames"), default)


def _positive_int_from_env(name: str, default: int) -> int:
    return _positive_int(os.environ.get(name), default)


LLM_ACTION_WINDOW_FRAMES = _positive_int_from_env(
    "LLM_FEAME_WINDOW",
    _configured_llm_action_window_default(DEFAULT_LLM_ACTION_WINDOW_FRAMES),
)

LLM_ACTION_WINDOW_SECONDS = LLM_ACTION_WINDOW_FRAMES / FPS

JUMP_VELOCITY = -1.75     # 起跳初速度（负值 = 向上）

GRAVITY = 0.22            # 每帧施加的重力加速度

INITIAL_SPEED = 1.75      # 障碍物初始水平移动速度（终端列/帧）

MAX_SPEED = 3.8           # 速度上限，约为初始速度的 2.17 倍

NORMAL_OBSTACLE_SPAWN_X = 82


def obstacle_spawn_x_for_terminal_width(width: int | None) -> int:
    """Return the obstacle spawn X for a terminal width.

    The original tuning assumes an 80-column terminal where x=82 is just off
    the right edge. Wider terminals need a wider spawn point so new obstacles
    enter from the visible playfield's right edge instead of the middle.
    """
    try:
        parsed_width = int(width)
    except (TypeError, ValueError):
        return NORMAL_OBSTACLE_SPAWN_X
    return max(NORMAL_OBSTACLE_SPAWN_X, parsed_width)


LLM_FORECAST_MAX_X = max(
    1250,
    math.ceil(MAX_SPEED * LLM_ACTION_WINDOW_FRAMES + DINO_COL - 10),
)

NORMAL_STATE_LOOKAHEAD = NORMAL_OBSTACLE_SPAWN_X - DINO_COL + 10

LLM_STATE_LOOKAHEAD = LLM_FORECAST_MAX_X - DINO_COL + 10

SPEED_ACCELERATION = 0.0005

DIFFICULTY_MAX_SCORE = 600

SPAWN_MIN = 45            # 连续障碍物之间的最小间距（终端列）

SPAWN_MAX = 90            # 连续障碍物之间的最大间距（终端列）

RUN_ANIM_FRAME_INTERVAL = max(1, round(FPS / 12))

BIRD_ANIM_FRAME_INTERVAL = max(1, round(FPS / 8))

LOADING_DINO_ANIM_INTERVAL = 0.35

CELESTIAL_SCORE_THRESHOLD = 1000

CELESTIAL_EMPTY_GAP_FRAMES = 200

CELESTIAL_SPEED_MULTIPLIER = 0.1

CELESTIAL_Y = 2

SPEED_DROP_MULTIPLIER = 3.0

REPLAY_DIR = "replays"

VERSION = "0.1.0"

PAUSE_COUNTDOWN_SECONDS = 3

LLM_PREFETCH_THRESHOLD_FRAMES = LLM_ACTION_WINDOW_FRAMES

LLM_FALLBACK_WINDOW_FRAMES = 12

LLM_LOADING_TEXT = "Dino is thinking seriously..."

LLM_LIFELINE_REWIND_FRAMES = 20

LLM_LIFELINE_REWIND_TEXT = "Rewinding 20 frames..."

LLM_HORIZONTAL_OVERLAP_DISTANCE = 6.0

LLM_RECOMMENDED_JUMP_EARLY_FRAMES = 14

LLM_RECOMMENDED_JUMP_LATE_FRAMES = 2

VALID_ACTIONS = {"jump", "duck", "none"}

ACTION_SYMBOLS = {
    "none": "-",
    "jump": "↑",
    "duck": "↓",
}

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

DEFAULT_OPENAI_MODEL = "gpt-5-mini"
