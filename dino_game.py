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
  │ Renderer │                     │ LLMAgent  │  调用 Claude API（秒级）
  └──────────┘                     └───────────┘

三种运行模式:
  python dino_game.py            # 人类手动玩
  python dino_game.py --agent    # 规则 AI Agent 自动玩
  python dino_game.py --llm      # Claude LLM Agent 玩 (需要 ANTHROPIC_API_KEY)
  python dino_game.py replay     # 从运行记录列表选择并重放
  python dino_game.py --record run.json  # 指定录制文件
  python dino_game.py --replay run.json  # 重放一局

游戏内操控:
  SPACE / ↑  跳跃
  ↓          蹲下（地面）/ 快速下落（空中）
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


# ═══════════════════════════════════════════════════════════════════════
# 游戏常量 — 调这些数字可以改变游戏手感
# ═══════════════════════════════════════════════════════════════════════

FPS = 30                  # 帧率，决定游戏流畅度 (30帧 = 每帧33ms)
FRAME_MS = 1000 // FPS    # 每帧毫秒数，传给 curses.timeout()

GROUND_ROW = 18           # 地面在终端的第几行（从上往下数）
DINO_COL = 8              # 恐龙固定在屏幕左侧第 8 列

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
SPEED_DROP_MULTIPLIER = 3.0
REPLAY_DIR = "replays"


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


def generate_cactus_group(difficulty: float = 1.0) -> tuple[str, ...]:
    """随机生成高/矮仙人掌组合，随难度逐步解锁 4 连。"""
    max_count = max_cactus_group_size(difficulty)
    while True:
        count = random.randint(1, max_count)
        plants = tuple(random.choice(("short", "tall")) for _ in range(count))
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
            difficulty: float = 1.0):
        self.kind = kind
        self.x = float(x)
        self.height = height
        self.plants = plants
        if kind == "cactus_group":
            if plants is None:
                plants = generate_cactus_group(difficulty)
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


class DinoGame:
    """游戏引擎 — 管理所有游戏状态和物理模拟

    职责:
      1. 恐龙物理（跳跃抛物线、蹲下）
      2. 障碍物生成与移动
      3. 碰撞检测
      4. 分数计算

    不负责: 渲染（交给 Renderer）、决策（交给 Agent）
    """

    def __init__(self):
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
        self.frame = 0          # 帧计数器（用于动画切换）
        self.spawn_timer = random.randint(SPAWN_MIN, SPAWN_MAX)
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

    def get_state(self) -> dict:
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
        for obs in sorted(self.obstacles, key=lambda o: o.x):
            # 只返回还没完全飞过恐龙的障碍物
            if obs.x + obs.width > DINO_COL - 2:
                nearest.append({
                    "kind": obs.kind,
                    "x": round(obs.x, 1),
                    "distance": round(obs.x - DINO_COL, 1),
                    "height": obs.height,
                    "width": obs.width,
                    "h": obs.h,
                })
                if len(nearest) >= 3:
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
                self.spawn_timer = random.randint(SPAWN_MIN, SPAWN_MAX)

        # ── 4. 装饰: 云朵 ──
        if random.random() < 0.02:          # 2% 概率每帧生成一朵云
            self.clouds.append({
                "x": 82.0,
                "y": random.randint(2, 8),  # 云在屏幕上方随机行
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
                    self.game_over = True
                    self.high_score = max(self.high_score, self.score)
                    break
            if self.game_over:
                break

        return spawned_obstacles

    def _spawn_obstacle(self) -> Obstacle:
        """在屏幕右侧 (x=82) 生成一个新障碍物

        障碍物种类随分数推进:
          - 0~200:   只有随机仙人掌组
          - 200~500: 加入鸟
          - 500+:    鸟出现更频繁
        """
        if self.score < 200:
            kinds = ["cactus_group", "cactus_group", "cactus_group"]
        elif self.score < 500:
            kinds = ["cactus_group", "cactus_group", "cactus_group", "bird"]
        else:
            kinds = ["cactus_group", "cactus_group", "cactus_group", "bird", "bird"]

        kind = random.choice(kinds)
        height = 0
        if kind == "bird":
            # 鸟有三种飞行高度:
            #   0 = 贴地（必须跳过）
            #   4 = 中空（站着就能过，也可蹲）
            #   8 = 高空（完全不用管）
            height = random.choice([0, 4, 8])

        obstacle = Obstacle(kind, 82, height, difficulty=difficulty_for_score(self.score))
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


class LLMAgent:
    """调用 Claude API 的 LLM Agent — 慢但能「理解」游戏

    工作流程:
      1. 每 0.8 秒向 Claude Haiku 发送一次当前游戏状态
      2. 在后台线程中等待 API 响应（避免阻塞游戏主循环）
      3. 响应到达后缓存动作，下一帧生效

    注意:
      - API 延迟 200ms~2s，所以 LLM 的决策总是「滞后」的
      - 实际效果不如 RuleAgent（延迟是硬伤）
      - 但它展示了一个重要概念: LLM 能直接读懂游戏状态并做决策
      - 需要 ANTHROPIC_API_KEY 环境变量
    """

    def __init__(self):
        self.pending_action = "none"    # 缓存的待执行动作
        self.last_call_time = 0         # 上次 API 调用时间戳
        self.call_interval = 0.8        # API 调用间隔（秒），避免速率限制
        self.lock = threading.Lock()    # 线程安全锁
        self._check_api_key()

    def _check_api_key(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("需要设置 ANTHROPIC_API_KEY 环境变量")

    def _call_llm(self, state: dict):
        """在后台线程中调用 Claude Haiku API

        选择 Haiku 而非 Sonnet/Opus 的原因:
          - 延迟更低（对实时游戏很关键）
          - 足够理解简单的游戏状态
          - 成本更低（高频调用）
        """
        try:
            import urllib.request

            # 构造 prompt — 把游戏状态翻译成自然语言
            prompt = f"""你正在玩一个恐龙跑酷游戏。根据当前游戏状态决定操作。

当前状态:
- 恐龙高度: {state['dino_y']} (0=地面)
- 正在跳跃: {state['jumping']}
- 正在蹲下: {state['ducking']}
- 游戏速度: {state['speed']}
- 前方障碍物: {json.dumps(state['obstacles'], ensure_ascii=False)}

距离 distance 表示障碍物离恐龙的距离，越小越近。
height 表示障碍物的高度(鸟)，0=低空，4=中空，8=高空。

你只能回答一个词: jump / duck / none
- jump: 跳跃（躲避仙人掌或低空鸟）
- duck: 蹲下（躲避中空鸟）
- none: 什么都不做

回答:"""

            # 通过 urllib 直接调用 Anthropic Messages API（避免依赖 SDK）
            data = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 10,        # 只需要一个词
                "messages": [{"role": "user", "content": prompt}],
            }).encode()

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )

            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                text = result["content"][0]["text"].strip().lower()

                # 从回复中提取动作
                action = "none"
                if "jump" in text:
                    action = "jump"
                elif "duck" in text:
                    action = "duck"

                with self.lock:
                    self.pending_action = action

        except Exception:
            # API 调用失败时默认不操作（宁可不跳也别崩溃）
            with self.lock:
                self.pending_action = "none"

    def decide(self, state: dict) -> str:
        """异步决策: 发起 API 调用，返回上一次的缓存结果

        每帧都会被调用，但只有间隔超过 call_interval 时才真正发请求。
        返回值是上一次 API 调用的结果（有延迟）。
        """
        now = time.time()

        # 限流: 间隔足够长才发新请求
        if now - self.last_call_time >= self.call_interval:
            self.last_call_time = now
            # 后台线程调用 API，不阻塞游戏主循环
            t = threading.Thread(target=self._call_llm, args=(state,), daemon=True)
            t.start()

        with self.lock:
            action = self.pending_action
            self.pending_action = "none"  # 消费掉，避免重复执行

        return action


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


def load_replay_file(path) -> dict:
    """读取 replay JSON 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def game_mode_from_args(args: list[str]) -> str:
    """根据命令行参数返回运行模式名。"""
    if "--llm" in args:
        return "llm"
    if "--agent" in args:
        return "agent"
    return "manual"


def default_replay_path(mode: str, seed: int | None = None, directory: str = REPLAY_DIR) -> str:
    """生成默认运行记录文件路径。"""
    if seed is None:
        seed = time.time_ns()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = str(seed)[-6:]
    return os.path.join(directory, f"{timestamp}-{mode}-{suffix}.json")


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

    def __init__(self, path, seed: int, mode: str = "manual"):
        self.path = path
        self.seed = seed
        self.mode = mode
        self.actions: list[dict] = []
        self.obstacles: list[dict] = []
        self.frames = 0
        self.input_count = 0

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
        data = {
            "version": 3,
            "seed": self.seed,
            "mode": self.mode,
            "frames": self.frames,
            "actions": self.actions,
            "obstacles": self.obstacles,
        }
        directory = os.path.dirname(os.fspath(self.path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


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
    random.seed(seed)
    game = DinoGame()
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


def footer_hint(agent_name: str, speed: float) -> str:
    """根据当前模式返回底部操作提示。"""
    if agent_name == "Replay":
        return f"Q 退出 | 回放 | 速度 {speed:.1f}x"
    if agent_name:
        return f"Q 退出 | 速度 {speed:.1f}x"
    return "SPACE/↑ 跳跃 | ↓ 蹲下 | Q 退出"


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

    def draw(self, game: DinoGame, agent_name: str):
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
        if game.ducking:
            art = DINO_DUCK
        elif game.jumping:
            art = DINO_JUMP
        elif (game.frame // RUN_ANIM_FRAME_INTERVAL) % 2 == 0:
            art = DINO_RUN_1
        else:
            art = DINO_RUN_2

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

        # ── 底部操作提示 ──
        hint = footer_hint(agent_name, game.speed)
        self.safe_addstr(h - 1, 2, hint, curses.A_DIM)

        self.scr.refresh()


# ═══════════════════════════════════════════════════════════════════════
# 主循环 — 把游戏引擎、渲染器、Agent 串起来
# ═══════════════════════════════════════════════════════════════════════

def main(stdscr):
    """游戏主循环

    每帧的执行顺序:
      1. 读取键盘输入 (curses.getch)
      2. 处理全局按键 (Q/A)
      3. 如果 Game Over → 等待重启
      4. Agent 决策 或 人类输入
      5. game.update() 推进一帧
      6. renderer.draw() 渲染画面
      7. 等待下一帧 (由 curses.timeout 控制)
    """
    args = sys.argv[1:]
    replay_subcommand = bool(args) and args[0] == "replay"
    replay_path = arg_value(args, "--replay")
    if replay_subcommand and not replay_path:
        replay_path = select_replay_file(stdscr, list_replay_files())
        if not replay_path:
            return

    record_path = arg_value(args, "--record")
    replay_player = ReplayPlayer.from_file(replay_path) if replay_path else None
    seed = replay_player.seed if replay_player else time.time_ns()
    random.seed(seed)
    mode = game_mode_from_args(args)
    if replay_player:
        recorder = ReplayRecorder(record_path, seed, mode="replay") if record_path else None
    else:
        if not record_path:
            record_path = default_replay_path(mode, seed)
        recorder = ReplayRecorder(record_path, seed, mode=mode)

    game = DinoGame()
    renderer = Renderer(stdscr)
    manual_input = ManualInputState()
    event_frame = 0

    # 根据命令行参数选择 Agent 模式
    agent = None
    agent_name = ""

    if replay_player:
        agent_name = "Replay"
    elif "--llm" in args:
        try:
            agent = LLMAgent()
            agent_name = "LLM Agent (Claude)"
        except ValueError:
            # 没有 API key，降级到规则 Agent
            agent = RuleAgent()
            agent_name = "Rule Agent (no API key)"
    elif "--agent" in args:
        agent = RuleAgent()
        agent_name = "Rule Agent"

    try:
        while True:
            key = stdscr.getch()    # 非阻塞，超时返回 -1

            # ── 全局按键 ──
            if key == ord('q') or key == ord('Q'):
                break

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
                    renderer.draw(game, agent_name)
                    continue

                if should_reset_after_game_over(key, agent_active=bool(agent)):
                    event_frame += 1
                    game.reset()
                    if recorder:
                        recorder.record_action(event_frame, "reset")
                renderer.draw(game, agent_name)
                continue

            # ── 输入处理 ──
            event_frame += 1
            if replay_player:
                if not replay_player.has_frame(event_frame):
                    renderer.draw(game, agent_name)
                    continue
                action = replay_player.action_for_frame(event_frame)
                apply_game_action(game, action)
            elif agent:
                # Agent 模式: 读取状态 → 决策 → 执行动作
                state = game.get_state()
                action = agent.decide(state)
                apply_game_action(game, action)
            else:
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
            renderer.draw(game, agent_name)
    finally:
        if recorder:
            recorder.save()


# ═══════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════

def cli():
    """Command-line entrypoint for the terminal dino game."""
    print("=" * 50)
    print("  🦕 Terminal Dino Runner")
    print("=" * 50)
    print()
    print("  用法:")
    print("    trex          手动玩")
    print("    trex --agent  AI Agent 玩")
    print("    trex --llm    Claude LLM 玩")
    print("    trex replay   选择运行记录并重放")
    print("    trex --record run.json  指定录制文件")
    print("    trex --replay run.json  直接重放文件")
    print()
    print("  启动中...")
    time.sleep(0.5)
    curses.wrapper(main)    # wrapper 自动处理 curses 初始化和清理


if __name__ == "__main__":
    cli()
