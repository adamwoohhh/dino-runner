# Contributing

本文档记录开发、测试、架构和扩展相关信息。面向玩家的安装和启动说明见 [README.md](README.md)。

## 开发环境

默认使用项目内的 `.venv`，避免把包安装到 Homebrew Python 或系统 Python：

```bash
make dev-install
```

安装后可以用 `make run`、`make agent`、`make llm` 启动，也可以直接运行虚拟环境里的命令：

```bash
.venv/bin/dino
.venv/bin/dino --agent
.venv/bin/dino --llm
```

直接运行源码也仍然可用：

```bash
python3 dino_game.py
```

## 测试

当前测试使用 Python 标准库 `unittest`：

```bash
make test
```

语法检查：

```bash
make check
```

常用命令由 `Makefile` 管理：

```bash
make install      # 安装 dino 命令
make dev-install  # editable 安装，适合开发
make run          # .venv/bin/dino
make agent        # .venv/bin/dino --agent
make llm          # .venv/bin/dino --llm
.venv/bin/dino replay             # 选择运行记录并重放
.venv/bin/dino --record run.json  # 指定 replay 录制路径
.venv/bin/dino --replay run.json  # 直接重放 replay 文件
make test         # 运行 unittest
make check        # 测试 + py_compile
make clean        # 清理缓存和构建产物
```

如果改动了命令入口或打包配置，需要确认：

```bash
python3 -c "import importlib.metadata as m; print([ep.value for ep in m.entry_points(group='console_scripts') if ep.name == 'dino'])"
test -x .venv/bin/dino
```

期望 `dino` 入口指向 `dino_game:cli`。

## 构建和发布

PyPI 包名是 `ai-dino-in-terminal`，安装后暴露的命令是 `dino`。

构建发布包需要本地安装维护者工具：

```bash
python3 -m pip install build twine
```

构建 wheel 和 source distribution：

```bash
make build
```

上传到 TestPyPI：

```bash
make publish-test
```

上传到 PyPI：

```bash
make publish
```

`make publish-test` 和 `make publish` 会重新构建发布包，并在上传前运行 `twine check`。

发布前至少运行：

```bash
make check
make build
```

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
├── ReplayRecorder/ReplayPlayer
├── Renderer       curses 终端渲染器
├── main()         游戏主循环
└── cli()          console script 入口
```

打包入口在 `pyproject.toml`：

```toml
[project]
name = "ai-dino-in-terminal"

[project.scripts]
dino = "dino_game:cli"
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

## Replay

Replay 文件是 JSON，包含 `version`、`seed`、`mode`、`frames`、`actions` 和 `obstacles`。默认每局 Game Over 时写入 `replays/`，文件名包含时间戳、`manual`/`agent`/`llm` 模式和 seed 后缀；也可以用 `--record run.json` 指定第一局路径，后续局会追加 `-2`、`-3` 后缀。`actions` 和 `obstacles` 都保存为 `{"frame": number, "action": ActionData | ObstacleData}`，数组语义已经区分输入和障碍物，因此不再写 `type=input` 或 `type=obstacle`；`actions` 不记录 `none` 帧，空操作由缺省值表示，`frames` 保留总回放长度。未结束时按 `Q` 或用 `Ctrl+C` 退出不会保存未完成 replay。`dino replay` 会先列出历史运行记录，方向键选择后回车进入重放；重放时按文件里的障碍物数据注入障碍物，因此不依赖随机调用顺序。

## 物理参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `FPS` | 30 | 每秒 30 帧 |
| `JUMP_VELOCITY` | -1.75 | 起跳初速度，负值表示向上 |
| `GRAVITY` | 0.22 | 每帧重力加速度 |
| 跳跃最大高度 | ~7.8 | 约第 8 帧到达顶点 |
| 完整跳跃时间 | ~17 帧 | 约 0.57 秒 |
| `INITIAL_SPEED` | 1.75 | 障碍物初始速度 |
| `MAX_SPEED` | 3.8 | 速度上限，约为初始速度的 2.17 倍 |
| 速度公式 | `INITIAL_SPEED + score * SPEED_ACCELERATION` | 每帧按 `0.0005` 加速 |
| 难度公式 | `min(1.0, score / DIFFICULTY_MAX_SCORE)` | `DIFFICULTY_MAX_SCORE` 当前为 `600` |

碰撞检测使用 AABB。恐龙碰撞箱比视觉精灵小一圈，让判定更宽容。

## 障碍物生成

| 分数区间 | 可能的障碍物 |
|---------|--------------|
| 0 ~ 200 | 随机仙人掌组 |
| 200 ~ 500 | 随机仙人掌组、鸟 |
| 500+ | 随机仙人掌组、鸟（鸟出现频率更高） |

随机仙人掌组由 1~4 个高/矮仙人掌组成。难度低于 `0.33` 时最多 2 连，低于 `0.66` 时最多 3 连，之后才允许 4 连。1~2 个时高矮完全随机；3~4 个时最多包含 1 个高仙人掌，避免出现 4 连高或其他按当前跳跃物理难以通过的宽高组合。

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
