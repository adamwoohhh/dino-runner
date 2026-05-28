"""Shared constants for the terminal dino game."""

FPS = 30                  # 帧率，决定游戏流畅度 (30帧 = 每帧33ms)

FRAME_MS = 1000 // FPS    # 每帧毫秒数，传给 curses.timeout()

GROUND_ROW = 18           # 地面在终端的第几行（从上往下数）

DINO_COL = 8              # 恐龙固定在屏幕左侧第 8 列

NORMAL_OBSTACLE_SPAWN_X = 82

LLM_FORECAST_MAX_X = 1250

NORMAL_STATE_LOOKAHEAD = NORMAL_OBSTACLE_SPAWN_X - DINO_COL + 10

LLM_STATE_LOOKAHEAD = LLM_FORECAST_MAX_X - DINO_COL + 10

JUMP_VELOCITY = -1.75     # 起跳初速度（负值 = 向上）

GRAVITY = 0.22            # 每帧施加的重力加速度

INITIAL_SPEED = 1.75      # 障碍物初始水平移动速度（终端列/帧）

MAX_SPEED = 3.8           # 速度上限，约为初始速度的 2.17 倍

SPEED_ACCELERATION = 0.0005

DIFFICULTY_MAX_SCORE = 600

SPAWN_MIN = 45            # 连续障碍物之间的最小间距（终端列）

SPAWN_MAX = 90            # 连续障碍物之间的最大间距（终端列）

RUN_ANIM_FRAME_INTERVAL = max(1, round(FPS / 12))

BIRD_ANIM_FRAME_INTERVAL = max(1, round(FPS / 8))

LOADING_DINO_ANIM_INTERVAL = 0.35

SPEED_DROP_MULTIPLIER = 3.0

REPLAY_DIR = "replays"

VERSION = "0.1.0"

PAUSE_COUNTDOWN_SECONDS = 3

LLM_ACTION_WINDOW_SECONDS = 10

LLM_ACTION_WINDOW_FRAMES = FPS * LLM_ACTION_WINDOW_SECONDS

LLM_PREFETCH_THRESHOLD_FRAMES = LLM_ACTION_WINDOW_FRAMES

LLM_FALLBACK_WINDOW_FRAMES = 12

LLM_LOADING_TEXT = "Dino is thinking seriously..."

LLM_HORIZONTAL_OVERLAP_DISTANCE = 6.0

LLM_RECOMMENDED_JUMP_EARLY_FRAMES = 14

LLM_RECOMMENDED_JUMP_LATE_FRAMES = 2

VALID_ACTIONS = {"jump", "duck", "none"}

ACTION_SYMBOLS = {
    "none": "-",
    "jump": "↑",
    "duck": "↓",
}

CONFIG_DIR_NAME = "ai-dino-in-terminal"

CONFIG_FILE_NAME = "config.json"

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

DEFAULT_OPENAI_MODEL = "gpt-5-mini"
