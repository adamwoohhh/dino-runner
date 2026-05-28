"""Core game engine, physics, obstacles, and actions."""

import random

from .art import CACTUS_PLANT_ART, OBSTACLE_ART
from .constants import *

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

def apply_game_action(game: DinoGame, action: str):
    """执行 replay/agent/manual 统一动作。"""
    if action == "jump":
        game.jump()
        game.duck(False)
    elif action == "duck":
        game.duck(True)
    else:
        game.duck(False)

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
