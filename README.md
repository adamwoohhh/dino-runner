# T-Rex Run | 暴龙快跑

Chrome 断网小恐龙的终端版。可以手动玩，也可以让规则 Agent 或 OpenAI LLM Agent 自动玩。

## 安装

推荐用 `pipx` 安装，这样会把命令行工具放在独立环境里：

```bash
pipx install ai-dino-in-terminal
dino
```

也可以用 `pip` 安装：

```bash
pip install ai-dino-in-terminal
dino
```

本地开发安装见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 启动

```bash
# 人类手动玩
dino
dino play

# 规则 Agent 自动玩
dino play --auto

# OpenAI LLM Agent 自动玩
dino config +setup
dino play --llm
dino play --llm --debug

# 查看或重置 LLM 配置
dino config
dino config +reset

# 选择历史运行记录并重放
dino replay
dino replay run.json

# 管理历史运行记录
dino replay +list
dino replay +clear

# 选择历史运行记录并进入竞技模式
dino compete
dino compete run.json

# 查看帮助和版本
dino help
dino play --help
dino --version
```

也可以直接运行源码：

```bash
python3 -m dino_game.cli
python3 -m dino_game.cli play
python3 -m dino_game.cli play --auto
python3 -m dino_game.cli play --llm
python3 -m dino_game.cli play --llm --debug
python3 -m dino_game.cli config
python3 -m dino_game.cli config +setup
python3 -m dino_game.cli config +reset
python3 -m dino_game.cli replay
python3 -m dino_game.cli replay run.json
python3 -m dino_game.cli replay +list
python3 -m dino_game.cli replay +clear
python3 -m dino_game.cli compete
python3 -m dino_game.cli compete run.json
```

## 模式

| 命令 | 说明 | 依赖 |
|------|------|------|
| `dino` / `dino play` | 手动操作恐龙 | 无 |
| `dino play --auto` | 使用本地规则 Agent 自动决策 | 无 |
| `dino play --llm` | 使用 OpenAI Responses API 决策 | `~/.config/ai-dino-in-terminal/config.json` 或启动时交互输入 |
| `dino play --llm --debug` | 使用 LLM 决策并写调试日志 | `logs/*.json` |
| `dino replay` | 从历史运行记录列表选择并重放 | `replays/*.json` |
| `dino replay run.json` | 直接从指定文件重放 | 对应 replay 文件 |
| `dino replay +list` | 浏览所有 replay 文件，回车查看元信息 | `replays/*.json` |
| `dino replay +clear` | 清除所有 replay 记录文件 | `replays/*.json` |
| `dino compete` | 从历史运行记录列表选择一局并进入双赛道竞技 | `replays/*.json` |
| `dino compete run.json` | 直接使用指定 replay 进入竞技模式 | 对应 replay 文件 |
| `dino config` | 查看本地 LLM 配置（API key 脱敏显示） | 无 |
| `dino config +setup` | 交互式写入本地 LLM 配置 | 选择 API 或 CODEX 模式 |
| `dino config +reset` | 重置本地 LLM 配置 | 无 |
| `dino help` | 查看可用命令和公共参数 | 无 |

LLM 配置文件固定保存在 `~/.config/ai-dino-in-terminal/config.json`。
配置包含 `llm_mode`，可选 `API` 或 `CODEX`。当 `llm_mode` 为 `API` 时，`api_key`、`base_url` 和 `model` 为必填；
当 `llm_mode` 为 `CODEX` 时，会跳过这些 API 参数。
如果 `dino play --llm` 缺少必要配置，启动游戏前会提示补全；
输入完成后会询问是否持久化到本地配置，默认 `N`，仅本次运行使用。

手动模式会在内存中记录当前局，Game Over 后界面提示 `S = 保存游戏记录`；只有按 `S` 才会把 replay 写入 `replays/` 目录，保存后提示变为 `已保存记录`，并继续停留在结束页面直到按 `R` 或 `Q`。默认文件名形如 `20260527-153012-manual-123456.json`。
Replay 文件是 JSON，包含随机种子、运行模式、总帧数、`actions` 和 `obstacles`；两组数据都使用 `{"frame": number, "action": ...}` 结构，`actions` 不记录 `none` 帧。重放时按记录数据推进游戏，不再依赖随机生成障碍物。未结束时按 `Q` 或用 `Ctrl+C` 退出不会保存未完成的 replay。

竞技模式会在同一屏幕渲染两条赛道：上方是源 replay 的历史记录，下方是玩家实时操作。两条赛道在源 replay 范围内使用相同的 seed 和障碍物数据；如果玩家超过源 replay 的帧数仍未结束，会继续用源 seed 实时生成障碍物。竞技结束后会写入新的 replay，并额外包含 `competitive: true` 和 `source_replay` 字段用于关联原始记录。

## 操控

| 按键 | 作用 |
|------|------|
| `SPACE` / `↑` | 跳跃 |
| `↓` | 蹲下（地面）/ 快速下落（空中） |
| `Enter` | 暂停；暂停时再次按下会倒计时 3 秒后继续 |
| `R` | Game Over 后重新开始 |
| `Q` | 退出 |

## 运行要求

- Python 3.11+
- 支持 `curses` 的终端环境
- 游戏本身无第三方运行时依赖

开发、测试、架构和扩展 Agent 的说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
