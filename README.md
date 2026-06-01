# DINO RUNNER: 一款可以让 AI 玩的终端游戏

![](./docs/readme/ac-header.gif)

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

如果不想依赖 `pipx` 或 PyPI，可以用 `install.sh` 从 GitHub Release 下载 wheel，
安装到独立虚拟环境后把 `dino` 链接到 `~/.local/bin`：

```bash
curl -fsSL https://raw.githubusercontent.com/adamwoohhh/agents-competition/main/install.sh | bash
```

默认使用 GitHub Release：

```bash
DINO_INSTALL_SOURCE=github DINO_VERSION=0.1.1 bash install.sh
```

也可以安装本地下载好的 wheel，不访问 PyPI：

```bash
DINO_WHEEL_PATH=dist/ai_dino_in_terminal-0.1.1-py3-none-any.whl bash install.sh
```

卸载：

```bash
bash install.sh --uninstall
```

## 发布 GitHub Release

GitHub Actions 会在推送 `v*` tag 时自动构建发布包，校验 `dist/*.whl` 和
`dist/*.tar.gz`，并把它们上传到 GitHub Release。tag 版本必须和
`pyproject.toml` 中的版本一致：

```bash
git tag v0.1.1
git push origin v0.1.1
```

## 快速开玩

### 手动玩

```bash
dino # 或者 `dino play`
```

### AI 玩

![](./docs/readme/ac-llm--lay.gif)

1.AI 模式，不指定 provider。
```bash
# 1. 完成安装
# 2. 判断执行模式：
#    2.1. Codex 安装 + 本地已经配置 ak：询问使用哪种模式。
#    2.2. Codex 安装，本地未配置 ak：使用 CODEX 模式。
#    2.3. Codex 未安装，本地已经配置 ak：使用 API 模式。
#    2.4. Codex 未安装，本地未配置 ak：进入 setup 流程。

dino play --llm
```

2. AI 模式，指定 provider 为本地 Codex。
 ```bash
# 1. 安装完成
# 2. 判断本地 Codex 是否安装（符合版本要求）
#    2.1. Codex 安装，进入游戏。
#    2.2. Codex 未安装，提示安装，终止游戏。

dino play --llm codex
 ```

3. AI 模式，指定 provider 为 API (OpenAI Response)。
 ```bash
# 1. 安装完成，开始玩
# 2. 判断本地配置文件：
#    2.1. 已经配置 ak，进入游戏。
#    2.2. 未配置 ak，进入 setup 配置流程。

dino play --llm api
 ```

## 其他玩法

### 保存游戏记录

结束一局游戏后，可以选择保存本局记录。后续可以回放或者在竞技模式中使用。

![](./docs/readme/ac-save.png)


### 观看回放

通过 `dino replay` 选择一局游戏记录回放。

![](./docs/readme/ac-replay.gif)


### 竞技模式

通过 `dino compete` 选择一局游戏记录，可以一边看回放一边跟玩。

![](./docs/readme/ac-compete.gif)

### 查看游戏数据

使用 `dino dashboard` 命令查看得分和 token 消耗情况。

![](./docs/readme/ac-dashboard.png)

## 完整指令说明

| 命令 | 说明 | 依赖 |
|------|------|------|
| `dino` / `dino play` | 手动操作恐龙 | 无 |
| `dino play --llm` | 自动选择 API 或 CODEX 模式 | API 配置或 Codex CLI |
| `dino play --llm api` | 使用 OpenAI Responses API 决策 | `~/.config/ai-dino-in-terminal/config.json` 或启动时交互输入 |
| `dino play --llm codex` | 使用本地 Codex CLI 决策 | Codex CLI，且版本满足要求 |
| `dino play --llm --debug` | 使用 LLM 决策并写 JSONL 调试日志 | `logs/*.jsonl` |
| `dino dashboard` | 查看带动画 banner 的累计得分和 token dashboard | `~/.config/ai-dino-in-terminal/game_records.jsonl` |
| `dino replay` | 从历史运行记录列表选择并重放 | `~/.config/ai-dino-in-terminal/replays/*.json` |
| `dino replay +list` | 浏览所有 replay 文件，回车查看元信息 | `~/.config/ai-dino-in-terminal/replays/*.json` |
| `dino replay +clear` | 清除所有 replay 记录文件 | `~/.config/ai-dino-in-terminal/replays/*.json` |
| `dino compete` | 从历史运行记录列表选择一局并进入双赛道竞技 | `~/.config/ai-dino-in-terminal/replays/*.json` |
| `dino config` | 查看本地 LLM 配置（API key 脱敏显示） | 无 |
| `dino config +setup` | 交互式写入本地 API LLM 配置 | API key / base_url / model |
| `dino setup` | 交互式写入本地 API LLM 配置 | API key / base_url / model |
| `dino config +reset` | 重置本地 LLM 配置 | 无 |
| `dino help` | 查看可用命令和公共参数 | 无 |


## 运行要求

- Python 3.11+
- 支持 `curses` 的终端环境
- 游戏本身无第三方运行时依赖

## 本地文件写入

| 数据类型 | 存放目录 |
|---------|-------- |
| 配置数据 | `~/.config/ai-dino-in-terminal/config.json` |
| 游戏数据 （累计得分、token用量） | `~/.config/ai-dino-in-terminal/game_records.jsonl` |
| 最高分记录 | `~/.config/ai-dino-in-terminal/scores.json` |
| 回放数据 | `~/.config/ai-dino-in-terminal/replays/*.json` |
| 运行日志（`--debug` 时打印） | 当前工作目录下的 `logs/*.jsonl` |
