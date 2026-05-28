#!/usr/bin/env python3
"""
Terminal Dino Runner — Chrome 断网小恐龙的终端版本

这是一个在终端中运行的横版跑酷游戏，模仿 Chrome 浏览器断网时出现的 T-Rex Runner。
核心目的是演示「如何让 AI Agent 自动玩游戏」。

架构概览:
  ┌──────────┐     get_state()     ┌───────────┐
  │  游戏引擎  │ ───────────────────▶ │   Agent   │
  │ DinoGame │ ◀─────────────────── │ (决策器)   │
  └──────────┘   jump() / duck()   └───────────┘
       │                                 │
       ▼                                 │
  ┌──────────┐                     ┌─────┴─────┐
  │  渲染器   │                     │ RuleAgent │  基于距离阈值（毫秒级）
  │ Renderer │                     │ LLMAgent  │  调用 OpenAI Responses API（秒级）
  └──────────┘                     └───────────┘

三种运行模式:
  python dino_game.py                 # 等价于 play，人类手动玩
  python dino_game.py play            # 人类手动玩
  python dino_game.py agent           # 规则 AI Agent 自动玩
  python dino_game.py llm             # OpenAI LLM Agent 玩 (需要本地配置或交互输入)
  python dino_game.py replay          # 从运行记录列表选择并重放
  python dino_game.py replay run.json # 重放一局
  python dino_game.py replay +list    # 浏览记录并查看元信息
  python dino_game.py replay +clear   # 清除所有记录
  python dino_game.py compete         # 选择一条运行记录并进入竞技模式
  python dino_game.py compete run.json # 直接竞技指定记录

游戏内操控:
  SPACE / ↑  跳跃
  ↓          蹲下（地面）/ 快速下落（空中）
  Enter      暂停；暂停时再次按下会倒计时 3 秒后继续
  R          Game Over 后重新开始
  Q          退出

依赖: 纯 Python 标准库（curses, json, threading），零第三方依赖
"""

import curses
import time
import random
import sys
import os
import json
import threading
import math
from dataclasses import dataclass
from importlib import metadata


# ═══════════════════════════════════════════════════════════════════════
# 游戏常量 — 调这些数字可以改变游戏手感
# ═══════════════════════════════════════════════════════════════════════

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
                          # 跳跃轨迹: 约 17 帧完成一次完整跳跃
                          # 最大高度: 约 7.6 个单位

INITIAL_SPEED = 1.75      # 障碍物初始水平移动速度（终端列/帧）
MAX_SPEED = 3.8           # 速度上限，约为初始速度的 2.17 倍
SPEED_ACCELERATION = 0.0005
                          # 速度公式: speed = min(MAX_SPEED, INITIAL_SPEED + score * SPEED_ACCELERATION)
DIFFICULTY_MAX_SCORE = 600
                          # 难度系数: difficulty = min(1.0, score / DIFFICULTY_MAX_SCORE)

SPAWN_MIN = 45            # 连续障碍物之间的最小间距（终端列）
SPAWN_MAX = 90            # 连续障碍物之间的最大间距（终端列）
                          # 按 30 FPS 的更快横向速度调大，留出落地窗口

RUN_ANIM_FRAME_INTERVAL = max(1, round(FPS / 12))
BIRD_ANIM_FRAME_INTERVAL = max(1, round(FPS / 8))
LOADING_DINO_ANIM_INTERVAL = 0.35
SPEED_DROP_MULTIPLIER = 3.0
REPLAY_DIR = "replays"
VERSION = "0.1.0"
PAUSE_COUNTDOWN_SECONDS = 3
LLM_ACTION_WINDOW_SECONDS = 10
LLM_ACTION_WINDOW_FRAMES = FPS * LLM_ACTION_WINDOW_SECONDS
# LLM calls can take longer than a short gameplay buffer; start the next
# window as soon as the previous one is available.
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


# ═══════════════════════════════════════════════════════════════════════
# 像素艺术 — 用 Unicode 方块字符绘制的游戏精灵
# ═══════════════════════════════════════════════════════════════════════
# 常用字符: █(实心) ▀▄(半块) ▌▐(侧半块) ░(浅色) ▁▂(底线)

# ── 恐龙（6行高，~10列宽）──

DINO_STAND = [            # 站立姿态（游戏开始前）
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",         # 头部，█▀█ 是眼睛
    r"  ▄██████ ",         # 身体
    r"  ████▄   ",
    r"   ██     ",         # 腿
    r"   █▄█▄   ",
]

DINO_RUN_1 = [            # 跑步帧 1 — 右脚前
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █▄ ▄   ",         # 两腿分开（右前）
]

DINO_RUN_2 = [            # 跑步帧 2 — 左脚前（与帧1交替播放产生跑步动画）
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"  ▄  █▄   ",         # 两腿分开（左前）
]

DINO_DUCK = [             # 蹲下姿态 — 整体下移2行，高度减小
    r"          ",         # 空行（原来头部的位置）
    r"          ",
    r"    ▄███▄ ",
    r"  ██▀█▀▀█ ",
    r"  ▀██████ ",
    r"    █▄ ▄█ ",
]

DINO_JUMP = [             # 跳跃姿态 — 腿伸直
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █  █   ",         # 腿伸直张开
]

DINO_LOADING_STAND = DINO_RUN_1

DINO_LOADING_STAND_BLINK = [
    r"    ▄███▄ ",
    r"    ██▀▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █▄ ▄   ",
]

DINO_LOADING_JUMP_OPEN = DINO_JUMP

DINO_LOADING_JUMP = [     # LLM loading: 原始跳跃姿态眨眼
    r"    ▄███▄ ",
    r"    ██▀▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █  █   ",
]

DINO_LOADING_DUCK_OPEN = DINO_DUCK

DINO_LOADING_DUCK = [     # LLM loading: 原始蹲下姿态眨眼
    r"          ",
    r"          ",
    r"    ▄███▄ ",
    r"  ██▀▀▀▀█ ",
    r"  ▀██████ ",
    r"    █▄ ▄█ ",
]

# ── 障碍物 ──

CACTUS_SM = [             # 小仙人掌（4行高，3列宽）
    " ▌ ",                # 顶部
    "▐█▌",                # 身体（两侧有臂）
    " █ ",
    " █ ",                # 根部
]

CACTUS_LG = [             # 大仙人掌（6行高，5列宽）— 最难跳过的障碍物
    "  ▌  ",
    "▌ █ ▌",              # 两侧伸出手臂
    "█▐█▌█",
    " ▀█▀ ",
    "  █  ",
    "  █  ",
]

CACTUS_PLANT_ART = {
    "short": CACTUS_SM,
    "tall": CACTUS_LG,
}

BIRD_1 = [                # 翼龙帧 1 — 翅膀朝上
    r" ▄  ",
    r"▀▀▀▀",
]

BIRD_2 = [                # 翼龙帧 2 — 翅膀朝下（与帧1交替产生拍翅动画）
    r"▄▄▄▄",
    r" ▀  ",
]

CLOUD = [                 # 装饰性云朵（不参与碰撞）
    "  ░░  ",
    " ░░░░ ",
    "░░░░░░",
]

# 障碍物类型 → 默认美术资源映射
OBSTACLE_ART = {
    "cactus_sm": CACTUS_SM,
    "cactus_lg": CACTUS_LG,
    "bird": BIRD_1,       # 鸟在渲染时会在 BIRD_1/BIRD_2 之间交替
}


def difficulty_for_score(score: int) -> float:
    """根据分数返回 0.0~1.0 的游戏难度系数。"""
    return min(1.0, max(0.0, score / DIFFICULTY_MAX_SCORE))


def max_cactus_group_size(difficulty: float) -> int:
    """按难度解锁更长的仙人掌连组。"""
    if difficulty < 0.33:
        return 2
    if difficulty < 0.66:
        return 3
    return 4


def generate_cactus_group(difficulty: float = 1.0, rng=random) -> tuple[str, ...]:
    """随机生成高/矮仙人掌组合，随难度逐步解锁 4 连。"""
    max_count = max_cactus_group_size(difficulty)
    while True:
        count = rng.randint(1, max_count)
        plants = tuple(rng.choice(("short", "tall")) for _ in range(count))
        if count >= 3 and plants.count("tall") > 1:
            continue
        if plants != ("tall", "tall", "tall", "tall"):
            return plants


def compose_cactus_group_art(plants: tuple[str, ...]) -> list[str]:
    """把多个高/矮仙人掌合成为一个底部对齐的障碍物美术。"""
    padded_plants = []
    max_h = max(len(CACTUS_PLANT_ART[plant]) for plant in plants)
    for plant in plants:
        art = CACTUS_PLANT_ART[plant]
        width = max(len(line) for line in art)
        top_padding = [" " * width] * (max_h - len(art))
        padded_plants.append(top_padding + art)

    rows = []
    for row in range(max_h):
        rows.append(" ".join(plant[row] for plant in padded_plants))
    return rows


# ═══════════════════════════════════════════════════════════════════════
# 游戏逻辑
# ═══════════════════════════════════════════════════════════════════════

class Obstacle:
    """单个障碍物实体

    Attributes:
        kind:   类型标识，"cactus_sm" / "cactus_lg" / "cactus_group" / "bird"
        x:      当前水平位置（浮点数，从右侧 82 出生，向左移动）
        height: 垂直偏移（仅鸟使用：0=贴地, 4=中空, 8=高空）
        art:    对应的 ASCII 美术行列表
        width:  美术中最宽一行的字符数（用于碰撞检测）
        h:      美术行数（用于碰撞检测）
    """

    def __init__(
            self,
            kind: str,
            x: float,
            height: int = 0,
            plants: tuple[str, ...] | None = None,
            difficulty: float = 1.0,
            rng=random):
        self.kind = kind
        self.x = float(x)
        self.height = height
        self.plants = plants
        if kind == "cactus_group":
            if plants is None:
                plants = generate_cactus_group(difficulty, rng=rng)
                self.plants = plants
            self.art = compose_cactus_group_art(plants)
        else:
            self.art = OBSTACLE_ART[kind]
        self.width = max(len(line) for line in self.art)
        self.h = len(self.art)

    @property
    def hitbox(self) -> tuple:
        """返回 AABB 碰撞箱 (left, right, bottom, top)

        坐标系: X 轴向右为正，Y 轴向上为正，地面 Y=0
        """
        return self.hitboxes[0]

    @property
    def hitboxes(self) -> list[tuple]:
        """返回一个或多个 AABB 碰撞箱。

        组合仙人掌按每株植物单独检测，避免把矮仙人掌上方空白当成碰撞。
        """
        if self.kind == "cactus_group":
            boxes = []
            offset = 0
            for plant in self.plants or ():
                art = CACTUS_PLANT_ART[plant]
                width = max(len(line) for line in art)
                boxes.append((
                    self.x + offset,
                    self.x + offset + width - 1,
                    0,
                    len(art) - 1,
                ))
                offset += width + 1
            return boxes

        left = self.x
        right = self.x + self.width - 1
        bottom = self.height
        if self.kind == "bird":
            if self.height == 0:
                bottom = 1
            elif self.height == 4:
                bottom = 3
        top = bottom + self.h - 1
        return [(left, right, bottom, top)]


def random_obstacle_for_score(score: int, x: float, rng=random) -> Obstacle:
    """Create a random obstacle for a score without mutating game state."""
    if score < 200:
        kinds = ["cactus_group", "cactus_group", "cactus_group"]
    elif score < 500:
        kinds = ["cactus_group", "cactus_group", "cactus_group", "bird"]
    else:
        kinds = ["cactus_group", "cactus_group", "cactus_group", "bird", "bird"]

    kind = rng.choice(kinds)
    height = 0
    if kind == "bird":
        height = rng.choice([0, 4, 8])

    return Obstacle(
        kind,
        x,
        height,
        difficulty=difficulty_for_score(score),
        rng=rng,
    )


def obstacle_debug_snapshot(obstacle: Obstacle) -> dict:
    """Return a JSON-friendly obstacle snapshot for diagnostics."""
    data = {
        "kind": obstacle.kind,
        "x": round(obstacle.x, 2),
        "height": obstacle.height,
        "width": obstacle.width,
        "h": obstacle.h,
    }
    if obstacle.kind == "cactus_group":
        data["plants"] = list(obstacle.plants or ())
    return data


class DinoGame:
    """游戏引擎 — 管理所有游戏状态和物理模拟

    职责:
      1. 恐龙物理（跳跃抛物线、蹲下）
      2. 障碍物生成与移动
      3. 碰撞检测
      4. 分数计算

    不负责: 渲染（交给 Renderer）、决策（交给 Agent）
    """

    def __init__(self, rng=None, obstacle_spawn_x: float = NORMAL_OBSTACLE_SPAWN_X):
        self.rng = rng if rng is not None else random
        self.obstacle_spawn_x = obstacle_spawn_x
        self.reset()

    def reset(self):
        """重置所有游戏状态，开始新一局"""
        self.dino_y = 0.0       # 恐龙当前高度 (0 = 站在地面上)
        self.dino_vy = 0.0      # 恐龙垂直速度 (负=向上, 正=向下)
        self.ducking = False    # 是否正在蹲下
        self.jumping = False    # 是否正在跳跃（含上升和下落全程）
        self.obstacles: list[Obstacle] = []
        self.clouds: list[dict] = []   # 装饰云朵 [{x, y}, ...]
        self.score = 0          # 当前分数（每帧 +1）
        self.high_score = 0     # 历史最高分（跨局保持）
        self.speed = INITIAL_SPEED
        self.game_over = False
        self.last_collision: dict | None = None
        self.frame = 0          # 帧计数器（用于动画切换）
        self.spawn_timer = self.rng.randint(SPAWN_MIN, SPAWN_MAX)
        self.ground_offset = 0  # 地面纹理滚动偏移（视觉效果）

    def jump(self):
        """发起跳跃 — 只有站在地面时才能起跳"""
        if self.dino_y < 0.5 and not self.jumping:
            self.dino_vy = JUMP_VELOCITY    # 赋予向上的初速度
            self.jumping = True
            self.ducking = False            # 跳跃时取消蹲下

    def duck(self, active: bool):
        """蹲下控制

        地面蹲下: 缩小碰撞箱高度 (5→3)，可以躲过中空飞鸟
        空中按下: 将当前上升速度反转为下落，实现「快速下落」
        """
        if self.dino_y < 0.5:             # 在地面
            self.ducking = active
        if active and self.jumping and self.dino_vy < 0:
            # 空中且仍在上升阶段 → 反转并放大速度，快速下落
            self.dino_vy = max(abs(self.dino_vy) * SPEED_DROP_MULTIPLIER, 1.0)

    def get_state(
            self,
            max_obstacle_distance: float = NORMAL_STATE_LOOKAHEAD,
            obstacles: list[Obstacle] | None = None,
            max_obstacle_count: int | None = 3) -> dict:
        """导出当前游戏状态的结构化快照 — Agent 的「眼睛」

        这是 Agent 与游戏交互的核心接口。Agent 通过这个方法
        「观察」游戏世界，然后做出 jump/duck/none 的决策。

        Returns:
            dict: {
                dino_y:     恐龙高度 (0=地面)
                dino_vy:    垂直速度
                jumping:    是否在跳
                ducking:    是否在蹲
                speed:      当前游戏速度
                score:      当前分数
                obstacles:  前方最近 3 个障碍物的列表，每个包含:
                    kind:     类型
                    x:        绝对X坐标
                    distance: 到恐龙的水平距离（正=在前方）
                    height:   垂直偏移（鸟的飞行高度）
                    width:    宽度
                    h:        高度
            }
        """
        nearest = []
        source_obstacles = self.obstacles if obstacles is None else obstacles
        for obs in sorted(source_obstacles, key=lambda o: o.x):
            distance = obs.x - DINO_COL
            # 只返回还没完全飞过恐龙的障碍物
            if obs.x + obs.width > DINO_COL - 2 and distance <= max_obstacle_distance:
                item = {
                    "kind": obs.kind,
                    "x": round(obs.x, 1),
                    "distance": round(distance, 1),
                    "height": obs.height,
                    "width": obs.width,
                    "h": obs.h,
                }
                if hasattr(obs, "forecast_frame"):
                    item["spawn_frame"] = obs.forecast_frame
                    item["forecast"] = True
                nearest.append(item)
                if max_obstacle_count is not None and len(nearest) >= max_obstacle_count:
                    break

        return {
            "dino_y": round(self.dino_y, 1),
            "dino_vy": round(self.dino_vy, 2),
            "jumping": self.jumping,
            "ducking": self.ducking,
            "speed": round(self.speed, 2),
            "score": self.score,
            "obstacles": nearest,
        }

    def get_llm_state(self) -> dict:
        """导出 LLM 使用的更大前视窗口状态。"""
        obstacles = self.obstacles + self.forecast_future_obstacles()
        return self.get_state(
            max_obstacle_distance=LLM_STATE_LOOKAHEAD,
            obstacles=obstacles,
            max_obstacle_count=None,
        )

    def _clone_rng(self):
        if not hasattr(self.rng, "getstate") or not hasattr(self.rng, "setstate"):
            return None
        clone = random.Random()
        clone.setstate(self.rng.getstate())
        return clone

    def forecast_future_obstacles(
            self,
            max_x: float = LLM_FORECAST_MAX_X) -> list[Obstacle]:
        """Predict future obstacle spawns for LLM vision without mutating game state."""
        forecast_rng = self._clone_rng()
        if forecast_rng is None:
            return []

        forecasts: list[Obstacle] = []
        score = self.score
        speed = self.speed
        spawn_timer = self.spawn_timer
        travelled = 0.0
        max_travel = max(0.0, max_x - NORMAL_OBSTACLE_SPAWN_X)

        while travelled <= max_travel:
            score += 1
            speed = min(MAX_SPEED, INITIAL_SPEED + score * SPEED_ACCELERATION)
            travelled += speed
            spawn_timer -= speed

            if spawn_timer <= 0:
                obstacle = random_obstacle_for_score(
                    score,
                    NORMAL_OBSTACLE_SPAWN_X + travelled,
                    forecast_rng,
                )
                obstacle.forecast_frame = self.frame + (score - self.score)
                forecasts.append(obstacle)
                spawn_timer = forecast_rng.randint(SPAWN_MIN, SPAWN_MAX)

            if forecast_rng.random() < 0.02:
                forecast_rng.randint(2, 8)

        return forecasts

    def update(self, replay_obstacles: list[dict] | None = None) -> list[Obstacle]:
        """推进一帧游戏逻辑 — 每帧调用一次

        执行顺序:
          1. 更新分数和速度
          2. 恐龙物理（跳跃抛物线）
          3. 移动所有障碍物
          4. 按计时器生成新障碍物
          5. 装饰效果（云朵、地面滚动）
          6. 碰撞检测
        """
        if self.game_over:
            return []

        self.last_collision = None
        spawned_obstacles: list[Obstacle] = []

        self.frame += 1
        self.score += 1
        # 速度随分数线性增长，但有上限
        self.speed = min(MAX_SPEED, INITIAL_SPEED + self.score * SPEED_ACCELERATION)

        # ── 1. 恐龙物理 ──
        # 经典抛物线运动: y(t) = y0 + v0*t + 0.5*g*t^2
        # 这里用逐帧欧拉积分近似
        if self.jumping:
            self.dino_y -= self.dino_vy     # vy 为负时向上 → y 增大
            self.dino_vy += GRAVITY          # 重力使 vy 逐渐变正（向下）
            if self.dino_y <= 0:             # 落回地面
                self.dino_y = 0
                self.dino_vy = 0
                self.jumping = False

        # ── 2. 移动障碍物（向左） ──
        for obs in self.obstacles:
            obs.x -= self.speed
        # 移出屏幕左侧的障碍物可以丢弃
        self.obstacles = [o for o in self.obstacles if o.x > -10]

        # ── 3. 生成新障碍物 ──
        if replay_obstacles is not None:
            for obstacle_data in replay_obstacles:
                obstacle = obstacle_from_action_data(obstacle_data)
                self.obstacles.append(obstacle)
                spawned_obstacles.append(obstacle)
        else:
            # spawn_timer 按速度递减，模拟「固定像素间距」
            self.spawn_timer -= self.speed
            if self.spawn_timer <= 0:
                obstacle = self._spawn_obstacle()
                spawned_obstacles.append(obstacle)
                self.spawn_timer = self.rng.randint(SPAWN_MIN, SPAWN_MAX)

        # ── 4. 装饰: 云朵 ──
        if self.rng.random() < 0.02:        # 2% 概率每帧生成一朵云
            self.clouds.append({
                "x": 82.0,
                "y": self.rng.randint(2, 8),  # 云在屏幕上方随机行
            })
        for c in self.clouds:
            c["x"] -= self.speed * 0.3      # 云移动速度 = 30% 障碍物速度（视差效果）
        self.clouds = [c for c in self.clouds if c["x"] > -8]

        # ── 5. 装饰: 地面滚动 ──
        self.ground_offset = (self.ground_offset + self.speed) % 4

        # ── 6. 碰撞检测 (AABB) ──
        # 碰撞箱故意比视觉精灵小一圈，让游戏更「公平」
        dino_h = 3 if self.ducking else 5   # 蹲下时碰撞箱更矮
        dino_left = DINO_COL + 2            # 左边缩进 2（头部空白区域）
        dino_right = DINO_COL + 7           # 右边也收窄
        dino_bottom = self.dino_y           # 底部 = 当前高度
        dino_top = self.dino_y + dino_h     # 顶部 = 高度 + 碰撞箱高度

        for obs in self.obstacles:
            for ol, oright, ob, ot in obs.hitboxes:
                # 两个矩形重叠的条件: 四个方向都有交集
                # 额外 ±1 容差让碰撞更宽容
                if (dino_right > ol + 1 and dino_left < oright - 1 and
                        dino_top > ob + 1 and dino_bottom < ot - 1):
                    self.last_collision = {
                        "frame": self.frame,
                        "dino_hitbox": [
                            round(dino_left, 2),
                            round(dino_right, 2),
                            round(dino_bottom, 2),
                            round(dino_top, 2),
                        ],
                        "obstacle": obstacle_debug_snapshot(obs),
                        "obstacle_hitbox": [
                            round(ol, 2),
                            round(oright, 2),
                            round(ob, 2),
                            round(ot, 2),
                        ],
                    }
                    self.game_over = True
                    self.high_score = max(self.high_score, self.score)
                    break
            if self.game_over:
                break

        return spawned_obstacles

    def _spawn_obstacle(self) -> Obstacle:
        """在屏幕右侧生成一个新障碍物

        障碍物种类随分数推进:
          - 0~200:   只有随机仙人掌组
          - 200~500: 加入鸟
          - 500+:    鸟出现更频繁
        """
        obstacle = random_obstacle_for_score(
            self.score,
            self.obstacle_spawn_x,
            self.rng,
        )
        self.obstacles.append(obstacle)
        return obstacle


# ═══════════════════════════════════════════════════════════════════════
# Agent 实现 — 两种策略
# ═══════════════════════════════════════════════════════════════════════

class RuleAgent:
    """基于距离阈值的反应式 Agent — 简单、快速、可靠

    策略原理:
      1. 找到前方最近的「需要跳过」的障碍物
      2. 计算一个「反应距离」= 7 + speed * 4
         - 7 是碰撞区起始距离（恐龙右边缘到障碍物左边缘的像素）
         - speed * 4 是提前量（速度越快越要早跳，留出 ~3 帧的起跳时间）
      3. 障碍物进入反应距离且恐龙在地面 → 跳！

    性能: 平均约 960 分（20 局测试），最好 1200+
    延迟: 微秒级（纯数学判断，无 I/O）
    """

    def decide(self, state: dict) -> str:
        """根据游戏状态返回动作

        Args:
            state: DinoGame.get_state() 的返回值

        Returns:
            "jump" / "duck" / "none"
        """
        if not state["obstacles"]:
            return "none"

        speed = state["speed"]
        on_ground = state["dino_y"] < 0.5 and not state["jumping"]

        # 反应窗口边界
        react_max = 2 + speed * 10   # 约提前 10 帧起跳，避免高点过早错过障碍
        react_min = -2              # 太近了也别跳（已经来不及了）

        # 依次检查前方障碍物（已按距离排序）
        for obs in state["obstacles"]:
            dist = obs["distance"]
            obstacle_react_max = react_max
            if obs["kind"] == "cactus_group" and obs["h"] <= 4:
                obstacle_react_max = 14 + speed * 2
            if dist > obstacle_react_max or dist < react_min:
                continue

            if obs["kind"] == "bird":
                # 中空鸟会撞到站立恐龙头部，蹲下躲避；高空鸟忽略
                if obs["height"] == 4:
                    return "duck"
                if obs["height"] >= 8:
                    continue

            # 低空鸟 或 任何仙人掌 — 必须跳！
            if on_ground:
                return "jump"

        return "none"


@dataclass(frozen=True)
class LLMConfig:
    """OpenAI-compatible LLM configuration."""

    api_key: str = ""
    base_url: str = DEFAULT_OPENAI_BASE_URL
    model: str = DEFAULT_OPENAI_MODEL

    def is_complete(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


@dataclass(frozen=True)
class CachedFrameCell:
    frame: int
    symbol: str
    status: str


@dataclass(frozen=True)
class CachedFrameWindow:
    current_frame: int
    cells: list[CachedFrameCell]


def config_file_path(home: str | None = None) -> str:
    """Return the fixed per-user config file path."""
    home_dir = home if home is not None else os.path.expanduser("~")
    return os.path.join(home_dir, ".config", CONFIG_DIR_NAME, CONFIG_FILE_NAME)


def load_llm_config(path: str | os.PathLike | None = None) -> LLMConfig:
    """Load LLM config from disk; missing or invalid files produce defaults."""
    config_path = os.fspath(path or config_file_path())
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return LLMConfig()
    if not isinstance(data, dict):
        return LLMConfig()
    return LLMConfig(
        api_key=str(data.get("api_key") or ""),
        base_url=str(data.get("base_url") or DEFAULT_OPENAI_BASE_URL),
        model=str(data.get("model") or DEFAULT_OPENAI_MODEL),
    )


def save_llm_config(config: LLMConfig, path: str | os.PathLike | None = None):
    """Persist LLM config as JSON."""
    config_path = os.fspath(path or config_file_path())
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    data = {
        "api_key": config.api_key,
        "base_url": config.base_url,
        "model": config.model,
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def reset_llm_config(path: str | os.PathLike | None = None) -> bool:
    """Delete the config file if it exists."""
    config_path = os.fspath(path or config_file_path())
    try:
        os.remove(config_path)
        return True
    except FileNotFoundError:
        return False


def mask_api_key(api_key: str) -> str:
    """Mask an API key for display."""
    if not api_key:
        return "(not set)"
    if len(api_key) <= 8:
        return f"{api_key[:2]}...{api_key[-2:]}"
    return f"{api_key[:4]}...{api_key[-4:]}"


def render_llm_config(config: LLMConfig, path: str | os.PathLike | None = None) -> str:
    """Render config for CLI display without leaking the full API key."""
    config_path = os.fspath(path or config_file_path())
    return "\n".join([
        f"path: {config_path}",
        f"api_key: {mask_api_key(config.api_key)}",
        f"base_url: {config.base_url or '(not set)'}",
        f"model: {config.model or '(not set)'}",
    ])


def prompt_for_llm_config(
        existing: LLMConfig | None = None,
        *,
        input_func=input,
        output_func=print,
        ask_persist: bool = False) -> tuple[LLMConfig, bool]:
    """Prompt for LLM settings and optionally ask whether to persist them."""
    existing = existing or LLMConfig()
    output_func("Configure OpenAI-compatible LLM settings.")

    api_key = input_func("API key: ").strip() or existing.api_key
    while not api_key:
        output_func("API key is required.")
        api_key = input_func("API key: ").strip()

    base_prompt = f"Base URL [{existing.base_url or DEFAULT_OPENAI_BASE_URL}]: "
    base_url = input_func(base_prompt).strip() or existing.base_url or DEFAULT_OPENAI_BASE_URL

    model_prompt = f"Model [{existing.model or DEFAULT_OPENAI_MODEL}]: "
    model = input_func(model_prompt).strip() or existing.model or DEFAULT_OPENAI_MODEL

    persist = False
    if ask_persist:
        answer = input_func("Save config to local file? [y/N]: ").strip().lower()
        persist = answer in {"y", "yes"}

    return LLMConfig(api_key=api_key, base_url=base_url, model=model), persist


def run_config_setup(
        *,
        config_path: str | os.PathLike | None = None,
        input_func=input,
        output_func=print) -> LLMConfig:
    """Interactive config setup that always writes to disk."""
    path = config_path or config_file_path()
    existing = load_llm_config(path)
    config, _ = prompt_for_llm_config(
        existing,
        input_func=input_func,
        output_func=output_func,
        ask_persist=False,
    )
    save_llm_config(config, path)
    output_func(f"Saved config to {path}")
    return config


def resolve_llm_config_for_run(
        *,
        config_path: str | os.PathLike | None = None,
        input_func=input,
        output_func=print) -> LLMConfig:
    """Load config for `dino llm`, prompting if required values are absent."""
    path = config_path or config_file_path()
    config = load_llm_config(path)
    if config.is_complete():
        return config

    config, persist = prompt_for_llm_config(
        config,
        input_func=input_func,
        output_func=output_func,
        ask_persist=True,
    )
    if persist:
        save_llm_config(config, path)
        output_func(f"Saved config to {path}")
    return config

# TODO: 要求 llm 返回 json 格式的数据，避免解析字符串
def extract_response_text(result: dict) -> str:
    """Extract text from common OpenAI Responses API response shapes."""
    output_text = result.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = result.get("output")
    if not isinstance(output, list):
        return ""
    parts = []
    for item in output:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n".join(parts)


def action_from_llm_text(text: str) -> str:
    """Map model text to a game action."""
    normalized = text.strip().lower()
    if "jump" in normalized:
        return "jump"
    if "duck" in normalized:
        return "duck"
    return "none"


def action_symbol(action: str) -> str:
    return ACTION_SYMBOLS.get(action, " ")


def cached_frame_window(
        planned_actions: dict[int, str],
        consumed_actions: dict[int, str],
        current_frame: int,
        radius: int = 12) -> CachedFrameWindow:
    cells = []
    for frame in range(current_frame - radius, current_frame + radius + 1):
        if frame < current_frame:
            action = consumed_actions.get(frame)
            status = "consumed" if action is not None else "missing"
        else:
            action = planned_actions.get(frame)
            if frame == current_frame:
                status = "current" if action is not None else "missing"
            else:
                status = "future" if action is not None else "missing"
        cells.append(CachedFrameCell(frame, action_symbol(action or ""), status))
    return CachedFrameWindow(current_frame=current_frame, cells=cells)


def parse_llm_action_window(
        text: str,
        requested_start_frame: int,
        expected_action_count: int | None = None) -> dict[int, str]:
    """Parse a model-returned JSON action window into frame-indexed actions."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("start_frame") != requested_start_frame:
        return {}
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return {}
    if expected_action_count is not None:
        actions = actions[:expected_action_count]
        actions = actions + ["none"] * (expected_action_count - len(actions))

    planned = {}
    for offset, action in enumerate(actions):
        if action not in VALID_ACTIONS:
            return {}
        planned[requested_start_frame + offset] = action
    return planned


def llm_action_window_text_format(start_frame: int, window_frames: int) -> dict:
    """Return the Responses API structured output format for action windows."""
    return {
        "type": "json_schema",
        "name": "dino_action_window",
        "description": "A fixed-length per-frame action plan for the dino game.",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "start_frame": {
                    "type": "integer",
                    "enum": [start_frame],
                },
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["jump", "duck", "none"],
                    },
                    "minItems": window_frames,
                    "maxItems": window_frames,
                },
            },
            "required": ["start_frame", "actions"],
            "additionalProperties": False,
        },
    }


def jump_physics_summary() -> tuple[int, float]:
    """Return the current jump airtime and peak height from game constants."""
    dino_y = 0.0
    dino_vy = JUMP_VELOCITY
    max_y = 0.0
    for frame in range(1, FPS * 2):
        dino_y -= dino_vy
        dino_vy += GRAVITY
        if dino_y <= 0 and frame > 1:
            return frame, max_y
        max_y = max(max_y, dino_y)
    return FPS * 2, max_y


def estimate_frames_until_horizontal_overlap(distance: float, speed: float) -> int:
    """Estimate frames until an obstacle reaches the dino collision band."""
    if distance <= LLM_HORIZONTAL_OVERLAP_DISTANCE:
        return 0
    target_distance = distance - LLM_HORIZONTAL_OVERLAP_DISTANCE
    travelled = 0.0
    for frames in range(1, LLM_ACTION_WINDOW_FRAMES * 2 + 1):
        frame_speed = min(MAX_SPEED, speed + SPEED_ACCELERATION * frames)
        travelled += frame_speed
        if travelled >= target_distance:
            return frames
    return math.ceil(target_distance / max(speed, 0.1))


def estimate_horizontal_clearance_frames(width: float, speed: float) -> int:
    """Estimate extra frames until the obstacle tail leaves the collision band."""
    trailing_width = max(0.0, width - 1.0)
    if trailing_width <= 0:
        return 0
    return math.ceil(trailing_width / max(speed, 0.1))


def obstacle_timing_estimate(
        obstacle: dict,
        speed: float,
        current_frame: int) -> dict:
    """Estimate overlap and clearance frames for one obstacle snapshot."""
    distance = float(obstacle.get("distance", 0.0))
    frames_until_overlap = estimate_frames_until_horizontal_overlap(distance, speed)
    overlap_frame = current_frame + frames_until_overlap
    overlap_speed = min(
        MAX_SPEED,
        speed + SPEED_ACCELERATION * frames_until_overlap,
    )
    raw_width = obstacle.get("width", 1.0)
    try:
        width = max(1.0, float(raw_width))
        width_text = f", width={width:g}"
    except (TypeError, ValueError):
        width = 1.0
        width_text = ""
    clearance_frames = estimate_horizontal_clearance_frames(width, overlap_speed)
    return {
        "distance": distance,
        "width": width,
        "width_text": width_text,
        "overlap_frame": overlap_frame,
        "clear_frame": overlap_frame + clearance_frames,
        "clearance_frames": clearance_frames,
    }


def llm_request_state_for_start_frame(
        state: dict,
        *,
        current_frame: int,
        start_frame: int) -> dict:
    """Drop obstacles that clear before the requested action window starts."""
    speed = float(state.get("speed", INITIAL_SPEED))
    filtered_obstacles = [
        obstacle
        for obstacle in (state.get("obstacles") or [])
        if obstacle_timing_estimate(
            obstacle,
            speed,
            current_frame,
        )["clear_frame"] >= start_frame
    ]
    request_state = dict(state)
    request_state["obstacles"] = filtered_obstacles
    return request_state


def llm_planning_guidance(state: dict, current_frame: int) -> str:
    """Build prompt guidance from local physics and obstacle timing estimates."""
    jump_frames, max_jump_height = jump_physics_summary()
    speed = float(state.get("speed", INITIAL_SPEED))
    lines = [
        "游戏物理设定:",
        (
            f"- 帧率 {FPS} FPS；一次 jump 约持续 {jump_frames} 帧，"
            f"最高高度约 {max_jump_height:.1f}。"
        ),
        "- jump 只有在地面且未 jumping 时生效；重复 jump 不会延长滞空。",
        (
            f"- 当前速度 {speed:.2f} 列/帧；速度每帧增加 "
            f"{SPEED_ACCELERATION:g}，最大速度 {MAX_SPEED:g}。"
        ),
        (
            f"- 水平碰撞通常在 distance <= "
            f"{LLM_HORIZONTAL_OVERLAP_DISTANCE:g} 左右开始，不是 distance=0。"
        ),
        (
            "- 宽障碍物会让水平重叠持续到 estimated_clear_frame；"
            "recommended_jump_window 会随 width 变大而后移，避免过早下落。"
        ),
        (
            "- 地面障碍或低空鸟不要过早起跳；推荐窗口大致覆盖 "
            f"estimated_clear_frame 前 {LLM_RECOMMENDED_JUMP_EARLY_FRAMES} 帧"
            f"到 estimated_overlap_frame 前 {LLM_RECOMMENDED_JUMP_LATE_FRAMES} 帧。"
        ),
        (
            "- 不要早于 recommended_jump_window 的起点起跳；"
            "优先选择 optimal_jump_frame。"
        ),
        "- 中空鸟 height=4 优先 duck；高空鸟 height=8 通常 none。",
        "推荐起跳窗口估算:",
    ]

    obstacles = state.get("obstacles") or []
    if not obstacles:
        lines.append("- 当前没有可见障碍物。")
        return "\n".join(lines)

    for index, obstacle in enumerate(obstacles, start=1):
        timing = obstacle_timing_estimate(obstacle, speed, current_frame)
        distance = timing["distance"]
        overlap_frame = timing["overlap_frame"]
        clear_frame = timing["clear_frame"]
        clearance_frames = timing["clearance_frames"]
        kind = obstacle.get("kind", "unknown")
        height = obstacle.get("height", 0)
        if kind == "bird" and height == 4:
            recommendation = "recommended_action=duck"
        elif kind == "bird" and height == 8:
            recommendation = "recommended_action=none"
        else:
            width_shift = clearance_frames
            if clearance_frames > 0:
                width_shift += 1
            jump_start = (
                overlap_frame
                - LLM_RECOMMENDED_JUMP_EARLY_FRAMES
                + width_shift
            )
            jump_end = overlap_frame - LLM_RECOMMENDED_JUMP_LATE_FRAMES
            if jump_start > jump_end:
                jump_start = jump_end
            optimal_jump_frame = (jump_start + jump_end) // 2
            recommendation = (
                f"estimated_clear_frame={clear_frame}, "
                f"recommended_jump_window={jump_start}-{jump_end}, "
                f"optimal_jump_frame={optimal_jump_frame}"
            )
        lines.append(
            f"- obstacle#{index}: kind={kind}, "
            f"distance={distance:g}{timing['width_text']}, "
            f"estimated_overlap_frame={overlap_frame}, {recommendation}"
        )
    return "\n".join(lines)


def llm_state_has_obstacles(state: dict) -> bool:
    """Return whether an LLM request state contains any obstacle information."""
    return bool(state.get("obstacles"))


def format_frame_ranges(frames: list[int]) -> str | None:
    """Return a compact frame range summary for display."""
    if not frames:
        return None
    ranges = []
    start = previous = frames[0]
    for frame in frames[1:]:
        if frame == previous + 1:
            previous = frame
            continue
        ranges.append((start, previous))
        start = previous = frame
    ranges.append((start, previous))
    return ", ".join(
        str(start) if start == end else f"{start}-{end}"
        for start, end in ranges
    )


class LLMAgent:
    """调用 OpenAI Responses API 的 LLM Agent，缓存未来逐帧动作。"""

    def __init__(
            self,
            config: LLMConfig | None = None,
            *,
            debug: bool = False,
            debug_path: str | os.PathLike | None = None):
        self.planned_actions: dict[int, str] = {}
        self.consumed_actions: dict[int, str] = {}
        self.requested_until_frame = 0
        self.request_in_flight = False
        self.requested_frame_ranges: list[tuple[int, int]] = []
        self.lock = threading.Lock()    # 线程安全锁
        self.config = config or load_llm_config()
        self.debug = debug
        self.debug_path = os.fspath(debug_path) if debug_path is not None else None
        if not self.config.is_complete():
            raise ValueError("LLM config requires api_key, base_url, and model")

    def set_debug_path(self, debug_path: str | os.PathLike | None):
        self.debug_path = os.fspath(debug_path) if debug_path is not None else None

    def _debug_log(self, event: str, **data):
        if not self.debug or not self.debug_path:
            return
        payload = {"event": event, **data}
        os.makedirs(os.path.dirname(self.debug_path), exist_ok=True)
        with open(self.debug_path, "a", encoding="utf-8") as f:
            print(json.dumps(payload, ensure_ascii=False), file=f, flush=True)

    def _call_llm(
            self,
            state: dict,
            *,
            start_frame: int,
            current_frame: int | None = None,
            window_frames: int = LLM_ACTION_WINDOW_FRAMES):
        """在后台线程中调用 OpenAI Responses API。"""
        if current_frame is None:
            current_frame = start_frame - 1
        try:
            import urllib.request

            state = llm_request_state_for_start_frame(
                state,
                current_frame=current_frame,
                start_frame=start_frame,
            )
            planning_guidance = llm_planning_guidance(state, current_frame)
            prompt = f"""你正在玩一个恐龙跑酷游戏。请根据当前状态规划未来 {window_frames} actions。

当前状态:
- 当前帧: {current_frame}
- 需要返回的第一帧 start_frame: {start_frame}
- start_frame 距当前状态还有 {start_frame - current_frame} 帧
- 恐龙高度: {state['dino_y']} (0=地面)
- 正在跳跃: {state['jumping']}
- 正在蹲下: {state['ducking']}
- 游戏速度: {state['speed']}
- 当前分数: {state['score']}
- 前方障碍物: {json.dumps(state['obstacles'], ensure_ascii=False)}

距离 distance 表示障碍物离恐龙的距离，越小越近。
障碍物每帧向恐龙靠近约 speed 列，因此 distance / speed 可估算还有多少帧相遇。
height 表示障碍物的高度(鸟)，0=低空，4=中空，8=高空。
当前恐龙状态由 dino_y、dino_vy、jumping、ducking 表示。

{planning_guidance}

你必须只返回 JSON，不要解释。格式:
{{"start_frame": {start_frame}, "actions": ["none", "jump"]}}

要求:
- start_frame 必须等于 {start_frame}
- actions 必须正好包含 {window_frames} actions
- 每个 action 只能是 jump / duck / none
- 每个 action 对应从 start_frame 开始的一帧
回答:"""

            data = json.dumps({
                "model": self.config.model,
                "input": prompt,
                "text": {
                    "format": llm_action_window_text_format(start_frame, window_frames),
                },
                # "max_output_tokens": max(200, window_frames * 8),
                "stream": False,
            }).encode()
            request_payload = json.loads(data.decode())
            self._debug_log(
                "llm_request",
                start_frame=start_frame,
                current_frame=current_frame,
                window_frames=window_frames,
                state=state,
                payload=request_payload,
            )

            req = urllib.request.Request(
                f"{self.config.base_url.rstrip('/')}/responses",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                response_text = extract_response_text(result)
                planned = parse_llm_action_window(
                    response_text,
                    requested_start_frame=start_frame,
                    expected_action_count=window_frames,
                )
                if not planned:
                    planned = self._fallback_actions(start_frame, window_frames)
                self._debug_log(
                    "llm_response",
                    start_frame=start_frame,
                    current_frame=current_frame,
                    window_frames=window_frames,
                    raw_response=result,
                    response_text=response_text,
                    planned_actions=planned,
                )

                with self.lock:
                    self.planned_actions.update(planned)
                    self.requested_until_frame = max(planned)

        except Exception as exc:
            with self.lock:
                planned = self._fallback_actions(start_frame, window_frames)
                self.planned_actions.update(planned)
                self.requested_until_frame = max(planned)
            self._debug_log(
                "llm_error",
                start_frame=start_frame,
                current_frame=current_frame,
                window_frames=window_frames,
                error=repr(exc),
                planned_actions=planned,
            )
        finally:
            with self.lock:
                self.request_in_flight = False

    def _fallback_actions(
            self,
            start_frame: int,
            window_frames: int = LLM_ACTION_WINDOW_FRAMES) -> dict[int, str]:
        return {
            start_frame + offset: "none"
            for offset in range(window_frames)
        }

    def _none_actions(self, start_frame: int, window_frames: int) -> dict[int, str]:
        return {
            start_frame + offset: "none"
            for offset in range(window_frames)
        }

    def needs_loading(self, frame: int) -> bool:
        with self.lock:
            return frame not in self.planned_actions

    def cached_frame_summary(self) -> str | None:
        with self.lock:
            frames = sorted(self.planned_actions)
        ranges = format_frame_ranges(frames)
        if ranges is None:
            return None
        return f"Cached frames: {ranges} ({len(frames)})"

    def cached_frame_window(self, current_frame: int, radius: int = 12) -> CachedFrameWindow | None:
        with self.lock:
            if not self.planned_actions and not self.consumed_actions:
                return None
            planned = dict(self.planned_actions)
            consumed = dict(self.consumed_actions)
        return cached_frame_window(planned, consumed, current_frame, radius)

    def reset_plan(self):
        with self.lock:
            self.planned_actions.clear()
            self.consumed_actions.clear()
            self.requested_until_frame = 0
            self.request_in_flight = False
            self.requested_frame_ranges.clear()

    def ensure_plan(self, state: dict, start_frame: int):
        with self.lock:
            if self.request_in_flight:
                return
            if self.requested_until_frame - start_frame >= LLM_PREFETCH_THRESHOLD_FRAMES:
                return
            request_start = (
                self.requested_until_frame + 1
                if self.requested_until_frame > 0
                else start_frame
            )
            request_end = request_start + LLM_ACTION_WINDOW_FRAMES - 1
            if not llm_state_has_obstacles(state):
                planned = self._none_actions(request_start, LLM_ACTION_WINDOW_FRAMES)
                self.planned_actions.update(planned)
                self.requested_until_frame = request_end
                self.requested_frame_ranges.append((request_start, request_end))
                self.request_in_flight = False
                return
            self.request_in_flight = True
            self.requested_frame_ranges.append((request_start, request_end))
        t = threading.Thread(
            target=self._call_llm,
            args=(state,),
            kwargs={
                "start_frame": request_start,
                "current_frame": start_frame - 1,
                "window_frames": LLM_ACTION_WINDOW_FRAMES,
            },
            daemon=True,
        )
        t.start()

    def decide(self, state: dict, frame: int | None = None) -> str:
        """返回当前帧已缓存动作，并预取后续动作窗口。"""
        if frame is None:
            frame = 1
        self.ensure_plan(state, frame + 1)

        with self.lock:
            action = self.planned_actions.pop(frame, "none")
            self.consumed_actions[frame] = action
            min_keep_frame = frame - LLM_ACTION_WINDOW_FRAMES
            for old_frame in list(self.planned_actions):
                if old_frame < min_keep_frame:
                    self.planned_actions.pop(old_frame, None)
            for old_frame in list(self.consumed_actions):
                if old_frame < min_keep_frame:
                    self.consumed_actions.pop(old_frame, None)

        return action


def cached_frames_text_for_agent(agent) -> str | None:
    if isinstance(agent, LLMAgent):
        return agent.cached_frame_summary()
    return None


def cached_frames_view_for_agent(agent, current_frame: int) -> CachedFrameWindow | None:
    if isinstance(agent, LLMAgent):
        return agent.cached_frame_window(current_frame)
    return None


def debug_log_llm_game_over(
        agent,
        game: DinoGame,
        *,
        frame: int,
        action: str):
    """Write a game-over diagnostic event to the LLM debug log."""
    if not isinstance(agent, LLMAgent):
        return
    agent._debug_log(
        "game_over",
        frame=frame,
        action=action,
        score=game.score,
        dino_y=round(game.dino_y, 2),
        dino_vy=round(game.dino_vy, 2),
        jumping=game.jumping,
        ducking=game.ducking,
        speed=round(game.speed, 3),
        collision=game.last_collision,
        obstacles=[
            obstacle_debug_snapshot(obstacle)
            for obstacle in game.obstacles
        ],
    )


# ═══════════════════════════════════════════════════════════════════════
# 手动输入状态
# ═══════════════════════════════════════════════════════════════════════

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


def load_replay_file(path) -> dict:
    """读取 replay JSON 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class CliArgs:
    """规范化后的命令行参数。"""

    command: str = "play"
    mode: str = "manual"
    record_path: str | None = None
    replay_path: str | None = None
    replay_action: str = "play"
    competition_path: str | None = None
    config_action: str = "show"
    llm_config: LLMConfig | None = None
    llm_debug: bool = False
    show_help: bool = False
    help_text: str | None = None
    version: str | None = None


COMMAND_GROUPS = [
    ("Core", [
        ("play", "Start a manual game"),
        ("agent", "Run with the local rule-based agent"),
        ("llm", "Run with the OpenAI LLM agent"),
    ]),
    ("Replay", [
        ("replay", "Play, inspect, or clear replay records"),
    ]),
    ("Competition", [
        ("compete", "Start competition mode from a replay"),
    ]),
    ("Config", [
        ("config", "View or update LLM configuration"),
    ]),
    ("Help", [
        ("help", "Show available commands and global options"),
    ]),
]

COMMAND_DESCRIPTIONS = {
    name: description
    for _, commands in COMMAND_GROUPS
    for name, description in commands
}
RUN_COMMAND_MODES = {
    "play": "manual",
    "agent": "agent",
    "llm": "llm",
}
HELP_FLAGS = {"--help", "-H"}
VERSION_FLAGS = {"--version", "-V"}


def tool_version() -> str:
    """返回安装包版本；源码运行时回退到本文件常量。"""
    try:
        return metadata.version("ai-dino-in-terminal")
    except metadata.PackageNotFoundError:
        return VERSION


def render_main_help() -> str:
    """渲染总 help，只展示子命令和公共参数。"""
    lines = [
        "Terminal Dino Runner",
        "",
        "Usage: dino <command> [options]",
        "Default: dino is equivalent to dino play",
        "",
        "Commands:",
    ]
    for group_name, commands in COMMAND_GROUPS:
        lines.append(f"  {group_name}")
        for name, description in commands:
            lines.append(f"    {name:<8} {description}")
        lines.append("")
    lines.extend([
        "Global options:",
        "  --help, -H       Show full usage and options for the current command",
        "  --version, -V    Show the tool version",
    ])
    return "\n".join(lines)


def render_command_help(command: str) -> str:
    """渲染某个子命令的完整用法和参数。"""
    if command == "play":
        usage = "dino play [--record FILE]"
        options = ["  --record FILE    Write the replay recording to FILE"]
    elif command == "agent":
        usage = "dino agent [--record FILE]"
        options = ["  --record FILE    Write the replay recording to FILE"]
    elif command == "llm":
        usage = "dino llm [--record FILE] [--debug]"
        options = [
            "  --record FILE    Write the replay recording to FILE",
            "  --debug          Write LLM request and response JSON lines to logs/",
        ]
    elif command == "replay":
        usage = "dino replay [FILE]"
        options = [
            "  FILE             Replay FILE directly; omit it to choose from a list",
            "  +list            List replay files and press Enter to inspect metadata",
            "  +clear           Delete all replay record files",
            "",
            "Examples:",
            "  dino replay +list",
            "  dino replay +clear",
        ]
    elif command == "compete":
        usage = "dino compete [FILE] [--record FILE]"
        options = [
            "  FILE             Start competition from FILE; omit it to choose from a list",
            "  --record FILE    Write the competition replay recording to FILE",
        ]
    elif command == "config":
        usage = "dino config [+setup|+reset]"
        options = [
            "  +setup           Prompt for LLM settings and save them locally",
            "  +reset           Remove the local LLM config file",
            "",
            "Examples:",
            "  dino config",
            "  dino config +setup",
            "  dino config +reset",
        ]
    elif command == "help":
        usage = "dino help [command]"
        options = ["  command          Show full usage and options for a command"]
    else:
        return render_main_help()

    lines = [
        f"Usage: {usage}",
        "",
        COMMAND_DESCRIPTIONS[command],
        "",
        "Options:",
        *options,
        "",
        "Global options:",
        "  --help, -H       Show full usage and options for the current command",
        "  --version, -V    Show the tool version",
    ]
    return "\n".join(lines)


def _split_record_option(args: list[str]) -> tuple[str | None, list[str]]:
    """从参数列表中取出 --record FILE，并返回剩余参数。"""
    record_path = None
    remaining = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--record":
            if index + 1 >= len(args) or args[index + 1].startswith("-"):
                raise ValueError("--record 需要一个文件路径")
            record_path = args[index + 1]
            index += 2
            continue
        remaining.append(arg)
        index += 1
    return record_path, remaining


def _split_debug_option(args: list[str]) -> tuple[bool, list[str]]:
    """从参数列表中取出 --debug，并返回剩余参数。"""
    debug = False
    remaining = []
    for arg in args:
        if arg == "--debug":
            debug = True
        else:
            remaining.append(arg)
    return debug, remaining


def parse_cli_args(args: list[str]) -> CliArgs:
    """解析新命令行接口；无法识别的子命令回退到总 help。"""
    args = list(args)
    if any(arg in VERSION_FLAGS for arg in args):
        return CliArgs(version=tool_version())
    if not args:
        return CliArgs()
    if args[0] in HELP_FLAGS:
        return CliArgs(show_help=True, help_text=render_main_help())
    if args[0] == "help":
        if len(args) > 1 and args[1] in COMMAND_DESCRIPTIONS:
            return CliArgs(show_help=True, help_text=render_command_help(args[1]))
        return CliArgs(show_help=True, help_text=render_main_help())
    if args[0] not in COMMAND_DESCRIPTIONS or args[0] == "help":
        return CliArgs(show_help=True, help_text=render_main_help())

    command = args[0]
    command_args = args[1:]
    if any(arg in HELP_FLAGS for arg in command_args):
        return CliArgs(command=command, show_help=True, help_text=render_command_help(command))

    if command in RUN_COMMAND_MODES:
        record_path, remaining = _split_record_option(command_args)
        llm_debug = False
        if command == "llm":
            llm_debug, remaining = _split_debug_option(remaining)
        if remaining:
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        return CliArgs(
            command=command,
            mode=RUN_COMMAND_MODES[command],
            record_path=record_path,
            llm_debug=llm_debug,
        )

    if command == "replay":
        if command_args == ["+list"]:
            return CliArgs(command=command, replay_action="list")
        if command_args == ["+clear"]:
            return CliArgs(command=command, replay_action="clear")
        if command_args and command_args[0].startswith("+"):
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        if len(command_args) > 1 or any(arg.startswith("-") for arg in command_args):
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        replay_path = command_args[0] if command_args else None
        return CliArgs(command=command, replay_path=replay_path)

    if command == "compete":
        record_path, remaining = _split_record_option(command_args)
        if len(remaining) > 1 or any(arg.startswith("-") for arg in remaining):
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        competition_path = remaining[0] if remaining else None
        return CliArgs(
            command=command,
            mode="competitive",
            record_path=record_path,
            competition_path=competition_path,
        )

    if command == "config":
        if not command_args:
            return CliArgs(command=command, config_action="show")
        if command_args == ["+setup"]:
            return CliArgs(command=command, config_action="setup")
        if command_args == ["+reset"]:
            return CliArgs(command=command, config_action="reset")
        return CliArgs(command=command, show_help=True, help_text=render_command_help(command))

    return CliArgs(show_help=True, help_text=render_main_help())


def game_mode_from_args(args: list[str]) -> str:
    """根据命令行参数返回运行模式名。"""
    return parse_cli_args(args).mode


def is_competition_mode(args: list[str]) -> bool:
    """判断命令行参数是否请求竞技模式。"""
    return parse_cli_args(args).command == "compete"


def competition_source_path(args: list[str]) -> str | None:
    """从竞技模式参数中读取源 replay 路径；缺省时由 UI 菜单选择。"""
    return parse_cli_args(args).competition_path


def default_replay_path(mode: str, seed: int | None = None, directory: str = REPLAY_DIR) -> str:
    """生成默认运行记录文件路径。"""
    if seed is None:
        seed = time.time_ns()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = str(seed)[-6:]
    return os.path.join(directory, f"{timestamp}-{mode}-{suffix}.json")


def record_path_for_run(
        record_path: str | None,
        mode: str,
        seed: int,
        run_index: int,
        directory: str = REPLAY_DIR) -> str:
    """返回某一局要写入的 replay 文件路径。"""
    if not record_path:
        return default_replay_path(mode, seed, directory)
    if run_index <= 1:
        return record_path
    root, ext = os.path.splitext(record_path)
    return f"{root}-{run_index}{ext or '.json'}"


def debug_log_path_for_replay(replay_path: str | os.PathLike, directory: str = "logs") -> str:
    """Return the debug log path that mirrors a replay filename under logs/."""
    return os.path.join(directory, os.path.basename(os.fspath(replay_path)))


def list_replay_files(directory: str = REPLAY_DIR) -> list[str]:
    """列出 replay JSON 文件，按最近修改时间倒序。"""
    if not os.path.isdir(directory):
        return []
    paths = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(".json") and os.path.isfile(os.path.join(directory, name))
    ]
    return sorted(paths, key=lambda path: os.path.getmtime(path), reverse=True)


def clear_replay_files(directory: str = REPLAY_DIR) -> int:
    """删除 replay 目录下的所有 JSON 记录文件，返回删除数量。"""
    removed = 0
    for path in list_replay_files(directory):
        os.remove(path)
        removed += 1
    return removed


def replay_created_at(path) -> float:
    """返回 replay 文件创建时间；不支持 birthtime 的平台退回 ctime。"""
    stat = os.stat(path)
    return getattr(stat, "st_birthtime", stat.st_ctime)


def replay_metadata(path) -> dict:
    """读取 replay 文件元信息，用于列表详情展示。"""
    path = os.fspath(path)
    data = load_replay_file(path)
    return {
        "path": path,
        "mode": data.get("mode", "unknown"),
        "frames": data.get("frames", 0),
        "created_at": replay_created_at(path),
        "competitive": bool(data.get("competitive", False)),
        "source_replay": data.get("source_replay") or "-",
    }


def render_replay_metadata(metadata: dict) -> str:
    """把 replay 元信息渲染成多行文本。"""
    created_at = time.strftime(
        "%Y-%m-%d %H:%M:%S",
        time.localtime(metadata["created_at"]),
    )
    competitive = "是" if metadata["competitive"] else "否"
    return "\n".join([
        f"文件: {os.path.basename(metadata['path'])}",
        f"模式: {metadata['mode']}",
        f"帧数: {metadata['frames']}",
        f"创建时间: {created_at}",
        f"是否竞技模式: {competitive}",
        f"竞技模式源记录: {metadata['source_replay']}",
    ])


def move_replay_selection(index: int, key: int, count: int) -> int:
    """根据上下方向键移动 replay 菜单光标。"""
    if count <= 0:
        return 0
    if key == curses.KEY_UP:
        return (index - 1) % count
    if key == curses.KEY_DOWN:
        return (index + 1) % count
    return index


def select_replay_file(stdscr, paths: list[str]) -> str | None:
    """在 curses 中列出运行记录，让用户选择要重放的文件。"""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(False)
    index = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        title = "选择要重放的运行记录"
        try:
            stdscr.addstr(1, 2, title, curses.A_BOLD)
        except curses.error:
            pass

        if not paths:
            msg = f"没有找到运行记录目录 {REPLAY_DIR}/ 下的 .json 文件"
            hint = "按 Enter / Q 返回"
            for y, text in ((3, msg), (5, hint)):
                try:
                    stdscr.addstr(y, 2, text[:max(0, w - 4)])
                except curses.error:
                    pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (10, 13, ord("q"), ord("Q"), 27):
                return None
            continue

        visible_rows = max(1, h - 5)
        start = min(max(0, index - visible_rows + 1), max(0, len(paths) - visible_rows))
        for row, path in enumerate(paths[start:start + visible_rows]):
            item_index = start + row
            basename = os.path.basename(path)
            mtime = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(os.path.getmtime(path)),
            )
            marker = "> " if item_index == index else "  "
            text = f"{marker}{basename}  {mtime}"
            attr = curses.A_REVERSE if item_index == index else curses.A_NORMAL
            try:
                stdscr.addstr(3 + row, 2, text[:max(0, w - 4)], attr)
            except curses.error:
                pass

        hint = "↑/↓ 选择 | Enter 回放 | Q 退出"
        try:
            stdscr.addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13):
            return paths[index]
        if key in (ord("q"), ord("Q"), 27):
            return None
        index = move_replay_selection(index, key, len(paths))


def show_replay_metadata(stdscr, path: str):
    """展示选中 replay 文件的元信息。"""
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(1, 2, "Replay 元信息", curses.A_BOLD)
        except curses.error:
            pass

        try:
            lines = render_replay_metadata(replay_metadata(path)).splitlines()
        except (OSError, json.JSONDecodeError) as exc:
            lines = [f"无法读取 replay 文件: {exc}"]

        for row, text in enumerate(lines):
            if row + 3 >= h - 1:
                break
            try:
                stdscr.addstr(row + 3, 2, text[:max(0, w - 4)])
            except curses.error:
                pass

        hint = "Enter / Q 返回列表"
        try:
            stdscr.addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13, ord("q"), ord("Q"), 27):
            return


def browse_replay_files(stdscr, paths: list[str]):
    """在 curses 中浏览 replay 文件，回车查看选中文件元信息。"""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(False)
    index = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(1, 2, "Replay 记录列表", curses.A_BOLD)
        except curses.error:
            pass

        if not paths:
            msg = f"没有找到运行记录目录 {REPLAY_DIR}/ 下的 .json 文件"
            hint = "按 Enter / Q 返回"
            for y, text in ((3, msg), (5, hint)):
                try:
                    stdscr.addstr(y, 2, text[:max(0, w - 4)])
                except curses.error:
                    pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (10, 13, ord("q"), ord("Q"), 27):
                return
            continue

        visible_rows = max(1, h - 5)
        start = min(max(0, index - visible_rows + 1), max(0, len(paths) - visible_rows))
        for row, path in enumerate(paths[start:start + visible_rows]):
            item_index = start + row
            basename = os.path.basename(path)
            mtime = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(os.path.getmtime(path)),
            )
            marker = "> " if item_index == index else "  "
            text = f"{marker}{basename}  {mtime}"
            attr = curses.A_REVERSE if item_index == index else curses.A_NORMAL
            try:
                stdscr.addstr(3 + row, 2, text[:max(0, w - 4)], attr)
            except curses.error:
                pass

        hint = "↑/↓ 选择 | Enter 查看元信息 | Q 退出"
        try:
            stdscr.addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13):
            show_replay_metadata(stdscr, paths[index])
            continue
        if key in (ord("q"), ord("Q"), 27):
            return
        index = move_replay_selection(index, key, len(paths))


def obstacle_to_action_data(obstacle: Obstacle) -> dict:
    """把障碍物转换成 replay 记录中的 action 数据。"""
    data = {
        "kind": obstacle.kind,
        "x": float(obstacle.x),
        "height": obstacle.height,
    }
    if obstacle.kind == "cactus_group":
        data["plants"] = list(obstacle.plants or ())
    return data


def obstacle_from_action_data(data: dict) -> Obstacle:
    """从 replay 记录中的 action 数据还原障碍物。"""
    plants = data.get("plants")
    if plants is not None:
        plants = tuple(plants)
    return Obstacle(
        data["kind"],
        data.get("x", 82),
        data.get("height", 0),
        plants=plants,
    )


class ReplayRecorder:
    """把一局游戏的随机种子、逐帧动作和障碍物事件写入文件。"""

    def __init__(
            self,
            path,
            seed: int,
            mode: str = "manual",
            competitive: bool = False,
            source_replay: str | None = None):
        self.path = path
        self.seed = seed
        self.mode = mode
        self.competitive = competitive
        self.source_replay = source_replay
        self.actions: list[dict] = []
        self.obstacles: list[dict] = []
        self.frames = 0
        self.input_count = 0
        self.saved = False

    def record(self, action: str):
        self.record_action(self.input_count + 1, action)

    def record_action(self, frame: int, action: str):
        self.input_count += 1
        self.frames = max(self.frames, frame)
        if action == "none":
            return
        self.actions.append({
            "frame": frame,
            "action": {
                "value": action,
            },
        })

    def record_obstacle(self, frame: int, obstacle: Obstacle):
        self.frames = max(self.frames, frame)
        self.obstacles.append({
            "frame": frame,
            "action": obstacle_to_action_data(obstacle),
        })

    def save(self):
        if self.saved:
            return
        data = {
            "version": 3,
            "seed": self.seed,
            "mode": self.mode,
            "frames": self.frames,
            "actions": self.actions,
            "obstacles": self.obstacles,
        }
        if self.competitive:
            data["competitive"] = True
            data["source_replay"] = self.source_replay
        directory = os.path.dirname(os.fspath(self.path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.saved = True


class ReplayPlayer:
    """按 replay 文件逐帧吐出动作和障碍物。"""

    def __init__(
            self,
            seed: int,
            actions: list[dict],
            obstacles: list[dict],
            mode: str = "manual",
            frames: int | None = None):
        self.seed = seed
        self.mode = mode
        self.action_events = actions
        self.obstacle_events = obstacles
        self.actions = [
            event.get("action", {}).get("value", event.get("action"))
            for event in actions
        ]
        self.actions_by_frame = {
            event["frame"]: event.get("action", {}).get("value", event.get("action"))
            for event in actions
        }
        self.obstacles_by_frame: dict[int, list[dict]] = {}
        for event in obstacles:
            self.obstacles_by_frame.setdefault(event["frame"], []).append(event["action"])
        last_action_frame = max((event["frame"] for event in actions), default=0)
        last_obstacle_frame = max((event["frame"] for event in obstacles), default=0)
        self.max_frame = max(frames or 0, last_action_frame, last_obstacle_frame)
        self.index = 0

    @classmethod
    def from_file(cls, path):
        data = load_replay_file(path)
        actions = data.get("actions")
        obstacles = data.get("obstacles", [])
        frames = data.get("frames")

        if data.get("events") is not None:
            actions = []
            obstacles = []
            for event in data["events"]:
                action = event.get("action", {})
                if action.get("type") == "input":
                    if action.get("value") != "none":
                        actions.append({
                            "frame": event["frame"],
                            "action": {"value": action.get("value", "none")},
                        })
                elif action.get("type") == "obstacle":
                    obstacle_action = dict(action)
                    obstacle_action.pop("type", None)
                    obstacles.append({
                        "frame": event["frame"],
                        "action": obstacle_action,
                    })
            frames = frames if frames is not None else max(
                (event["frame"] for event in data["events"]),
                default=0,
            )
        elif actions and all(isinstance(action, str) for action in actions):
            actions = [
                {
                    "frame": index + 1,
                    "action": {
                        "value": action,
                    },
                }
                for index, action in enumerate(actions)
                if action != "none"
            ]
            frames = frames if frames is not None else len(data.get("actions", []))

        return cls(
            seed=data["seed"],
            actions=list(actions or []),
            obstacles=list(obstacles or []),
            mode=data.get("mode", "manual"),
            frames=frames,
        )

    def action_for_frame(self, frame: int) -> str:
        return self.actions_by_frame.get(frame, "none")

    def obstacles_for_frame(self, frame: int) -> list[dict]:
        return list(self.obstacles_by_frame.get(frame, []))

    def has_frame(self, frame: int) -> bool:
        return frame <= self.max_frame

    def next_action(self) -> str | None:
        if self.index >= len(self.actions):
            return None
        action = self.actions[self.index]
        self.index += 1
        return action


class CompetitionRun:
    """协调竞技模式中的历史赛道和玩家赛道。"""

    def __init__(
            self,
            replay_player: ReplayPlayer,
            source_replay: str,
            record_path):
        self.replay_player = replay_player
        self.source_replay = os.fspath(source_replay)
        self.history_game = DinoGame(rng=random.Random(replay_player.seed))
        self.player_game = DinoGame(rng=random.Random(replay_player.seed))
        self.recorder = ReplayRecorder(
            record_path,
            seed=replay_player.seed,
            mode="competitive",
            competitive=True,
            source_replay=self.source_replay,
        )
        self.frame = 0
        self.history_finished = replay_player.max_frame <= 0
        self.player_finished = False

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
            finish_recording(self.recorder)


def apply_game_action(game: DinoGame, action: str):
    """执行 replay/agent/manual 统一动作。"""
    if action == "jump":
        game.jump()
        game.duck(False)
    elif action == "duck":
        game.duck(True)
    else:
        game.duck(False)


def run_replay_simulation(seed: int, actions: list[str]) -> dict:
    """无 UI 重放，用于测试 replay 是否确定性。"""
    game = DinoGame(rng=random.Random(seed))
    for action in actions:
        if game.game_over:
            if action == "reset":
                game.reset()
            continue
        apply_game_action(game, action)
        game.update()
    return {
        "score": game.score,
        "game_over": game.game_over,
        "state": game.get_state(),
    }


def arg_value(args: list[str], flag: str) -> str | None:
    """从命令行参数中读取形如 `--flag path` 的值。"""
    if flag not in args:
        return None
    index = args.index(flag)
    if index + 1 >= len(args):
        raise ValueError(f"{flag} 需要一个文件路径")
    return args[index + 1]


def start_recording_run(
        mode: str,
        record_path: str | None,
        run_index: int,
        directory: str = REPLAY_DIR,
        seed: int | None = None) -> tuple[DinoGame, ReplayRecorder]:
    """启动一局新游戏，并为这一局创建独立 replay recorder。"""
    if seed is None:
        seed = time.time_ns()
    game = DinoGame(
        rng=random.Random(seed),
        obstacle_spawn_x=NORMAL_OBSTACLE_SPAWN_X,
    )
    path = record_path_for_run(record_path, mode, seed, run_index, directory)
    return game, ReplayRecorder(path, seed, mode=mode)


def finish_recording(recorder: ReplayRecorder | None):
    """Game Over 时保存当前局；重复调用不会重复写。"""
    if recorder:
        recorder.save()


def footer_hint(agent_name: str, speed: float) -> str:
    """根据当前模式返回底部操作提示。"""
    if agent_name == "Competition":
        return f"SPACE/↑ 跳跃 | ↓ 蹲下 | Enter 暂停 | Q 退出 | 竞技 | 速度 {speed:.1f}x"
    if agent_name == "Replay":
        return f"Enter 暂停 | Q 退出 | 回放 | 速度 {speed:.1f}x"
    if agent_name:
        return f"Enter 暂停 | Q 退出 | 速度 {speed:.1f}x"
    return "SPACE/↑ 跳跃 | ↓ 蹲下 | Enter 暂停 | Q 退出"


def loading_dino_blinks(animation_time: float) -> bool:
    return int(animation_time / LOADING_DINO_ANIM_INTERVAL) % 2 == 1


def dino_art_for_state(
        game: DinoGame,
        loading: bool = False,
        animation_time: float = 0.0) -> list[str]:
    """Select visual dino art without affecting physics or collision boxes."""
    if loading:
        blink = loading_dino_blinks(animation_time)
        if game.ducking:
            return DINO_LOADING_DUCK if blink else DINO_LOADING_DUCK_OPEN
        if game.jumping:
            return DINO_LOADING_JUMP if blink else DINO_LOADING_JUMP_OPEN
        return DINO_LOADING_STAND_BLINK if blink else DINO_LOADING_STAND
    if game.ducking:
        return DINO_DUCK
    if game.jumping:
        return DINO_JUMP
    if (game.frame // RUN_ANIM_FRAME_INTERVAL) % 2 == 0:
        return DINO_RUN_1
    return DINO_RUN_2


# ═══════════════════════════════════════════════════════════════════════
# 渲染器 — 把游戏状态画到终端
# ═══════════════════════════════════════════════════════════════════════

class Renderer:
    """curses 终端渲染器

    坐标映射:
      游戏世界 Y 轴（向上为正）→ 终端行号（向下递增）
      转换公式: screen_row = ground_row - art_height - game_y

    颜色方案 (curses color pair):
      1 = 绿色  → 恐龙
      2 = 红色  → 障碍物
      3 = 黄色  → 分数、Game Over
      4 = 青色  → 标题、云朵
      5 = 白色  → 地面
      6 = 紫色  → Agent 标签和思考可视化
    """

    def __init__(self, stdscr):
        self.scr = stdscr
        curses.curs_set(0)              # 隐藏光标
        stdscr.nodelay(True)            # getch() 非阻塞
        stdscr.timeout(FRAME_MS)        # getch() 超时 = 帧间隔

        curses.start_color()
        curses.use_default_colors()     # 使用终端默认背景色
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)

    def safe_addstr(self, y: int, x: int, text: str, attr: int = 0):
        """安全地向屏幕写字符串 — 自动裁剪越界部分

        curses 在写到屏幕右下角时会抛异常，这个方法处理所有边界情况。
        """
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x >= w:
            return
        if x < 0:
            text = text[-x:]        # 左边被裁掉的部分
            x = 0
        if x + len(text) >= w:
            text = text[:w - x - 1] # 右边裁剪
        if text:
            try:
                self.scr.addstr(y, x, text, attr)
            except curses.error:
                pass                 # 忽略右下角写入异常

    def draw_competition_lane(
            self,
            game: DinoGame,
            label: str,
            ground_row: int,
            dino_color_pair: int,
            status: str):
        """绘制竞技模式中的单条赛道。"""
        h, w = self.scr.getmaxyx()
        header_y = max(0, ground_row - 8)
        self.safe_addstr(
            header_y,
            2,
            f" {label} ",
            curses.A_BOLD | curses.color_pair(dino_color_pair),
        )
        score_text = f"{status}  {game.score:05d}"
        self.safe_addstr(
            header_y,
            max(2, w - len(score_text) - 2),
            score_text,
            curses.A_BOLD | curses.color_pair(3),
        )

        if game.ducking:
            art = DINO_DUCK
        elif game.jumping:
            art = DINO_JUMP
        elif (game.frame // RUN_ANIM_FRAME_INTERVAL) % 2 == 0:
            art = DINO_RUN_1
        else:
            art = DINO_RUN_2

        dino_screen_y = ground_row - len(art) - int(game.dino_y)
        for i, line in enumerate(art):
            self.safe_addstr(
                dino_screen_y + i,
                DINO_COL,
                line,
                curses.color_pair(dino_color_pair) | curses.A_BOLD,
            )

        for obs in game.obstacles:
            ox = int(obs.x)
            if obs.kind == "bird":
                if (game.frame // BIRD_ANIM_FRAME_INTERVAL) % 2 == 0:
                    obs_art = BIRD_1
                else:
                    obs_art = BIRD_2
            else:
                obs_art = obs.art

            obs_screen_y = ground_row - len(obs_art) - obs.height
            for i, line in enumerate(obs_art):
                self.safe_addstr(
                    obs_screen_y + i,
                    ox,
                    line,
                    curses.color_pair(2) | curses.A_BOLD,
                )

        ground = ""
        offset = int(game.ground_offset)
        pattern = "▁▁▁▁▂▁▁▁▂▁▁▁▁▁▂▁▁▁"
        while len(ground) < w:
            ground += pattern
        ground = ground[offset:offset + w - 1]
        self.safe_addstr(ground_row, 0, ground, curses.color_pair(5) | curses.A_DIM)

        if game.game_over:
            self.safe_addstr(
                max(header_y + 1, ground_row - 7),
                2,
                f"GAME OVER  Score: {game.score:05d}",
                curses.A_BOLD | curses.color_pair(3),
            )

    def draw_competition(self, competition: CompetitionRun):
        """绘制竞技模式的双赛道画面。"""
        self.scr.erase()
        h, w = self.scr.getmaxyx()

        title = " DINO RUNNER [竞技模式] "
        self.safe_addstr(0, 2, title, curses.A_BOLD | curses.color_pair(1))

        top_ground = max(8, min(10, h // 2 - 2))
        bottom_ground = min(h - 3, max(top_ground + 8, h - 3))
        separator_y = min(h - 2, max(top_ground + 1, (top_ground + bottom_ground) // 2))
        self.safe_addstr(separator_y, 0, "─" * max(0, w - 1), curses.A_DIM)

        history_status = "撞毁" if competition.history_game.game_over else "结束"
        if not competition.history_finished:
            history_status = "回放"
        player_status = "撞毁" if competition.player_game.game_over else "操作"
        if competition.player_finished and not competition.player_game.game_over:
            player_status = "结束"

        self.draw_competition_lane(
            competition.history_game,
            "历史赛道",
            top_ground,
            6,
            history_status,
        )
        self.draw_competition_lane(
            competition.player_game,
            "玩家赛道",
            bottom_ground,
            1,
            player_status,
        )

        if competition.finished:
            msg = "竞技结束  Q = 退出"
            self.safe_addstr(
                max(1, h // 2),
                max(0, w // 2 - len(msg) // 2),
                msg,
                curses.A_BOLD | curses.color_pair(3),
            )

        hint = footer_hint("Competition", competition.player_game.speed)
        self.safe_addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        self.scr.refresh()

    def draw_center_overlay(self, lines: list[str], color_pair: int = 3):
        """在屏幕中央绘制多行提示。"""
        if not lines:
            return
        h, w = self.scr.getmaxyx()
        mid_y = h // 2 - len(lines) // 2
        for index, line in enumerate(lines):
            x = max(0, w // 2 - len(line) // 2)
            self.safe_addstr(
                mid_y + index,
                x,
                line,
                curses.A_BOLD | curses.color_pair(color_pair),
            )

    def draw_pause_overlay(self, pause_state: PauseState, now: float):
        """绘制暂停或恢复倒计时提示。"""
        self.draw_center_overlay(pause_overlay_lines(pause_state, now), color_pair=3)

    def draw_cached_frame_window(self, y: int, x: int, window: CachedFrameWindow):
        """Draw cached LLM action frames as a colored sliding window."""
        segments: list[tuple[str, int]] = [
            (
                f"Frame {window.current_frame:>5}  ",
                curses.color_pair(6) | curses.A_DIM,
            )
        ]
        for cell in window.cells:
            text = f"{cell.symbol}"
            if cell.status == "current":
                attr = curses.color_pair(3) | curses.A_BOLD
                text = f"[{text}]"
            elif cell.status == "consumed":
                attr = curses.color_pair(5) | curses.A_DIM
                text = f" {text} "
            elif cell.status == "future":
                attr = curses.color_pair(6) | curses.A_BOLD
                text = f" {text} "
            else:
                attr = curses.A_DIM
                text = " · "
            segments.append((text, attr))

        cursor = x
        for text, attr in segments:
            self.safe_addstr(y, cursor, text, attr)
            cursor += len(text)

    def draw(
            self,
            game: DinoGame,
            agent_name: str,
            pause_state: PauseState | None = None,
            now: float | None = None,
            loading_text: str | None = None,
            cached_frames_text: str | None = None,
            cached_frames_view: CachedFrameWindow | None = None):
        """绘制完整的一帧画面

        绘制顺序（从后到前）:
          1. 标题栏和分数
          2. 云朵（背景层）
          3. 恐龙（主角）
          4. 障碍物
          5. 地面
          6. Agent 思考可视化
          7. Game Over 弹窗（如果死了）
          8. 底部操作提示
        """
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        ground_row = min(GROUND_ROW, h - 5)  # 终端太小时自动上移

        # ── 标题栏 ──
        title = " DINO RUNNER "
        self.safe_addstr(0, 2, title, curses.A_BOLD | curses.color_pair(1))

        if agent_name:
            tag = f" [{agent_name}] "
            self.safe_addstr(0, 2 + len(title) + 1, tag,
                             curses.A_BOLD | curses.color_pair(6))

        # 右上角显示最高分和当前分
        score_text = f"HI {game.high_score:05d}  {game.score:05d}"
        self.safe_addstr(0, w - len(score_text) - 2, score_text,
                         curses.A_BOLD | curses.color_pair(3))

        # ── 云朵（装饰） ──
        for c in game.clouds:
            cx = int(c["x"])
            cy = c["y"]
            for i, line in enumerate(CLOUD):
                self.safe_addstr(cy + i, cx, line, curses.color_pair(4) | curses.A_DIM)

        # ── 恐龙 ──
        # 根据状态选择动画帧
        loading_dino = bool(loading_text and not (pause_state and pause_state.status != "running"))
        animation_time = now if now is not None else time.monotonic()
        art = dino_art_for_state(
            game,
            loading=loading_dino,
            animation_time=animation_time,
        )

        # 游戏 Y 坐标 → 屏幕行号
        dino_screen_y = ground_row - len(art) - int(game.dino_y)
        color = curses.color_pair(1) | curses.A_BOLD
        for i, line in enumerate(art):
            self.safe_addstr(dino_screen_y + i, DINO_COL, line, color)

        # ── 障碍物 ──
        for obs in game.obstacles:
            ox = int(obs.x)
            if obs.kind == "bird":
                if (game.frame // BIRD_ANIM_FRAME_INTERVAL) % 2 == 0:
                    art = BIRD_1
                else:
                    art = BIRD_2
            else:
                art = obs.art

            obs_screen_y = ground_row - len(art) - obs.height
            for i, line in enumerate(art):
                self.safe_addstr(obs_screen_y + i, ox, line,
                                 curses.color_pair(2) | curses.A_BOLD)

        # ── 地面（滚动纹理） ──
        gnd = ""
        offset = int(game.ground_offset)
        pattern = "▁▁▁▁▂▁▁▁▂▁▁▁▁▁▂▁▁▁"
        while len(gnd) < w:
            gnd += pattern
        gnd = gnd[offset:offset + w - 1]
        self.safe_addstr(ground_row, 0, gnd, curses.color_pair(5) | curses.A_DIM)

        # ── Agent 思考可视化 ──
        # 在地面下方显示 Agent 当前「看到」的信息
        if agent_name:
            state = game.get_state()
            if state["obstacles"]:
                obs = state["obstacles"][0]
                thought = f"[dist={obs['distance']:.0f} spd={state['speed']:.1f}]"
                self.safe_addstr(ground_row + 2, 2, thought,
                                 curses.color_pair(6) | curses.A_DIM)

        # ── Game Over 弹窗 ──
        if game.game_over:
            msgs = [
                "╔══════════════════════════╗",
                "║      G A M E  O V E R   ║",
                f"║      Score: {game.score:>5d}       ║",
                "║                          ║",
                "║   R = 重来   Q = 退出    ║",
                "╚══════════════════════════╝",
            ]
            mid_y = h // 2 - len(msgs) // 2
            mid_x = w // 2 - len(msgs[0]) // 2
            for i, line in enumerate(msgs):
                self.safe_addstr(mid_y + i, mid_x, line,
                                 curses.A_BOLD | curses.color_pair(3))

        if pause_state and pause_state.status != "running":
            self.draw_pause_overlay(pause_state, now if now is not None else time.monotonic())
        elif loading_text:
            self.draw_center_overlay([loading_text], color_pair=6)

        # ── 底部操作提示 ──
        if cached_frames_view:
            self.draw_cached_frame_window(h - 2, 2, cached_frames_view)
        elif cached_frames_text:
            self.safe_addstr(h - 2, 2, cached_frames_text, curses.color_pair(6) | curses.A_DIM)

        hint = footer_hint(agent_name, game.speed)
        self.safe_addstr(h - 1, 2, hint, curses.A_DIM)

        self.scr.refresh()


# ═══════════════════════════════════════════════════════════════════════
# 主循环 — 把游戏引擎、渲染器、Agent 串起来
# ═══════════════════════════════════════════════════════════════════════

def manual_action_from_key(input_state: ManualInputState, key: int) -> str:
    """把当前键盘输入转换为手动玩家动作，不直接修改游戏状态。"""
    if key == ord(' ') or key == curses.KEY_UP:
        input_state.should_duck(key)
        return "jump"
    ducking = input_state.should_duck(key)
    return "duck" if ducking else "none"


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


def main(stdscr, cli_args: CliArgs | None = None):
    """游戏主循环

    每帧的执行顺序:
      1. 读取键盘输入 (curses.getch)
      2. 处理全局按键 (Q)
      3. 如果 Game Over → 等待重启
      4. Agent 决策 或 人类输入
      5. game.update() 推进一帧
      6. renderer.draw() 渲染画面
      7. 等待下一帧 (由 curses.timeout 控制)
    """
    cli_args = cli_args or parse_cli_args(sys.argv[1:])
    if cli_args.command == "replay" and cli_args.replay_action == "list":
        browse_replay_files(stdscr, list_replay_files())
        return

    competition_mode = cli_args.command == "compete"
    competition_path = cli_args.competition_path
    if competition_mode and not competition_path:
        competition_path = select_replay_file(stdscr, list_replay_files())
        if not competition_path:
            return

    replay_path = cli_args.replay_path
    if cli_args.command == "replay" and not replay_path:
        replay_path = select_replay_file(stdscr, list_replay_files())
        if not replay_path:
            return

    renderer = Renderer(stdscr)
    record_path = cli_args.record_path

    if competition_mode:
        replay_player = ReplayPlayer.from_file(competition_path)
        competition_record_path = (
            record_path
            or default_replay_path("competitive", replay_player.seed)
        )
        competition = CompetitionRun(
            replay_player,
            source_replay=competition_path,
            record_path=competition_record_path,
        )
        run_competition_loop(stdscr, renderer, competition)
        return

    replay_player = ReplayPlayer.from_file(replay_path) if replay_path else None
    mode = cli_args.mode
    run_index = 1
    if replay_player:
        game = DinoGame(rng=random.Random(replay_player.seed))
        recorder = None
    else:
        game, recorder = start_recording_run(mode, record_path, run_index)

    manual_input = ManualInputState()
    pause_state = PauseState()
    event_frame = 0

    # 根据命令行参数选择 Agent 模式
    agent = None
    agent_name = ""

    if replay_player:
        agent_name = "Replay"
    elif cli_args.mode == "llm":
        try:
            debug_path = (
                debug_log_path_for_replay(recorder.path)
                if cli_args.llm_debug and recorder
                else None
            )
            agent = LLMAgent(
                cli_args.llm_config,
                debug=cli_args.llm_debug,
                debug_path=debug_path,
            )
            agent_name = "LLM Agent (OpenAI)"
        except ValueError:
            # TODO: 没有 API key 时，给出提示 + 终止执行
            # 没有 API key，降级到规则 Agent
            agent = RuleAgent()
            agent_name = "Rule Agent (LLM config unavailable)"
    elif cli_args.mode == "agent":
        agent = RuleAgent()
        agent_name = "Rule Agent"

    try:
        while True:
            key = stdscr.getch()    # 非阻塞，超时返回 -1

            # ── 全局按键 ──
            if key == ord('q') or key == ord('Q'):
                break
            now = time.monotonic()
            pause_state = next_pause_state(pause_state, key, now)

            # ── Game Over 状态 ──
            if game.game_over:
                if replay_player:
                    event_frame += 1
                    if not replay_player.has_frame(event_frame):
                        renderer.draw(game, agent_name)
                        continue
                    action = replay_player.action_for_frame(event_frame)
                    if action == "reset":
                        game.reset()
                    renderer.draw(
                        game,
                        agent_name,
                        cached_frames_view=cached_frames_view_for_agent(agent, event_frame + 1),
                    )
                    continue

                if should_reset_after_game_over(key, agent_active=bool(agent)):
                    run_index += 1
                    game, recorder = start_recording_run(mode, record_path, run_index)
                    manual_input = ManualInputState()
                    pause_state = PauseState()
                    event_frame = 0
                    if isinstance(agent, LLMAgent):
                        agent.reset_plan()
                        if cli_args.llm_debug and recorder:
                            agent.set_debug_path(debug_log_path_for_replay(recorder.path))
                renderer.draw(
                    game,
                    agent_name,
                    cached_frames_view=cached_frames_view_for_agent(agent, event_frame + 1),
                )
                continue

            if pause_state.status != "running":
                renderer.draw(
                    game,
                    agent_name,
                    pause_state,
                    now,
                    cached_frames_view=cached_frames_view_for_agent(agent, event_frame + 1),
                )
                continue

            # ── 输入处理 ──
            next_frame = event_frame + 1
            if replay_player:
                event_frame = next_frame
                if not replay_player.has_frame(event_frame):
                    renderer.draw(game, agent_name)
                    continue
                action = replay_player.action_for_frame(event_frame)
                apply_game_action(game, action)
            elif isinstance(agent, LLMAgent):
                state = game.get_llm_state()
                agent.ensure_plan(state, next_frame)
                if agent.needs_loading(next_frame):
                    renderer.draw(
                        game,
                        agent_name,
                        loading_text=LLM_LOADING_TEXT,
                        cached_frames_view=cached_frames_view_for_agent(agent, next_frame),
                    )
                    continue
                event_frame = next_frame
                action = agent.decide(state, frame=event_frame)
                apply_game_action(game, action)
            elif agent:
                event_frame = next_frame
                # Agent 模式: 读取状态 → 决策 → 执行动作
                state = game.get_state()
                action = agent.decide(state)
                apply_game_action(game, action)
            else:
                event_frame = next_frame
                # 人类模式: 直接响应键盘
                action = "none"
                if key == ord(' ') or key == curses.KEY_UP:
                    action = "jump"
                    game.jump()
                ducking = manual_input.should_duck(key)
                game.duck(ducking)
                if action != "jump":
                    action = "duck" if ducking else "none"

            if recorder:
                recorder.record_action(event_frame, action)

            # ── 更新 & 渲染 ──
            if replay_player:
                spawned_obstacles = game.update(
                    replay_obstacles=replay_player.obstacles_for_frame(event_frame),
                )
            else:
                spawned_obstacles = game.update()
                if recorder:
                    for obstacle in spawned_obstacles:
                        recorder.record_obstacle(event_frame, obstacle)
                    if game.game_over:
                        debug_log_llm_game_over(
                            agent,
                            game,
                            frame=event_frame,
                            action=action,
                        )
                        finish_recording(recorder)
            renderer.draw(
                game,
                agent_name,
                cached_frames_view=cached_frames_view_for_agent(agent, event_frame + 1),
            )
    except KeyboardInterrupt:
        return


# ═══════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════

def cli():
    """Command-line entrypoint for the terminal dino game."""
    cli_args = parse_cli_args(sys.argv[1:])
    if cli_args.version:
        print(cli_args.version)
        return
    if cli_args.show_help:
        print(cli_args.help_text)
        return
    if cli_args.command == "config":
        if cli_args.config_action == "setup":
            run_config_setup()
            return
        if cli_args.config_action == "reset":
            removed = reset_llm_config()
            if removed:
                print(f"Removed config {config_file_path()}")
            else:
                print(f"No config found at {config_file_path()}")
            return
        print(render_llm_config(load_llm_config()))
        return
    if cli_args.command == "replay" and cli_args.replay_action == "clear":
        removed = clear_replay_files()
        print(f"已清除 {removed} 个 replay 记录文件")
        return
    if cli_args.mode == "llm":
        cli_args = CliArgs(
            command=cli_args.command,
            mode=cli_args.mode,
            record_path=cli_args.record_path,
            replay_path=cli_args.replay_path,
            replay_action=cli_args.replay_action,
            competition_path=cli_args.competition_path,
            config_action=cli_args.config_action,
            llm_config=resolve_llm_config_for_run(),
            llm_debug=cli_args.llm_debug,
            show_help=cli_args.show_help,
            help_text=cli_args.help_text,
            version=cli_args.version,
        )
    curses.wrapper(main, cli_args)    # wrapper 自动处理 curses 初始化和清理


if __name__ == "__main__":
    cli()
