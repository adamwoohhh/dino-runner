# T-Rex Run | 暴龙快跑

Chrome 断网小恐龙的终端版。可以手动玩，也可以让规则 Agent 或 Claude LLM Agent 自动玩。

## 安装

在项目目录中安装到本地虚拟环境 `.venv`：

```bash
make install
```

这会创建 `.venv`，并把命令安装到：

```text
.venv/bin/dino
```

## 启动

```bash
# 人类手动玩
make run

# 规则 Agent 自动玩
make agent

# Claude LLM Agent 自动玩
export ANTHROPIC_API_KEY=sk-ant-...
make llm

# 选择历史运行记录并重放
.venv/bin/dino replay

# 选择历史运行记录并进入竞技模式
.venv/bin/dino compete
```

也可以直接使用底层命令：

```bash
.venv/bin/dino
.venv/bin/dino --agent
.venv/bin/dino --llm
.venv/bin/dino replay
.venv/bin/dino compete
.venv/bin/dino --record run.json
.venv/bin/dino --replay run.json
.venv/bin/dino --compete run.json
python3 dino_game.py
python3 dino_game.py --agent
python3 dino_game.py --llm
python3 dino_game.py replay
python3 dino_game.py compete
python3 dino_game.py --record run.json
python3 dino_game.py --replay run.json
python3 dino_game.py --compete run.json
```

## 模式

| 命令 | 说明 | 依赖 |
|------|------|------|
| `dino` | 手动操作恐龙 | 无 |
| `dino --agent` | 使用本地规则 Agent 自动决策 | 无 |
| `dino --llm` | 使用 Claude API 决策 | `ANTHROPIC_API_KEY` |
| `dino replay` | 从历史运行记录列表选择并重放 | `replays/*.json` |
| `dino compete` | 从历史运行记录列表选择一局并进入双赛道竞技 | `replays/*.json` |
| `dino --record run.json` | 指定录制文件路径 | 无 |
| `dino --replay run.json` | 直接从指定文件重放 | 对应 replay 文件 |
| `dino --compete run.json` | 直接使用指定 replay 进入竞技模式 | 对应 replay 文件 |

如果 `dino --llm` 没有检测到 `ANTHROPIC_API_KEY`，游戏会降级为规则 Agent。

默认每次运行都会记录到 `replays/` 目录，文件名形如
`20260527-153012-manual-123456.json`，其中包含运行模式 `manual`、`agent`
或 `llm`。Replay 文件是 JSON，包含随机种子、运行模式、总帧数、`actions` 和 `obstacles`；
两组数据都使用 `{"frame": number, "action": ...}` 结构，`actions` 不记录 `none` 帧。重放时按记录数据推进游戏，不再依赖随机生成障碍物。
每局只在 Game Over 时写入一个 replay 文件；同一进程内按 `R` 重开会为新局创建新文件。未结束时按 `Q` 或用 `Ctrl+C` 退出不会保存未完成的 replay。

竞技模式会在同一屏幕渲染两条赛道：上方是源 replay 的历史记录，下方是玩家实时操作。两条赛道在源 replay 范围内使用相同的 seed 和障碍物数据；如果玩家超过源 replay 的帧数仍未结束，会继续用源 seed 实时生成障碍物。竞技结束后会写入新的 replay，并额外包含 `competitive: true` 和 `source_replay` 字段用于关联原始记录。

## 操控

| 按键 | 作用 |
|------|------|
| `SPACE` / `↑` | 跳跃 |
| `↓` | 蹲下（地面）/ 快速下落（空中） |
| `R` | Game Over 后重新开始 |
| `Q` | 退出 |

## 运行要求

- Python 3.11+
- 支持 `curses` 的终端环境
- 游戏本身无第三方运行时依赖

开发、测试、架构和扩展 Agent 的说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
