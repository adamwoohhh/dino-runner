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

游戏内操控:
  SPACE / ↑  跳跃
  ↓          蹲下（地面）/ 快速下落（空中）
  A          切换 人类 ↔ AI 模式
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

FPS = 20                  # 帧率，决定游戏流畅度 (20帧 = 每帧50ms)
FRAME_MS = 1000 // FPS    # 每帧毫秒数，传给 curses.timeout()

GROUND_ROW = 18           # 地面在终端的第几行（从上往下数）
DINO_COL = 8              # 恐龙固定在屏幕左侧第 8 列

JUMP_VELOCITY = -2.2      # 起跳初速度（负值 = 向上）
GRAVITY = 0.25            # 每帧施加的重力加速度
                          # 跳跃轨迹: 约 18 帧完成一次完整跳跃
                          # 最大高度: 约 10.8 个单位

INITIAL_SPEED = 1.0       # 障碍物初始水平移动速度（像素/帧）
MAX_SPEED = 3.5           # 速度上限，避免游戏变得不可能
                          # 速度公式: speed = min(MAX_SPEED, 1.0 + score * 0.001)

SPAWN_MIN = 25            # 连续障碍物之间的最小间距（像素）
SPAWN_MAX = 50            # 连续障碍物之间的最大间距（像素）
                          # 设为 25 保证恐龙跳完一次后有时间落地再跳


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

CACTUS_CLUSTER = [        # 仙人掌丛（4行高，5列宽）— 两个小仙人掌并排
    " ▌ ▌ ",
    "▐█▌█▌",
    " █ █ ",
    " █ █ ",
]

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
    "cactus_cluster": CACTUS_CLUSTER,
    "bird": BIRD_1,       # 鸟在渲染时会在 BIRD_1/BIRD_2 之间交替
}


# ═══════════════════════════════════════════════════════════════════════
# 游戏逻辑
# ═══════════════════════════════════════════════════════════════════════

class Obstacle:
    """单个障碍物实体

    Attributes:
        kind:   类型标识，"cactus_sm" / "cactus_lg" / "cactus_cluster" / "bird"
        x:      当前水平位置（浮点数，从右侧 82 出生，向左移动）
        height: 垂直偏移（仅鸟使用：0=贴地, 4=中空, 8=高空）
        art:    对应的 ASCII 美术行列表
        width:  美术中最宽一行的字符数（用于碰撞检测）
        h:      美术行数（用于碰撞检测）
    """

    def __init__(self, kind: str, x: float, height: int = 0):
        self.kind = kind
        self.x = float(x)
        self.height = height
        self.art = OBSTACLE_ART[kind]
        self.width = max(len(line) for line in self.art)
        self.h = len(self.art)

    @property
    def hitbox(self) -> tuple:
        """返回 AABB 碰撞箱 (left, right, bottom, top)

        坐标系: X 轴向右为正，Y 轴向上为正，地面 Y=0
        """
        left = self.x
        right = self.x + self.width - 1
        bottom = self.height
        top = self.height + self.h - 1
        return (left, right, bottom, top)


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
            # 空中且仍在上升阶段 → 反转速度，快速下落
            self.dino_vy = abs(self.dino_vy)

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

    def update(self):
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
            return

        self.frame += 1
        self.score += 1
        # 速度随分数线性增长，但有上限
        self.speed = min(MAX_SPEED, INITIAL_SPEED + self.score * 0.001)

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
        # spawn_timer 按速度递减，模拟「固定像素间距」
        self.spawn_timer -= self.speed
        if self.spawn_timer <= 0:
            self._spawn_obstacle()
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
            ol, oright, ob, ot = obs.hitbox
            # 两个矩形重叠的条件: 四个方向都有交集
            # 额外 ±1 容差让碰撞更宽容
            if (dino_right > ol + 1 and dino_left < oright - 1 and
                    dino_top > ob + 1 and dino_bottom < ot - 1):
                self.game_over = True
                self.high_score = max(self.high_score, self.score)
                break

    def _spawn_obstacle(self):
        """在屏幕右侧 (x=82) 生成一个新障碍物

        障碍物种类随分数推进:
          - 0~200:   只有仙人掌
          - 200~500: 加入鸟
          - 500+:    鸟出现更频繁
        """
        if self.score < 200:
            kinds = ["cactus_sm", "cactus_sm", "cactus_lg"]
        elif self.score < 500:
            kinds = ["cactus_sm", "cactus_lg", "cactus_cluster", "bird"]
        else:
            kinds = ["cactus_sm", "cactus_lg", "cactus_cluster", "bird", "bird"]

        kind = random.choice(kinds)
        height = 0
        if kind == "bird":
            # 鸟有三种飞行高度:
            #   0 = 贴地（必须跳过）
            #   4 = 中空（站着就能过，也可蹲）
            #   8 = 高空（完全不用管）
            height = random.choice([0, 4, 8])

        self.obstacles.append(Obstacle(kind, 82, height))


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
        react_max = 7 + speed * 4   # 太远不跳（跳了白跳，落地后可能撞下一个）
        react_min = -2              # 太近了也别跳（已经来不及了）

        # 依次检查前方障碍物（已按距离排序）
        for obs in state["obstacles"]:
            dist = obs["distance"]
            if dist > react_max or dist < react_min:
                continue

            # 中高空鸟 (height >= 4) — 恐龙站立高度碰不到，忽略
            if obs["kind"] == "bird" and obs["height"] >= 4:
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
        elif game.frame % 10 < 5:       # 每 10 帧切换一次跑步帧
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
                # 鸟每 8 帧切换拍翅动画
                art = BIRD_1 if game.frame % 8 < 4 else BIRD_2
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
        if not agent_name:
            hint = "SPACE/↑ 跳跃 | ↓ 蹲下 | A 切换AI | Q 退出"
        else:
            hint = f"A 切换手动 | Q 退出 | 速度 {game.speed:.1f}x"
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
    game = DinoGame()
    renderer = Renderer(stdscr)

    # 根据命令行参数选择 Agent 模式
    agent = None
    agent_name = ""

    if "--llm" in sys.argv:
        try:
            agent = LLMAgent()
            agent_name = "LLM Agent (Claude)"
        except ValueError:
            # 没有 API key，降级到规则 Agent
            agent = RuleAgent()
            agent_name = "Rule Agent (no API key)"
    elif "--agent" in sys.argv:
        agent = RuleAgent()
        agent_name = "Rule Agent"

    while True:
        key = stdscr.getch()    # 非阻塞，超时返回 -1

        # ── 全局按键 ──
        if key == ord('q') or key == ord('Q'):
            break

        # A 键随时切换 人类 ↔ AI 模式
        if key == ord('a') or key == ord('A'):
            if agent:
                agent = None
                agent_name = ""
            else:
                agent = RuleAgent()
                agent_name = "Rule Agent"

        # ── Game Over 状态 ──
        if game.game_over:
            if key == ord('r') or key == ord('R'):
                game.reset()
            elif agent:
                # Agent 模式自动重来（短暂停顿让人看到分数）
                time.sleep(0.5)
                game.reset()
            renderer.draw(game, agent_name)
            continue

        # ── 输入处理 ──
        if agent:
            # Agent 模式: 读取状态 → 决策 → 执行动作
            state = game.get_state()
            action = agent.decide(state)
            if action == "jump":
                game.jump()
            elif action == "duck":
                game.duck(True)
            else:
                game.duck(False)
        else:
            # 人类模式: 直接响应键盘
            if key == ord(' ') or key == curses.KEY_UP:
                game.jump()
            if key == curses.KEY_DOWN:
                game.duck(True)
            else:
                game.duck(False)

        # ── 更新 & 渲染 ──
        game.update()
        renderer.draw(game, agent_name)


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
    print()
    print("  启动中...")
    time.sleep(0.5)
    curses.wrapper(main)    # wrapper 自动处理 curses 初始化和清理


if __name__ == "__main__":
    cli()
