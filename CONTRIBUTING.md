# Contributing

本文档记录开发、测试、架构和扩展相关信息。面向玩家的安装和启动说明见 [README.md](README.md)。

## 开发环境

建议使用虚拟环境，避免把开发依赖安装到系统 Python：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

安装后可以用 `trex`、`trex --agent`、`trex --llm` 验证命令入口。直接运行源码也仍然可用：

```bash
python3 dino_game.py
```

## 测试

当前测试使用 Python 标准库 `unittest`：

```bash
python3 -m unittest tests/test_packaging.py
```

语法检查：

```bash
python3 -m py_compile dino_game.py
```

如果改动了命令入口或打包配置，需要确认：

```bash
python3 -c "import importlib.metadata as m; print([ep.value for ep in m.entry_points(group='console_scripts') if ep.name == 'trex'])"
command -v trex
```

期望 `trex` 入口指向 `dino_game:cli`。

## 项目结构

项目主体是单文件游戏：

```text
dino_game.py
├── 游戏常量        FPS、重力、速度等参数
├── 像素艺术        Unicode 字符画精灵
├── Obstacle       障碍物实体和碰撞箱
├── DinoGame       游戏引擎、物理、碰撞、生成、状态导出
├── RuleAgent      基于距离阈值的规则 Agent
├── LLMAgent       Claude API Agent
├── Renderer       curses 终端渲染器
├── main()         游戏主循环
└── cli()          console script 入口
```

打包入口在 `pyproject.toml`：

```toml
[project.scripts]
trex = "dino_game:cli"
```

## Agent 数据流

Agent 通过三步接入游戏：

1. `DinoGame.get_state()` 导出结构化状态。
2. Agent 实现 `decide(state) -> str`，返回 `jump`、`duck` 或 `none`。
3. 主循环把动作映射到 `game.jump()` / `game.duck()`。

状态示例：

```python
state = game.get_state()
# {
#   "dino_y": 3.4,
#   "dino_vy": -0.2,
#   "jumping": True,
#   "ducking": False,
#   "speed": 1.5,
#   "score": 320,
#   "obstacles": [
#     {"kind": "cactus_lg", "distance": 12.3, "height": 0, "width": 5, "h": 6},
#   ],
# }
```

## RuleAgent

`RuleAgent` 是本地反应式策略，延迟接近 0。核心规则是：

```text
反应距离 = 7 + speed * 4
```

- `7` 约等于恐龙右边缘到障碍物左边缘即将重叠的距离。
- `speed * 4` 是随速度增加的提前量。
- 仙人掌和低空鸟需要跳。
- 中高空鸟当前规则会忽略。

这个策略不是完美规划器。它不会枚举未来动作序列，也不能保证只要物理可通过就永不失败。

## LLMAgent

`LLMAgent` 使用 Anthropic Messages API：

- 每隔约 `0.8s` 发起一次请求。
- 请求在后台线程执行，不阻塞游戏主循环。
- API 请求 timeout 是 `5s`。
- 每帧消费上一次已返回的缓存动作。

因此 LLM 模式用于演示“模型读取结构化状态并决策”，不是实时游戏的最佳策略。接口慢返回或失败时，游戏仍继续推进；失败动作会降级为 `none`。

## 物理参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `FPS` | 20 | 每秒 20 帧 |
| `JUMP_VELOCITY` | -2.2 | 起跳初速度，负值表示向上 |
| `GRAVITY` | 0.25 | 每帧重力加速度 |
| 跳跃最大高度 | ~10.8 | 约第 9 帧到达顶点 |
| 完整跳跃时间 | ~18 帧 | 约 0.9 秒 |
| `INITIAL_SPEED` | 1.0 | 障碍物初始速度 |
| `MAX_SPEED` | 3.5 | 速度上限 |
| 速度公式 | `1.0 + score * 0.001` | 每 1000 分加速 1.0 |

碰撞检测使用 AABB。恐龙碰撞箱比视觉精灵小一圈，让判定更宽容。

## 障碍物生成

| 分数区间 | 可能的障碍物 |
|---------|--------------|
| 0 ~ 200 | 小仙人掌、大仙人掌 |
| 200 ~ 500 | 小仙人掌、大仙人掌、仙人掌丛、鸟 |
| 500+ | 鸟出现频率翻倍 |

鸟有三种高度：

- `height=0`：贴地，必须跳过。
- `height=4`：中空，站立可过，也可蹲。
- `height=8`：高空，不需要处理。

## 扩展 Agent

新增 Agent 只需要实现 `decide(state) -> str`：

```python
class MyAgent:
    def decide(self, state: dict) -> str:
        return "jump"  # or "duck" or "none"
```

可以尝试的方向：

- 用更完整的规则考虑连续障碍物。
- 枚举未来 N 帧动作，做短期规划。
- 使用强化学习或神经网络策略。
- 基于终端截图做视觉识别，而不是读取 `get_state()`。
