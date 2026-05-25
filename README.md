# Terminal Dino Runner

Chrome 断网小恐龙的终端版。可以手动玩，也可以让规则 Agent 或 Claude LLM Agent 自动玩。

## 安装

在项目目录中安装 `trex` 命令：

```bash
python3 -m pip install .
```

如果使用 Homebrew Python 并遇到 `externally-managed-environment`，可以改用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

## 启动

```bash
# 人类手动玩
trex

# 规则 Agent 自动玩
trex --agent

# Claude LLM Agent 自动玩
export ANTHROPIC_API_KEY=sk-ant-...
trex --llm
```

也可以不安装命令，直接运行源码文件：

```bash
python3 dino_game.py
python3 dino_game.py --agent
python3 dino_game.py --llm
```

## 模式

| 命令 | 说明 | 依赖 |
|------|------|------|
| `trex` | 手动操作恐龙 | 无 |
| `trex --agent` | 使用本地规则 Agent 自动决策 | 无 |
| `trex --llm` | 使用 Claude API 决策 | `ANTHROPIC_API_KEY` |

如果 `trex --llm` 没有检测到 `ANTHROPIC_API_KEY`，游戏会降级为规则 Agent。

## 操控

| 按键 | 作用 |
|------|------|
| `SPACE` / `↑` | 跳跃 |
| `↓` | 蹲下（地面）/ 快速下落（空中） |
| `A` | 切换 人类 ↔ 规则 Agent |
| `R` | Game Over 后重新开始 |
| `Q` | 退出 |

## 运行要求

- Python 3.11+
- 支持 `curses` 的终端环境
- 游戏本身无第三方运行时依赖

开发、测试、架构和扩展 Agent 的说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
